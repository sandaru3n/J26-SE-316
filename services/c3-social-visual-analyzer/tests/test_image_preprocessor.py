"""Checklist 2-5: RGB conversion, resizing, aspect ratio, normalization."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from app.services.image_preprocessor import (
    ImagePreprocessor,
    convert_to_rgb,
    normalize_image,
    resize_image,
)
from tests.conftest import make_pattern_image


# --------------------------------------------------------------- RGB conversion


def test_rgba_converted_to_rgb_over_white_background() -> None:
    image = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
    image.putpixel((0, 0), (0, 0, 255, 0))  # fully transparent
    image.putpixel((1, 0), (0, 0, 0, 128))  # half transparent black

    rgb = convert_to_rgb(image)

    assert rgb.mode == "RGB"
    assert rgb.size == (10, 10)
    assert rgb.getpixel((0, 0)) == (255, 255, 255)
    assert rgb.getpixel((5, 5)) == (255, 0, 0)
    assert all(120 <= channel <= 135 for channel in rgb.getpixel((1, 0)))


def test_grayscale_converted_to_rgb() -> None:
    gray = Image.new("L", (8, 6), 77)
    rgb = convert_to_rgb(gray)
    assert rgb.mode == "RGB"
    assert rgb.getpixel((3, 3)) == (77, 77, 77)


def test_palette_image_converted_safely() -> None:
    palette = make_pattern_image((64, 48)).quantize(colors=16)
    assert palette.mode == "P"
    rgb = convert_to_rgb(palette)
    assert rgb.mode == "RGB"
    assert rgb.size == (64, 48)


def test_palette_with_transparency_uses_background() -> None:
    palette = Image.new("P", (4, 4), 0)
    palette.putpalette([0, 0, 0, 255, 0, 0] + [0] * 762)
    palette.putpixel((1, 1), 1)
    palette.info["transparency"] = 0
    rgb = convert_to_rgb(palette, background=(255, 255, 255))
    assert rgb.getpixel((0, 0)) == (255, 255, 255)
    assert rgb.getpixel((1, 1)) == (255, 0, 0)


def test_la_and_cmyk_and_16bit_modes_supported() -> None:
    assert convert_to_rgb(Image.new("LA", (4, 4), (10, 255))).getpixel((0, 0)) == (10, 10, 10)
    assert convert_to_rgb(Image.new("CMYK", (4, 4), (0, 0, 0, 0))).mode == "RGB"
    sixteen = Image.fromarray(np.full((4, 4), 65535, dtype=np.uint16))
    assert convert_to_rgb(sixteen).getpixel((0, 0)) == (255, 255, 255)


def test_rgb_input_returns_copy_not_same_object() -> None:
    image = make_pattern_image((40, 40))
    converted = convert_to_rgb(image)
    assert converted is not image
    assert np.array_equal(np.asarray(converted), np.asarray(image))


# --------------------------------------------------------------- resize / aspect ratio


@pytest.mark.parametrize(
    ("original", "expected"),
    [
        ((1920, 1080), (1024, 576)),  # landscape
        ((1080, 1920), (576, 1024)),  # portrait
        ((500, 400), (500, 400)),  # small: not upscaled
        ((1024, 1024), (1024, 1024)),  # exact fit
        ((4000, 1000), (1024, 256)),  # wide banner
        ((2048, 2048), (1024, 1024)),  # square stays square
    ],
)
def test_resize_preserves_aspect_ratio(original: tuple[int, int], expected: tuple[int, int]) -> None:
    resized = resize_image(Image.new("RGB", original), 1024, 1024)
    assert resized.size == expected
    original_ratio = original[0] / original[1]
    assert abs(resized.width / resized.height - original_ratio) < 0.01


def test_landscape_not_forced_to_square() -> None:
    assert resize_image(Image.new("RGB", (1920, 1080))).size != (1024, 1024)


def test_small_image_upscaled_only_when_requested() -> None:
    small = Image.new("RGB", (500, 400))
    assert resize_image(small, 1000, 1000).size == (500, 400)
    assert resize_image(small, 1000, 1000, allow_upscale=True).size == (1000, 800)


def test_resize_rejects_invalid_bounds() -> None:
    with pytest.raises(ValueError):
        resize_image(Image.new("RGB", (10, 10)), 0, 10)


# --------------------------------------------------------------- normalization


def test_normalization_outputs_float32() -> None:
    normalized = normalize_image(make_pattern_image((1024, 576)))
    assert normalized.array.dtype == np.float32
    assert normalized.dtype == "float32"
    assert normalized.shape == [576, 1024, 3]


def test_normalization_values_between_zero_and_one() -> None:
    image = Image.new("RGB", (2, 1))
    image.putpixel((0, 0), (0, 0, 0))
    image.putpixel((1, 0), (255, 255, 255))
    normalized = normalize_image(image)
    assert normalized.min == 0.0
    assert normalized.max == 1.0
    assert float(normalized.array.min()) >= 0.0 and float(normalized.array.max()) <= 1.0
    assert normalized.info().model_dump() == {
        "dtype": "float32",
        "min": 0.0,
        "max": 1.0,
        "shape": [1, 2, 3],
    }


def test_normalization_does_not_modify_source_image() -> None:
    image = make_pattern_image((32, 32))
    before = np.asarray(image).copy()
    normalize_image(image)
    assert np.array_equal(np.asarray(image), before)


# --------------------------------------------------------------- saving


def test_save_png_refuses_overwrite(tmp_path) -> None:
    from app.exceptions import StorageError

    target = tmp_path / "out.png"
    ImagePreprocessor.save_png(make_pattern_image((40, 40)), target)
    with Image.open(target) as saved:
        assert saved.format == "PNG" and saved.mode == "RGB"
    with pytest.raises(StorageError):
        ImagePreprocessor.save_png(make_pattern_image((40, 40)), target)
