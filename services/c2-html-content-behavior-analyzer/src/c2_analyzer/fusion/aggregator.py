"""Turn the parts' outputs into findings, modality summaries and the explanation.

Part 9: Batch B-1 - end-to-end URL analysis engine.

Every finding is a plain-English sentence a non-expert can act on, plus a SHORT evidence
string: a domain, a masked code snippet, a text fragment. Never raw page HTML - the
frontend and ThreatRadar store and display these, and a scam page's markup must not
travel further than C2 (XSS / PII rule). ``safe_evidence`` masks PII (Part 5A / 7
masking: emails, phones, NIC, cards), removes tags and caps the length.

Findings are ranked: evidence-floor rules first, then by severity, then by modality
(fetch, behavior, dom, content, fusion), and capped (configs/analyze.yaml) with a count of
the rest, so the caller always sees the most important reasons first.
"""

from __future__ import annotations

import re

from c2_analyzer.content.extractor import content_rules, has_urgency
from c2_analyzer.content.taxonomy import BENIGN, load_taxonomy
from c2_analyzer.dom.dictionary import specs as dom_specs
from c2_analyzer.schemas.analysis import (
    SEVERITY_RANK,
    AnalysisFinding,
    EvidenceStep,
    IntentEvidence,
)
from c2_analyzer.schemas.behavior import BehaviorResult
from c2_analyzer.schemas.content import PageText
from c2_analyzer.schemas.dom import DomResult
from c2_analyzer.utils.pii import mask_pii

MAX_CHAIN_STEPS = 8  # evidence chain lines shown per behavior finding (dashboard)

MODALITY_ORDER = {"fetch": 0, "behavior": 1, "dom": 2, "content": 3, "fusion": 4}
TAG = re.compile(r"<[^>]{0,500}>")
SPACES = re.compile(r"\s+")
DOMAIN_KEYS = ("domain", "domains", "service", "top_domain")


def safe_evidence(text: object, limit: int = 160) -> str | None:
    """PII-masked, tag-free, single-line, at most ``limit`` characters (or None)."""
    if text is None:
        return None
    value = mask_pii(str(text))
    value = TAG.sub(" ", value).replace("<", "‹").replace(">", "›")
    value = SPACES.sub(" ", value).strip()
    if not value:
        return None
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def _first_sentence(text: str) -> str:
    first = text.split(". ")[0].strip()
    return first if first.endswith(".") else first + "."


def dom_findings(result: DomResult, limit: int) -> tuple[list[AnalysisFinding], dict[str, str]]:
    """Part 3 evidence items (high / medium) -> findings; + feature -> evidence text."""
    descriptions = {name: spec.description for name, spec in dom_specs().items()}
    findings, evidence_of = [], {}
    for item in result.evidence:
        domain = next((item.details[k] for k in DOMAIN_KEYS if item.details.get(k)), None)
        evidence = safe_evidence(domain, limit)
        if evidence:
            evidence_of[item.feature] = evidence
        if item.severity not in ("high", "medium"):
            continue
        findings.append(
            AnalysisFinding(
                id=f"dom.{item.feature}",
                modality="dom",
                severity=item.severity,
                title=safe_evidence(item.message, 200) or item.feature,
                detail=_first_sentence(descriptions.get(item.feature, item.message)),
                evidence=evidence,
            )
        )
    return findings, evidence_of


def behavior_findings(
    result: BehaviorResult, limit: int
) -> tuple[list[AnalysisFinding], list[tuple[str, str, str | None]]]:
    """Part 8 findings -> findings; + (pattern, variant, evidence) for the evidence floor."""
    findings, keys = [], []
    for finding in result.findings:
        snippet = next((e.code for e in finding.evidence if e.code), None)
        evidence = safe_evidence(snippet, limit)
        keys.append((finding.pattern_id, finding.variant, evidence))
        findings.append(
            AnalysisFinding(
                id=f"behavior.{finding.pattern_id}.{finding.variant}",
                modality="behavior",
                severity=finding.severity,
                title=finding.name,
                detail=safe_evidence(finding.message, 400) or finding.name,
                evidence=evidence,
                steps=[
                    EvidenceStep(
                        kind=item.kind,
                        line=item.line,
                        code=safe_evidence(item.code, 120) or "",
                        note=safe_evidence(item.note, 80),
                    )
                    for item in finding.evidence[:MAX_CHAIN_STEPS]
                    if item.code
                ],
            )
        )
    return findings, keys


def content_findings(
    text: PageText, text_arms: dict[str, dict], limit: int
) -> list[AnalysisFinding]:
    """Urgency wording + what the text models think (only when they see a threat)."""
    findings = []
    rules = content_rules()
    urgent = [s for s in text.segments if has_urgency(s.text, rules)]
    if urgent:
        findings.append(
            AnalysisFinding(
                id="content.urgency",
                modality="content",
                severity="low",
                title="Urgent / alarming wording",
                detail=f"{len(urgent)} text segment(s) pressure the visitor (deadline, "
                "suspension, warning) - a common scam tactic.",
                evidence=safe_evidence(urgent[0].text, limit),
            )
        )
    votes = {
        name: arm
        for name, arm in text_arms.items()
        if arm.get("predicted") not in (None, "benign")
        and (arm.get("probabilities") or {}).get(arm["predicted"], 0) >= 0.5
    }
    if votes:
        classes = sorted({arm["predicted"] for arm in votes.values()})
        shares = ", ".join(
            f"{arm['display']} {arm['probabilities'][arm['predicted']]:.0%} {arm['predicted']}"
            for arm in votes.values()
        )
        cta = next((s.text for s in text.segments if s.field in ("cta", "title")), None)
        findings.append(
            AnalysisFinding(
                id="content.text_model",
                modality="content",
                severity="medium",
                title=f"Page text reads like a {' / '.join(classes)} page",
                detail=f"The multilingual text models classify the visible text as a threat "
                f"({shares}).",
                evidence=safe_evidence(cta, limit),
            )
        )
    return findings


BEHAVIOR_INTENT_METHOD = "static AST source->sink patterns (Part 8, never executed)"
CONTENT_INTENT_METHOD = (
    "cue-word matches of the intent taxonomy (preliminary; intent model pending, Part 6B)"
)
MAX_INTENT_CUES = 5


def behavior_intents(result: BehaviorResult, limit: int) -> list[IntentEvidence]:
    """Part 8 findings grouped by pattern: the behavioral intents the page's code shows."""
    grouped: dict[str, IntentEvidence] = {}
    for finding in result.findings:  # most severe first
        intent = grouped.get(finding.pattern_id)
        if intent is None:
            grouped[finding.pattern_id] = IntentEvidence(
                intent=finding.pattern_id,
                display=finding.name,
                method="ast_source_sink",
                severity=finding.severity,
                count=finding.count,
                example=safe_evidence(finding.message, limit),
            )
            continue
        intent.count += finding.count
        if SEVERITY_RANK[finding.severity] > SEVERITY_RANK[intent.severity or "info"]:
            intent.severity = finding.severity
    return list(grouped.values())


def behavior_stats(result: BehaviorResult) -> dict[str, float]:
    """Counters behind the behavior intents (scripts, sources, sinks, flows)."""
    summary = result.summary
    return {
        "scripts_analyzed": summary.scripts_analyzed,
        "scripts_lexical": summary.scripts_lexical,
        "library_scripts_skipped": summary.library_scripts_skipped,
        "sources_total": summary.sources_total,
        "sinks_total": summary.sinks_total,
        "flows_total": summary.flows_total,
        "flows_external": sum(bool(flow.sink_is_external) for flow in result.flows),
        "behavior_risk_score": float(result.behavior_risk_score),
    }


def content_intents(text: PageText, limit: int) -> list[IntentEvidence]:
    """Social-engineering intents suggested by the taxonomy's cue words (en / si / ta).

    PRELIMINARY: cue words only suggest (Part 5B weak labelling); the intent-level model
    is Part 6B. Benign is never listed - no cue simply means no intent evidence.
    """
    taxonomy = load_taxonomy()
    found: dict[str, IntentEvidence] = {}
    for segment in text.segments:
        if segment.field == "hidden":
            continue
        for intent_id, cues in taxonomy.cue_hits(segment.text).items():
            if intent_id == BENIGN:
                continue
            intent = found.setdefault(
                intent_id,
                IntentEvidence(
                    intent=intent_id,
                    display=intent_id.replace("_", " "),
                    method="cue_words",
                    example=safe_evidence(segment.text, limit),
                ),
            )
            intent.count += 1
            for cue in cues:
                if cue not in intent.cues and len(intent.cues) < MAX_INTENT_CUES:
                    intent.cues.append(cue)
    order = {name: index for index, name in enumerate(taxonomy.priority)}
    return sorted(found.values(), key=lambda item: order.get(item.intent, len(order)))


def content_stats(text: PageText) -> dict[str, float]:
    """Counters behind the content modality (segments, language confidence, scripts)."""
    ratios = text.language.script_ratios
    return {
        "segments": len(text.segments),
        "page_text_chars": text.page_text_chars,
        "language_confidence": round(float(text.language.confidence), 4),
        "si_script_ratio": round(float(ratios.get("si", 0.0)), 4),
        "ta_script_ratio": round(float(ratios.get("ta", 0.0)), 4),
        "latin_script_ratio": round(float(ratios.get("latin", 0.0)), 4),
    }


def rank(findings: list[AnalysisFinding], cap: int) -> tuple[list[AnalysisFinding], int]:
    """Most important first (floor rules, severity, modality); (kept, omitted count)."""
    ordered = sorted(
        findings,
        key=lambda f: (
            not f.raises_verdict,
            -SEVERITY_RANK[f.severity],
            MODALITY_ORDER.get(f.modality, 9),
            f.id,
        ),
    )
    return ordered[:cap], max(0, len(ordered) - cap)
