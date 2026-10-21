"""The dashboard's Demo-mode fixtures may only show v0.3 TEST pages (PP1 honesty rule).

Part 9: Batch B-2 - read APIs for the team frontend (scripts/export_ui_fixtures.py).

A page the models were trained on would make the replayed demo look better than the
models are, so every analysed page in ``frontend/.../c2/fixtures`` (Scan examples and
feed scans) must be in the TEST split of ``data/splits/v0.3/split.csv``. The export
script refuses anything else; this test guards the files that are actually shipped.
"""

from __future__ import annotations

import csv
import json

import pytest

from c2_analyzer.config import project_root

FIXTURES = project_root().parents[1] / "frontend/scamtrace-dashboard/src/features/c2/fixtures"
SPLIT = project_root() / "data/splits/v0.3/split.csv"

pytestmark = pytest.mark.skipif(
    not (FIXTURES / "analyses.json").is_file() or not SPLIT.is_file(),
    reason="dashboard fixtures or the v0.3 split not present",
)


def load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def split_of() -> dict[str, str]:
    with SPLIT.open(encoding="utf-8", newline="") as handle:
        return {row["sample_id"]: row["split"] for row in csv.DictReader(handle)}


def test_scan_examples_are_test_pages():
    splits = split_of()
    analyses = load("analyses.json")
    pages = {name: a["request_id"] for name, a in analyses.items() if name != "unreachable"}
    assert pages, "no analysed example in analyses.json"
    assert {name: splits.get(sid) for name, sid in pages.items()} == {
        name: "test" for name in pages
    }
    assert "c2_phishing_000081" not in pages.values()  # the old (train) Zimbra page


def test_feed_scans_are_demo_test_pages():
    splits = split_of()
    scans = load("scans.json")["items"]
    details = load("scan_details.json")
    assert scans and all(item["demo"] for item in scans)
    assert {str(item["id"]) for item in scans} == set(details)
    not_test = {
        sid: splits.get(sid)
        for sid in (detail["request_id"] for detail in details.values())
        if splits.get(sid) != "test"
    }
    assert not_test == {}


def test_top_domains_carry_hosted_on():
    for window in load("stats.json").values():
        assert all("hosted_on" in domain for domain in window["top_domains"])
