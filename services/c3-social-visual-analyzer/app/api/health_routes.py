"""Service health endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_pipeline
from app.schemas.pipeline_schema import HealthResponse
from app.services.image_pipeline import ImagePipeline

router = APIRouter(tags=["health"])

PHASE = "Phase 1 - OCR and Image Preprocessing"


@router.get("/health", response_model=HealthResponse)
def health(pipeline: Annotated[ImagePipeline, Depends(get_pipeline)]) -> HealthResponse:
    return HealthResponse(status="online", service=pipeline.settings.service_name, phase=PHASE)
