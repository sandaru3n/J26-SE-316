// Demo mode (presentation safety net): bundled fixtures exported from REAL C2 output by
// services/c2-.../scripts/export_ui_fixtures.py (URLs already defanged). Loaded lazily, so the
// dashboard's main bundle does not carry them.

let cache = null

export function loadDemo() {
  cache ??= Promise.all([
    import('../fixtures/analyses.json'),
    import('../fixtures/scans.json'),
    import('../fixtures/scan_details.json'),
    import('../fixtures/stats.json'),
    import('../fixtures/research.json'),
  ]).then(([analyses, scans, details, stats, research]) => ({
    analyses: analyses.default,
    scans: scans.default,
    details: details.default,
    stats: stats.default,
    research: research.default,
  }))
  return cache
}

// Every example is a v0.3 TEST page (the export script refuses train / val pages), so the
// replayed verdicts are held-out results, not pages the models were trained on.
export const DEMO_EXAMPLES = [
  { key: 'benign_sinhala', label: 'Sinhala news page', hint: 'Legitimate, language caveat', input: 'hxxps://www[.]lankadeepa[.]lk/latest_news' },
  { key: 'phishing', label: 'GitHub Pages credential phishing', hint: 'Malicious, evidence floor', input: 'hxxps://organization-teams-009[.]github[.]io/Technical-Committee-Meetings/' },
  { key: 'crypto_scam', label: 'Crypto investment scam', hint: 'Malicious, crypto_scam', input: 'hxxps://digitalapexminingtech[.]com/' },
  { key: 'unreachable', label: 'Taken-down URL', hint: 'Unreachable, no verdict', input: 'hxxps://c2-demo-unreachable[.]invalid/login' },
]

export const DEMO_NOTICE = 'Demo mode: live scanning is off. Choose an example below, or turn Demo mode off to scan this URL.'
export const DEMO_REPLAY_TOOLTIP = 'replayed from v0.3 test set'

/** Comparable form of a typed / defanged URL: refanged, no scheme, no "www.", no trailing "/". */
function urlKey(input) {
  return String(input || '')
    .trim()
    .toLowerCase()
    .replaceAll('[.]', '.')
    .replace(/^(hxxp|http|fxp|ftp)s?:\/\//, '')
    .replace(/^www\./, '')
    .replace(/\/+$/, '')
}

/**
 * The recorded fixture for one of the DEMO_EXAMPLES URLs (fanged or defanged, with or without
 * scheme / "www." / trailing slash), else null. Nothing else is matched: a URL that was never
 * analysed must not get someone else's verdict.
 */
export function pickDemoAnalysis(analyses, input) {
  const key = urlKey(input)
  const example = key && DEMO_EXAMPLES.find((candidate) => urlKey(candidate.input) === key)
  return (example && analyses[example.key]) || null
}

const sleep = (ms, signal) =>
  new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms)
    signal?.addEventListener('abort', () => {
      clearTimeout(timer)
      reject(new DOMException('Aborted', 'AbortError'))
    })
  })

/**
 * Simulated round trip for a demo example: the recorded answer after roughly its real processing
 * time, with its ORIGINAL analyzed_at and demo: true (the UI labels it "Recorded result").
 * Any other input (or pasted HTML) -> { demo: true, notice } at once, no fake delay.
 */
export async function demoAnalyze(input, { signal } = {}) {
  const { analyses } = await loadDemo()
  const result = pickDemoAnalysis(analyses, input)
  if (!result) return { demo: true, notice: DEMO_NOTICE }
  const total = result.timings_ms?.total || 900
  await sleep(Math.min(Math.max(total * 3, 1800), 3200), signal)
  return { ...result, demo: true }
}

/** A fixture scan shown again in the scripted feed: new "replayed at" time, recorded time kept. */
export function replayRow(item, at = new Date()) {
  return { ...item, demo: true, replayed: true, recorded_at: item.recorded_at || item.created_at, created_at: at.toISOString() }
}

/** Client-side version of GET /api/v1/scans over the fixture list. */
export function filterScans(items, { source, verdict, threat_class: threatClass, q } = {}) {
  const needle = (q || '').trim().toLowerCase()
  return items.filter((item) => {
    if (source && item.source !== source) return false
    if (verdict === 'none' ? item.verdict !== null : verdict && item.verdict !== verdict) return false
    if (threatClass && item.threat_class !== threatClass) return false
    if (needle) {
      const haystack = `${item.url} ${item.final_domain || ''}`.toLowerCase().replaceAll('[.]', '.')
      if (!haystack.includes(needle.replaceAll('[.]', '.'))) return false
    }
    return true
  })
}
