"""Copy the SQLite results store (data/c2_results.db) into PostgreSQL.

Part 9: Batch B-2 - results store, PostgreSQL backend (optional).

Idempotent: rows are copied with their ORIGINAL ids (scan ids appear in dashboard links
and in review notes) and ``ON CONFLICT DO NOTHING``, so a second run inserts nothing and
never overwrites a row PostgreSQL already has (it may be newer than the SQLite copy).
Safety: if PostgreSQL holds a DIFFERENT job under an id the SQLite file also uses (C2
already wrote to PostgreSQL before the copy), nothing is copied - merging two histories
would silently drop one of them. Everything happens in ONE transaction; the SQLite file is
opened read-only and never changed. Afterwards the id sequence continues after the
largest id, so new jobs never collide with copied ones.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from c2_analyzer.store import pg
from c2_analyzer.store.db import SCHEMA_VERSION

JOB_COLUMNS = (
    "id, url, normalized_url, source, source_ref, status, attempts, created_at, "
    "started_at, finished_at, error, next_attempt_at, demo"
)
RESULT_COLUMNS = (
    "job_id, analysis_id, verdict, threat_class, risk_score, status, final_url_domain, "
    "page_language, top_findings, full_response, created_at"
)
REVIEW_COLUMNS = (
    "job_id, reason, state, decided_label, decided_by, decided_at, exported_at, created_at"
)


class CopyConflict(RuntimeError):
    """PostgreSQL already holds other jobs under ids the SQLite file uses."""


@dataclass
class CopyReport:
    source: dict[str, int] = field(default_factory=dict)  # rows in the SQLite file
    inserted: dict[str, int] = field(default_factory=dict)
    already_present: dict[str, int] = field(default_factory=dict)
    target_after: dict[str, int] = field(default_factory=dict)  # rows in PostgreSQL after


def open_sqlite_readonly(path: Path) -> sqlite3.Connection:
    """Read-only (the API may be running on it); refuses another schema version."""
    if not path.is_file():
        raise FileNotFoundError(f"SQLite results store not found: {path}")
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version != SCHEMA_VERSION:
        connection.close()
        raise RuntimeError(
            f"{path.name} has schema v{version}, this code copies v{SCHEMA_VERSION} "
            "(start the API once on it to upgrade)"
        )
    return connection


def count_sqlite(connection: sqlite3.Connection) -> dict[str, int]:
    return {t: connection.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in pg.TABLES}


def count_postgres(connection) -> dict[str, int]:
    return {
        t: connection.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"] for t in pg.TABLES
    }


def copy_sqlite_to_postgres(sqlite_path: Path, url: str) -> CopyReport:
    """Copy every row of ``sqlite_path`` into the PostgreSQL store at ``url``."""
    source = open_sqlite_readonly(sqlite_path)
    try:
        jobs = source.execute(
            f"SELECT {JOB_COLUMNS}, duplicate_of FROM scan_jobs ORDER BY id"
        ).fetchall()
        results = source.execute(f"SELECT {RESULT_COLUMNS} FROM scan_results").fetchall()
        reviews = source.execute(f"SELECT {REVIEW_COLUMNS} FROM review_queue").fetchall()
        report = CopyReport(source=count_sqlite(source))
    finally:
        source.close()

    with pg.connect(url) as target:
        pg.migrate(target)
        with target.transaction():
            present = _matching_jobs(target, jobs)
            report.inserted["scan_jobs"] = _insert(
                target,
                "scan_jobs",
                JOB_COLUMNS,
                "id",
                [_job_row(job) for job in jobs if job["id"] not in present],
            )
            new_duplicates = [
                (job["duplicate_of"], job["id"])
                for job in jobs
                if job["id"] not in present and job["duplicate_of"] is not None
            ]
            if new_duplicates:  # after all jobs exist (a duplicate points at another job)
                with target.cursor() as cursor:
                    cursor.executemany(
                        "UPDATE scan_jobs SET duplicate_of = %s WHERE id = %s", new_duplicates
                    )
            report.inserted["scan_results"] = _insert(
                target, "scan_results", RESULT_COLUMNS, "job_id", [tuple(r) for r in results]
            )
            report.inserted["review_queue"] = _insert(
                target, "review_queue", REVIEW_COLUMNS, "job_id", [tuple(r) for r in reviews]
            )
            target.execute(
                "SELECT setval(pg_get_serial_sequence('scan_jobs', 'id'), "
                "COALESCE(MAX(id), 0) + 1, false) FROM scan_jobs"
            )
        report.already_present = {t: report.source[t] - report.inserted[t] for t in pg.TABLES}
        report.target_after = count_postgres(target)
    return report


def _job_row(job: sqlite3.Row) -> tuple:
    values = [job[name.strip()] for name in JOB_COLUMNS.split(",")]
    values[-1] = bool(values[-1])  # demo: SQLite 0 / 1 -> BOOLEAN
    return tuple(values)


def _matching_jobs(target, jobs: list[sqlite3.Row]) -> set[int]:
    """Ids PostgreSQL already has for the SAME job (an earlier copy); raise on others."""
    if not jobs:
        return set()
    rows = target.execute(
        "SELECT id, url, created_at FROM scan_jobs WHERE id = ANY(%s)", ([j["id"] for j in jobs],)
    ).fetchall()
    by_id = {job["id"]: job for job in jobs}
    clashes = [
        row["id"]
        for row in rows
        if (row["url"], row["created_at"])
        != (by_id[row["id"]]["url"], by_id[row["id"]]["created_at"])
    ]
    if clashes:
        raise CopyConflict(
            f"PostgreSQL already has {len(clashes)} other job(s) under ids used by the SQLite "
            f"file (first: {sorted(clashes)[:5]}). Nothing was copied - copy into an empty "
            "database, before C2 writes to PostgreSQL."
        )
    return {row["id"] for row in rows}


def _insert(target, table: str, columns: str, key: str, rows: list[tuple]) -> int:
    """INSERT ... ON CONFLICT DO NOTHING; returns how many rows were new."""
    if not rows:
        return 0
    before = target.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
    placeholders = ", ".join(["%s"] * len(columns.split(",")))
    with target.cursor() as cursor:
        cursor.executemany(
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT ({key}) DO NOTHING",
            rows,
        )
    return target.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"] - before
