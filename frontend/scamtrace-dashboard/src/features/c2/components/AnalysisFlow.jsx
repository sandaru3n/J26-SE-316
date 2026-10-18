import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { CheckCircle2, ChevronLeft, ChevronRight, CircleDashed, CircleSlash, Loader2, Maximize2, MinusCircle, Presentation, RotateCcw, XCircle } from 'lucide-react'
import { defangUrl } from '../api/defang.js'
import { CLASS_LABELS, VERDICT_STYLE } from '../constants.js'
import { EDGES, FLOW_STAGES, LANES, STATUS_LABEL, STAGE_BY_ID, allOutcomes, replaySchedule, stageCaption } from '../flow/flowModel.js'
import { NOVELTIES } from '../flow/novelty.js'
import { useDetailDialog } from '../hooks/useDetailDialog.js'
import { StageDetail } from './SectionDetails.jsx'

const REPLAY_MS = 5000 // whole replay ≈ 5 s, stage slots proportional to the real timings_ms
const LIVE_STEP_MS = 520 // while waiting: a highlight walks the stages (the API answers once, at the end)
const PRESENTER_KEY = 'c2.presenter'
const STAGE_IDS = FLOW_STAGES.map((stage) => stage.id)

function readPresenter() {
  try {
    return localStorage.getItem(PRESENTER_KEY) === '1'
  } catch {
    return false
  }
}

function usePrefersReducedMotion() {
  const query = '(prefers-reduced-motion: reduce)'
  const [reduced, setReduced] = useState(() => typeof window !== 'undefined' && window.matchMedia?.(query).matches)
  useEffect(() => {
    const media = window.matchMedia?.(query)
    if (!media) return undefined
    const onChange = () => setReduced(media.matches)
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])
  return reduced
}

/**
 * Milliseconds since the timer (re)started: restarts when `key` changes, ticks by
 * requestAnimationFrame while `active`, stops by itself at `limit`.
 */
function useTimer(active, key, limit = Infinity) {
  const [value, setValue] = useState({ key: null, ms: 0 })
  useEffect(() => {
    if (!active) return undefined
    const start = performance.now()
    let frame = requestAnimationFrame(function tick(now) {
      const ms = Math.max(0, now - start)
      setValue({ key, ms })
      if (ms < limit) frame = requestAnimationFrame(tick)
    })
    return () => cancelAnimationFrame(frame)
  }, [active, key, limit])
  return value.key === key ? value.ms : 0
}

const STATE_STYLE = {
  ok: { icon: CheckCircle2, tone: 'text-[color:var(--c2-ok)]', pill: 'bg-[color:var(--c2-ok-tint)] text-[color:var(--c2-ok-hi)] ring-[color:var(--c2-ok-ring)]' },
  skipped: { icon: CircleSlash, tone: 'text-[color:var(--c2-fg-muted)]', pill: 'bg-[color:var(--c2-chip-bg)] text-[color:var(--c2-fg-2)] ring-[color:var(--c2-chip-ring)]' },
  failed: { icon: XCircle, tone: 'text-[color:var(--c2-sus)]', pill: 'bg-[color:var(--c2-sus-tint)] text-[color:var(--c2-sus-hi)] ring-[color:var(--c2-sus-ring)]' },
  notrun: { icon: MinusCircle, tone: 'text-[color:var(--c2-fg-faint)]', pill: 'bg-[color:var(--c2-chip-bg)] text-[color:var(--c2-fg-muted)] ring-[color:var(--c2-chip-ring)]' },
  running: { icon: Loader2, tone: 'text-[color:var(--c2-accent)]', pill: 'bg-[color:var(--c2-accent-tint)] text-[color:var(--c2-accent-hi)] ring-[color:var(--c2-accent-ring)]', spin: true },
  waiting: { icon: CircleDashed, tone: 'text-[color:var(--c2-fg-faint)]', pill: 'bg-[color:var(--c2-chip-bg)] text-[color:var(--c2-fg-muted)] ring-[color:var(--c2-chip-ring)]' },
}

function FlowNode({ stage, view, outcome, result, focused, dimmed, registerNode, onOpen }) {
  const style = STATE_STYLE[view] || STATE_STYLE.waiting
  const StatusIcon = style.icon
  const Icon = stage.icon
  const revealed = view !== 'waiting' && view !== 'running'
  const isVerdict = stage.id === 'verdict'
  const verdictStyle = isVerdict && revealed && result?.verdict ? VERDICT_STYLE[result.verdict] : null
  return (
    <button
      type="button"
      ref={(node) => registerNode(stage.id, node)}
      onClick={() => onOpen(stage.id)}
      disabled={!result}
      aria-label={`${stage.n ? `Stage ${stage.n}: ` : ''}${stage.title} — ${STATUS_LABEL[view]}${revealed && outcome?.ms !== null && outcome?.ms !== undefined ? `, ${outcome.ms.toFixed(1)} ms` : ''}. Open details.`}
      aria-current={focused ? 'step' : undefined}
      className={`c2-flow-node group relative z-[2] flex w-full min-w-0 flex-col gap-1 rounded-xl border bg-[color:var(--c2-panel-bg)] px-3 py-2.5 text-left md:w-[12.5rem] ${
        view === 'running' ? 'c2-stage-running border-[color:var(--c2-accent-line)]' : verdictStyle ? `border-transparent ring-2 ${verdictStyle.ring}` : 'border-[color:var(--c2-border-strong)]'
      } ${focused ? 'c2-flow-focus' : ''} ${dimmed ? 'opacity-45' : ''} ${result ? 'cursor-pointer hover:border-[color:var(--c2-accent-solid)]' : 'cursor-default'}`}
    >
      <span className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-2">
          <span className={`flex h-7 w-7 items-center justify-center rounded-lg ${verdictStyle ? `${verdictStyle.bg} ${verdictStyle.text}` : 'bg-[color:var(--c2-accent-tint)] text-[color:var(--c2-accent)]'}`}>
            <Icon className="h-4 w-4" aria-hidden="true" />
          </span>
          {stage.n && <span className="font-mono text-xs font-semibold text-[color:var(--c2-fg-faint)]">{stage.n}</span>}
        </span>
        <span className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 font-mono text-[0.625rem] ring-1 ${style.pill}`}>
          <StatusIcon className={`h-3 w-3 ${style.spin ? 'animate-spin motion-reduce:animate-none' : ''}`} aria-hidden="true" />
          {STATUS_LABEL[view]}
        </span>
      </span>
      <span className="text-[0.9375rem] font-semibold leading-tight text-[color:var(--c2-fg-strong)]">{stage.title}</span>
      <span className="line-clamp-2 min-h-[2rem] text-xs leading-4 text-[color:var(--c2-fg-muted)]">{stage.desc}</span>
      <span className="mt-auto flex min-h-[1.5rem] items-center justify-between gap-2">
        {isVerdict && revealed && result?.verdict ? (
          <span className={`text-sm font-semibold ${verdictStyle.text}`}>
            {result.verdict} · {result.risk_score}
            <span className="block text-xs font-normal text-[color:var(--c2-fg-2)]">
              {result.verdict === 'Legitimate' ? 'no threat class' : CLASS_LABELS[result.threat_class] || result.threat_class}
            </span>
          </span>
        ) : (
          <span className="font-mono text-xs text-[color:var(--c2-fg)]">
            {revealed && outcome?.ms !== null && outcome?.ms !== undefined ? `${outcome.ms.toFixed(1)} ms` : revealed && stage.keys.length ? '—' : ''}
          </span>
        )}
        {stage.novelty && <span className="rounded bg-[color:var(--c2-accent-tint-2)] px-1.5 py-0.5 font-mono text-[0.625rem] font-semibold text-[color:var(--c2-accent-hi)]">{stage.novelty}</span>}
      </span>
      {revealed && outcome?.note && view !== 'ok' && (
        <span className="truncate text-[0.6875rem] text-[color:var(--c2-sus-ink)]" title={outcome.note}>
          {outcome.note}
        </span>
      )}
    </button>
  )
}

/** Orthogonal / bezier connector between two node rectangles (container coordinates). */
function edgePath(a, b) {
  const r = 10
  if (b.left >= a.right - 2) {
    const sx = a.right, sy = a.top + a.height / 2, ex = b.left, ey = b.top + b.height / 2
    if (Math.abs(ey - sy) < 2) return `M${sx},${sy} L${ex},${ey}`
    // long fan-in (a lane → fusion): run straight along the lane, turn only in the gap before B
    if (ex - sx > 90) return `M${sx},${sy} L${ex - 30},${sy} C${ex - 8},${sy} ${ex - 22},${ey} ${ex},${ey}`
    const dx = (ex - sx) / 2
    return `M${sx},${sy} C${sx + dx},${sy} ${ex - dx},${ey} ${ex},${ey}`
  }
  if (b.top >= a.bottom - 2) {
    const overlap = b.left < a.right && b.right > a.left
    if (overlap) {
      const x1 = a.left + a.width / 2, x2 = b.left + b.width / 2
      const my = (a.bottom + b.top) / 2
      return `M${x1},${a.bottom} C${x1},${my} ${x2},${my} ${x2},${b.top}`
    }
    // down out of A, along the gap, down beside B, then into B's left side (a "bus")
    const sx = a.left + a.width / 2, sy = a.bottom, y1 = a.bottom + 18, x1 = b.left - 14, ey = b.top + b.height / 2
    const dir = x1 < sx ? -1 : 1
    return [
      `M${sx},${sy}`,
      `L${sx},${y1 - r}`,
      `Q${sx},${y1} ${sx + dir * r},${y1}`,
      `L${x1 - dir * r},${y1}`,
      `Q${x1},${y1} ${x1},${y1 + r}`,
      `L${x1},${ey - r}`,
      `Q${x1},${ey} ${x1 + r},${ey}`,
      `L${b.left},${ey}`,
    ].join(' ')
  }
  const sx = a.left + a.width / 2, ex = b.left + b.width / 2
  return `M${sx},${a.top} C${sx},${a.top - 30} ${ex},${b.bottom + 30} ${ex},${b.bottom}`
}

function FlowEdges({ box, nodes, states, layoutKey }) {
  const markerId = useId().replace(/:/g, '')
  const [geometry, setGeometry] = useState({ width: 0, height: 0, paths: [] })

  // `box` comes from a callback ref (state): a child's layout effect runs before the
  // parent's object ref is attached, so a ref object would still be null on first mount.
  useLayoutEffect(() => {
    if (!box || typeof ResizeObserver === 'undefined') return undefined
    // ResizeObserver also fires once right after observe(): that is the first measurement.
    const observer = new ResizeObserver(() => {
      const origin = box.getBoundingClientRect()
      const rect = (id) => {
        const node = nodes.current[id]
        if (!node) return null
        const r = node.getBoundingClientRect()
        return { left: r.left - origin.left, right: r.right - origin.left, top: r.top - origin.top, bottom: r.bottom - origin.top, width: r.width, height: r.height }
      }
      const paths = EDGES.map(([from, to]) => {
        const a = rect(from), b = rect(to)
        return a && b ? { key: `${from}-${to}`, from, to, d: edgePath(a, b) } : null
      }).filter(Boolean)
      setGeometry({ width: origin.width, height: origin.height, paths })
    })
    observer.observe(box)
    Object.values(nodes.current).forEach((node) => node && observer.observe(node))
    return () => observer.disconnect()
  }, [box, nodes, layoutKey])

  const revealed = (id) => !['waiting', 'running'].includes(states[id])
  return (
    <svg className="pointer-events-none absolute inset-0 z-[1] overflow-visible" width={geometry.width} height={geometry.height} aria-hidden="true">
      <defs>
        {['base', 'lit', 'muted'].map((kind) => (
          <marker key={kind} id={`${markerId}-${kind}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" className={`c2-edge-head-${kind}`} />
          </marker>
        ))}
      </defs>
      {geometry.paths.map((edge) => {
        const lit = revealed(edge.from) && states[edge.to] !== 'waiting'
        const muted = lit && ['notrun', 'skipped'].includes(states[edge.to])
        const failed = lit && states[edge.to] === 'failed'
        return (
          <g key={edge.key}>
            <path d={edge.d} className="c2-edge-base" markerEnd={lit ? undefined : `url(#${markerId}-base)`} />
            <path
              d={edge.d}
              pathLength="1"
              className={`c2-edge-lit ${muted ? 'c2-edge-muted' : ''} ${failed ? 'c2-edge-failed' : ''}`}
              style={{ strokeDashoffset: lit ? 0 : 1 }}
              markerEnd={lit ? `url(#${markerId}-${muted ? 'muted' : 'lit'})` : undefined}
            />
          </g>
        )
      })}
    </svg>
  )
}

function Lane({ lane, children }) {
  const novelty = { content: 'N2', behavior: 'N1' }[lane.id]
  return (
    <div className="c2-lane relative rounded-xl border border-dashed border-[color:var(--c2-border-strong)] bg-[color:var(--c2-inset-70)] px-3 pb-2.5 pt-1.5 md:pl-7">
      <p className="mb-1.5 flex items-center gap-2 font-mono text-[0.6875rem] font-semibold uppercase tracking-[0.14em] text-[color:var(--c2-fg-muted)]">
        {lane.label}
        <span className="normal-case tracking-normal text-[color:var(--c2-fg-faint)]">· {lane.modality === 'dom' ? 'DOM' : lane.modality} modality</span>
        {novelty && <span className="rounded bg-[color:var(--c2-accent-tint-2)] px-1.5 py-0.5 text-[0.625rem] text-[color:var(--c2-accent-hi)]">{novelty}</span>}
      </p>
      <div className="flex flex-col gap-6 md:flex-row md:gap-8">{children}</div>
    </div>
  )
}

const LEGEND = ['ok', 'skipped', 'failed', 'notrun']

/** Status key + novelty key, in the free space of the first row (not part of the flow). */
function Legend() {
  return (
    <div className="hidden min-w-0 flex-1 flex-col justify-center gap-2 rounded-xl border border-[color:var(--c2-border)] px-4 py-2.5 text-xs text-[color:var(--c2-fg-2)] lg:flex">
      <p className="flex flex-wrap items-center gap-1.5">
        {LEGEND.map((state) => {
          const style = STATE_STYLE[state]
          const Icon = style.icon
          return (
            <span key={state} className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 font-mono text-[0.625rem] ring-1 ${style.pill}`}>
              <Icon className="h-3 w-3" aria-hidden="true" /> {STATUS_LABEL[state]}
            </span>
          )
        })}
      </p>
      {Object.values(NOVELTIES).map((novelty) => (
        <p key={novelty.id} className="truncate" title={novelty.title}>
          <span className="mr-1.5 rounded bg-[color:var(--c2-accent-tint-2)] px-1.5 py-0.5 font-mono text-[0.625rem] font-semibold text-[color:var(--c2-accent-hi)]">{novelty.id}</span>
          {novelty.short}
        </p>
      ))}
    </div>
  )
}

function Toggle({ checked, onChange, label, icon: Icon }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm font-medium ${
        checked ? 'border-[color:var(--c2-accent-solid)] bg-[color:var(--c2-accent-tint-2)] text-[color:var(--c2-accent-hi)]' : 'border-[color:var(--c2-border-strong)] text-[color:var(--c2-fg-2)] hover:text-[color:var(--c2-fg-max)]'
      }`}
    >
      <Icon className="h-4 w-4" aria-hidden="true" />
      {label}
      <span className={`relative h-4 w-7 rounded-full ${checked ? 'bg-[color:var(--c2-accent-solid)]' : 'bg-[color:var(--c2-border-stronger)]'}`} aria-hidden="true">
        <span className={`absolute top-0.5 h-3 w-3 rounded-full bg-white transition ${checked ? 'left-3.5' : 'left-0.5'}`} />
      </span>
    </button>
  )
}

const ToolButton = ({ children, ...props }) => (
  <button
    type="button"
    {...props}
    className="inline-flex items-center gap-1.5 rounded-lg border border-[color:var(--c2-border-strong)] px-3 py-1.5 text-sm font-medium text-[color:var(--c2-fg)] hover:border-[color:var(--c2-accent-solid)] hover:text-[color:var(--c2-accent-hi)] disabled:cursor-not-allowed disabled:opacity-40"
  >
    {children}
  </button>
)

/**
 * The C2 pipeline as a large flowchart: Input → Fetch → Preprocess → three modality lanes
 * (Structure / Content / Behavior) → Tri-modal fusion → Verdict.
 * - live (running, no result yet): a highlight walks the stages, all labelled "in progress";
 * - replay: every stage shows its REAL status + time, revealed in timings_ms order (~5 s);
 * - presenter mode: no auto-play; ◀ / ▶ (and ← / →) step through the stages with a caption of
 *   what that stage did on this page; Space opens the stage's full-detail popup.
 */
export default function AnalysisFlow({ result, running = false, target = null, autoReplay = true }) {
  const reducedMotion = usePrefersReducedMotion()
  const dialog = useDetailDialog()
  const [box, setBox] = useState(null)
  const nodes = useRef({})
  const [presenter, setPresenterState] = useState(readPresenter)
  const [step, setStep] = useState(0)
  const [replay, setReplay] = useState({ key: 0, on: false })
  const [liveKey, setLiveKey] = useState(0)

  const setPresenter = useCallback((value) => {
    setPresenterState(value)
    setStep(0)
    setReplay((previous) => ({ ...previous, on: false }))
    try {
      localStorage.setItem(PRESENTER_KEY, value ? '1' : '0')
    } catch {
      /* private window: the toggle still works for this visit */
    }
  }, [])
  const startReplay = useCallback(() => setReplay((previous) => ({ key: previous.key + 1, on: true })), [])

  const outcomes = useMemo(() => (result ? allOutcomes(result) : null), [result])
  const schedule = useMemo(() => (outcomes ? replaySchedule(outcomes, REPLAY_MS) : []), [outcomes])

  // a new answer: replay it (or start the presentation at the first stage)
  const [seen, setSeen] = useState(null)
  if (result !== seen) {
    setSeen(result)
    setStep(0)
    setReplay((previous) => ({ key: previous.key + 1, on: Boolean(result) && autoReplay && !presenter && !reducedMotion }))
  }
  const [wasRunning, setWasRunning] = useState(false)
  if (running !== wasRunning) {
    setWasRunning(running)
    if (running) setLiveKey((value) => value + 1)
  }

  const replayElapsed = useTimer(replay.on, replay.key, REPLAY_MS + 200)
  const liveElapsed = useTimer(running && !result, liveKey)
  const replaying = replay.on && replayElapsed < REPLAY_MS + 200

  const states = useMemo(() => {
    const view = {}
    if (!result) {
      const walking = Math.min(STAGE_IDS.length - 2, 1 + Math.floor(liveElapsed / LIVE_STEP_MS))
      STAGE_IDS.forEach((id, index) => {
        if (id === 'input') view[id] = running || target ? 'ok' : 'waiting'
        else view[id] = running && index === walking ? 'running' : 'waiting'
      })
      return view
    }
    STAGE_IDS.forEach((id, index) => {
      if (presenter) view[id] = index <= step ? outcomes[id].state : 'waiting'
      else if (replaying) {
        const slot = schedule[index]
        view[id] = replayElapsed >= slot.end ? outcomes[id].state : replayElapsed >= slot.start ? 'running' : 'waiting'
      } else view[id] = outcomes[id].state
    })
    return view
  }, [result, running, target, liveElapsed, presenter, step, replaying, replayElapsed, schedule, outcomes])

  const openStage = useCallback(
    (id) => {
      if (!result || !dialog) return
      const stage = STAGE_BY_ID[id]
      dialog.open(`${stage.n ? `${stage.n} · ` : ''}${stage.title}`, () => <StageDetail stageId={id} result={result} />, stage.novelty ? `${stage.novelty} — ${NOVELTIES[stage.novelty].title}` : stage.desc)
    },
    [result, dialog],
  )

  const go = useCallback((delta) => setStep((value) => Math.max(0, Math.min(STAGE_IDS.length - 1, value + delta))), [])

  // presenter keys: ← / → / Home / End move, Space opens the current stage
  useEffect(() => {
    if (!presenter || !result) return undefined
    function onKey(event) {
      if (event.altKey || event.ctrlKey || event.metaKey) return
      // Inside a modal: act only while focus is in THIS flow's dialog (a stage popup opened on
      // top takes the keys). On a page: not while any popup is open. Esc stays the dialog's.
      const own = box?.closest('dialog')
      if (own ? !own.contains(document.activeElement) : dialog?.isOpen) return
      const tag = event.target?.tagName
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(tag) || event.target?.isContentEditable) return
      if (event.key === 'ArrowRight') go(1)
      else if (event.key === 'ArrowLeft') go(-1)
      else if (event.key === 'Home') setStep(0)
      else if (event.key === 'End') setStep(STAGE_IDS.length - 1)
      else if (event.key === ' ' && tag !== 'BUTTON') openStage(STAGE_IDS[step])
      else return
      event.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [presenter, result, dialog, go, openStage, step, box])

  const registerNode = useCallback((id, node) => {
    nodes.current[id] = node
  }, [])

  const node = (id) => (
    <FlowNode
      key={id}
      stage={STAGE_BY_ID[id]}
      view={states[id]}
      outcome={outcomes?.[id]}
      result={result}
      focused={presenter && result && STAGE_IDS[step] === id}
      dimmed={presenter && result && STAGE_IDS[step] !== id}
      registerNode={registerNode}
      onOpen={openStage}
    />
  )

  const current = STAGE_BY_ID[STAGE_IDS[step]]
  const total = result?.timings_ms?.total
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Toggle checked={presenter} onChange={setPresenter} label="Presenter mode" icon={Presentation} />
          {!presenter && result && (
            <ToolButton onClick={startReplay} disabled={reducedMotion} title={reducedMotion ? 'Reduced motion is on: the final state is shown' : undefined}>
              <RotateCcw className="h-4 w-4" aria-hidden="true" /> Replay
            </ToolButton>
          )}
          {presenter && result && (
            <>
              <ToolButton onClick={() => go(-1)} disabled={step === 0} aria-label="Previous stage">
                <ChevronLeft className="h-4 w-4" aria-hidden="true" /> Prev
              </ToolButton>
              <ToolButton onClick={() => go(1)} disabled={step === STAGE_IDS.length - 1} aria-label="Next stage">
                Next <ChevronRight className="h-4 w-4" aria-hidden="true" />
              </ToolButton>
              <span className="font-mono text-xs text-[color:var(--c2-fg-muted)]">
                step {step + 1} / {STAGE_IDS.length} · ← → keys · Space = details
              </span>
            </>
          )}
        </div>
        <p className="font-mono text-xs text-[color:var(--c2-fg-muted)]" role="status">
          {running && !result
            ? `analyzing ${target ? defangUrl(target) : '(pasted HTML)'} · ${(liveElapsed / 1000).toFixed(1)} s — C2 answers once, at the end`
            : result
              ? `${replaying ? 'replaying real timings · ' : ''}total ${total !== undefined ? `${total.toFixed(0)} ms` : '—'}${result.degraded ? ' · DEGRADED' : ''}`
              : ''}
        </p>
      </div>

      <div ref={setBox} className="relative flex flex-col gap-9">
        <div className="flex flex-col gap-6 md:flex-row md:flex-wrap md:items-stretch md:gap-8">
          {node('input')}
          {node('fetch')}
          {node('preprocess')}
          <Legend />
        </div>
        <div className="flex flex-col gap-6 md:flex-row md:flex-wrap md:items-center md:gap-8">
          <div className="flex flex-col gap-3" role="group" aria-label="Three modality lanes (tri-modal)">
            {LANES.map((lane) => (
              <Lane key={lane.id} lane={lane}>
                {FLOW_STAGES.filter((stage) => stage.lane === lane.id).map((stage) => node(stage.id))}
              </Lane>
            ))}
          </div>
          {node('fusion')}
          {node('verdict')}
        </div>
        <FlowEdges box={box} nodes={nodes} states={states} layoutKey={`${presenter}-${Boolean(result)}`} />
      </div>

      {presenter && result && (
        <div className="c2-enter rounded-xl border border-[color:var(--c2-accent-line)] bg-[color:var(--c2-accent-tint)] p-4" aria-live="polite">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="font-mono text-xs uppercase tracking-[0.14em] text-[color:var(--c2-accent)]">
                {current.n ? `Stage ${current.n} of 8` : current.id === 'input' ? 'Input' : 'Output'}
                {current.novelty ? ` · ${current.novelty} — ${NOVELTIES[current.novelty].title}` : ''}
              </p>
              <h3 className="mt-1 text-xl font-semibold text-[color:var(--c2-fg-strong)]">
                {current.n ? `${current.n} · ` : ''}
                {current.title}
              </h3>
              <p className="text-sm text-[color:var(--c2-fg-2)]">{current.desc}</p>
            </div>
            <ToolButton onClick={() => openStage(current.id)}>
              <Maximize2 className="h-4 w-4" aria-hidden="true" /> Full detail
            </ToolButton>
          </div>
          <ul className="mt-3 flex flex-col gap-1 text-base text-[color:var(--c2-fg-hi)]">
            {stageCaption(current.id, result).map((line, index) => (
              <li key={index} className="break-words">
                {line}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
