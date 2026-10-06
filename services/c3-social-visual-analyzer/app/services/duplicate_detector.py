"""Visual duplicate detection by pHash Hamming distance.

Duplicates are only *reported*; nothing is deleted. A later dataset-cleaning
stage decides whether to exclude them.
"""

from __future__ import annotations

import logging

from app.schemas.image_schema import DuplicateResult
from app.services.hash_store import HashStore
from app.services.image_hash_service import ImageHashService

logger = logging.getLogger(__name__)


class DuplicateDetector:
    """Finds the closest stored pHash and classifies the match.

    * distance == 0          -> ``exact_duplicate``
    * distance <= threshold  -> ``near_duplicate``
    * distance >  threshold  -> not a duplicate
    """

    def __init__(self, hash_store: HashStore, threshold: int = 5) -> None:
        if threshold < 0:
            raise ValueError("threshold must be >= 0")
        self._hash_store = hash_store
        self.threshold = threshold

    def find_duplicate(self, phash: str, exclude_sample_id: str | None = None) -> DuplicateResult:
        """Compare ``phash`` with every stored hash and return the best match."""
        best_sample_id: str | None = None
        best_distance: int | None = None
        compared = 0

        for sample_id, record in self._hash_store.items():
            if sample_id == exclude_sample_id:
                continue
            try:
                distance = ImageHashService.hamming_distance(phash, record.phash)
            except ValueError:
                logger.warning("Skipping %s: stored pHash size differs from current setting", sample_id)
                continue
            compared += 1
            if best_distance is None or distance < best_distance:
                best_sample_id, best_distance = sample_id, distance
                if distance == 0:
                    break

        if best_distance is None or best_distance > self.threshold:
            logger.info("Duplicate check completed: no duplicate among %d stored hashes", compared)
            return DuplicateResult(threshold=self.threshold, compared_against=compared)

        duplicate_type = "exact_duplicate" if best_distance == 0 else "near_duplicate"
        logger.warning(
            "%s detected: matches %s (distance=%d)",
            duplicate_type.replace("_", " ").capitalize(),
            best_sample_id,
            best_distance,
        )
        return DuplicateResult(
            is_duplicate=True,
            duplicate_type=duplicate_type,
            matched_sample_id=best_sample_id,
            hash_distance=best_distance,
            threshold=self.threshold,
            compared_against=compared,
        )
