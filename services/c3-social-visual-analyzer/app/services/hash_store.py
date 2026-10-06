"""Persistent store of perceptual hashes (``data/annotations/image_hashes.json``)."""

from __future__ import annotations

import json
import logging
import re
import threading
from pathlib import Path

from pydantic import ValidationError

from app.exceptions import HashDatabaseError, SampleAlreadyExistsError, StorageError
from app.schemas.image_schema import HashRecord
from app.utils.file_utils import atomic_write_json

logger = logging.getLogger(__name__)

_HEX_PATTERN = re.compile(r"^[0-9a-f]+$")


class HashStore:
    """Thread-safe JSON-backed mapping of ``sample_id -> HashRecord``.

    The file is loaded lazily and rewritten atomically (temp file + replace) so a
    crash mid-write cannot corrupt it. A malformed file is never silently
    overwritten: a :class:`HashDatabaseError` is raised so the data can be
    inspected and repaired.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.RLock()
        self._records: dict[str, HashRecord] | None = None
        self._revision = 0

    @property
    def revision(self) -> int:
        """Counter incremented on every change, used to detect concurrent adds."""
        return self._revision

    def _load(self) -> dict[str, HashRecord]:
        if self._records is not None:
            return self._records
        if not self._path.exists():
            self._records = {}
            return self._records
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.error("Hash database %s is malformed: %s", self._path.name, exc)
            raise HashDatabaseError() from exc
        except OSError as exc:
            logger.error("Hash database %s could not be read: %s", self._path.name, exc)
            raise HashDatabaseError() from exc
        if not isinstance(raw, dict):
            logger.error("Hash database %s is not a JSON object", self._path.name)
            raise HashDatabaseError()

        records: dict[str, HashRecord] = {}
        for sample_id, entry in raw.items():
            try:
                record = HashRecord.model_validate(entry)
            except ValidationError as exc:
                logger.error("Hash database entry %r is malformed: %s", sample_id, exc)
                raise HashDatabaseError() from exc
            if not _HEX_PATTERN.fullmatch(record.phash):
                logger.error("Hash database entry %r has a non-hex pHash", sample_id)
                raise HashDatabaseError()
            records[sample_id] = record
        self._records = records
        return records

    def _persist(self, records: dict[str, HashRecord]) -> None:
        payload = {sample_id: record.model_dump() for sample_id, record in records.items()}
        try:
            atomic_write_json(self._path, payload)
        except StorageError as exc:
            raise HashDatabaseError("Failed to write the image hash database.") from exc

    def contains(self, sample_id: str) -> bool:
        with self._lock:
            return sample_id in self._load()

    def items(self) -> list[tuple[str, HashRecord]]:
        """Snapshot of all stored records in insertion order."""
        with self._lock:
            return list(self._load().items())

    def add(self, sample_id: str, record: HashRecord) -> None:
        """Add a record; refuses to overwrite an existing ``sample_id``."""
        with self._lock:
            records = self._load()
            if sample_id in records:
                raise SampleAlreadyExistsError()
            updated = {**records, sample_id: record}
            self._persist(updated)
            self._records = updated
            self._revision += 1

    def remove(self, sample_id: str) -> None:
        """Remove a record (used to roll back a partially committed sample)."""
        with self._lock:
            records = self._load()
            if sample_id not in records:
                return
            updated = {key: value for key, value in records.items() if key != sample_id}
            self._persist(updated)
            self._records = updated
            self._revision += 1
