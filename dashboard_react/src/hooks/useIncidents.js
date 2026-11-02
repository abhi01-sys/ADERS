import { useState, useEffect, useCallback } from 'react'
import { getIncidents } from '../api/incidents'

/**
 * Polls /incidents/ every `intervalMs` ms and merges new WebSocket events.
 */
export function useIncidents(intervalMs = 5000) {
  const [incidents, setIncidents] = useState([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState(null)

  const refresh = useCallback(async () => {
    try {
      const data = await getIncidents(200)
      setIncidents(data)
      setError(null)
    } catch (e) {
      setError('Backend offline')
    } finally {
      setLoading(false)
    }
  }, [])

  // Initial load + polling
  useEffect(() => {
    refresh()
    const id = setInterval(refresh, intervalMs)
    return () => clearInterval(id)
  }, [refresh, intervalMs])

  // Accept a new incident from WebSocket and prepend it
  const addIncident = useCallback((inc) => {
    setIncidents((prev) => {
      const exists = prev.some((i) => i.id === inc.id)
      return exists ? prev : [inc, ...prev]
    })
  }, [])

  return { incidents, loading, error, refresh, addIncident }
}

