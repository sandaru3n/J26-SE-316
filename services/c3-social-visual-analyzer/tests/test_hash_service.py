"""Checklist 7: perceptual hashing and the hash database."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.exceptions import HashDatabaseError, SampleAlreadyExistsError
from app.schemas.image_schema import HashRecord
from app.services.hash_store import HashStore
from app.services.image_hash_service import ImageHashService, generate_phash
from tests.conftest import make_pattern_image


def test_phash_generated_as_hex_string() -> None:
    service = ImageHashService(hash_size=8)
    result = service.hash_image(make_pattern_image())
    assert result.algorithm == "phash"
    assert re.fullmatch(r"[0-9a-f]{16}", result.hash)


def test_phash_is_deterministic() -> None:
    image = make_pattern_image()
    assert generate_phash(image) == generate_phash(image.copy())


def test_same_image_has_distance_zero() -> None:
    image = make_pattern_image()
    first = generate_phash(image)
    second = generate_phash(make_pattern_image())
    assert ImageHashService.hamming_distance(first, second) == 0


def test_hamming_distance_rejects_mismatched_sizes() -> None:
    small = generate_phash(make_pattern_image(), hash_size=8)
    large = generate_phash(make_pattern_image(), hash_size=16)
    with pytest.raises(ValueError):
        ImageHashService.hamming_distance(small, large)


def _record(phash: str = "ffffffffffffffff") -> HashRecord:
    return HashRecord(file="data/processed/x.png", phash=phash, created_at="2026-01-01T00:00:00+00:00")


def test_hash_store_persists_and_reloads(tmp_path: Path) -> None:
    path = tmp_path / "image_hashes.json"
    store = HashStore(path)
    store.add("SCAM_0001", _record())

    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["SCAM_0001"]["phash"] == "ffffffffffffffff"
    assert HashStore(path).contains("SCAM_0001")
    assert not list(tmp_path.glob("*.tmp"))


def test_hash_store_refuses_to_overwrite_sample(tmp_path: Path) -> None:
    store = HashStore(tmp_path / "image_hashes.json")
    store.add("SCAM_0001", _record())
    with pytest.raises(SampleAlreadyExistsError):
        store.add("SCAM_0001", _record("0000000000000000"))


def test_hash_store_remove_rolls_back(tmp_path: Path) -> None:
    store = HashStore(tmp_path / "image_hashes.json")
    store.add("SCAM_0001", _record())
    store.remove("SCAM_0001")
    assert not HashStore(tmp_path / "image_hashes.json").contains("SCAM_0001")


@pytest.mark.parametrize(
    "content",
    ["{not json", "[1, 2, 3]", '{"SCAM_0001": {"file": "x"}}', '{"SCAM_0001": {"file": "x", "phash": "zz!"}}'],
)
def test_malformed_hash_database_raises_controlled_error(tmp_path: Path, content: str) -> None:
    path = tmp_path / "image_hashes.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(HashDatabaseError):
        HashStore(path).contains("SCAM_0001")
    assert path.read_text(encoding="utf-8") == content
