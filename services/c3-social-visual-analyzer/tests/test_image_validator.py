"""Checklist 1 & 6: image validation and corrupted-image detection."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import features

from app.config import Settings
from app.services.image_validator import CORRUPTED_MESSAGE, ImageValidator, validate_image
from tests.conftest import make_pattern_image


@pytest.fixture
def validator(settings: Settings) -> ImageValidator:
    return ImageValidator(settings)


def test_valid_jpeg_accepted(validator: ImageValidator, write_image) -> None:
    path = write_image("photo.jpg", make_pattern_image((1920, 1080)))
    result = validator.validate(path)
    assert result.valid is True
    assert result.format == "JPEG"
    assert (result.width, result.height) == (1920, 1080)
    assert result.file_size_bytes == path.stat().st_size
    assert result.error is None


def test_valid_png_accepted(validator: ImageValidator, write_image) -> None:
    result = validator.validate(write_image("shot.png"))
    assert result.valid is True
    assert result.format == "PNG"


@pytest.mark.skipif(not features.check("webp"), reason="Pillow built without WebP support")
def test_valid_webp_accepted(validator: ImageValidator, write_image) -> None:
    result = validator.validate(write_image("post.webp"))
    assert result.valid is True
    assert result.format == "WEBP"


def test_module_level_validate_image(settings: Settings, write_image) -> None:
    assert validate_image(write_image("a.png"), settings).valid is True


def test_truncated_jpeg_rejected_as_corrupted(validator: ImageValidator, write_image) -> None:
    path = write_image("broken.jpg", make_pattern_image((800, 600)))
    data = path.read_bytes()
    path.write_bytes(data[: len(data) // 2])
    result = validator.validate(path)
    assert result.valid is False
    assert result.error_code == "CORRUPTED_IMAGE"
    assert result.error == CORRUPTED_MESSAGE
    assert result.format is None and result.width is None


def test_random_bytes_with_image_extension_rejected(validator: ImageValidator, tmp_path: Path) -> None:
    path = tmp_path / "fake.png"
    path.write_bytes(b"MZ\x90\x00 this is not an image" * 20)
    result = validator.validate(path)
    assert result.valid is False
    assert result.error_code == "CORRUPTED_IMAGE"


def test_unsupported_extension_rejected(validator: ImageValidator, write_image, tmp_path: Path) -> None:
    gif = write_image("anim.gif")
    assert validator.validate(gif).error_code == "UNSUPPORTED_EXTENSION"

    script = tmp_path / "payload.exe"
    script.write_bytes(b"MZ binary")
    assert validator.validate(script).error_code == "UNSUPPORTED_EXTENSION"


def test_extension_is_not_trusted_for_format(validator: ImageValidator, write_image) -> None:
    disguised_gif = write_image("disguised.png", image_format="GIF")
    result = validator.validate(disguised_gif)
    assert result.valid is False
    assert result.error_code == "UNSUPPORTED_FORMAT"


def test_empty_file_rejected(validator: ImageValidator, tmp_path: Path) -> None:
    path = tmp_path / "empty.jpg"
    path.write_bytes(b"")
    result = validator.validate(path)
    assert result.error_code == "EMPTY_FILE"
    assert result.file_size_bytes == 0


def test_missing_and_directory_paths_rejected(validator: ImageValidator, tmp_path: Path) -> None:
    assert validator.validate(tmp_path / "nope.jpg").error_code == "FILE_NOT_FOUND"
    folder = tmp_path / "folder.jpg"
    folder.mkdir()
    assert validator.validate(folder).error_code == "NOT_A_FILE"


def test_oversized_file_rejected(tmp_path: Path, write_image) -> None:
    small_limit = Settings(_env_file=None, data_dir=tmp_path / "d", max_image_size_mb=0.001)
    path = write_image("big.png", make_pattern_image((400, 400)))
    result = ImageValidator(small_limit).validate(path)
    assert result.error_code == "FILE_TOO_LARGE"


def test_excessive_dimensions_rejected(tmp_path: Path, write_image) -> None:
    strict = Settings(_env_file=None, data_dir=tmp_path / "d", max_image_width=500, max_image_height=500)
    result = ImageValidator(strict).validate(write_image("wide.png", make_pattern_image((800, 300))))
    assert result.valid is False
    assert result.error_code == "DIMENSIONS_TOO_LARGE"
    assert (result.width, result.height) == (800, 300)
