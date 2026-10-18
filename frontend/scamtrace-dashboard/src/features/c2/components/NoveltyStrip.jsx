import { Code2, Languages, Layers } from 'lucide-react'
import { defangText } from '../api/defang.js'
import { ARM_LABELS, CLASS_LABELS, LANGUAGE_LABELS, SEVERITY_STYLE, pct } from '../constants.js'
import { NOVELTIES, n1Evidence, n2Evidence, n3Evidence } from '../flow/novelty.js'
import { ExpandButton } from './DetailDialog.jsx'
import { N1Detail, N2Detail, N3Detail } from './SectionDetails.jsx'
import { Chip } from './ui.jsx'

function NoEvidence({ children }) {
  return (
    <p className="rounded-lg border border-dashed border-[color:var(--c2-border-strong)] px-3 py-2 text-sm text-[color:var(--c2-fg-muted)]">
      <span className="font-semibold text-[color:var(--c2-fg-2)]">No evidence for this page.</span> {children}
    </p>
  )
}

function Card({ novelty, icon: Icon, detail, children, stagesLabel }) {
  return (
    <article className="c2-panel flex flex-col gap-3 rounded-xl border border-[color:var(--c2-border)] p-4">
      <header className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[color:var(--c2-accent-tint)] text-[color:var(--c2-accent)] ring-1 ring-[color:var(--c2-accent-ring-soft)]">
            <Icon className="h-5 w-5" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="font-mono text-xs font-bold text-[color:var(--c2-accent)]">{novelty.id}</p>
            <h3 className="text-[0.9375rem] font-semibold leading-snug text-[color:var(--c2-fg-strong)]">{novelty.title}</h3>
          </div>
        </div>
        <ExpandButton title={`${novelty.id} — ${novelty.title}`} subtitle={novelty.status || novelty.claim} render={detail} />
      </header>
      <p className="text-xs leading-relaxed text-[color:var(--c2-fg-2)]">{novelty.claim}</p>
      {novelty.status && (
        <p className="rounded-md bg-[color:var(--c2-sus-tint)] px-2 py-1 font-mono text-[0.6875rem] leading-snug text-[color:var(--c2-sus-ink)] ring-1 ring-[color:var(--c2-sus-ring-soft)]">{novelty.status}</p>
      )}
      <div className="border-t border-[color:var(--c2-border)] pt-3">
        <p className="mb-2 font-mono text-[0.6875rem] uppercase tracking-wider text-[color:var(--c2-fg-muted)]">Produced for this page · {stagesLabel}</p>
        <div className="flex flex-col gap-2">{children}</div>
      </div>
    </article>
  )
}

function Stat({ value, label }) {
  return (
    <span className="flex flex-col rounded-lg bg-[color:var(--c2-inset)] px-2.5 py-1.5 ring-1 ring-[color:var(--c2-border)]">
      <span className="font-mono text-sm font-semibold text-[color:var(--c2-fg-strong)]">{value}</span>
      <span className="text-[0.6875rem] text-[color:var(--c2-fg-muted)]">{label}</span>
    </span>
  )
}

function N1Card({ result }) {
  const evidence = n1Evidence(result)
  return (
    <Card novelty={NOVELTIES.N1} icon={Code2} detail={() => <N1Detail result={result} />} stagesLabel="stages 6–7">
      {evidence.stats && (
        <div className="grid grid-cols-3 gap-2">
          <Stat value={evidence.stats.scripts_analyzed} label="scripts (AST)" />
          <Stat value={evidence.stats.flows_total} label="source → sink" />
          <Stat value={evidence.stats.flows_external} label="external flows" />
        </div>
      )}
      {!evidence.ran ? (
        <NoEvidence>The behavior modality did not run ({evidence.status || 'no page'}).</NoEvidence>
      ) : evidence.hasEvidence ? (
        <ul className="flex flex-col gap-1.5">
          {evidence.intents.slice(0, 3).map((item) => (
            <li key={item.intent} className="flex items-start gap-2 text-sm">
              <span className={`mt-0.5 rounded px-1.5 py-0.5 font-mono text-[0.625rem] font-semibold uppercase ring-1 ${SEVERITY_STYLE[item.severity] || SEVERITY_STYLE.info}`}>{item.severity || 'info'}</span>
              <span className="min-w-0">
                <span className="font-semibold text-[color:var(--c2-fg-strong)]">{defangText(item.display || item.intent)}</span>
                {item.example && <span className="line-clamp-2 block text-xs text-[color:var(--c2-fg-2)]">{defangText(item.example)}</span>}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <NoEvidence>No behavioral intent pattern in the page's own scripts.</NoEvidence>
      )}
      {evidence.chains.length > 0 && <p className="text-xs text-[color:var(--c2-fg-muted)]">{evidence.chains.length} evidence chain(s) — open Details to follow source → sink.</p>}
    </Card>
  )
}

function N2Card({ result }) {
  const evidence = n2Evidence(result)
  const vote = (arm) => (arm?.status === 'ok' ? `${CLASS_LABELS[arm.predicted] || arm.predicted} ${pct(arm.probabilities?.[arm.predicted], 0)}` : arm ? arm.status : '—')
  return (
    <Card novelty={NOVELTIES.N2} icon={Languages} detail={() => <N2Detail result={result} />} stagesLabel="stages 4–5">
      {!evidence.ran ? (
        <NoEvidence>The content modality did not run ({evidence.status || 'no page'}).</NoEvidence>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2">
            <Stat value={evidence.language ? LANGUAGE_LABELS[evidence.language] || evidence.language : '—'} label={`page language${evidence.confidence !== undefined ? ` · ${pct(evidence.confidence, 0)}` : ''}`} />
            <Stat value={vote(evidence.xlmr)} label="XLM-R page class" />
          </div>
          {evidence.intents.length ? (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-[color:var(--c2-fg-muted)]">Cue intents (preliminary):</span>
              {evidence.intents.map((item) => (
                <Chip key={item.intent} tone="amber" title={item.cues?.length ? `cues: ${item.cues.map((cue) => defangText(cue)).join(', ')}` : undefined}>
                  {defangText(item.display || item.intent)}
                  {item.count ? ` ×${item.count}` : ''}
                </Chip>
              ))}
            </div>
          ) : (
            <NoEvidence>No cue word of the intent taxonomy matched the visible text.</NoEvidence>
          )}
        </>
      )}
    </Card>
  )
}

function N3Card({ result }) {
  const evidence = n3Evidence(result)
  const top = Object.entries(evidence.probabilities).sort((a, b) => b[1] - a[1])
  return (
    <Card novelty={NOVELTIES.N3} icon={Layers} detail={() => <N3Detail result={result} />} stagesLabel="stage 8 → verdict">
      {!evidence.hasEvidence ? (
        <NoEvidence>No modality ran, so nothing was fused ({result.status}).</NoEvidence>
      ) : (
        <>
          <ul className="flex flex-col gap-1" aria-label="Five-class fused probabilities">
            {top.map(([name, value]) => (
              <li key={name} className="grid grid-cols-[7.5rem_1fr_3rem] items-center gap-2 text-xs">
                <span className={name === evidence.explainedClass ? 'font-semibold text-[color:var(--c2-fg-strong)]' : 'text-[color:var(--c2-fg-2)]'}>{CLASS_LABELS[name] || name}</span>
                <span className="h-2 overflow-hidden rounded-full bg-[color:var(--c2-track)]" aria-hidden="true">
                  <span className={`block h-full rounded-full ${name === 'benign' ? 'bg-[color:var(--c2-ok-solid)]' : name === evidence.explainedClass ? 'bg-[color:var(--c2-mal-solid)]' : 'bg-[color:var(--c2-accent-70)]'}`} style={{ width: `${value * 100}%` }} />
                </span>
                <span className="text-right font-mono">{pct(value, 0)}</span>
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(evidence.byModality).map(([name, value]) => (
              <Chip key={name} tone="cyan">
                {name} {evidence.totalShare ? pct(value / evidence.totalShare, 0) : '—'}
              </Chip>
            ))}
            {evidence.drivingArm && <Chip>driver: {ARM_LABELS[evidence.drivingArm] || evidence.drivingArm}</Chip>}
            {evidence.degraded && <Chip tone="amber">degraded</Chip>}
          </div>
        </>
      )}
    </Card>
  )
}

/** The three thesis novelties, each with what it produced for THIS page (or "no evidence"). */
export default function NoveltyStrip({ result }) {
  return (
    <section aria-label="Research novelties" className="grid gap-4 lg:grid-cols-3">
      <N1Card result={result} />
      <N2Card result={result} />
      <N3Card result={result} />
    </section>
  )
}
