"""Controlled exceptions raised by the service.

Every exception carries a stable ``code``, a client-safe ``message`` (never
containing filesystem paths or tracebacks) and an HTTP status.
"""

from __future__ import annotations


class ServiceError(Exception):
    """Base class for all controlled service errors."""

    code: str = "INTERNAL_ERROR"
    status_code: int = 500
    default_message: str = "An internal error occurred."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class InvalidSampleIdError(ServiceError):
    code = "INVALID_SAMPLE_ID"
    status_code = 400
    default_message = (
        "sample_id must start with a letter and contain only letters, digits, "
        "'_' or '-' (max 64 characters), e.g. SCAM_0001."
    )


class SampleAlreadyExistsError(ServiceError):
    code = "SAMPLE_ID_EXISTS"
    status_code = 409
    default_message = "A processed sample with this sample_id already exists."


class StorageError(ServiceError):
    code = "STORAGE_ERROR"
    status_code = 500
    default_message = "Failed to read or write service storage."


class HashDatabaseError(ServiceError):
    code = "HASH_DATABASE_ERROR"
    status_code = 500
    default_message = "The image hash database is unreadable or malformed."


class AnnotationStorageError(ServiceError):
    code = "ANNOTATION_STORAGE_ERROR"
    status_code = 500
    default_message = "The annotation dataset storage is unreadable or malformed."


class ImageProcessingError(ServiceError):
    code = "IMAGE_PROCESSING_FAILED"
    status_code = 422
    default_message = "The image passed validation but could not be processed."


class OcrEngineUnavailableError(ServiceError):
    code = "OCR_ENGINE_UNAVAILABLE"
    status_code = 503
    default_message = (
        "The OCR engine (Tesseract) is not installed or not reachable. "
        "Install Tesseract or set TESSERACT_CMD."
    )


class OcrLanguageUnavailableError(ServiceError):
    code = "OCR_LANGUAGE_UNAVAILABLE"
    status_code = 503
    default_message = "None of the requested OCR languages, nor the fallback language, are installed."


class OcrExecutionError(ServiceError):
    code = "OCR_FAILED"
    status_code = 500
    default_message = "OCR execution failed."
