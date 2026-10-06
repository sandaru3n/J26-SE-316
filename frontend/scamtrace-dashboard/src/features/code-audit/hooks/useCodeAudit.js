import { useCallback, useState } from 'react'
import { analyzeRepository } from '../api/codeAuditApi.js'

/**
 * Hook managing the repository-analysis flow of the C4 component:
 * loading state, error state and the latest scan result.
 */
export function useCodeAudit() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  const analyze = useCallback(
    async (repositoryUrl) => {
      if (loading) return
      setLoading(true)
      setError('')
      setResult(null)
      try {
        const data = await analyzeRepository(repositoryUrl)
        setResult(data)
      } catch (err) {
        setError(
          err?.message ||
            'Unable to analyze repository. Please verify that the repository is public and try again.'
        )
      } finally {
        setLoading(false)
      }
    },
    [loading]
  )

  const reset = useCallback(() => {
    setError('')
    setResult(null)
  }, [])

  return { loading, error, result, analyze, reset }
}
