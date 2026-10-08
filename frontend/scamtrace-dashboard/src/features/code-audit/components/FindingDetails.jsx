import SeverityBadge from './SeverityBadge.jsx'

/** Detail panel for a single selected finding. */
export default function FindingDetails({ finding, loading, onClose }) {
  if (loading) {
    return (
      <section className="ca-detail">
        <p className="ca-loading">Loading finding details…</p>
      </section>
    )
  }
  if (!finding) return null

  return (
    <section className="ca-detail">
      <div className="ca-detail__header">
        <h3 className="ca-detail__title">{finding.title}</h3>
        <button type="button" className="ca-detail__close" onClick={onClose}>
          ✕
        </button>
      </div>

      <dl className="ca-detail__grid">
        <div>
          <dt>Severity</dt>
          <dd><SeverityBadge severity={finding.severity} /></dd>
        </div>
        <div>
          <dt>Category</dt>
          <dd>{finding.category}</dd>
        </div>
        <div>
          <dt>CWE</dt>
          <dd>{(finding.cwe || []).join(', ') || '—'}</dd>
        </div>
        <div>
          <dt>File</dt>
          <dd className="ca-detail__file">{finding.file_path}</dd>
        </div>
        <div>
          <dt>Line</dt>
          <dd>{finding.start_line}</dd>
        </div>
        <div>
          <dt>Detected By</dt>
          <dd>{finding.source === 'SEMGREP' ? 'Semgrep' : finding.source}</dd>
        </div>
      </dl>

      <div className="ca-detail__section">
        <h4>Description</h4>
        <p>{finding.description}</p>
      </div>

      <div className="ca-detail__section">
        <h4>Rule</h4>
        <code className="ca-detail__rule">{finding.rule_id}</code>
      </div>

      {finding.code_snippet && (
        <div className="ca-detail__section">
          <h4>Code</h4>
          <pre className="ca-detail__code">{finding.code_snippet}</pre>
        </div>
      )}

      <p className="ca-detail__note">
        AI-assisted remediation will be available in a later phase.
      </p>
    </section>
  )
}
