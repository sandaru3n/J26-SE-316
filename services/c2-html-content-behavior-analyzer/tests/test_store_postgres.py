"""Results store: PostgreSQL backend + SQLite -> PostgreSQL copy (Part 9 B-2).

Offline tests always run (backend choice, secrets never leaked, 503 / /ready / /analyze
when the store is unreachable). Tests marked ``needs_pg`` run only when TEST_DATABASE_URL
points at a PostgreSQL database; each uses its own throw-away schema (tests/pg_helpers).
The whole tests/test_ingest.py suite can also run on PostgreSQL: C2_TEST_STORE=postgres.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from c2_analyzer.api.dependencies import get_ingest_service
from c2_analyzer.api.main import create_app, store_health
from c2_analyzer.config import Settings
from c2_analyzer.store import pg
from c2_analyzer.store.repository import (
    NewJob,
    ResultsStore,
    StoreUnavailable,
    describe_store,
    iso,
    store_target,
)
from c2_analyzer.store.sqlite_to_pg import CopyConflict, copy_sqlite_to_postgres
from tests.pg_helpers import fresh_schema_url, pg_test_url

needs_pg = pytest.mark.skipif(not pg_test_url(), reason="TEST_DATABASE_URL not set")
SECRET_URL = "postgresql://c2user:Sup3r%23Secret@127.0.0.1:1/c2db"


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 18, 9, 0, 0, 123456, tzinfo=UTC)

    def __call__(self) -> datetime:
        self.now += timedelta(seconds=1)
        return self.now


def response(n: int) -> dict:
    return {"analysis_id": f"an-{n}", "verdict": "Malicious", "nested": {"b": 1, "a": [n]}}


def summary(verdict: str | None, status: str = "ok", cls: str | None = "phishing") -> dict:
    return {
        "verdict": verdict,
        "threat_class": cls,
        "risk_score": 90 if verdict == "Malicious" else 10,
        "status": status,
        "final_url_domain": "evil-shop.example",
        "page_language": "si",
        "top_findings": [{"id": "dom.x", "severity": "high", "title": "සිංහල title"}],
    }


def scenario(store: ResultsStore) -> dict:
    """Every repository method once; returns what callers would see (backend-neutral)."""
    out: dict = {}
    ids = store.create_jobs(
        [
            NewJob("https://a.example/login", "a.example/login", "threatradar_push", {"ch": 1}),
            NewJob("https://b.example/50%_off", "b.example/50%_off", "threatradar_pull", {}),
            NewJob("https://c.example/", "c.example/", "api", {}, demo=True),
        ]
    )
    out["ids"] = ids
    out["depth"] = store.queue_depth()
    first = store.claim_next()
    out["claimed"] = (first.id, first.attempts, first.source_ref, first.demo)
    store.release(first.id)
    store.release(first.id)  # attempts never below 0
    out["after_release"] = store.job(first.id)["attempts"]
    first = store.claim_next()
    out["complete_at"] = store.complete(first.id, response(1), summary("Malicious"))
    second = store.claim_next()
    store.retry_later(second.id, "timeout " * 100, store.clock() + timedelta(hours=1))
    out["retry_job"] = store.job(second.id)
    third = store.claim_next()
    store.fail(third.id, "boom")
    out["no_more"] = store.claim_next()
    since = iso(store.clock() - timedelta(days=1))
    out["reusable"] = store.reusable_job("a.example/login", since)
    dup = store.create_jobs(
        [
            NewJob(
                "https://a.example/login",
                "a.example/login",
                "threatradar_push",
                {},
                status="skipped_duplicate",
                duplicate_of=first.id,
            )
        ]
    )[0]
    out["dup_result"] = store.result(dup)
    user_id, finished = store.insert_finished(
        NewJob("(pasted HTML)", None, "user", {}), response(2), summary("Legitimate", cls=None)
    )
    out["user"] = (user_id, finished)
    out["known"] = sorted(store.known_urls(["a.example/login", "c.example/", "z.example/"]))
    out["counts"] = store.job_counts()
    out["scans_all"] = store.list_scans()
    out["scans_filtered"] = [
        [r["id"] for r in store.list_scans(source="threatradar_push")],
        [r["id"] for r in store.list_scans(verdict="Malicious")],
        [r["id"] for r in store.list_scans(verdict="none")],
        [r["id"] for r in store.list_scans(threat_class="phishing")],
        [r["id"] for r in store.list_scans(since=since)],
        [r["id"] for r in store.list_scans(since="2099-01-01")],
        [r["id"] for r in store.list_scans(q="A.EXAMPLE")],
        [r["id"] for r in store.list_scans(q="50%")],
        [r["id"] for r in store.list_scans(q="_")],
        [r["id"] for r in store.list_scans(limit=1, before_id=user_id)],
    ]
    out["window"] = store.window_rows(since)
    out["dups_since"] = store.duplicates_since(since)
    out["review_added"] = [store.add_review(first.id, "malicious"), store.add_review(dup, "x")]
    out["review_again"] = store.add_review(first.id, "malicious")
    out["reviews"] = store.reviews()
    store.decide_review(first.id, "confirmed", "phishing", "tester")
    store.mark_exported([first.id])
    out["confirmed"] = store.reviews("confirmed", limit=5)
    out["review_counts"] = store.review_counts()
    with pytest.raises(KeyError):
        store.decide_review(999, "confirmed", None, "tester")
    with pytest.raises(ValueError):
        store.create_jobs([NewJob("https://x.example/", None, "nope", {})])
    out["requeued"] = store.requeue_running()
    out["deleted_demo"] = store.delete_demo()
    out["final_counts"] = store.job_counts()
    out["health"] = store.health()["ok"]
    return out


# ---- offline -------------------------------------------------------------------------------


def test_scenario_on_sqlite_has_the_expected_shape():
    store = ResultsStore(":memory:", clock=Clock())
    out = scenario(store)
    assert out["claimed"] == (1, 1, {"ch": 1}, False) and out["after_release"] == 0
    assert len(out["retry_job"]["error"]) == 500 and out["no_more"] is None
    assert out["reusable"] == 1 and out["dup_result"] == response(1)
    assert out["known"] == ["a.example/login"]  # demo rows never count
    assert out["scans_filtered"][6] == [1] and out["scans_filtered"][7] == []
    assert isinstance(out["scans_all"][0]["created_at"], str) and out["scans_all"][0]["demo"] == 0
    assert out["review_added"] == [True, False] and out["review_again"] is False
    assert out["reviews"][0]["top_findings"][0]["title"] == "සිංහල title"
    assert out["confirmed"][0]["exported_at"] and out["deleted_demo"] == 1 and out["health"]


def test_store_target_prefers_database_url(tmp_path):
    db = tmp_path / "r.db"
    with_url = Settings(_env_file=None, database_url=SecretStr(SECRET_URL), results_db=db)
    assert store_target(with_url) == SECRET_URL
    assert store_target(Settings(_env_file=None, database_url=SecretStr(" "), results_db=db)) == db
    assert describe_store(SECRET_URL) == 'PostgreSQL database "c2db" on 127.0.0.1:1'
    with pytest.raises(ValueError, match="postgresql://"):
        ResultsStore("mongodb://localhost/c2")


def test_secrets_never_appear_in_errors():
    error = RuntimeError(f"could not connect: {SECRET_URL} password Sup3r#Secret")
    text = pg.safe_error(error, SECRET_URL)
    assert "Sup3r" not in text and SECRET_URL not in text and text.startswith("RuntimeError")
    assert "c2user" not in pg.describe_target(SECRET_URL)


def test_unreachable_postgres_fails_clearly_without_the_connection_string():
    with pytest.raises(StoreUnavailable) as caught:
        ResultsStore(SECRET_URL)  # port 1: nothing listens
    message = str(caught.value)
    assert message.startswith('PostgreSQL results store unavailable (database "c2db"')
    assert "Sup3r" not in message and SECRET_URL not in message
    assert caught.value.__cause__ is None  # driver exception (and its text) not chained


def test_api_when_the_store_is_unavailable():
    """Dashboard / ingest endpoints answer 503 with the reason; /ready reports it;
    /analyze keeps answering (the check is just not saved)."""
    from c2_analyzer.api.dependencies import get_engine, get_rate_limiter, get_result_cache
    from c2_analyzer.api.guards import RateLimiter, ResultCache
    from tests.test_ingest import FakeEngine

    def unavailable():
        raise StoreUnavailable('PostgreSQL results store unavailable (database "c2"): down')

    app = create_app("production", warm_up=False)
    app.dependency_overrides[get_ingest_service] = unavailable
    app.dependency_overrides[get_engine] = FakeEngine
    app.dependency_overrides[get_result_cache] = lambda: ResultCache(600, 10)
    app.dependency_overrides[get_rate_limiter] = lambda: RateLimiter(1000, 60)
    client = TestClient(app)
    scans = client.get("/api/v1/scans")
    assert scans.status_code == 503 and "unavailable" in scans.json()["detail"]
    assert client.get("/api/v1/stats/overview").status_code == 503
    assert store_health(app) == {
        "backend": "postgresql",
        "ok": False,
        "error": 'PostgreSQL results store unavailable (database "c2"): down',
    }
    analyzed = client.post("/api/v1/analyze", json={"url": "https://shop.example/"})
    assert analyzed.status_code == 200


def test_ready_reports_the_sqlite_store():
    from c2_analyzer.ingest.service import IngestService
    from tests.test_ingest import api

    client = api(IngestService(ResultsStore(":memory:")))
    assert store_health(client.app) == {"backend": "sqlite", "ok": True, "error": None}


# ---- PostgreSQL (TEST_DATABASE_URL) --------------------------------------------------------


@needs_pg
def test_postgres_answers_exactly_like_sqlite():
    sqlite_out = scenario(ResultsStore(":memory:", clock=Clock()))
    store = ResultsStore(fresh_schema_url(), clock=Clock())
    try:
        assert store.backend == "postgresql"
        assert scenario(store) == sqlite_out
    finally:
        store.close()


@needs_pg
def test_postgres_schema_types_indexes_and_migrations_run_twice():
    url = fresh_schema_url()
    stores: list[ResultsStore] = []
    errors: list[BaseException] = []

    def open_store():
        try:
            stores.append(ResultsStore(url))
        except BaseException as error:  # noqa: BLE001
            errors.append(error)

    threads = [threading.Thread(target=open_store) for _ in range(4)]  # concurrent starts
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors and len(stores) == 4
    with pg.connect(url) as connection:
        assert pg.migrate(connection) == pg.PG_SCHEMA_VERSION  # again: no change
        versions = connection.execute("SELECT version FROM c2_schema_migrations").fetchall()
        assert [row["version"] for row in versions] == [1]
        types = {
            (row["table_name"], row["column_name"]): row["data_type"]
            for row in connection.execute(
                "SELECT table_name, column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = current_schema()"
            ).fetchall()
        }
        indexes = {
            row["indexname"]
            for row in connection.execute(
                "SELECT indexname FROM pg_indexes WHERE schemaname = current_schema()"
            ).fetchall()
        }
    assert types[("scan_jobs", "created_at")] == "timestamp with time zone"
    assert types[("scan_results", "full_response")] == "jsonb"
    assert (
        types[("scan_jobs", "source_ref")] == "jsonb" and types[("scan_jobs", "demo")] == "boolean"
    )
    assert types[("scan_jobs", "id")] == "bigint"
    assert {"ix_jobs_queue", "ix_jobs_source", "ix_results_verdict", "ix_results_class"} <= indexes
    for store in stores:
        store.close()


@needs_pg
def test_two_processes_never_claim_the_same_job():
    url = fresh_schema_url()
    first, second = ResultsStore(url), ResultsStore(url)  # two pools = two processes
    first.create_jobs(
        [NewJob(f"https://{n}.example/", f"{n}.example/", "api", {}) for n in range(20)]
    )
    claimed: list[int] = []

    def drain(store: ResultsStore) -> None:
        while (job := store.claim_next()) is not None:
            claimed.append(job.id)

    threads = [threading.Thread(target=drain, args=(s,)) for s in (first, second, first, second)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(claimed) == list(range(1, 21))  # every job exactly once
    first.close()
    second.close()


@needs_pg
def test_copy_sqlite_to_postgres_is_idempotent(tmp_path):
    sqlite_file = tmp_path / "results.db"
    source = ResultsStore(sqlite_file, clock=Clock())
    scenario(source)
    expected = {
        "scans": source.list_scans(),
        "reviews": source.reviews(None),
        "jobs": [source.job(n) for n in range(1, 7)],
        "result": source.result(4),
    }
    source.close()
    url = fresh_schema_url()

    report = copy_sqlite_to_postgres(sqlite_file, url)
    assert report.inserted == report.source == report.target_after
    assert report.source == {"scan_jobs": 4, "scan_results": 2, "review_queue": 1}
    again = copy_sqlite_to_postgres(sqlite_file, url)
    assert again.inserted == {"scan_jobs": 0, "scan_results": 0, "review_queue": 0}
    assert again.already_present == report.source and again.target_after == report.source

    store = ResultsStore(url)
    assert store.list_scans() == expected["scans"]
    assert store.reviews(None) == expected["reviews"]
    assert [store.job(n) for n in range(1, 7)] == expected["jobs"]
    assert store.result(4) == expected["result"]  # the duplicate follows its original
    new_id = store.create_jobs([NewJob("https://n.example/", "n.example/", "api", {})])[0]
    assert new_id == 6  # the id sequence continues after the copied ids
    store.close()


@needs_pg
def test_copy_refuses_when_postgres_has_other_jobs(tmp_path):
    sqlite_file = tmp_path / "results.db"
    source = ResultsStore(sqlite_file, clock=Clock())
    source.create_jobs([NewJob("https://a.example/", "a.example/", "api", {})])
    source.close()
    url = fresh_schema_url()
    live = ResultsStore(url)
    live.create_jobs([NewJob("https://other.example/", "other.example/", "api", {})])
    with pytest.raises(CopyConflict, match="Nothing was copied"):
        copy_sqlite_to_postgres(sqlite_file, url)
    assert [r["url"] for r in live.list_scans()] == [] and live.job(1)["url"].startswith(
        "https://other"
    )
    live.close()
