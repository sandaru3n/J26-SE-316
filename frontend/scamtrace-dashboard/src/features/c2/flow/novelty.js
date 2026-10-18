// The three thesis novelties, derived ONLY from fields of the real AnalysisResponse.
// When a stored scan predates the optional `intents` / `stats` fields, the evidence falls back to
// the findings it does carry, and the card says where the evidence came from.

export const NOVELTIES = {
  N1: {
    id: 'N1',
    title: 'Lightweight Static JavaScript Behavioral-Intent Analysis',
    short: 'Static JS behavioral intent',
    claim: 'Infers malicious behavioral intentions from AST / source-to-sink patterns without executing the webpage.',
    stages: ['js', 'behavior'],
  },
  N2: {
    id: 'N2',
    title: 'Localized Multilingual Social-Engineering Intent Detection',
    short: 'Multilingual social-engineering intent',
    claim: 'Detects scam / lure semantics in English, Sinhala and Tamil using cross-lingual NLP.',
    status: 'page-level XLM-R class + cue-based intents (preliminary) · intent model pending (Part 6B)',
    stages: ['content', 'text'],
  },
  N3: {
    id: 'N3',
    title: 'Intent-Aware Tri-Modal Fusion',
    short: 'Intent-aware tri-modal fusion',
    claim: 'Content + DOM structure + JS behavior → 5 threat classes, not just phishing vs benign.',
    stages: ['fusion', 'verdict'],
  },
}

const SEVERITY_ORDER = { critical: 4, high: 3, medium: 2, low: 1, info: 0 }

/** N1: behavioral intents (pattern level) + flow counters + source → sink chains. */
export function n1Evidence(result) {
  const modality = result.modalities?.behavior
  const findings = (result.findings || []).filter((finding) => finding.modality === 'behavior')
  let intents = modality?.intents
  let provenance = modality?.intent_method || null
  if (!Array.isArray(intents)) {
    // older stored scan: group the behavior findings (id = behavior.<pattern>.<variant>) by pattern
    const grouped = new Map()
    findings.forEach((finding) => {
      const pattern = finding.id.split('.')[1] || finding.id
      const known = grouped.get(pattern)
      if (!known) grouped.set(pattern, { intent: pattern, display: finding.title, severity: finding.severity, count: null, example: finding.detail })
      else if ((SEVERITY_ORDER[finding.severity] ?? 0) > (SEVERITY_ORDER[known.severity] ?? 0)) known.severity = finding.severity
    })
    intents = [...grouped.values()]
    provenance = 'from the behavior findings (this stored scan predates the intents field)'
  }
  const chains = findings.filter((finding) => finding.steps?.length).map((finding) => ({ title: finding.title, steps: finding.steps }))
  return {
    ran: modality?.status === 'ok',
    status: modality?.status,
    reason: modality?.reason,
    summary: modality?.summary,
    intents,
    provenance,
    stats: modality?.stats && Object.keys(modality.stats).length ? modality.stats : null,
    chains,
    arm: modality?.arms?.[0] || null,
    hasEvidence: intents.length > 0,
  }
}

/** N2: page language + page-level XLM-R / TF-IDF class + preliminary cue-word intents. */
export function n2Evidence(result) {
  const modality = result.modalities?.content
  const arms = modality?.arms || []
  const xlmr = arms.find((arm) => arm.arm === 'text_xlmr') || null
  const tfidf = arms.find((arm) => arm.arm === 'text_tfidf') || null
  let intents = modality?.intents
  let provenance = modality?.intent_method || null
  if (!Array.isArray(intents)) {
    const urgency = (result.findings || []).find((finding) => finding.id === 'content.urgency')
    intents = urgency ? [{ intent: 'urgency_threat', display: 'urgency (cue rule)', count: null, cues: [], example: urgency.evidence }] : []
    provenance = 'from the content.urgency finding (this stored scan predates the cue-intents field)'
  }
  return {
    ran: modality?.status === 'ok',
    status: modality?.status,
    reason: modality?.reason,
    language: result.page_language,
    confidence: modality?.stats?.language_confidence,
    scriptRatios: modality?.stats
      ? { si: modality.stats.si_script_ratio, ta: modality.stats.ta_script_ratio, latin: modality.stats.latin_script_ratio }
      : null,
    stats: modality?.stats && Object.keys(modality.stats).length ? modality.stats : null,
    xlmr,
    tfidf,
    intents,
    provenance,
    textFindings: (result.findings || []).filter((finding) => finding.modality === 'content'),
    hasEvidence: Boolean((xlmr && xlmr.status === 'ok') || intents.length),
  }
}

const MODALITY_OF_ARM = { dom: 'Structure', text_tfidf: 'Content', text_xlmr: 'Content', behavior: 'Behavior' }

/** N3: the 5-class fused distribution, per-modality share of the explained class, driving arm. */
export function n3Evidence(result) {
  const explanation = result.explanation || {}
  const contributions = explanation.arm_contributions || {}
  const byModality = {}
  Object.entries(contributions).forEach(([arm, value]) => {
    const key = MODALITY_OF_ARM[arm] || arm
    byModality[key] = (byModality[key] || 0) + value
  })
  const totalShare = Object.values(byModality).reduce((sum, value) => sum + value, 0)
  return {
    probabilities: result.class_probabilities || {},
    explainedClass: explanation.explained_class,
    byModality,
    totalShare,
    drivingArm: explanation.driving_arm,
    verdictSource: explanation.verdict_source,
    floorRules: explanation.evidence_floor_rules || [],
    armsUsed: explanation.arms_used || [],
    degraded: result.degraded,
    hasEvidence: Object.keys(result.class_probabilities || {}).length > 0,
  }
}
