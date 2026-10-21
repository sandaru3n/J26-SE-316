"""Export the dashboard's Demo-mode fixtures from REAL C2 output (Part 9 B-2, PP1 safety net).

Part 9: Batch B-2 - read APIs for the team frontend.

Why: the C2 pages in frontend/scamtrace-dashboard must work in the presentation even
without the C2 service or Wi-Fi. Instead of hand-written JSON, this script runs the real
API in-process (production app, real models, html mode = nothing fetched; the unreachable
example uses a reserved ``.invalid`` host, so no request leaves the machine) and saves the
answers. Every URL / domain is DEFANGED (``defang_analysis``) before it is written, so the
fixtures never hold a clickable scam link.

  python scripts/export_ui_fixtures.py --out <dashboard>/src/features/c2/fixtures
  (<dashboard> = ../../frontend/scamtrace-dashboard)
  --analyses-only: rewrite only analyses.json (the Scan page answers); history / stats /
  research fixtures are kept as they are (no results database needed).

  --db <file.db>: read the feed / history / stats fixtures from this SQLite results store
  instead of the configured one (DATABASE_URL / RESULTS_DB), e.g. a throw-away store that
  holds ONLY the demo scans, so no real user check can end up in the fixtures:
    python scripts/demo_ingest.py --db data/tmp/ui_fixtures.db
    python scripts/export_ui_fixtures.py --out <...>/fixtures --db data/tmp/ui_fixtures.db

TEST pages only: every fixture page (Scan examples AND feed scans) must be in the TEST
split of the shared v0.3 split - a page the models were trained on would make the demo
look better than the models are. Anything else stops the export (nothing is written).

Needs the trained v0.3 models and, for the feed / history / stats fixtures, demo scans in
the results store (python scripts/demo_ingest.py).
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from c2_analyzer.api.dependencies import get_ingest_service
from c2_analyzer.api.dev_data import DevDataset
from c2_analyzer.api.main import create_app
from c2_analyzer.config import project_root
from c2_analyzer.ingest.service import IngestService
from c2_analyzer.store.repository import ResultsStore
from c2_analyzer.utils.defang import defang_analysis

# (fixture name, sample id - None = pick the first TEST page of `label` the engine calls
#  Malicious, preferring one where the evidence floor fired if `prefer_floor` -, why)
PAGES = [
    ("benign_sinhala", "c2_benign_000118", None, False, "Sinhala news page - Legitimate + caveat"),
    ("phishing", None, "phishing", True, "phishing page - Malicious, evidence floor preferred"),
    ("crypto_scam", None, "crypto_scam", False, "crypto investment scam - Malicious"),
]
UNREACHABLE_URL = "https://c2-demo-unreachable.invalid/login"


def write(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"  wrote {path.name} ({path.stat().st_size // 1024} KB)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True, help="fixtures folder")
    parser.add_argument("--version", default="v0.3")
    parser.add_argument("--analyses-only", action="store_true", help="only rewrite analyses.json")
    parser.add_argument("--db", type=Path, help="SQLite results store to export the scans from")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    os.chdir(project_root())

    app = create_app("production", warm_up=False)
    if args.db:
        db = args.db.resolve()
        if not db.is_file():
            raise SystemExit(f"--db {db} does not exist (run scripts/demo_ingest.py --db first)")
        app.dependency_overrides[get_ingest_service] = lambda: IngestService(ResultsStore(db))
    client = TestClient(app)  # read APIs: the results store (demo scans)
    # /analyze stores every check in the history - the fixture analyses must not
    # end up there, so they go to a throw-away in-memory store.
    scratch = create_app("production", warm_up=False)
    scratch.dependency_overrides[get_ingest_service] = lambda: IngestService(
        ResultsStore(":memory:")
    )
    analyzer = TestClient(scratch)
    dataset = DevDataset.from_settings()
    manifest = dataset.manifest(args.version)

    def analyze(body: dict) -> dict:
        response = analyzer.post("/api/v1/analyze", json=body)
        response.raise_for_status()
        return defang_analysis(response.json())

    def require_test(sample_id: str, what: str) -> None:
        split = dataset.split_of(args.version, sample_id) if sample_id else None
        if split != "test":
            raise SystemExit(
                f"{what}: {sample_id!r} is in the {split!r} split - demo fixtures may only use "
                f"{args.version} TEST pages; nothing was written"
            )

    def analyze_sample(sample_id: str) -> dict:
        require_test(sample_id, "fixture page")
        html, url = dataset.raw_html(args.version, sample_id)
        return analyze({"html": html, "url": url, "source": "user"})

    def pick(label: str, prefer_floor: bool) -> tuple[str, dict]:
        """First TEST page of ``label`` called Malicious (with a floor rule if preferred)."""
        fallback = None
        for candidate in manifest.loc[manifest["label"] == label, "sample_id"]:
            if dataset.split_of(args.version, candidate) != "test":
                continue
            result = analyze_sample(candidate)
            if result["verdict"] != "Malicious":
                continue
            if not prefer_floor or (result.get("explanation") or {}).get("evidence_floor_rules"):
                return candidate, result
            fallback = fallback or (candidate, result)
        if fallback is None:
            raise SystemExit(f"no {args.version} test page of {label!r} is called Malicious")
        return fallback

    analyses = {}
    for name, sample_id, label, prefer_floor, why in PAGES:
        if sample_id is None:
            sample_id, analyses[name] = pick(label, prefer_floor)
        else:
            analyses[name] = analyze_sample(sample_id)
        result = analyses[name]
        result["request_id"] = sample_id
        print(f"{name}: {sample_id} -> {result['verdict'] or result['status']} ({why})")
    analyses["unreachable"] = analyze({"url": UNREACHABLE_URL, "source": "user"})
    print(f"unreachable: {analyses['unreachable']['status']}")
    if args.analyses_only:
        write(out / "analyses.json", analyses)
        print(f"done (analyses only) -> {out}")
        return

    scans = client.get("/api/v1/scans", params={"limit": 200, "source": "threatradar_push"})
    items = [item for item in scans.json()["items"] if item.get("demo")]  # demo rows only
    if not items:
        raise SystemExit("no demo scans in the results store (run scripts/demo_ingest.py)")
    details = {}
    for item in items:  # every feed scan must be a TEST page too (checked BEFORE writing)
        detail = client.get(f"/api/v1/scans/{item['id']}")
        detail.raise_for_status()
        details[str(item["id"])] = detail.json()
        require_test(details[str(item["id"])].get("request_id"), f"feed scan #{item['id']}")
    write(out / "analyses.json", analyses)
    write(out / "scans.json", {"items": items, "next_cursor": None})
    write(out / "scan_details.json", details)
    write(
        out / "stats.json",
        {
            w: client.get("/api/v1/stats/overview", params={"window": w}).json()
            for w in ("24h", "7d")
        },
    )
    write(out / "research.json", client.get("/api/v1/research/summary").json())
    ready = client.get("/ready")
    write(out / "ready.json", ready.json())
    print(f"done -> {out}")


if __name__ == "__main__":
    main()
