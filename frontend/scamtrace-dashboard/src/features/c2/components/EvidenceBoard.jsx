import { Code2, Download, Languages, LayoutTemplate, Layers, ShieldAlert } from 'lucide-react'
import { defangAnalysis, defangText } from '../api/defang.js'
import { ARM_LABELS, CLASS_LABELS, SEVERITY_RANK, SEVERITY_STYLE, pct } from '../constants.js'
import { ExpandButton } from './DetailDialog.jsx'
import { FindingsDetail, ModalityDetail } from './SectionDetails.jsx'
import { Chip, Panel } from './ui.jsx'

const EVIDENCE_BOARD_TITLE = 'Cross-Modal Explainable Threat Evidence'

const COLUMNS = [
  { name: 'dom', lane: 'Structure', title: 'DOM structure', icon: LayoutTemplate },
  { name: 'content', lane: 'Content', title: 'Content & language', icon: Languages, novelty: 'N2' },
  { name: 'behavior', lane: 'Behavior', title: 'JS behavior', icon: Code2, novelty: 'N1' },
]
const STATUS_TONE = { ok: 'green', failed: 'red', skipped: 'slate' }
const INTENT_TONE = { critical: 'red', high: 'red', medium: 'amber' }

const bySeverity = (a, b) => (SEVERITY_RANK[b.severity] ?? 0) - (SEVERITY_RANK[a.severity] ?? 0)

function EvidenceItem({ finding }) {
  return (
    <li className="rounded-lg border border-[color:var(--c2-border)] bg-[color:var(--c2-inset)] p-2.5">
      <div className="flex items-start gap-2">
        <span className={`mt-0.5 shrink-0 rounded px-1.5 py-0.5 font-mono text-[0.625rem] font-semibold uppercase ring-1 ${SEVERITY_STYLE[finding.severity] || SEVERITY_STYLE.info}`}>{finding.severity}</span>
        <p className="min-w-0 text-sm font-medium text-[color:var(--c2-fg-strong)]">
          {defangText(finding.title)}
          {finding.raises_verdict && (
            <span className="ml-1.5 inline-flex items-center gap-0.5 font-mono text-[0.625rem] font-normal text-[color:var(--c2-mal-hi)]">
              <ShieldAlert className="h-3 w-3" aria-hidden="true" /> floor
            </span>
          )}
        </p>
      </div>
      {finding.evidence && (
        <code className="mt-1.5 block overflow-x-auto whitespace-pre rounded bg-[color:var(--c2-code-bg)] px-2 py-1 font-mono text-[0.6875rem] text-[color:var(--c2-sus-ink)]">{defangText(finding.evidence)}</code>
      )}
    </li>
  )
}

function armVote(arm) {
  if (!arm) return null
  const name = arm.display || ARM_LABELS[arm.arm] || arm.arm
  if (arm.status !== 'ok') return { name, text: arm.status, predicted: null }
  return { name, text: `${CLASS_LABELS[arm.predicted] || arm.predicted} ${pct(arm.probabilities?.[arm.predicted], 0)}`, predicted: arm.predicted }
}

function Column({ column, result }) {
  const modality = result.modalities?.[column.name]
  const Icon = column.icon
  const findings = (result.findings || []).filter((finding) => finding.modality === column.name).sort(bySeverity)
  const shownEvidence = new Set(findings.flatMap((finding) => [finding.title, finding.evidence, finding.detail]))
  const extra = (modality?.top_evidence || []).filter((item) => !shownEvidence.has(item))
  const intents = Array.isArray(modality?.intents) ? modality.intents : []
  return (
    <div className="flex min-w-0 flex-col gap-3 rounded-xl border border-[color:var(--c2-border)] p-3">
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-mono text-[0.6875rem] font-semibold uppercase tracking-[0.14em] text-[color:var(--c2-fg-muted)]">
            {column.lane}
            {column.novelty && <span className="ml-1.5 rounded bg-[color:var(--c2-accent-tint-2)] px-1 py-0.5 text-[0.625rem] text-[color:var(--c2-accent-hi)]">{column.novelty}</span>}
          </p>
          <h3 className="flex items-center gap-1.5 font-semibold text-[color:var(--c2-fg-strong)]">
            <Icon className="h-4 w-4 text-[color:var(--c2-accent)]" aria-hidden="true" /> {column.title}
          </h3>
        </div>
        <div className="flex items-center gap-1.5">
          {modality && <Chip tone={STATUS_TONE[modality.status] || 'slate'}>{modality.status}</Chip>}
          <ExpandButton title={`${column.lane} — ${column.title}`} subtitle="All evidence of this modality" render={() => <ModalityDetail name={column.name} result={result} />} />
        </div>
      </header>
      {!modality || modality.status !== 'ok' ? (
        <p className="text-sm text-[color:var(--c2-fg-muted)]">
          No evidence: this modality {modality ? `was ${modality.status}` : 'is not in the response'}
          {modality?.reason ? ` (${defangText(modality.reason)})` : ''}.
        </p>
      ) : (
        <>
          <ul className="flex flex-col gap-1">
            {(modality.arms || []).map((arm) => {
              const vote = armVote(arm)
              return (
                <li key={arm.arm} className="flex items-center justify-between gap-2 text-xs">
                  <span className="text-[color:var(--c2-fg-2)]">{vote.name}</span>
                  <span className={`font-mono ${vote.predicted && vote.predicted !== 'benign' ? 'text-[color:var(--c2-mal-hi)]' : 'text-[color:var(--c2-fg)]'}`}>{vote.text}</span>
                </li>
              )
            })}
          </ul>
          {intents.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {intents.map((item) => (
                <Chip key={item.intent} tone={item.method === 'cue_words' ? 'amber' : INTENT_TONE[item.severity] || 'slate'}>
                  {item.method === 'cue_words' ? 'cue: ' : 'intent: '}
                  {defangText(item.display || item.intent)}
                </Chip>
              ))}
            </div>
          )}
          {findings.length > 0 ? (
            <ul className="flex flex-col gap-2">
              {findings.map((finding, index) => (
                <EvidenceItem key={`${finding.id}-${index}`} finding={finding} />
              ))}
            </ul>
          ) : (
            <p className="text-sm text-[color:var(--c2-fg-muted)]">No finding from this modality.</p>
          )}
          {extra.length > 0 && (
            <ul className="flex flex-col gap-1 border-t border-[color:var(--c2-border)] pt-2">
              {extra.map((item, index) => (
                <li key={index} className="flex gap-2 text-xs text-[color:var(--c2-fg)]">
                  <span className="text-[color:var(--c2-accent-icon)]" aria-hidden="true">›</span>
                  <span className="min-w-0 break-words">{defangText(item)}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}

/** How many model arms (across the three modalities) agree with the explained class. */
function agreement(result) {
  const arms = ['dom', 'content', 'behavior'].flatMap((name) => result.modalities?.[name]?.arms || []).filter((arm) => arm.status === 'ok')
  const target = result.explanation?.explained_class || result.threat_class
  if (!arms.length || !target) return null
  return { agree: arms.filter((arm) => arm.predicted === target).length, total: arms.length, target }
}

function exportJson(result) {
  const safe = defangAnalysis(result)
  const blob = new Blob([`${JSON.stringify(safe, null, 2)}\n`], { type: 'application/json' })
  const href = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = href
  anchor.download = `c2-analysis-${String(result.analysis_id || 'result').replace(/[^\w-]/g, '_')}.json`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  setTimeout(() => URL.revokeObjectURL(href), 1000)
}

/** One place for the evidence of all three modalities, plus fetch / fusion evidence and a JSON export. */
export default function EvidenceBoard({ result }) {
  const others = (result.findings || []).filter((finding) => !['dom', 'content', 'behavior'].includes(finding.modality)).sort(bySeverity)
  const floor = result.explanation?.evidence_floor_rules || []
  const agree = agreement(result)
  return (
    <Panel
      title={EVIDENCE_BOARD_TITLE}
      icon={Layers}
      actions={
        <div className="flex items-center gap-2">
          <ExpandButton title="All findings" subtitle="Every finding C2 returned, by severity" render={() => <FindingsDetail result={result} />} label="All findings" />
          <button
            type="button"
            onClick={() => exportJson(result)}
            className="inline-flex items-center gap-1.5 rounded-md bg-[color:var(--c2-accent-solid)] px-2.5 py-1 text-xs font-semibold text-[color:var(--c2-on-accent)] hover:bg-[color:var(--c2-accent-solid-hover)]"
            title="Download the full analysis as JSON (URLs defanged)"
          >
            <Download className="h-3.5 w-3.5" aria-hidden="true" /> Export JSON
          </button>
        </div>
      }
    >
      <p className="mb-3 text-sm text-[color:var(--c2-fg-2)]">
        Evidence from the three modalities side by side — what the page <em>looks like</em> (structure), <em>says</em> (content) and <em>does</em> (behavior).
        {agree && (
          <span className="ml-1 font-medium text-[color:var(--c2-fg-strong)]">
            {agree.agree} of {agree.total} model arms point to {CLASS_LABELS[agree.target] || agree.target}.
          </span>
        )}
      </p>
      <div className="grid gap-3 lg:grid-cols-3">
        {COLUMNS.map((column) => (
          <Column key={column.name} column={column} result={result} />
        ))}
      </div>
      {(others.length > 0 || floor.length > 0) && (
        <div className="mt-3 rounded-xl border border-[color:var(--c2-border)] p-3">
          <p className="mb-2 font-mono text-[0.6875rem] font-semibold uppercase tracking-[0.14em] text-[color:var(--c2-fg-muted)]">Fetch & fusion</p>
          {floor.length > 0 && (
            <p className="mb-2 text-xs text-[color:var(--c2-fg-2)]">
              Evidence-floor rules fired: <span className="font-mono text-[color:var(--c2-mal-hi)]">{floor.join(' · ')}</span>
            </p>
          )}
          <ul className="grid gap-2 md:grid-cols-2">
            {others.map((finding, index) => (
              <EvidenceItem key={`${finding.id}-${index}`} finding={finding} />
            ))}
          </ul>
        </div>
      )}
    </Panel>
  )
}
