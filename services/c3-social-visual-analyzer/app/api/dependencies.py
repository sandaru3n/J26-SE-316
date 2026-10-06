"""FastAPI dependency providers."""

from __future__ import annotations

from fastapi import Request

from app.services.image_pipeline import ImagePipeline


def get_pipeline(request: Request) -> ImagePipeline:
    """Return the pipeline attached to the running application."""
    return request.app.state.pipeline
