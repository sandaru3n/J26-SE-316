"""Checklist 9-11: OCR configuration, extraction and confidence.

Unit tests mock pytesseract. Tests marked ``ocr_integration`` call the real
Tesseract binary and are skipped automatically when it is not installed.
"""

from __future__ import annotations

import pytest
import pytesseract
from PIL import Image, ImageDraw, ImageFont

from app.config import Settings
from app.exceptions import (
    OcrEngineUnavailableError,
    OcrExecutionError,
    OcrLanguageUnavailableError,
)
from app.services import ocr_service
from app.services.ocr_service import (
    TesseractOcrEngine,
    average_confidence,
    clean_ocr_text,
    create_ocr_engine,
    parse_tesseract_data,
)

SAMPLE_DATA = {
    "level": [1, 5, 5, 5, 5, 5, 5],
    "page_num": [1, 1, 1, 1, 1, 1, 1],
    "block_num": [0, 1, 1, 1, 1, 1, 1],
    "par_num": [0, 1, 1, 1, 1, 1, 1],
    "line_num": [0, 1, 1, 1, 2, 2, 2],
    "word_num": [0, 1, 2, 3, 1, 2, 3],
    "text": ["", "PAYPAL", "  ", "Verify", "your", "account", "ගිණුම"],
    "conf": [-1, 96.0, -1, "93.5", 90, 86.0, 70.0],
}


def _mock_tesseract(
    monkeypatch: pytest.MonkeyPatch,
    languages: list[str],
    data: dict | None = None,
) -> dict:
    captured: dict = {}

    def fake_image_to_data(image, lang, config, output_type, timeout):
        captured.update(lang=lang, config=config, output_type=output_type, size=image.size)
        return data if data is not None else SAMPLE_DATA

    monkeypatch.setattr(ocr_service.pytesseract, "get_languages", lambda config="": languages)
    monkeypatch.setattr(ocr_service.pytesseract, "get_tesseract_version", lambda: "5.4.0")
    monkeypatch.setattr(ocr_service.pytesseract, "image_to_data", fake_image_to_data)
    return captured


# --------------------------------------------------------------- parsing helpers


def test_parse_ignores_empty_tokens_and_invalid_confidence() -> None:
    words, text = parse_tesseract_data(SAMPLE_DATA)
    assert [w.text for w in words] == ["PAYPAL", "Verify", "your", "account", "ගිණුම"]
    assert [w.confidence for w in words] == [96.0, 93.5, 90.0, 86.0, 70.0]
    assert text == "PAYPAL Verify\nyour account ගිණුම"


def test_min_word_confidence_filters_tokens() -> None:
    words, text = parse_tesseract_data(SAMPLE_DATA, min_word_confidence=88)
    assert [w.text for w in words] == ["PAYPAL", "Verify", "your"]
    assert "account" not in text


def test_average_confidence_uses_only_meaningful_words() -> None:
    words, _ = parse_tesseract_data(SAMPLE_DATA)
    assert average_confidence(words) == pytest.approx((96 + 93.5 + 90 + 86 + 70) / 5, abs=0.01)
    assert average_confidence([]) is None


def test_clean_ocr_text_preserves_unicode_and_punctuation() -> None:
    raw = "  ඔබගේ   ගිණුම\t\tඅවහිර!  \r\n\r\n\n  உங்கள்  கணக்கு?  \n   \nPay-Pal: $5.00  "
    assert clean_ocr_text(raw) == "ඔබගේ ගිණුම අවහිර!\nஉங்கள் கணக்கு?\nPay-Pal: $5.00"


def test_clean_ocr_text_keeps_zero_width_joiner() -> None:
    assert clean_ocr_text("ශ්\u200dරී") == "ශ්\u200dරී"


# --------------------------------------------------------------- engine with mocks


def test_ocr_service_returns_correct_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _mock_tesseract(monkeypatch, ["eng", "sin", "tam", "osd"])
    engine = TesseractOcrEngine(languages="eng+sin+tam", psm=6, oem=1)

    result = engine.extract(Image.new("RGB", (320, 120), "white"))

    assert captured["lang"] == "eng+sin+tam"
    assert captured["config"] == "--oem 1 --psm 6"
    assert captured["output_type"] == pytesseract.Output.DICT
    payload = result.model_dump()
    for key in (
        "text",
        "average_confidence",
        "requested_languages",
        "used_languages",
        "word_count",
        "words",
        "warning",
    ):
        assert key in payload
    assert result.engine == "tesseract"
    assert result.engine_version == "5.4.0"
    assert result.used_languages == "eng+sin+tam"
    assert result.warning is None
    assert result.word_count == 5 == len(result.words)
    assert result.words[0].model_dump() == {"text": "PAYPAL", "confidence": 96.0}
    assert (result.input_width, result.input_height) == (320, 120)


def test_missing_language_packs_fall_back_with_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _mock_tesseract(monkeypatch, ["eng", "osd"])
    result = TesseractOcrEngine(languages="eng+sin+tam").extract(Image.new("RGB", (50, 50)))
    assert captured["lang"] == "eng"
    assert result.requested_languages == "eng+sin+tam"
    assert result.used_languages == "eng"
    assert result.warning == "Requested OCR languages eng+sin+tam unavailable (missing: sin, tam). Using eng."


def test_partial_language_availability_keeps_installed_ones(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_tesseract(monkeypatch, ["eng", "sin"])
    used, warning = TesseractOcrEngine(languages="eng+sin+tam").resolve_languages()
    assert used == "eng+sin"
    assert warning is not None and "tam" in warning


def test_fallback_language_used_when_no_requested_pack(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_tesseract(monkeypatch, ["eng"])
    used, warning = TesseractOcrEngine(languages="sin+tam", fallback_language="eng").resolve_languages()
    assert used == "eng"
    assert warning is not None


def test_no_usable_language_raises_controlled_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_tesseract(monkeypatch, ["osd"])
    with pytest.raises(OcrLanguageUnavailableError):
        TesseractOcrEngine(languages="sin+tam", fallback_language="eng").extract(Image.new("RGB", (5, 5)))


def test_tesseract_not_installed_raises_controlled_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(config=""):
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(ocr_service.pytesseract, "get_languages", missing)
    engine = TesseractOcrEngine()
    assert engine.is_available() is False
    with pytest.raises(OcrEngineUnavailableError):
        engine.extract(Image.new("RGB", (5, 5)))


def test_tesseract_runtime_failure_raises_controlled_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_tesseract(monkeypatch, ["eng"])

    def failing(*args, **kwargs):
        raise pytesseract.TesseractError(1, "boom")

    monkeypatch.setattr(ocr_service.pytesseract, "image_to_data", failing)
    with pytest.raises(OcrExecutionError):
        TesseractOcrEngine(languages="eng").extract(Image.new("RGB", (5, 5)))


def test_empty_image_gives_empty_text(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_tesseract(monkeypatch, ["eng"], data={"text": ["", " "], "conf": [-1, -1]})
    result = TesseractOcrEngine(languages="eng").extract(Image.new("RGB", (5, 5)))
    assert (result.text, result.word_count, result.average_confidence) == ("", 0, None)


def test_engine_factory_uses_settings(tmp_path) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path, ocr_languages="eng+tam", ocr_psm=11)
    engine = create_ocr_engine(settings)
    assert isinstance(engine, TesseractOcrEngine)
    assert engine.requested_languages == "eng+tam"
    assert engine.tesseract_config == "--oem 3 --psm 11"


def test_settings_reject_unsafe_language_spec(tmp_path) -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, data_dir=tmp_path, ocr_languages="eng; rm -rf /")


# --------------------------------------------------------------- real Tesseract


def _real_engine() -> TesseractOcrEngine:
    return create_ocr_engine(Settings(_env_file=None))  # type: ignore[return-value]


def _tesseract_available() -> bool:
    try:
        return _real_engine().is_available()
    except Exception:  # noqa: BLE001 - availability probe only
        return False


requires_tesseract = pytest.mark.skipif(
    not _tesseract_available(), reason="Tesseract OCR is not installed / not on PATH"
)


@pytest.mark.ocr_integration
@requires_tesseract
def test_real_tesseract_reads_rendered_english_text() -> None:
    image = Image.new("RGB", (900, 200), "white")
    font = ImageFont.load_default(size=64)
    ImageDraw.Draw(image).text((30, 50), "VERIFY ACCOUNT", fill="black", font=font)

    result = _real_engine().extract(image)

    assert "eng" in result.used_languages
    assert "VERIFY" in result.text.upper()
    assert result.word_count >= 2
    assert result.average_confidence is not None and result.average_confidence > 50


@pytest.mark.ocr_integration
@requires_tesseract
def test_real_tesseract_reports_language_fallback() -> None:
    engine = _real_engine()
    requested = set(engine.requested_languages.split("+"))
    used, warning = engine.resolve_languages()
    if requested <= engine.available_languages():
        assert warning is None and used == engine.requested_languages
    else:
        assert warning is not None and used
