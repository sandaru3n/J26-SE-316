import { useCallback, useState } from 'react'
import {
  analyzeRepository,
  getFinding,
  getFindings,
} from '../api/codeAuditApi.js'

/**
 * Hook managing the C4 flow: repository analysis, security findings,
 * severity filtering and finding details.
 */
export function useCodeAudit() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  const [findings, setFindings] = useState(null)
  const [findingsLoading, setFindingsLoading] = useState(false)
  const [findingsError, setFindingsError] = useState('')
  const [severityFilter, setSeverityFilter] = useState(null)

  const [selectedFinding, setSelectedFinding] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const loadFindings = useCallback(async (scanId, severity = null) => {
    setFindingsLoading(true)
    setFindingsError('')
    setSelectedFinding(null)
    try {
      const data = await getFindings(scanId, severity)
      setFindings(data)
      setSeverityFilter(severity)
    } catch (err) {
      setFindingsError(err?.message || 'Unable to load security findings.')
    } finally {
      setFindingsLoading(false)
    }
  }, [])

  const analyze = useCallback(
    async (repositoryUrl) => {
      if (loading) return
      setLoading(true)
      setError('')
      setResult(null)
      setFindings(null)
      setFindingsError('')
      setSeverityFilter(null)
      setSelectedFinding(null)
      try {
        const data = await analyzeRepository(repositoryUrl)
        setResult(data)
        if (data?.scan_id) {
          await loadFindings(data.scan_id, null)
        }
      } catch (err) {
        setError(
          err?.message ||
            'Unable to analyze repository. Please verify that the repository is public and try again.'
        )
      } finally {
        setLoading(false)
      }
    },
    [loading, loadFindings]
  )

  const filterBySeverity = useCallback(
    (severity) => {
      if (!result?.scan_id || findingsLoading) return
      loadFindings(result.scan_id, severity)
    },
    [result, findingsLoading, loadFindings]
  )

  const selectFinding = useCallback(async (findingId) => {
    setDetailLoading(true)
    try {
      setSelectedFinding(await getFinding(findingId))
    } catch {
      setSelectedFinding(null)
    } finally {
      setDetailLoading(false)
    }
  }, [])

  const clearSelectedFinding = useCallback(() => setSelectedFinding(null), [])

  return {
    loading,
    error,
    result,
    analyze,
    findings,
    findingsLoading,
    findingsError,
    severityFilter,
    filterBySeverity,
    selectedFinding,
    detailLoading,
    selectFinding,
    clearSelectedFinding,
  }
}
