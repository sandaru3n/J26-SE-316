"""Builders for client-safe API responses (no paths, no tracebacks)."""

from __future__ import annotations

from fastapi.responses import JSONResponse

from app.exceptions import ServiceError
from app.schemas.pipeline_schema import (
    ApiErrorDetail,
    ApiErrorResponse,
    ApiImageSummary,
    DatasetRecord,
    PreprocessSuccessResponse,
)

_REJECTION_STATUS_CODES: dict[str, int] = {
    "FILE_TOO_LARGE": 413,
    "UNSUPPORTED_EXTENSION": 415,
    "UNSUPPORTED_FORMAT": 415,
}


def error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    sample_id: str | None = None,
    status: str = "error",
    reason: str | None = None,
) -> JSONResponse:
    body = ApiErrorResponse(
        sample_id=sample_id,
        status=status,  # type: ignore[arg-type]
        error=ApiErrorDetail(code=code, message=message, reason=reason),
    )
    return JSONResponse(status_code=status_code, content=body.model_dump())


def service_error_response(exc: ServiceError, sample_id: str | None = None) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message, sample_id=sample_id)


def rejection_response(sample_id: str, reason_code: str, reason: str) -> JSONResponse:
    return error_response(
        _REJECTION_STATUS_CODES.get(reason_code, 422),
        "INVALID_IMAGE",
        f"Uploaded file is corrupted or is not a supported image: {reason}.",
        sample_id=sample_id,
        status="rejected",
        reason=reason_code,
    )


def success_response(record: DatasetRecord) -> PreprocessSuccessResponse:
    return PreprocessSuccessResponse(
        sample_id=record.sample_id,
        validation=record.validation,
        image=ApiImageSummary(
            original_format=record.image.original_format,
            original_width=record.image.original_width,
            original_height=record.image.original_height,
            processed_width=record.image.processed_width,
            processed_height=record.image.processed_height,
            color_mode=record.image.color_mode,
        ),
        duplicate_detection=record.duplicate_detection,
        ocr=record.ocr,
        original_image=record.original_image,
        processed_image=record.processed_image,
        created_at=record.created_at,
    )
