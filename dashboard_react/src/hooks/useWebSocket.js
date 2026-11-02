import { useEffect, useRef, useCallback } from 'react'
import toast from 'react-hot-toast'

const WS_URL = 'ws://localhost:8000/ws'

/**
 * Custom hook that opens a WebSocket to the FastAPI backend.
 * Calls `onEvent(event)` whenever a new JSON message arrives.
 * Auto-reconnects on disconnect with exponential backoff.
 */
export function useWebSocket(onEvent) {
  const wsRef = useRef(null)
  const retryRef = useRef(0)
  const mountedRef = useRef(true)

  const connect = useCallback(() => {
    if (!mountedRef.current) return
    try {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        retryRef.current = 0
        console.log('[WS] Connected to ADERS backend')
      }

      ws.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data)
          onEvent(data)
        } catch {/* ignore malformed */ }
      }

      ws.onerror = () => { ws.close() }

      ws.onclose = () => {
        if (!mountedRef.current) return
        const delay = Math.min(1000 * 2 ** retryRef.current, 15000)
        retryRef.current++
        setTimeout(connect, delay)
      }
    } catch {/* browser WS not available in SSR */ }
  }, [onEvent])

  useEffect(() => {
    mountedRef.current = true
    connect()
    return () => {
      mountedRef.current = false
      wsRef.current?.close()
    }
  }, [connect])
}

