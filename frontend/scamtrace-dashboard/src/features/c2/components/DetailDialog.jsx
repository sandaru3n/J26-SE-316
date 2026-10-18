import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Maximize2, X } from 'lucide-react'
import { DialogContext } from '../context/detailDialogContext.js'
import { useDetailDialog } from '../hooks/useDetailDialog.js'

/**
 * One modal for every "open in full detail" popup. Native <dialog>.showModal(): the page
 * behind is inert (focus stays inside), Esc closes, focus returns to the opener. Content is
 * React elements only (text), never HTML strings.
 */
export function DetailDialogProvider({ children }) {
  const [entry, setEntry] = useState(null)
  const dialog = useRef(null)
  const opener = useRef(null)

  const open = useCallback((title, render, subtitle) => {
    opener.current = document.activeElement
    setEntry({ title, render, subtitle })
  }, [])
  const close = useCallback(() => dialog.current?.close(), [])

  useEffect(() => {
    const node = dialog.current
    if (entry && node && !node.open) node.showModal()
  }, [entry])

  function onClose() {
    setEntry(null)
    const back = opener.current
    opener.current = null
    if (back && typeof back.focus === 'function') back.focus()
  }

  const value = useMemo(() => ({ open, close, isOpen: Boolean(entry) }), [open, close, entry])
  return (
    <DialogContext.Provider value={value}>
      {children}
      <dialog
        ref={dialog}
        onClose={onClose}
        onClick={(event) => event.target === dialog.current && close()}
        aria-labelledby="c2-dialog-title"
        className="c2-dialog m-auto w-[min(64rem,calc(100vw-2rem))] max-h-[calc(100vh-3rem)] overflow-hidden rounded-2xl border border-[color:var(--c2-border-strong)] bg-[color:var(--c2-panel-bg)] p-0 text-[color:var(--c2-text-base)] shadow-2xl"
      >
        {entry && (
          <div className="flex max-h-[calc(100vh-3rem)] flex-col">
            <header className="flex items-start justify-between gap-4 border-b border-[color:var(--c2-border)] px-5 py-4">
              <div className="min-w-0">
                <h2 id="c2-dialog-title" className="text-lg font-semibold text-[color:var(--c2-fg-strong)]">
                  {entry.title}
                </h2>
                {entry.subtitle && <p className="mt-0.5 text-sm text-[color:var(--c2-fg-muted)]">{entry.subtitle}</p>}
              </div>
              <button
                type="button"
                onClick={close}
                className="rounded-md p-1.5 text-[color:var(--c2-fg-2)] hover:bg-[color:var(--c2-hover)] hover:text-[color:var(--c2-fg-max)]"
                aria-label="Close"
              >
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </header>
            <div className="overflow-y-auto px-5 py-4">{entry.render()}</div>
          </div>
        )}
      </dialog>
    </DialogContext.Provider>
  )
}

/** "Open in full detail" button for a panel header. */
export function ExpandButton({ title, subtitle, render, label = 'Details' }) {
  const dialog = useDetailDialog()
  if (!dialog) return null
  return (
    <button
      type="button"
      onClick={() => dialog.open(title, render, subtitle)}
      className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-[color:var(--c2-border-strong)] px-2 py-1 text-xs font-medium text-[color:var(--c2-fg-2)] hover:border-[color:var(--c2-accent-solid)] hover:text-[color:var(--c2-accent-hi)]"
      aria-label={`${label}: ${title}`}
    >
      <Maximize2 className="h-3.5 w-3.5" aria-hidden="true" />
      {label}
    </button>
  )
}
