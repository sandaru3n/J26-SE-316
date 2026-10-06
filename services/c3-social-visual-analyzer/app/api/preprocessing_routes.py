"""Image preprocessing + OCR endpoint."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse

from app.api.dependencies import get_pipeline
from app.api.responses import rejection_response, service_error_response, success_response
from app.exceptions import InvalidSampleIdError, ServiceError
from app.schemas.pipeline_schema import ApiErrorResponse, PreprocessSuccessResponse
from app.services.image_pipeline import ImagePipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["preprocessing"])

_ERROR_RESPONSES = {
    status: {"model": ApiErrorResponse}
    for status in (400, 409, 413, 415, 422, 500, 503)
}


@router.post(
    "/preprocess-image",
    response_model=PreprocessSuccessResponse,
    responses=_ERROR_RESPONSES,
    summary="Validate, preprocess, hash, duplicate-check and OCR one post image",
)
def preprocess_image(
    sample_id: Annotated[str, Form(description="Dataset sample id, e.g. SCAM_0001")],
    image: Annotated[UploadFile, File(description="JPEG, PNG or WebP image")],
    pipeline: Annotated[ImagePipeline, Depends(get_pipeline)],
) -> PreprocessSuccessResponse | JSONResponse:
    """Run the full Phase 1 pipeline on an uploaded image.

    Duplicates are reported in ``duplicate_detection`` and are not an error.
    Invalid or corrupted images are quarantined and return a 4xx response.
    """
    try:
        result = pipeline.process_upload(image.file, image.filename, sample_id)
    except InvalidSampleIdError as exc:
        return service_error_response(exc)
    except ServiceError as exc:
        return service_error_response(exc, sample_id=sample_id.strip())
    finally:
        image.file.close()

    if result.status == "rejected" or result.record is None:
        rejection = result.rejection
        return rejection_response(
            result.sample_id,
            rejection.error_code if rejection else "CORRUPTED_IMAGE",
            rejection.reason if rejection else "Invalid image",
        )
    return success_response(result.record)
