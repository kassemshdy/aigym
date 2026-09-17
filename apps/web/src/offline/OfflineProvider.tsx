import { createContext, useContext, useEffect, useState } from 'react'
import { replayOutbox } from '@/data/client'
import { listPending, onOutboxChange } from './outbox'

interface OfflineState {
  offline: boolean
  pendingCount: number
}

const OfflineContext = createContext<OfflineState>({ offline: false, pendingCount: 0 })

/** Tracks connectivity and the outbox's pending count, and replays the
 * queue whenever either changes in the reconnecting direction. Mounted once
 * at the app root (main.tsx) so the header badge (AppShell) and every
 * screen see the same live state — never silent about whether a write
 * landed, per .agents/skills/offline-sync. */
export function OfflineProvider({ children }: { children: React.ReactNode }) {
  const [offline, setOffline] = useState(!navigator.onLine)
  const [pendingCount, setPendingCount] = useState(0)

  useEffect(() => {
    let cancelled = false

    async function refreshCount() {
      const pending = await listPending()
      if (!cancelled) setPendingCount(pending.length)
    }

    function handleOnline() {
      setOffline(false)
      void replayOutbox().then(refreshCount)
    }
    function handleOffline() {
      setOffline(true)
    }

    void refreshCount()
    if (navigator.onLine) void replayOutbox().then(refreshCount)

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    const unsubscribe = onOutboxChange(() => void refreshCount())

    return () => {
      cancelled = true
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
      unsubscribe()
    }
  }, [])

  return (
    <OfflineContext.Provider value={{ offline, pendingCount }}>{children}</OfflineContext.Provider>
  )
}

export function useOffline() {
  return useContext(OfflineContext)
}
