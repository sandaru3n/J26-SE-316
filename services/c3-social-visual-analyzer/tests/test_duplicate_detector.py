"""Checklist 8: duplicate detection by pHash Hamming distance."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image, ImageEnhance

from app.schemas.image_schema import HashRecord
from app.services.duplicate_detector import DuplicateDetector
from app.services.hash_store import HashStore
from app.services.image_hash_service import ImageHashService, generate_phash
from tests.conftest import image_bytes, make_pattern_image


@pytest.fixture
def store(tmp_path: Path) -> HashStore:
    return HashStore(tmp_path / "image_hashes.json")


def _register(store: HashStore, sample_id: str, phash: str) -> None:
    store.add(sample_id, HashRecord(file=f"data/processed/{sample_id}.png", phash=phash))


def test_empty_store_reports_no_duplicate(store: HashStore) -> None:
    result = DuplicateDetector(store).find_duplicate(generate_phash(make_pattern_image()))
    assert result.model_dump(include={"is_duplicate", "duplicate_type", "matched_sample_id", "hash_distance"}) == {
        "is_duplicate": False,
        "duplicate_type": None,
        "matched_sample_id": None,
        "hash_distance": None,
    }


def test_same_image_is_exact_duplicate(store: HashStore) -> None:
    _register(store, "SCAM_0012", generate_phash(make_pattern_image()))
    result = DuplicateDetector(store).find_duplicate(generate_phash(make_pattern_image()))
    assert result.is_duplicate is True
    assert result.duplicate_type == "exact_duplicate"
    assert result.matched_sample_id == "SCAM_0012"
    assert result.hash_distance == 0


def test_near_duplicate_detected_within_threshold(store: HashStore) -> None:
    original = make_pattern_image((800, 600))
    _register(store, "SCAM_0001", generate_phash(original))

    edited = ImageEnhance.Brightness(original.resize((640, 480))).enhance(1.15)
    recompressed = Image.open(io.BytesIO(image_bytes(edited, "JPEG", quality=35)))
    edited_hash = generate_phash(recompressed)

    distance = ImageHashService.hamming_distance(generate_phash(original), edited_hash)
    result = DuplicateDetector(store, threshold=5).find_duplicate(edited_hash)

    assert distance <= 5
    assert result.is_duplicate is True
    assert result.matched_sample_id == "SCAM_0001"
    assert result.hash_distance == distance
    assert result.duplicate_type == ("exact_duplicate" if distance == 0 else "near_duplicate")


def test_near_duplicate_classification_by_distance(store: HashStore) -> None:
    _register(store, "SCAM_0001", "0000000000000000")
    detector = DuplicateDetector(store, threshold=5)

    near = detector.find_duplicate("0000000000000007")  # 3 bits differ
    assert (near.duplicate_type, near.hash_distance) == ("near_duplicate", 3)

    boundary = detector.find_duplicate("000000000000001f")  # 5 bits differ
    assert boundary.duplicate_type == "near_duplicate"

    beyond = detector.find_duplicate("000000000000003f")  # 6 bits differ
    assert beyond.is_duplicate is False


def test_different_image_is_not_duplicate(store: HashStore) -> None:
    _register(store, "SCAM_0001", generate_phash(make_pattern_image(variant=0)))
    result = DuplicateDetector(store).find_duplicate(generate_phash(make_pattern_image(variant=1)))
    assert result.is_duplicate is False
    assert result.compared_against == 1


def test_closest_match_is_returned(store: HashStore) -> None:
    _register(store, "FAR", "00000000000000ff")
    _register(store, "CLOSE", "0000000000000001")
    result = DuplicateDetector(store).find_duplicate("0000000000000000")
    assert (result.matched_sample_id, result.hash_distance) == ("CLOSE", 1)


def test_own_sample_id_can_be_excluded(store: HashStore) -> None:
    _register(store, "SCAM_0001", "0000000000000000")
    result = DuplicateDetector(store).find_duplicate("0000000000000000", exclude_sample_id="SCAM_0001")
    assert result.is_duplicate is False
