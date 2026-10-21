"""Machine Learning pipeline package for Intelligent URL and Domain Analyzer."""

from app.ml.feature_extractor import FEATURE_NAMES, MlFeatureExtractor
from app.ml.dataset_loader import DatasetLoader
from app.ml.model_service import MlInferenceService, get_ml_service

# Optional import of training pipeline to ensure inference service is never blocked
try:
    from app.ml.pipeline import MlTrainingPipeline
except Exception:  # pragma: no cover
    MlTrainingPipeline = None

__all__ = [
    "FEATURE_NAMES",
    "MlFeatureExtractor",
    "DatasetLoader",
    "MlTrainingPipeline",
    "MlInferenceService",
    "get_ml_service",
]
