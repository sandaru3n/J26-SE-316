"""PostgreSQL test databases: one throw-away schema per store, dropped after the run.

Used only when TEST_DATABASE_URL is set (never DATABASE_URL). Each schema is selected
through the connection's ``search_path`` option, so every pooled connection of the store
sees only its own tables. ``C2_TEST_STORE=postgres`` additionally runs the whole
tests/test_ingest.py suite on PostgreSQL instead of in-memory SQLite.
"""

from __future__ import annotations

import os
import uuid
from urllib.parse import quote

_created: list[str] = []


def pg_test_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL", "").strip() or None


def ingest_tests_on_postgres() -> bool:
    return os.environ.get("C2_TEST_STORE", "").strip().lower() == "postgres"


def fresh_schema_url() -> str:
    """A new empty schema in the TEST database; returns a URL whose connections use it."""
    from c2_analyzer.store import pg

    base = pg_test_url()
    if not base:
        raise RuntimeError("TEST_DATABASE_URL is not set")
    schema = f"c2_test_{uuid.uuid4().hex[:12]}"
    with pg.connect(base) as connection:
        connection.execute(f"CREATE SCHEMA {schema}")
    _created.append(schema)
    option = quote(f"-csearch_path={schema}", safe="")
    return f"{base}{'&' if '?' in base else '?'}options={option}"


def drop_test_schemas() -> None:
    if not _created or not pg_test_url():
        return
    from c2_analyzer.store import pg

    with pg.connect(pg_test_url()) as connection:
        for schema in _created:
            connection.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    _created.clear()
