import { defangText, defangUrl } from '../api/defang.js'
import { ARM_LABELS, CLASSES, CLASS_LABELS, LANGUAGE_LABELS, SEVERITY_STYLE, formatTime, num, pct } from '../constants.js'
import { STAGE_BY_ID, stageCaption, stageOutcome } from '../flow/flowModel.js'
import { NOVELTIES, n1Evidence, n2Evidence, n3Evidence } from '../flow/novelty.js'
import EvidenceChain from './EvidenceChain.jsx'
import FindingList from './FindingList.jsx'
import { ArmContributions, ProbabilityBars } from './ProbabilityBars.jsx'
import { Chip } from './ui.jsx'

// Full-detail popup bodies. Everything is rendered as React text; scan values go through
// defangText / defangUrl, and nothing derived from scan data is a link.

export function Section({ title, children }) {
  return (
    <section className="mb-5 last:mb-0">
      <h3 className="mb-2 font-mono text-xs font-semibold uppercase tracking-[0.14em] text-[color:var(--c2-accent)]">{title}</h3>
      {children}
    </section>
  )
}

export function Muted({ children }) {
  return <p className="text-sm text-[color:var(--c2-fg-muted)]">{children}</p>
}

function KeyValues({ rows }) {
  const shown = rows.filter(([, value]) => value !== null && value !== undefined && value !== '')
  if (!shown.length) return <Muted>Nothing recorded.</Muted>
  return (
    <dl className="grid grid-cols-[minmax(8rem,max-content)_1fr] gap-x-4 gap-y-1 text-sm">
      {shown.map(([key, value]) => (
        <div key={key} className="contents">
          <dt className="text-[color:var(--c2-fg-muted)]">{key}</dt>
          <dd className="min-w-0 break-words font-mono text-xs leading-5 text-[color:var(--c2-fg-hi)]">{typeof value === 'string' ? defangText(value) : value}</dd>
        </div>
      ))}
    </dl>
  )
}

function Timings({ result, keys }) {
  const timings = result.timings_ms || {}
  const rows = (keys || Object.keys(timings)).filter((key) => key in timings)
  if (!rows.length) return <Muted>No timing recorded (the step did not run).</Muted>
  return <KeyValues rows={rows.map((key) => [key, `${Number(timings[key]).toFixed(1)} ms`])} />
}

/** Every model arm with its full 5-class distribution and the fusion weight used. */
export function ArmsTable({ arms }) {
  if (!arms?.length) return <Muted>No model arm for this modality.</Muted>
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[40rem] text-left text-xs">
        <thead className="text-[color:var(--c2-fg-muted)]">
          <tr>
            <th className="py-1 pr-3 font-medium">Arm</th>
            <th className="py-1 pr-3 font-medium">Status</th>
            <th className="py-1 pr-3 font-medium">Predicted</th>
            {CLASSES.map((name) => (
              <th key={name} className="py-1 pr-3 text-right font-medium">
                {CLASS_LABELS[name]}
              </th>
            ))}
            <th className="py-1 text-right font-medium">Weight</th>
          </tr>
        </thead>
        <tbody className="font-mono text-[color:var(--c2-fg-hi)]">
          {arms.map((arm) => (
            <tr key={arm.arm} className="border-t border-[color:var(--c2-border)]">
              <td className="py-1.5 pr-3 font-sans">{arm.display || ARM_LABELS[arm.arm] || arm.arm}</td>
              <td className="py-1.5 pr-3">
                {arm.status}
                {arm.reason ? <span className="block font-sans text-[color:var(--c2-fg-muted)]">{defangText(arm.reason)}</span> : null}
              </td>
              <td className="py-1.5 pr-3">{arm.predicted ? CLASS_LABELS[arm.predicted] || arm.predicted : '—'}</td>
              {CLASSES.map((name) => (
                <td key={name} className={`py-1.5 pr-3 text-right ${name === arm.predicted ? 'font-semibold text-[color:var(--c2-fg-strong)]' : ''}`}>
                  {pct(arm.probabilities?.[name], 1)}
                </td>
              ))}
              <td className="py-1.5 text-right">{num(arm.fusion_weight, 2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SeverityTag({ severity }) {
  if (!severity) return null
  return <span className={`rounded px-1.5 py-0.5 font-mono text-[0.625rem] font-semibold uppercase ring-1 ${SEVERITY_STYLE[severity] || SEVERITY_STYLE.info}`}>{severity}</span>
}

export function IntentList({ intents, empty }) {
  if (!intents?.length) return <Muted>{empty}</Muted>
  return (
    <ul className="flex flex-col gap-2">
      {intents.map((item) => (
        <li key={item.intent} className="rounded-lg border border-[color:var(--c2-border)] bg-[color:var(--c2-inset)] p-2.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-[color:var(--c2-fg-strong)]">{defangText(item.display || item.intent)}</span>
            <span className="font-mono text-[0.6875rem] text-[color:var(--c2-fg-muted)]">{item.intent}</span>
            <SeverityTag severity={item.severity} />
            {item.count ? <Chip>{item.count}×</Chip> : null}
          </div>
          {item.cues?.length > 0 && (
            <p className="mt-1 text-xs text-[color:var(--c2-fg-2)]">
              Cue words: <span className="font-mono text-[color:var(--c2-sus-ink)]">{item.cues.map((cue) => defangText(cue)).join(' · ')}</span>
            </p>
          )}
          {item.example && <p className="mt-1 break-words text-sm text-[color:var(--c2-fg-2)]">“{defangText(item.example)}”</p>}
        </li>
      ))}
    </ul>
  )
}

function StatsGrid({ stats, labels }) {
  if (!stats) return null
  return (
    <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {Object.entries(labels).map(([key, label]) =>
        stats[key] === undefined ? null : (
          <li key={key} className="rounded-lg bg-[color:var(--c2-inset)] px-3 py-2 ring-1 ring-[color:var(--c2-border)]">
            <span className="block font-mono text-lg font-semibold text-[color:var(--c2-fg-strong)]">
              {key.endsWith('_ratio') || key === 'language_confidence' ? pct(stats[key], 0) : stats[key]}
            </span>
            <span className="block text-xs text-[color:var(--c2-fg-muted)]">{label}</span>
          </li>
        ),
      )}
    </ul>
  )
}

const BEHAVIOR_STAT_LABELS = {
  scripts_analyzed: 'scripts (AST)',
  scripts_lexical: 'scripts (lexical)',
  library_scripts_skipped: 'libraries skipped',
  sources_total: 'sensitive sources',
  sinks_total: 'sinks',
  flows_total: 'source → sink flows',
  flows_external: 'external flows',
  behavior_risk_score: 'behavior risk (0–100)',
}
const CONTENT_STAT_LABELS = {
  segments: 'text segments',
  page_text_chars: 'chars to the models',
  language_confidence: 'language confidence',
  si_script_ratio: 'Sinhala script',
  ta_script_ratio: 'Tamil script',
  latin_script_ratio: 'Latin script',
}

/** One modality in full: status, summary, every arm, intents + counters, its findings. */
export function ModalityDetail({ name, result }) {
  const modality = result.modalities?.[name]
  if (!modality) return <Muted>This modality is not in the response.</Muted>
  const findings = (result.findings || []).filter((finding) => finding.modality === name)
  return (
    <>
      <Section title="Status">
        <KeyValues rows={[['status', modality.status], ['reason', modality.reason], ['summary', modality.summary]]} />
      </Section>
      {modality.stats && Object.keys(modality.stats).length > 0 && (
        <Section title="Counters">
          <StatsGrid stats={modality.stats} labels={name === 'behavior' ? BEHAVIOR_STAT_LABELS : CONTENT_STAT_LABELS} />
        </Section>
      )}
      {Array.isArray(modality.intents) && name !== 'dom' && (
        <Section title={name === 'behavior' ? 'Behavioral intents (N1)' : 'Cue-based intents — preliminary (N2)'}>
          <IntentList intents={modality.intents} empty="No intent evidence on this page." />
          {modality.intent_method && <p className="mt-2 text-xs text-[color:var(--c2-fg-muted)]">Method: {modality.intent_method}</p>}
        </Section>
      )}
      <Section title="Top evidence">
        {modality.top_evidence?.length ? (
          <ul className="flex list-disc flex-col gap-1 pl-5 text-sm text-[color:var(--c2-fg)]">
            {modality.top_evidence.map((item, index) => (
              <li key={index} className="break-words">
                {defangText(item)}
              </li>
            ))}
          </ul>
        ) : (
          <Muted>No evidence item for this modality.</Muted>
        )}
      </Section>
      <Section title="Model arms (full class distribution)">
        <ArmsTable arms={modality.arms} />
      </Section>
      <Section title={`Findings of this modality (${findings.length})`}>
        <FindingList findings={findings} />
      </Section>
    </>
  )
}

/** Fusion in full: fused probabilities, arm contributions, all top features, tier cut-offs. */
export function FusionDetail({ result }) {
  const explanation = result.explanation || {}
  const thresholds = explanation.thresholds || {}
  return (
    <>
      <Section title="Fused class probabilities (5 classes)">
        <ProbabilityBars probabilities={result.class_probabilities} highlight={explanation.explained_class} />
      </Section>
      <Section title="Per-arm contribution to the explained class">
        <ArmContributions explanation={explanation} modalities={result.modalities} />
      </Section>
      <Section title="How the verdict was decided">
        <KeyValues
          rows={[
            ['method', explanation.method],
            ['explained class', explanation.explained_class && (CLASS_LABELS[explanation.explained_class] || explanation.explained_class)],
            ['driving arm', explanation.driving_arm && (ARM_LABELS[explanation.driving_arm] || explanation.driving_arm)],
            ['arms used', (explanation.arms_used || []).map((arm) => ARM_LABELS[arm] || arm).join(', ')],
            ['verdict source', explanation.verdict_source],
            ['evidence floor rules', (explanation.evidence_floor_rules || []).join(', ') || 'none'],
            ['degraded', result.degraded ? 'yes — a modality failed, weights renormalized' : 'no'],
            ['threshold set', thresholds.arms],
            ['Malicious if P(benign) <', num(thresholds.malicious_below_p_benign, 4)],
            ['Suspicious if P(benign) <', num(thresholds.suspicious_below_p_benign, 4)],
            ['Malicious from risk', thresholds.malicious_min_risk],
            ['Suspicious from risk', thresholds.suspicious_min_risk],
          ]}
        />
      </Section>
      <Section title={`Top input features (${(explanation.top_features || []).length})`}>
        {explanation.top_features?.length ? (
          <ul className="flex flex-col gap-1">
            {explanation.top_features.map((feature, index) => (
              <li key={index} className="grid grid-cols-[6rem_1fr_4.5rem] gap-2 text-xs">
                <span className="font-mono text-[color:var(--c2-fg-muted)]">[{ARM_LABELS[feature.arm] || feature.arm}]</span>
                <span className="break-words text-[color:var(--c2-fg)]">{defangText(feature.text)}</span>
                <span className="text-right font-mono text-[color:var(--c2-fg-hi)]">{num(feature.contribution, 3)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <Muted>No feature-level explanation in this response.</Muted>
        )}
      </Section>
    </>
  )
}

export function VerdictDetail({ result }) {
  return (
    <>
      <Section title="Verdict">
        <KeyValues
          rows={[
            ['verdict', result.verdict || `none (${result.status})`],
            ['threat class', result.threat_class && (CLASS_LABELS[result.threat_class] || result.threat_class)],
            ['risk score', result.risk_score !== null && result.risk_score !== undefined ? `${result.risk_score} / 100` : null],
            ['status', result.status],
            ['status reason', result.status_reason],
            ['page language', result.page_language && (LANGUAGE_LABELS[result.page_language] || result.page_language)],
            ['verdict source', result.explanation?.verdict_source],
            ['evidence floor rules', (result.explanation?.evidence_floor_rules || []).join(', ') || 'none'],
          ]}
        />
      </Section>
      <Section title="Input">
        <KeyValues
          rows={[
            ['mode', result.input?.mode],
            ['submitted URL', defangUrl(result.input?.submitted_url)],
            ['final URL', defangUrl(result.input?.final_url)],
            ['redirect hosts', result.input?.redirect_hosts?.join(' → ')],
            ['HTTP status', result.input?.http_status],
            ['content type', result.input?.content_type],
            ['cached', result.cached ? 'yes' : 'no'],
          ]}
        />
      </Section>
      {result.warnings?.length > 0 && (
        <Section title="Warnings">
          <ul className="flex list-disc flex-col gap-1 pl-5 text-sm text-[color:var(--c2-sus-ink)]">
            {result.warnings.map((warning, index) => (
              <li key={index}>{defangText(warning)}</li>
            ))}
          </ul>
        </Section>
      )}
      <Section title="Timings">
        <Timings result={result} />
      </Section>
      <Section title="Versions">
        <KeyValues
          rows={[
            ['analysis id', result.analysis_id],
            ['analyzed at', formatTime(result.analyzed_at)],
            ['schema', result.schema_version],
            ...Object.entries(result.model_versions || {}).map(([key, value]) => [key, value || '—']),
          ]}
        />
      </Section>
    </>
  )
}

export function FindingsDetail({ result }) {
  return <FindingList findings={result.findings} total={result.findings_total} omitted={result.findings_omitted} />
}

const STAGE_MODALITY = { dom: 'dom', content: 'content', text: 'content', js: 'behavior', behavior: 'behavior' }

/** A pipeline stage in full: outcome, what it did on this page, its timings, its output. */
export function StageDetail({ stageId, result }) {
  const stage = STAGE_BY_ID[stageId]
  const outcome = stageOutcome(stage, result)
  return (
    <>
      <Section title="On this page">
        <ul className="flex flex-col gap-1 text-sm text-[color:var(--c2-fg)]">
          {stageCaption(stageId, result).map((line, index) => (
            <li key={index} className="break-words">
              {line}
            </li>
          ))}
        </ul>
      </Section>
      <Section title="Outcome">
        <KeyValues rows={[['status', outcome.state], ['note', outcome.note !== stage.desc ? outcome.note : null], ['what it does', stage.desc]]} />
      </Section>
      {stage.keys.length > 0 && (
        <Section title="Timings">
          <Timings result={result} keys={stage.keys} />
        </Section>
      )}
      {STAGE_MODALITY[stageId] && <ModalityDetail name={STAGE_MODALITY[stageId]} result={result} />}
      {stageId === 'fusion' && <FusionDetail result={result} />}
      {(stageId === 'verdict' || stageId === 'input' || stageId === 'fetch') && <VerdictDetail result={result} />}
    </>
  )
}

export function N1Detail({ result }) {
  const evidence = n1Evidence(result)
  return (
    <>
      <p className="mb-4 text-sm text-[color:var(--c2-fg-2)]">{NOVELTIES.N1.claim}</p>
      {!evidence.ran && <Muted>The behavior modality did not run on this page ({evidence.status || 'not in response'}{evidence.reason ? `: ${evidence.reason}` : ''}).</Muted>}
      {evidence.stats && (
        <Section title="Static analysis counters">
          <StatsGrid stats={evidence.stats} labels={BEHAVIOR_STAT_LABELS} />
        </Section>
      )}
      <Section title="Behavioral intents found">
        <IntentList intents={evidence.intents} empty="No evidence for this page: no behavioral intent pattern was found in the page's own scripts." />
        {evidence.provenance && <p className="mt-2 text-xs text-[color:var(--c2-fg-muted)]">Source: {evidence.provenance}</p>}
      </Section>
      <Section title={`Source → sink evidence chains (${evidence.chains.length})`}>
        {evidence.chains.length ? (
          evidence.chains.map((chain, index) => (
            <div key={index} className="mb-3">
              <p className="text-sm font-semibold text-[color:var(--c2-fg-strong)]">{defangText(chain.title)}</p>
              <EvidenceChain steps={chain.steps} />
            </div>
          ))
        ) : (
          <Muted>No evidence chain recorded for this page.</Muted>
        )}
      </Section>
      <Section title="Behavior-only model arm">
        <ArmsTable arms={evidence.arm ? [evidence.arm] : []} />
      </Section>
    </>
  )
}

export function N2Detail({ result }) {
  const evidence = n2Evidence(result)
  return (
    <>
      <p className="mb-2 text-sm text-[color:var(--c2-fg-2)]">{NOVELTIES.N2.claim}</p>
      <p className="mb-4 rounded-md bg-[color:var(--c2-sus-tint)] px-2 py-1 text-xs text-[color:var(--c2-sus-ink)] ring-1 ring-[color:var(--c2-sus-ring-soft)]">
        Status: {NOVELTIES.N2.status}. Cue words only suggest an intent — a benign page can match one (e.g. a news story naming the police).
      </p>
      {!evidence.ran && <Muted>The content modality did not run on this page ({evidence.status || 'not in response'}{evidence.reason ? `: ${evidence.reason}` : ''}).</Muted>}
      <Section title="Language">
        <KeyValues
          rows={[
            ['page language', evidence.language && (LANGUAGE_LABELS[evidence.language] || evidence.language)],
            ['confidence', evidence.confidence !== undefined ? pct(evidence.confidence, 0) : null],
          ]}
        />
        {evidence.stats && (
          <div className="mt-2">
            <StatsGrid stats={evidence.stats} labels={CONTENT_STAT_LABELS} />
          </div>
        )}
      </Section>
      <Section title="Page-level text classes (XLM-R + TF-IDF)">
        <ArmsTable arms={[evidence.xlmr, evidence.tfidf].filter(Boolean)} />
      </Section>
      <Section title="Cue-based social-engineering intents (preliminary)">
        <IntentList intents={evidence.intents} empty="No evidence for this page: no cue word of the intent taxonomy matched the visible text." />
        {evidence.provenance && <p className="mt-2 text-xs text-[color:var(--c2-fg-muted)]">Source: {evidence.provenance}</p>}
      </Section>
      <Section title={`Content findings (${evidence.textFindings.length})`}>
        <FindingList findings={evidence.textFindings} />
      </Section>
    </>
  )
}

export function N3Detail({ result }) {
  const evidence = n3Evidence(result)
  if (!evidence.hasEvidence) return <Muted>No evidence for this page: no modality ran, so nothing was fused ({result.status}).</Muted>
  return (
    <>
      <p className="mb-4 text-sm text-[color:var(--c2-fg-2)]">{NOVELTIES.N3.claim}</p>
      <Section title="Share of each modality in the explained class">
        <ul className="flex flex-col gap-1 text-sm">
          {Object.entries(evidence.byModality).map(([name, value]) => (
            <li key={name} className="grid grid-cols-[7rem_1fr_4rem] items-center gap-3">
              <span className="text-[color:var(--c2-fg-2)]">{name}</span>
              <span className="h-2.5 overflow-hidden rounded-full bg-[color:var(--c2-track)]" aria-hidden="true">
                <span className="block h-full rounded-full bg-[color:var(--c2-accent-solid)]" style={{ width: `${evidence.totalShare ? (value / evidence.totalShare) * 100 : 0}%` }} />
              </span>
              <span className="text-right font-mono text-xs">{evidence.totalShare ? pct(value / evidence.totalShare, 0) : '—'}</span>
            </li>
          ))}
        </ul>
      </Section>
      <FusionDetail result={result} />
    </>
  )
}
