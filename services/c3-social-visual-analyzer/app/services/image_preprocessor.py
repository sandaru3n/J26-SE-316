"""Image preprocessing: RGB conversion, aspect-preserving resize, normalization.

These functions are model-agnostic so later phases (CLIP, YOLO, Siamese
similarity) can reuse the same processed RGB output.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from app.exceptions import ImageProcessingError, StorageError
from app.schemas.image_schema import NormalizationInfo

logger = logging.getLogger(__name__)

DEFAULT_BACKGROUND: tuple[int, int, int] = (255, 255, 255)
RESAMPLE_FILTER = Image.Resampling.LANCZOS
_SIXTEEN_BIT_MAX = 65535
_EXIF_ORIENTATION_TAG = 0x0112


def _has_transparency(image: Image.Image) -> bool:
    if image.mode in ("RGBA", "LA", "PA", "La", "RGBa"):
        return True
    return "transparency" in image.info


def _high_bit_depth_to_l(image: Image.Image) -> Image.Image:
    """Scale 16/32-bit integer or float grayscale into 8-bit without clipping."""
    array = np.asarray(image, dtype=np.float64)
    if image.mode.startswith("I;16") or (image.mode == "I" and array.max(initial=0) > 255):
        array = array * (255.0 / _SIXTEEN_BIT_MAX)
    elif image.mode == "F" and array.max(initial=0) <= 1.0:
        array = array * 255.0
    return Image.fromarray(np.clip(np.rint(array), 0, 255).astype(np.uint8), mode="L")


def convert_to_rgb(
    image: Image.Image,
    background: tuple[int, int, int] = DEFAULT_BACKGROUND,
) -> Image.Image:
    """Return a 3-channel RGB copy of ``image``.

    Transparent pixels (RGBA, LA, palette/grey with a transparency key) are
    alpha-composited over a consistent ``background`` colour so they do not turn
    into arbitrary black regions.
    """
    if image.mode == "RGB" and "transparency" not in image.info:
        return image.copy()

    if _has_transparency(image):
        rgba = image.convert("RGBA")
        canvas = Image.new("RGBA", rgba.size, (*background, 255))
        return Image.alpha_composite(canvas, rgba).convert("RGB")

    if image.mode.startswith("I") or image.mode == "F":
        return _high_bit_depth_to_l(image).convert("RGB")

    return image.convert("RGB")


def resize_image(
    image: Image.Image,
    max_width: int = 1024,
    max_height: int = 1024,
    allow_upscale: bool = False,
) -> Image.Image:
    """Fit ``image`` inside ``max_width`` x ``max_height`` keeping aspect ratio.

    A single scale factor is applied to both axes, so the image is never
    stretched, squashed, padded or cropped. Smaller images are returned
    unchanged unless ``allow_upscale`` is set.
    """
    if max_width <= 0 or max_height <= 0:
        raise ValueError("max_width and max_height must be positive")

    width, height = image.size
    scale = min(max_width / width, max_height / height)
    if scale >= 1.0 and not allow_upscale:
        return image.copy()

    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return image.resize(new_size, resample=RESAMPLE_FILTER)


@dataclass
class NormalizedImage:
    """A float32 array in [0, 1] with shape (height, width, channels)."""

    array: np.ndarray
    shape: list[int]
    dtype: str
    min: float
    max: float

    def info(self) -> NormalizationInfo:
        """Return serialisable metadata without the array itself."""
        return NormalizationInfo(dtype=self.dtype, min=self.min, max=self.max, shape=self.shape)


def normalize_image(image: Image.Image) -> NormalizedImage:
    """Convert 8-bit pixel values 0-255 into a float32 array in 0.0-1.0."""
    array = np.asarray(image, dtype=np.uint8).astype(np.float32)
    array /= 255.0
    return NormalizedImage(
        array=array,
        shape=list(array.shape),
        dtype=str(array.dtype),
        min=float(array.min()),
        max=float(array.max()),
    )


class ImagePreprocessor:
    """Loads a validated image and produces the processed RGB output."""

    def __init__(
        self,
        max_width: int = 1024,
        max_height: int = 1024,
        background: tuple[int, int, int] = DEFAULT_BACKGROUND,
    ) -> None:
        self.max_width = max_width
        self.max_height = max_height
        self.background = background

    def load(self, path: Path) -> tuple[Image.Image, str, bool]:
        """Open an already-validated image, applying EXIF orientation.

        Returns the decoded image, its original mode, and whether an EXIF
        rotation was applied.
        """
        try:
            with Image.open(path) as source:
                source.load()
                original_mode = source.mode
                transposed = source.getexif().get(_EXIF_ORIENTATION_TAG, 1) != 1
                image = ImageOps.exif_transpose(source)
        except (OSError, ValueError, SyntaxError) as exc:
            logger.error("Failed to load validated image %s: %s", path.name, exc)
            raise ImageProcessingError() from exc
        return image, original_mode, transposed

    def to_rgb(self, image: Image.Image) -> Image.Image:
        rgb = convert_to_rgb(image, self.background)
        logger.info("RGB conversion completed (%s -> RGB)", image.mode)
        return rgb

    def resize(self, image: Image.Image) -> Image.Image:
        resized = resize_image(image, self.max_width, self.max_height)
        logger.info("Resize completed: %dx%d -> %dx%d", *image.size, *resized.size)
        return resized

    @staticmethod
    def save_png(image: Image.Image, destination: Path) -> Path:
        """Save as PNG without metadata; refuses to overwrite an existing file."""
        try:
            with destination.open("xb") as handle:
                image.save(handle, format="PNG")
        except FileExistsError as exc:
            raise StorageError("Processed image filename already exists.") from exc
        except OSError as exc:
            destination.unlink(missing_ok=True)
            logger.error("Filesystem write failed for processed image %s: %s", destination.name, exc)
            raise StorageError("Failed to save the processed image.") from exc
        return destination
