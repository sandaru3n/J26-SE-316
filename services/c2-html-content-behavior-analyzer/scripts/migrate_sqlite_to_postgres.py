"""Copy the SQLite results store into PostgreSQL (DATABASE_URL). Safe to run again.

Part 9: Batch B-2 - results store, PostgreSQL backend (optional).

    python scripts/migrate_sqlite_to_postgres.py                # RESULTS_DB -> DATABASE_URL
    python scripts/migrate_sqlite_to_postgres.py --sqlite other.db
    python scripts/migrate_sqlite_to_postgres.py --counts-only   # row counts in both, no copy

Creates the tables if needed (same migrations as the API), copies jobs / results /
reviews with their original ids, skips rows PostgreSQL already has, then prints the row
counts per table in both databases. The connection string is never printed.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from c2_analyzer.config import get_settings, project_root, resolve_path
from c2_analyzer.store import pg
from c2_analyzer.store.sqlite_to_pg import (
    CopyConflict,
    copy_sqlite_to_postgres,
    count_postgres,
    count_sqlite,
    open_sqlite_readonly,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sqlite", type=Path, help="SQLite file (default RESULTS_DB)")
    parser.add_argument("--counts-only", action="store_true", help="print counts, copy nothing")
    args = parser.parse_args()
    sqlite_path = args.sqlite.resolve() if args.sqlite else None
    os.chdir(project_root())  # .env (DATABASE_URL, RESULTS_DB) is read from the service folder
    settings = get_settings()
    sqlite_path = sqlite_path or resolve_path(settings.results_db)
    url = settings.database_url.get_secret_value().strip()
    if not pg.is_postgres_url(url):
        print("DATABASE_URL is not set to a postgresql:// URL (see .env.example)")
        return 2
    target = pg.describe_target(url)
    print(f"SQLite:     {sqlite_path}")
    print(f"PostgreSQL: {target}")

    try:
        if args.counts_only:
            source = open_sqlite_readonly(sqlite_path)
            try:
                before = count_sqlite(source)
            finally:
                source.close()
            with pg.connect(url) as connection:
                pg.migrate(connection)
                after = count_postgres(connection)
            _table(before, after)
            return 0
        report = copy_sqlite_to_postgres(sqlite_path, url)
    except CopyConflict as error:
        print(f"REFUSED: {error}")
        return 1
    except Exception as error:  # noqa: BLE001 - one clear line, never the connection string
        print(f"FAILED: {pg.safe_error(error, url)}")
        return 1

    print(f"\n{'table':<14}{'sqlite':>8}{'inserted':>10}{'skipped':>9}{'postgres':>10}")
    for table in pg.TABLES:
        print(
            f"{table:<14}{report.source[table]:>8}{report.inserted[table]:>10}"
            f"{report.already_present[table]:>9}{report.target_after[table]:>10}"
        )
    print("\nskipped = already in PostgreSQL (a previous run); nothing is overwritten.")
    return 0


def _table(sqlite_counts: dict[str, int], pg_counts: dict[str, int]) -> None:
    print(f"\n{'table':<14}{'sqlite':>8}{'postgres':>10}")
    for table in pg.TABLES:
        print(f"{table:<14}{sqlite_counts[table]:>8}{pg_counts[table]:>10}")


if __name__ == "__main__":
    sys.exit(main())
