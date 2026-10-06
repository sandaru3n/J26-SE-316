"""Validation of image files before any further processing.

The file extension is only a first filter: the actual content is identified,
verified and fully decoded with Pillow, so a renamed executable, a truncated
JPEG or a decompression bomb is rejected instead of being processed.
"""

from __future__ import annotations

import logging
import struct
import warnings
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.config import ALLOWED_EXTENSIONS, ALLOWED_FORMATS, Settings, get_settings
from app.schemas.image_schema import ImageValidationResult, ValidationErrorCode

logger = logging.getLogger(__name__)

CORRUPTED_MESSAGE = "Corrupted or unreadable image"

_DECODE_ERRORS = (OSError, SyntaxError, ValueError, EOFError, struct.error, IndexError)


class ImageValidator:
    """Validates image files against the configured safety limits."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def validate(self, file_path: Path) -> ImageValidationResult:
        """Validate ``file_path`` and return a structured result (never raises)."""
        path = Path(file_path)

        if not path.exists():
            return self._invalid("FILE_NOT_FOUND", "File does not exist")
        if not path.is_file():
            return self._invalid("NOT_A_FILE", "Path is not a regular file")

        size = path.stat().st_size
        if size == 0:
            return self._invalid("EMPTY_FILE", "File is empty", size=size)
        if size > self._settings.max_image_size_bytes:
            return self._invalid(
                "FILE_TOO_LARGE",
                f"File exceeds the {self._settings.max_image_size_mb:g} MB size limit",
                size=size,
            )
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
            return self._invalid(
                "UNSUPPORTED_EXTENSION",
                f"Unsupported file extension. Allowed: {allowed}",
                size=size,
            )

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                return self._inspect_content(path, size)
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            return self._invalid(
                "DIMENSIONS_TOO_LARGE",
                "Image pixel count exceeds the decompression safety limit",
                size=size,
            )

    def _inspect_content(self, path: Path, size: int) -> ImageValidationResult:
        try:
            with Image.open(path) as image:
                image_format = image.format
                width, height = image.size
                if image_format not in ALLOWED_FORMATS:
                    return self._invalid(
                        "UNSUPPORTED_FORMAT",
                        "Unsupported image format. Allowed: JPEG, PNG, WEBP",
                        size=size,
                    )
                if width <= 0 or height <= 0:
                    return self._invalid("INVALID_DIMENSIONS", "Image has invalid dimensions", size=size)
                if width > self._settings.max_image_width or height > self._settings.max_image_height:
                    return self._invalid(
                        "DIMENSIONS_TOO_LARGE",
                        (
                            f"Image dimensions exceed the "
                            f"{self._settings.max_image_width}x{self._settings.max_image_height} limit"
                        ),
                        size=size,
                        image_format=image_format,
                        width=width,
                        height=height,
                    )
                image.verify()

            # verify() does not decode pixel data, so a full load is required to
            # catch truncated or otherwise damaged image bodies.
            with Image.open(path) as image:
                image.load()
        except UnidentifiedImageError:
            return self._invalid("CORRUPTED_IMAGE", CORRUPTED_MESSAGE, size=size)
        except _DECODE_ERRORS as exc:
            logger.info("Image decode failed for %s: %s", path.name, exc)
            return self._invalid("CORRUPTED_IMAGE", CORRUPTED_MESSAGE, size=size)

        logger.info("Validation completed: %s %s %dx%d", path.name, image_format, width, height)
        return ImageValidationResult(
            valid=True,
            format=image_format,
            width=width,
            height=height,
            file_size_bytes=size,
        )

    @staticmethod
    def _invalid(
        code: ValidationErrorCode,
        message: str,
        *,
        size: int | None = None,
        image_format: str | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> ImageValidationResult:
        return ImageValidationResult(
            valid=False,
            format=image_format,
            width=width,
            height=height,
            file_size_bytes=size,
            error=message,
            error_code=code,
        )


def validate_image(file_path: Path, settings: Settings | None = None) -> ImageValidationResult:
    """Validate an image file using the configured (or given) settings."""
    return ImageValidator(settings or get_settings()).validate(file_path)
