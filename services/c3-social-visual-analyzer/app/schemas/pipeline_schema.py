"""Schemas for the full pipeline result, dataset records and API responses."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.image_schema import (
    DuplicateDetectionRecord,
    ImageValidationResult,
    ProcessedImageInfo,
    RejectionRecord,
)
from app.schemas.ocr_schema import OcrResult


class ValidationSummary(BaseModel):
    valid: bool
    error: str | None = None


class ProcessingMetadata(BaseModel):
    """Settings used for this sample, kept for research reproducibility."""

    pipeline_version: str
    processed_max_width: int
    processed_max_height: int
    background_color: list[int]
    phash_hash_size: int
    phash_near_duplicate_threshold: int
    ocr_min_word_confidence: float
    ocr_max_side: int


class DatasetRecord(BaseModel):
    """One line of ``ocr_results.jsonl``."""

    sample_id: str
    original_filename: str | None
    original_image: str
    processed_image: str
    image: ProcessedImageInfo
    validation: ValidationSummary
    duplicate_detection: DuplicateDetectionRecord
    ocr: OcrResult
    processing: ProcessingMetadata
    processing_status: Literal["success"] = "success"
    created_at: str


class PipelineResult(BaseModel):
    """Return value of the pipeline: either a dataset record or a rejection."""

    sample_id: str
    status: Literal["success", "rejected"]
    validation: ImageValidationResult
    record: DatasetRecord | None = None
    rejection: RejectionRecord | None = None


class ApiErrorDetail(BaseModel):
    code: str
    message: str
    reason: str | None = None


class ApiErrorResponse(BaseModel):
    success: Literal[False] = False
    sample_id: str | None = None
    status: Literal["rejected", "error"]
    error: ApiErrorDetail


class ApiImageSummary(BaseModel):
    original_format: str
    original_width: int
    original_height: int
    processed_width: int
    processed_height: int
    color_mode: str


class PreprocessSuccessResponse(BaseModel):
    success: Literal[True] = True
    sample_id: str
    status: Literal["success"] = "success"
    validation: ValidationSummary
    image: ApiImageSummary
    duplicate_detection: DuplicateDetectionRecord
    ocr: OcrResult
    original_image: str
    processed_image: str
    created_at: str


class HealthResponse(BaseModel):
    status: str
    service: str
    phase: str
