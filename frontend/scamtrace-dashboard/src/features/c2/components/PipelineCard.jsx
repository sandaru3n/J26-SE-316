import { useEffect, useRef, useState } from 'react'
import { Maximize2, Workflow, X } from 'lucide-react'
import AnalysisFlow from './AnalysisFlow.jsx'
import PipelineStages from './PipelineStages.jsx'
import { Panel } from './ui.jsx'

/**
 * The compact "Pipeline" card (stage list + scan.log) with a Details button that opens the full
 * AnalysisFlow flowchart in a large modal. The modal is rendered here (not via the shared
 * popup) so it always shows the CURRENT props: live progress while a scan runs, then the replay.
 * Native <dialog>.showModal(): page inert behind it (focus stays inside), Esc closes, focus
 * returns to the Details button. Stage popups opened from the flowchart stack on top of it.
 */
export default function PipelineCard({ result, running = false, startedAt = null, target = null, status }) {
  const [open, setOpen] = useState(false)
  const dialog = useRef(null)
  const button = useRef(null)

  useEffect(() => {
    const node = dialog.current
    if (open && node && !node.open) node.showModal()
  }, [open])

  function onClose() {
    setOpen(false)
    button.current?.focus()
  }

  return (
    <Panel
      title="Pipeline"
      icon={Workflow}
      actions={
        <button
          ref={button}
          type="button"
          onClick={() => setOpen(true)}
          aria-haspopup="dialog"
          className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-[color:var(--c2-border-strong)] px-2 py-1 text-xs font-medium text-[color:var(--c2-fg-2)] hover:border-[color:var(--c2-accent-solid)] hover:text-[color:var(--c2-accent-hi)]"
        >
          <Maximize2 className="h-3.5 w-3.5" aria-hidden="true" />
          Details
        </button>
      }
    >
      {status}
      <PipelineStages running={running} startedAt={startedAt} result={result} target={target} />
      <dialog
        ref={dialog}
        onClose={onClose}
        onClick={(event) => event.target === dialog.current && dialog.current.close()}
        aria-labelledby="c2-pipeline-dialog-title"
        className="c2-dialog m-auto h-[90vh] max-h-[90vh] w-[90vw] max-w-[90vw] overflow-hidden rounded-2xl border border-[color:var(--c2-border-strong)] bg-[color:var(--c2-panel-bg)] p-0 text-[color:var(--c2-text-base)] shadow-2xl"
      >
        {open && (
          <div className="flex h-full flex-col">
            <header className="flex items-start justify-between gap-4 border-b border-[color:var(--c2-border)] px-5 py-4">
              <div className="min-w-0">
                <h2 id="c2-pipeline-dialog-title" className="text-lg font-semibold text-[color:var(--c2-fg-strong)]">
                  C2 analysis pipeline
                </h2>
                <p className="mt-0.5 text-sm text-[color:var(--c2-fg-muted)]">
                  Structure · Content · Behavior → tri-modal fusion. Click a stage for its full detail.
                </p>
              </div>
              <button
                type="button"
                onClick={() => dialog.current?.close()}
                className="rounded-md p-1.5 text-[color:var(--c2-fg-2)] hover:bg-[color:var(--c2-hover)] hover:text-[color:var(--c2-fg-max)]"
                aria-label="Close"
              >
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </header>
            <div className="min-h-0 flex-1 overflow-auto px-5 py-4">
              <AnalysisFlow result={result} running={running} target={target} />
            </div>
          </div>
        )}
      </dialog>
    </Panel>
  )
}
