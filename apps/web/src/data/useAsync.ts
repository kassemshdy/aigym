import { useEffect, useState } from 'react'

/**
 * The thin read-side counterpart to queries.ts's write functions — no
 * TanStack Query (decision: its cache is exactly what Phase 3's IndexedDB
 * outbox replaces, so it's less code to throw away without it). Just
 * component-local state around a promise, with a `reload` escape hatch for
 * after a mutation.
 */
export function useAsync<T>(fn: () => Promise<T>, deps: readonly unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let cancelled = false

    async function run() {
      setLoading(true)
      setError(false)
      try {
        const result = await fn()
        if (!cancelled) setData(result)
      } catch {
        if (!cancelled) setError(true)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void run()

    return () => {
      cancelled = true
    }
    // fn is recreated every render by design (it closes over route params);
    // deps is the caller's explicit dependency list instead.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  return { data, loading, error, reload: () => setTick((n) => n + 1) }
}
