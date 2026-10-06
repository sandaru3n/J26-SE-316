"""Perceptual hashing (pHash) used for visual duplicate detection.

pHash is computed from the low-frequency DCT coefficients of a downscaled
greyscale image, so re-encoded, resized or slightly edited copies of the same
picture get hashes a small Hamming distance apart. Cryptographic hashes
(SHA-256) cannot do this and are kept only as byte-level metadata.
"""

from __future__ import annotations

import logging

import imagehash
from PIL import Image

from app.schemas.image_schema import HashResult

logger = logging.getLogger(__name__)


class ImageHashService:
    """Generates and compares perceptual hashes."""

    algorithm = "phash"

    def __init__(self, hash_size: int = 8) -> None:
        self.hash_size = hash_size

    def generate_phash(self, image: Image.Image) -> str:
        """Return the pHash of ``image`` as a hex string."""
        value = str(imagehash.phash(image, hash_size=self.hash_size))
        logger.info("pHash generated: %s", value)
        return value

    def hash_image(self, image: Image.Image) -> HashResult:
        return HashResult(hash=self.generate_phash(image), hash_size=self.hash_size)

    @staticmethod
    def hamming_distance(first_hash: str, second_hash: str) -> int:
        """Number of differing bits between two hex-encoded hashes of equal size."""
        first = imagehash.hex_to_hash(first_hash)
        second = imagehash.hex_to_hash(second_hash)
        if first.hash.shape != second.hash.shape:
            raise ValueError("Cannot compare perceptual hashes of different sizes")
        return int(first - second)


def generate_phash(image: Image.Image, hash_size: int = 8) -> str:
    """Convenience wrapper around :meth:`ImageHashService.generate_phash`."""
    return ImageHashService(hash_size).generate_phash(image)
