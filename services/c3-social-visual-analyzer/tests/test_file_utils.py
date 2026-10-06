"""Safe file handling for untrusted uploads."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from app.exceptions import InvalidSampleIdError, StorageError
from app.utils.file_utils import (
    atomic_write_json,
    ensure_within_directory,
    generate_safe_filename,
    safe_suffix,
    sanitize_original_filename,
    save_stream_exclusive,
    to_record_path,
    validate_sample_id,
)


@pytest.mark.parametrize("sample_id", ["SCAM_0001", "LEGIT_0001", "POST_0001", "post-12", " SCAM_7 "])
def test_valid_sample_ids_accepted(sample_id: str) -> None:
    assert validate_sample_id(sample_id) == sample_id.strip()


@pytest.mark.parametrize(
    "sample_id",
    [
        "../../windows/system32",
        "../../../etc/passwd",
        "..",
        "SCAM/0001",
        "SCAM\\0001",
        "C:evil",
        "_hidden",
        "",
        "A" * 65,
        "SCAM 0001",
        None,
    ],
)
def test_unsafe_sample_ids_rejected(sample_id: str | None) -> None:
    with pytest.raises(InvalidSampleIdError):
        validate_sample_id(sample_id)


def test_client_filename_is_not_trusted() -> None:
    assert sanitize_original_filename("../../etc/passwd.jpg") == "passwd.jpg"
    assert sanitize_original_filename("C:\\Users\\x\\evil.png") == "evil.png"
    assert safe_suffix("photo.JPG") == ".jpg"
    assert safe_suffix("run.exe") == ".upload"
    assert safe_suffix("shot.php.png") == ".png"
    assert safe_suffix(None) == ".upload"


def test_generated_filenames_are_unique_and_safe() -> None:
    first = generate_safe_filename("SCAM_0001", ".jpg")
    second = generate_safe_filename("SCAM_0001", ".jpg")
    assert first != second
    assert first.startswith("SCAM_0001_") and first.endswith(".jpg")
    with pytest.raises(ValueError):
        generate_safe_filename("SCAM_0001", "/../x")


def test_paths_outside_base_are_refused(tmp_path: Path) -> None:
    base = tmp_path / "data"
    base.mkdir()
    with pytest.raises(StorageError):
        ensure_within_directory(base / ".." / "escape.txt", base)
    assert to_record_path(base / "raw" / "a.jpg", base) == "data/raw/a.jpg"


def test_stream_save_never_overwrites(tmp_path: Path) -> None:
    saved = save_stream_exclusive(io.BytesIO(b"abc"), tmp_path, "x.jpg", max_bytes=10)
    assert saved.path is not None and saved.path.read_bytes() == b"abc"
    with pytest.raises(StorageError):
        save_stream_exclusive(io.BytesIO(b"zzz"), tmp_path, "x.jpg", max_bytes=10)
    assert (tmp_path / "x.jpg").read_bytes() == b"abc"


def test_stream_save_stops_at_size_limit(tmp_path: Path) -> None:
    saved = save_stream_exclusive(io.BytesIO(b"0" * 100), tmp_path, "big.jpg", max_bytes=10)
    assert saved.exceeded_limit is True and saved.path is None
    assert not (tmp_path / "big.jpg").exists()


def test_atomic_write_json_replaces_content(tmp_path: Path) -> None:
    target = tmp_path / "db.json"
    atomic_write_json(target, {"a": 1})
    atomic_write_json(target, {"b": "ශ්‍රී"})
    assert target.read_text(encoding="utf-8").strip().startswith("{")
    assert "ශ්‍රී" in target.read_text(encoding="utf-8")
    assert [p.name for p in tmp_path.iterdir()] == ["db.json"]
