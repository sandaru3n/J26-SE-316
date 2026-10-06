import RepositoryInput from '../components/RepositoryInput.jsx'
import ScanSummary from '../components/ScanSummary.jsx'
import { useCodeAudit } from '../hooks/useCodeAudit.js'
import '../codeAudit.css'

/**
 * C4 — Code Quality & Vulnerability Auditor.
 * Phase 1: GitHub repository ingestion and summary.
 */
export default function RepositoryAudit() {
  const { loading, error, result, analyze } = useCodeAudit()

  return (
    <main className="ca-page">
      <header className="ca-page__header">
        <h1>Code Quality &amp; Vulnerability Auditor</h1>
        <p className="ca-page__subtitle">
          Analyze a GitHub repository for code quality and security risks.
        </p>
      </header>

      <section className="ca-card">
        <h2 className="ca-card__title">Repository Analysis</h2>
        <p className="ca-card__description">
          Paste a public GitHub repository URL to begin.
        </p>
        <RepositoryInput onSubmit={analyze} loading={loading} />
        {loading && <p className="ca-loading">Analyzing repository…</p>}
        {error && <p className="ca-error ca-error--server">{error}</p>}
      </section>

      {result && <ScanSummary result={result} />}
    </main>
  )
}
