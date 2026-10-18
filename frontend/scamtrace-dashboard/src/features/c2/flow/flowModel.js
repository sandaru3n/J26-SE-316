import { Brain, Code2, FileCode2, Gauge, Globe, Languages, Layers, LayoutTemplate, Link2, Workflow } from 'lucide-react'
import { defangText, defangUrl } from '../api/defang.js'
import { ARM_LABELS, CLASS_LABELS, LANGUAGE_LABELS, pct } from '../constants.js'

// The three modality lanes that merge into fusion (N3: tri-modal).
export const LANES = [
  { id: 'structure', label: 'Structure', modality: 'dom' },
  { id: 'content', label: 'Content', modality: 'content' },
  { id: 'behavior', label: 'Behavior', modality: 'behavior' },
]

// The real stages of the 9B-1 orchestrator, in execution order, with their timings_ms keys.
// `novelty` links a stage to the thesis novelty it implements (N1 / N2 / N3).
export const FLOW_STAGES = [
  { id: 'input', n: null, title: 'Input URL', icon: Link2, keys: [], desc: 'URL or pasted page HTML' },
  { id: 'fetch', n: 1, title: 'Fetch', icon: Globe, keys: ['fetch'], desc: 'Static GET · no JS · SSRF-safe' },
  { id: 'preprocess', n: 2, title: 'Preprocess', icon: Workflow, keys: ['preprocess', 'quality'], desc: 'HTML → parsed page + quality' },
  { id: 'dom', n: 3, title: 'DOM structure', icon: LayoutTemplate, lane: 'structure', keys: ['dom_features', 'dom_model'], desc: '52 features → Random Forest' },
  { id: 'content', n: 4, title: 'Content & language', icon: Languages, lane: 'content', keys: ['content'], desc: 'Segments + en / si / ta ID', novelty: 'N2' },
  { id: 'text', n: 5, title: 'Text models', icon: Brain, lane: 'content', keys: ['text_models'], desc: 'XLM-R + TF-IDF on page text', novelty: 'N2' },
  { id: 'js', n: 6, title: 'JS AST analysis', icon: FileCode2, lane: 'behavior', keys: ['js_analysis'], desc: 'tree-sitter AST · never run', novelty: 'N1' },
  { id: 'behavior', n: 7, title: 'Behavior intent', icon: Code2, lane: 'behavior', keys: ['behavior', 'behavior_model'], desc: 'Source → sink → intents', novelty: 'N1' },
  { id: 'fusion', n: 8, title: 'Tri-modal fusion', icon: Layers, keys: ['fusion'], desc: 'Late fusion → 5 classes', novelty: 'N3' },
  { id: 'verdict', n: null, title: 'Verdict', icon: Gauge, keys: [], desc: 'Legit · Suspicious · Malicious' },
]
export const STAGE_BY_ID = Object.fromEntries(FLOW_STAGES.map((stage) => [stage.id, stage]))

// Connectors of the flowchart (source → target).
export const EDGES = [
  ['input', 'fetch'],
  ['fetch', 'preprocess'],
  ['preprocess', 'dom'],
  ['preprocess', 'content'],
  ['preprocess', 'js'],
  ['content', 'text'],
  ['js', 'behavior'],
  ['dom', 'fusion'],
  ['text', 'fusion'],
  ['behavior', 'fusion'],
  ['fusion', 'verdict'],
]

const MODALITY_OF = { dom: 'dom', content: 'content', text: 'content', js: 'behavior', behavior: 'behavior' }

export const STATUS_LABEL = { ok: 'ok', skipped: 'skipped', failed: 'failed', notrun: 'not run', running: 'in progress', waiting: 'waiting' }

/** The REAL outcome of one stage from an AnalysisResponse: state, ms (sum of its keys), note. */
export function stageOutcome(stage, result) {
  const timings = result.timings_ms || {}
  const ran = stage.keys.some((key) => key in timings)
  const ms = ran ? stage.keys.reduce((sum, key) => sum + (timings[key] || 0), 0) : null
  if (stage.id === 'input') {
    return { state: 'ok', ms: null, note: result.input?.mode === 'html' ? 'pasted HTML' : 'URL submitted' }
  }
  if (stage.id === 'verdict') {
    if (result.verdict) return { state: 'ok', ms: timings.total ?? null, note: `${result.verdict} · risk ${result.risk_score}` }
    return { state: 'notrun', ms: null, note: `no verdict — ${result.status}` }
  }
  if (stage.id === 'fetch') {
    if (result.input?.mode === 'html') {
      return { state: 'skipped', ms: null, note: result.demo ? 'recorded page (demo)' : 'pasted HTML, not fetched' }
    }
    if (result.status === 'unreachable') return { state: 'failed', ms, note: 'page could not be fetched' }
  }
  const modality = MODALITY_OF[stage.id] && result.modalities?.[MODALITY_OF[stage.id]]
  if (modality?.status === 'failed') return { state: 'failed', ms, note: 'failed — degraded fusion' }
  if (stage.id === 'text' && ran) {
    const arms = (modality?.arms || []).filter((arm) => arm.status === 'ok')
    if (!arms.length) return { state: 'failed', ms, note: 'no text model answered' }
  }
  if (!ran) {
    if (result.status !== 'ok' && result.status !== 'inconclusive') return { state: 'notrun', ms: null, note: 'no page to analyze' }
    if (result.status === 'inconclusive' && stage.id !== 'preprocess') return { state: 'notrun', ms: null, note: 'inconclusive page' }
    return { state: 'skipped', ms: null, note: 'not needed for this page' }
  }
  return { state: 'ok', ms, note: stage.desc }
}

export function allOutcomes(result) {
  return Object.fromEntries(FLOW_STAGES.map((stage) => [stage.id, stageOutcome(stage, result)]))
}

/**
 * Replay schedule: each stage gets a slot proportional to its REAL time (timings_ms order =
 * execution order), with a floor so 0.1 ms stages stay visible; the whole replay ≈ totalMs.
 * Returns [{id, start, end}] in ms from the start of the replay.
 */
export function replaySchedule(outcomes, totalMs = 5000) {
  const floor = 0.05
  const raw = FLOW_STAGES.map((stage) => {
    const outcome = outcomes[stage.id]
    return { id: stage.id, weight: outcome.ms && stage.keys.length ? outcome.ms : 0 }
  })
  const sum = raw.reduce((total, item) => total + item.weight, 0) || 1
  const shares = raw.map((item) => Math.max(floor, item.weight / sum))
  const scale = totalMs / shares.reduce((total, share) => total + share, 0)
  let cursor = 0
  return raw.map((item, index) => {
    const start = cursor
    cursor += shares[index] * scale
    return { id: item.id, start, end: cursor }
  })
}

const armVote = (arm) =>
  arm?.status === 'ok' && arm.predicted
    ? `${arm.display || ARM_LABELS[arm.arm] || arm.arm}: ${CLASS_LABELS[arm.predicted] || arm.predicted} ${pct(arm.probabilities?.[arm.predicted], 0)}`
    : arm
      ? `${arm.display || ARM_LABELS[arm.arm] || arm.arm}: ${arm.status}${arm.reason ? ` (${arm.reason})` : ''}`
      : null

const ms = (value) => (value === null || value === undefined ? null : `${Number(value).toFixed(1)} ms`)

/** What this stage did on THIS page — plain sentences from the real response only. */
export function stageCaption(stageId, result) {
  const timings = result.timings_ms || {}
  const modalities = result.modalities || {}
  const lines = []
  const push = (text) => text && lines.push(defangText(String(text)))
  switch (stageId) {
    case 'input':
      push(result.input?.mode === 'html' ? 'Mode: pasted HTML (nothing fetched).' : 'Mode: URL — C2 fetches the page itself.')
      push(`Target: ${defangUrl(result.input?.submitted_url) || '(no URL)'}`)
      if (result.source) push(`Source: ${result.source}`)
      break
    case 'fetch':
      if (result.input?.mode === 'html') push(result.demo ? 'Skipped: this demo replays a recorded page, so no request was sent.' : 'Skipped: the HTML was pasted, so no request was sent.')
      else {
        if (timings.fetch !== undefined) push(`Fetched in ${ms(timings.fetch)}.`)
        if (result.input?.http_status) push(`HTTP ${result.input.http_status}${result.input?.content_type ? ` · ${result.input.content_type}` : ''}`)
        if (result.input?.redirect_hosts?.length > 1) push(`${result.input.redirect_hosts.length - 1} redirect(s): ${result.input.redirect_hosts.join(' → ')}`)
        if (result.input?.final_url) push(`Final URL: ${defangUrl(result.input.final_url)}`)
      }
      if (result.status === 'unreachable' && result.status_reason) push(`Unreachable: ${result.status_reason}`)
      break
    case 'preprocess':
      if (timings.preprocess !== undefined) push(`Parsed the HTML into a structured page in ${ms(timings.preprocess)}.`)
      if (timings.quality !== undefined) push(`Quality check (bot challenge / parked / empty page) in ${ms(timings.quality)}.`)
      if (result.status === 'inconclusive' && result.status_reason) push(`Inconclusive: ${result.status_reason}`)
      break
    case 'dom':
      push(modalities.dom?.summary)
      ;(modalities.dom?.top_evidence || []).slice(0, 2).forEach((item) => push(`• ${item}`))
      push(armVote(modalities.dom?.arms?.[0]))
      break
    case 'content': {
      const language = result.page_language
      const confidence = modalities.content?.stats?.language_confidence
      if (language) push(`Page language: ${LANGUAGE_LABELS[language] || language}${confidence !== undefined ? ` (${pct(confidence, 0)})` : ''}.`)
      if (modalities.content?.stats?.segments !== undefined) push(`${modalities.content.stats.segments} text segments extracted.`)
      const intents = modalities.content?.intents || []
      if (intents.length) push(`Cue-based intents (preliminary): ${intents.map((item) => item.display || item.intent).join(', ')}.`)
      ;(modalities.content?.top_evidence || []).slice(0, 1).forEach((item) => push(`• “${item}”`))
      break
    }
    case 'text':
      ;(modalities.content?.arms || []).forEach((arm) => push(armVote(arm)))
      if (/truncated/.test(modalities.content?.summary || '')) push('XLM-R input was truncated to 512 tokens.')
      break
    case 'js': {
      const stats = modalities.behavior?.stats
      if (stats?.scripts_analyzed !== undefined) {
        push(`${stats.scripts_analyzed} script(s) parsed into an AST${stats.scripts_lexical ? `, ${stats.scripts_lexical} by lexical fallback` : ''}${stats.library_scripts_skipped ? `, ${stats.library_scripts_skipped} known libraries skipped` : ''}.`)
        push(`${stats.sources_total} sensitive source(s), ${stats.sinks_total} sink(s) found — without running any code.`)
      } else push(modalities.behavior?.summary)
      if (timings.js_analysis !== undefined) push(`Static analysis took ${ms(timings.js_analysis)}.`)
      break
    }
    case 'behavior': {
      const stats = modalities.behavior?.stats
      if (stats?.flows_total !== undefined) push(`${stats.flows_total} source → sink flow(s), ${stats.flows_external} to an external destination.`)
      const intents = modalities.behavior?.intents || []
      if (intents.length) intents.slice(0, 3).forEach((item) => push(`• ${item.display || item.intent} (${item.severity})`))
      else (modalities.behavior?.top_evidence || []).slice(0, 2).forEach((item) => push(`• ${item}`))
      push(armVote(modalities.behavior?.arms?.[0]))
      break
    }
    case 'fusion': {
      const explanation = result.explanation || {}
      if (explanation.method) push(`Method: ${explanation.method}.`)
      if (explanation.arms_used?.length) push(`Arms fused: ${explanation.arms_used.map((arm) => ARM_LABELS[arm] || arm).join(', ')}${result.degraded ? ' (degraded)' : ''}.`)
      const top = Object.entries(result.class_probabilities || {}).sort((a, b) => b[1] - a[1])[0]
      if (top) push(`Top class: ${CLASS_LABELS[top[0]] || top[0]} ${pct(top[1], 0)}.`)
      if (explanation.driving_arm) push(`Driving arm: ${ARM_LABELS[explanation.driving_arm] || explanation.driving_arm}.`)
      break
    }
    case 'verdict':
      if (result.verdict) {
        push(`${result.verdict} · ${result.verdict === 'Legitimate' ? 'no threat class' : CLASS_LABELS[result.threat_class] || result.threat_class} · risk ${result.risk_score}/100.`)
        const floor = result.explanation?.evidence_floor_rules || []
        if (floor.length) push(`Evidence floor: ${floor.length} rule(s) fired (${floor.join(', ')}).`)
        if (result.explanation?.verdict_source) push(`Verdict source: ${result.explanation.verdict_source}.`)
      } else push(`No verdict: ${result.status}${result.status_reason ? ` — ${result.status_reason}` : ''}.`)
      if (timings.total !== undefined) push(`Total analysis time ${ms(timings.total)}.`)
      break
    default:
      break
  }
  return lines.length ? lines : ['No output recorded for this stage on this page.']
}
