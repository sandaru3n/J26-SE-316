"""Pydantic schemas for validation, preprocessing, hashing and duplicates."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ValidationErrorCode = Literal[
    "FILE_NOT_FOUND",
    "NOT_A_FILE",
    "EMPTY_FILE",
    "FILE_TOO_LARGE",
    "UNSUPPORTED_EXTENSION",
    "UNSUPPORTED_FORMAT",
    "INVALID_DIMENSIONS",
    "DIMENSIONS_TOO_LARGE",
    "CORRUPTED_IMAGE",
]

DuplicateType = Literal["exact_duplicate", "near_duplicate"]


class ImageValidationResult(BaseModel):
    """Outcome of validating an image file on disk."""

    valid: bool
    format: str | None = None
    width: int | None = None
    height: int | None = None
    file_size_bytes: int | None = None
    error: str | None = None
    error_code: ValidationErrorCode | None = None


class NormalizationInfo(BaseModel):
    """Metadata about a normalized array (the array itself is never stored)."""

    dtype: str
    min: float
    max: float
    shape: list[int]


class ProcessedImageInfo(BaseModel):
    """Image-level metadata recorded for every successfully processed sample."""

    original_format: str
    original_mode: str
    original_width: int
    original_height: int
    original_file_size_bytes: int
    original_sha256: str
    exif_transposed: bool
    processed_width: int
    processed_height: int
    processed_format: str = "PNG"
    color_mode: str = "RGB"
    resample: str = "LANCZOS"
    normalization: NormalizationInfo


class HashResult(BaseModel):
    """A perceptual hash of an image."""

    algorithm: Literal["phash"] = "phash"
    hash: str
    hash_size: int


class DuplicateResult(BaseModel):
    """Outcome of comparing a pHash against the stored hash database."""

    is_duplicate: bool = False
    duplicate_type: DuplicateType | None = None
    matched_sample_id: str | None = None
    hash_distance: int | None = None
    threshold: int | None = None
    compared_against: int = 0


class DuplicateDetectionRecord(DuplicateResult):
    """Duplicate result together with the pHash that was compared."""

    algorithm: Literal["phash"] = "phash"
    phash: str


class HashRecord(BaseModel):
    """One entry of ``image_hashes.json``."""

    file: str
    phash: str
    algorithm: Literal["phash"] = "phash"
    hash_size: int = 8
    sha256: str | None = None
    duplicate_of: str | None = None
    created_at: str | None = None


class RejectionRecord(BaseModel):
    """One line of ``rejected_images.jsonl``."""

    sample_id: str
    status: Literal["rejected"] = "rejected"
    reason: str
    error_code: str
    stored_path: str | None = None
    original_filename: str | None = None
    file_size_bytes: int | None = None
    sha256: str | None = None
    created_at: str = Field(default="")
