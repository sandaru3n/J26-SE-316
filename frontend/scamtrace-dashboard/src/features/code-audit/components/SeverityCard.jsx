/**
 * Severity summary card. Also acts as the severity filter control:
 * clicking a card requests findings of that severity from the API.
 */
export default function SeverityCard({ label, count, severity, active, onSelect }) {
  const key = (severity || 'all').toLowerCase()
  return (
    <button
      type="button"
      className={`ca-sev-card ca-sev-card--${key}${active ? ' ca-sev-card--active' : ''}`}
      onClick={() => onSelect(severity || null)}
    >
      <span className="ca-sev-card__label">{label}</span>
      <span className="ca-sev-card__count">{count}</span>
    </button>
  )
}
