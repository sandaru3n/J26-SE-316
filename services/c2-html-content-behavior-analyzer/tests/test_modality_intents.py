"""Optional modality intents + stats in AnalysisResponse (dashboard novelty view).

Part 9: additive fields - older clients and stored scans without them stay valid.
"""

from __future__ import annotations

from pathlib import Path

from c2_analyzer.behavior.pipeline import behavior_for_html
from c2_analyzer.content.extractor import content_for_html
from c2_analyzer.fusion.aggregator import (
    behavior_intents,
    behavior_stats,
    content_intents,
    content_stats,
)
from c2_analyzer.schemas.analysis import IntentEvidence, ModalityResult
from c2_analyzer.utils.defang import defang_analysis

PAGES = Path(__file__).parent / "fixtures" / "sample_pages"

LURE = """<html><head><title>Account limited</title></head><body>
<h1>Your account has been limited</h1>
<p>Verify your account now. Enter the OTP sent to your phone to confirm your identity.</p>
<form action="/x"><input name="otp"><button>Verify now</button></form>
</body></html>"""


def test_content_intents_come_from_cue_words_and_skip_benign():
    _, text = content_for_html(LURE)
    intents = content_intents(text, 160)
    ids = [item.intent for item in intents]
    assert "credential_request" in ids and "benign" not in ids
    first = intents[0]
    assert first.method == "cue_words" and first.count >= 1 and first.cues
    assert first.example and "<" not in first.example
    stats = content_stats(text)
    assert stats["segments"] == len(text.segments) and 0 <= stats["language_confidence"] <= 1


def test_content_without_cues_has_no_intents():
    _, text = content_for_html("<html><body><p>Opening hours: nine to five.</p></body></html>")
    assert content_intents(text, 160) == []


def test_behavior_intents_group_findings_by_pattern():
    html = (PAGES / "js_exfiltration.html").read_text(encoding="utf-8")
    _, _, behavior = behavior_for_html(html, "https://shop.example.com/login")
    intents = behavior_intents(behavior, 160)
    assert behavior.findings, "fixture page must produce a behavior finding"
    assert {item.intent for item in intents} == {f.pattern_id for f in behavior.findings}
    assert all(item.method == "ast_source_sink" and item.severity for item in intents)
    assert sum(item.count for item in intents) == sum(f.count for f in behavior.findings)
    stats = behavior_stats(behavior)
    assert stats["flows_total"] == behavior.summary.flows_total
    assert stats["flows_external"] <= stats["flows_total"]


def test_fields_are_optional_and_defanged():
    old = ModalityResult.model_validate({"status": "ok", "summary": "s"})  # a stored v1 scan
    assert old.intents == [] and old.intent_method is None and old.stats == {}
    modality = ModalityResult(
        status="ok",
        intents=[
            IntentEvidence(
                intent="credential_request",
                method="cue_words",
                count=1,
                cues=["login at bad-bank.com"],
                example="Go to https://bad-bank.com/login now",
            )
        ],
    )
    safe = defang_analysis({"modalities": {"content": modality.model_dump(mode="json")}})
    intent = safe["modalities"]["content"]["intents"][0]
    assert intent["example"] == "Go to hxxps://bad-bank[.]com/login now"
    assert intent["cues"] == ["login at bad-bank[.]com"]
