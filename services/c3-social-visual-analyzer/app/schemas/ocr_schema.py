"""Pydantic schemas for OCR output."""

from __future__ import annotations

from pydantic import BaseModel


class OcrWord(BaseModel):
    """A single meaningful OCR token with its engine confidence (0-100)."""

    text: str
    confidence: float


class OcrResult(BaseModel):
    """Engine-agnostic OCR output consumed by later analysis phases."""

    engine: str
    engine_version: str | None = None
    text: str
    average_confidence: float | None
    requested_languages: str
    used_languages: str
    word_count: int
    words: list[OcrWord]
    warning: str | None = None
    input_width: int
    input_height: int
    config: str | None = None
