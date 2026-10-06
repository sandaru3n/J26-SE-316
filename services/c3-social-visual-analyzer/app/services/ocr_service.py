"""OCR extraction with per-word confidence.

The pipeline depends on the abstract :class:`OcrEngine`, so Tesseract can be
swapped for another engine later without touching preprocessing code.
"""

from __future__ import annotations

import logging
import re
import threading
from abc import ABC, abstractmethod
from statistics import fmean
from typing import Any

import pytesseract
from PIL import Image

from app.config import Settings
from app.exceptions import (
    OcrEngineUnavailableError,
    OcrExecutionError,
    OcrLanguageUnavailableError,
)
from app.schemas.ocr_schema import OcrResult, OcrWord

logger = logging.getLogger(__name__)

_HORIZONTAL_WHITESPACE = re.compile(r"[ \t\f\v\u00a0\u3000]+")
_NON_LANGUAGE_PACKS = frozenset({"osd", "equ"})


def clean_ocr_text(text: str) -> str:
    """Apply minimal, language-neutral cleanup to OCR output.

    Normalises line endings, collapses runs of spaces/tabs, trims each line and
    drops empty lines. Unicode (including Sinhala/Tamil and zero-width joiners)
    and punctuation are preserved; nothing is translated or classified.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = (_HORIZONTAL_WHITESPACE.sub(" ", line).strip() for line in normalized.split("\n"))
    return "\n".join(line for line in lines if line)


def _parse_confidence(value: Any) -> float | None:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    if confidence < 0 or confidence != confidence:  # negative or NaN
        return None
    return confidence


def parse_tesseract_data(
    data: dict[str, list[Any]],
    min_word_confidence: float = 0.0,
) -> tuple[list[OcrWord], str]:
    """Extract meaningful words and line-structured text from ``image_to_data``.

    Tokens that are empty, whitespace-only, or carry an invalid confidence
    (e.g. ``-1`` for layout rows) are ignored, as are tokens below
    ``min_word_confidence``.
    """
    words: list[OcrWord] = []
    lines: dict[tuple[int, int, int, int], list[str]] = {}

    texts = data.get("text", [])
    confidences = data.get("conf", [])
    for index, raw_text in enumerate(texts):
        token = _HORIZONTAL_WHITESPACE.sub(" ", str(raw_text or "")).strip()
        if not token:
            continue
        confidence = _parse_confidence(confidences[index] if index < len(confidences) else None)
        if confidence is None or confidence < min_word_confidence:
            continue
        words.append(OcrWord(text=token, confidence=round(confidence, 2)))
        line_key = tuple(
            int(data.get(key, [0] * len(texts))[index] or 0)
            for key in ("page_num", "block_num", "par_num", "line_num")
        )
        lines.setdefault(line_key, []).append(token)

    text = clean_ocr_text("\n".join(" ".join(tokens) for tokens in lines.values()))
    return words, text


def average_confidence(words: list[OcrWord]) -> float | None:
    """Mean confidence of meaningful words, or ``None`` when there are none."""
    if not words:
        return None
    return round(fmean(word.confidence for word in words), 2)


class OcrEngine(ABC):
    """Interface every OCR backend must implement."""

    name: str

    @abstractmethod
    def extract(self, image: Image.Image) -> OcrResult:
        """Run OCR on an RGB image."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether the engine can currently run."""


class TesseractOcrEngine(OcrEngine):
    """Tesseract (via pytesseract) with graceful language-pack fallback."""

    name = "tesseract"

    def __init__(
        self,
        languages: str = "eng+sin+tam",
        fallback_language: str = "eng",
        tesseract_cmd: str = "",
        min_word_confidence: float = 0.0,
        low_confidence_warning: float = 60.0,
        psm: int = 3,
        oem: int = 3,
        timeout_seconds: int = 60,
    ) -> None:
        self.requested_languages = languages
        self.fallback_language = fallback_language
        self.min_word_confidence = min_word_confidence
        self.low_confidence_warning = low_confidence_warning
        self.psm = psm
        self.oem = oem
        self.timeout_seconds = timeout_seconds
        self._lock = threading.Lock()
        self._available_languages: frozenset[str] | None = None
        self._version: str | None = None
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    @classmethod
    def from_settings(cls, settings: Settings) -> "TesseractOcrEngine":
        return cls(
            languages=settings.ocr_languages,
            fallback_language=settings.ocr_fallback_language,
            tesseract_cmd=settings.tesseract_cmd,
            min_word_confidence=settings.ocr_min_word_confidence,
            low_confidence_warning=settings.ocr_low_confidence_warning,
            psm=settings.ocr_psm,
            oem=settings.ocr_oem,
            timeout_seconds=settings.ocr_timeout_seconds,
        )

    @property
    def tesseract_config(self) -> str:
        return f"--oem {self.oem} --psm {self.psm}"

    def available_languages(self) -> frozenset[str]:
        """Installed Tesseract language packs (cached after the first success)."""
        with self._lock:
            if self._available_languages is not None:
                return self._available_languages
            try:
                languages = frozenset(pytesseract.get_languages(config="")) - _NON_LANGUAGE_PACKS
                version = str(pytesseract.get_tesseract_version())
            except pytesseract.TesseractNotFoundError as exc:
                logger.error("Tesseract unavailable: executable not found")
                raise OcrEngineUnavailableError() from exc
            except (pytesseract.TesseractError, OSError, RuntimeError) as exc:
                logger.error("Tesseract unavailable: %s", exc)
                raise OcrEngineUnavailableError() from exc
            self._available_languages = languages
            self._version = version
            return languages

    def is_available(self) -> bool:
        try:
            self.available_languages()
        except OcrEngineUnavailableError:
            return False
        return True

    def resolve_languages(self) -> tuple[str, str | None]:
        """Pick the languages to use and an optional warning about fallbacks."""
        available = self.available_languages()
        requested = self.requested_languages.split("+")
        present = [lang for lang in requested if lang in available]

        if present == requested:
            return self.requested_languages, None

        missing = [lang for lang in requested if lang not in available]
        if present:
            used = "+".join(present)
        elif self.fallback_language in available:
            used = self.fallback_language
        else:
            logger.error(
                "No requested OCR language (%s) or fallback (%s) installed; available: %s",
                self.requested_languages,
                self.fallback_language,
                ", ".join(sorted(available)) or "none",
            )
            raise OcrLanguageUnavailableError()

        warning = (
            f"Requested OCR languages {self.requested_languages} unavailable "
            f"(missing: {', '.join(missing)}). Using {used}."
        )
        logger.warning(warning)
        return used, warning

    def extract(self, image: Image.Image) -> OcrResult:
        """Run Tesseract ``image_to_data`` and build a structured result."""
        used_languages, warning = self.resolve_languages()
        try:
            data = pytesseract.image_to_data(
                image,
                lang=used_languages,
                config=self.tesseract_config,
                output_type=pytesseract.Output.DICT,
                timeout=self.timeout_seconds,
            )
        except pytesseract.TesseractNotFoundError as exc:
            logger.error("Tesseract unavailable during OCR")
            raise OcrEngineUnavailableError() from exc
        except pytesseract.TesseractError as exc:
            logger.error("Tesseract OCR failed: %s", exc)
            raise OcrExecutionError() from exc
        except RuntimeError as exc:
            logger.error("Tesseract OCR timed out or failed: %s", exc)
            raise OcrExecutionError("OCR execution timed out or failed.") from exc

        words, text = parse_tesseract_data(data, self.min_word_confidence)
        mean_confidence = average_confidence(words)
        logger.info(
            "OCR completed: %d words, average confidence %s, languages %s",
            len(words),
            mean_confidence,
            used_languages,
        )
        if mean_confidence is not None and mean_confidence < self.low_confidence_warning:
            logger.warning("OCR confidence unusually low: %.2f", mean_confidence)

        return OcrResult(
            engine=self.name,
            engine_version=self._version,
            text=text,
            average_confidence=mean_confidence,
            requested_languages=self.requested_languages,
            used_languages=used_languages,
            word_count=len(words),
            words=words,
            warning=warning,
            input_width=image.width,
            input_height=image.height,
            config=self.tesseract_config,
        )


def create_ocr_engine(settings: Settings) -> OcrEngine:
    """Factory selecting the configured OCR backend."""
    if settings.ocr_engine.lower() == "tesseract":
        return TesseractOcrEngine.from_settings(settings)
    raise ValueError(f"Unsupported OCR engine: {settings.ocr_engine}")
