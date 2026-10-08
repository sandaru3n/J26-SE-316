const LABELS = {
  CRITICAL: 'Critical',
  HIGH: 'High',
  MEDIUM: 'Medium',
  LOW: 'Low',
  INFO: 'Info',
}

/** Reusable severity badge: CRITICAL / HIGH / MEDIUM / LOW / INFO. */
export default function SeverityBadge({ severity }) {
  const key = (severity || '').toUpperCase()
  const label = LABELS[key] || severity
  return (
    <span className={`ca-sev-badge ca-sev-badge--${key.toLowerCase()}`}>
      {label}
    </span>
  )
}
