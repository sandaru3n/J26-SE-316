// Defanging = making URLs / domains NON-clickable before they are shown (threat-intel practice):
// https://bad.example.com/x -> hxxps://bad[.]example[.]com/x. The C2 read APIs already defang;
// POST /api/v1/analyze does not (it is an API answer, not a display), so the UI defangs it here.
// Idempotent: defanging twice changes nothing. Mirrors services/c2-.../utils/defang.py.

const SCHEMES = { http: 'hxxp', https: 'hxxps', ftp: 'fxp', ftps: 'fxps' }
const URL_IN_TEXT = /\b([a-z][a-z0-9+.-]*):\/\/([^\s/?#"'<>\\]+)/gi
// A bare domain: labels + an alphabetic ending. Endings are checked below so that rule ids
// (behavior.clickfix) and file names (config.yaml) stay readable.
const DOMAIN_IN_TEXT = /(?<![\w.[@/-])((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+([a-z][a-z0-9-]{1,62}))(?![\w[-])/gi
const COMMON_TLDS = new Set(
  ('com net org info biz xyz top site online shop store app dev io co me live click link club icu vip cc tk ml ga cf gq ' +
    'pw buzz guru ai win bid loan work website space tech fun pro mobi asia cloud email services support help ' +
    'finance money bank cash exchange trade crypto best today world life net lk invalid example test local onion').split(' '),
)

function looksLikeDomain(tld) {
  const ending = tld.toLowerCase()
  return COMMON_TLDS.has(ending) || /^[a-z]{2}$/.test(ending) || ending.startsWith('xn--')
}

export function defangHost(host) {
  if (!host) return host
  return String(host).replaceAll('[.]', '.').replaceAll('.', '[.]')
}

export function defangText(text) {
  if (text === null || text === undefined || text === '') return text
  return String(text)
    .replace(URL_IN_TEXT, (_, scheme, host) => `${SCHEMES[scheme.toLowerCase()] || scheme}://${defangHost(host)}`)
    .replace(DOMAIN_IN_TEXT, (match, domain, tld) => (looksLikeDomain(tld) ? defangHost(domain) : match))
}

export function defangUrl(url) {
  if (!url) return url
  const text = String(url).trim()
  const match = /^(https?):\/\/([^/?#]*)(.*)$/i.exec(text)
  if (!match) return defangText(text)
  const [, scheme, host, rest] = match
  return `${SCHEMES[scheme.toLowerCase()]}://${defangHost(host)}${rest}`
}

// Mirrors utils/defang.py::defang_analysis: text fields defanged, URLs defanged, ids kept.
const TEXT_KEYS = new Set(['title', 'detail', 'evidence', 'summary', 'text', 'status_reason', 'code', 'note', 'example', 'reason'])
const URL_KEYS = new Set(['submitted_url', 'final_url', 'url'])
const TEXT_LIST_KEYS = new Set(['top_evidence', 'warnings', 'cues'])

/** A deep copy of an AnalysisResponse that is safe to save / share (used by "Export JSON"). */
export function defangAnalysis(value, key = null) {
  if (Array.isArray(value)) {
    if (key === 'redirect_hosts') return value.map((item) => (typeof item === 'string' ? defangHost(item) : item))
    if (TEXT_LIST_KEYS.has(key)) return value.map((item) => (typeof item === 'string' ? defangText(item) : item))
    return value.map((item) => defangAnalysis(item))
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([name, item]) => [name, defangAnalysis(item, name)]))
  }
  if (typeof value === 'string') {
    if (URL_KEYS.has(key)) return defangUrl(value)
    if (TEXT_KEYS.has(key)) return defangText(value)
  }
  return value
}
