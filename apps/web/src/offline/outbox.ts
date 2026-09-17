/**
 * One ordered queue for every offline-eligible write (workout sessions,
 * sets, nutrition logs, check-in status) — not one queue per feature, so a
 * set logged after a check-in can never replay ahead of it. Replay stops at
 * the first failure and picks up from there next time, which is what keeps
 * the order a guarantee rather than a best effort.
 */
import { withStore } from './db'

export interface QueuedRequest {
  id: number
  idempotencyKey: string
  path: string
  method: 'POST' | 'PATCH' | 'DELETE'
  body: unknown
  queuedAt: string
}

const listeners = new Set<() => void>()

function notify() {
  for (const fn of listeners) fn()
}

/** Subscribe to "the queue changed" — OfflineProvider uses this to keep the
 * pending-count badge live without polling. */
export function onOutboxChange(fn: () => void): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export async function enqueue(entry: Omit<QueuedRequest, 'id' | 'queuedAt'>): Promise<void> {
  await withStore('readwrite', (store) =>
    store.add({ ...entry, queuedAt: new Date().toISOString() }),
  )
  notify()
}

export async function listPending(): Promise<QueuedRequest[]> {
  const rows = await withStore<QueuedRequest[]>('readonly', (store) => store.getAll())
  return rows.sort((a, b) => a.id - b.id)
}

async function remove(id: number): Promise<void> {
  await withStore('readwrite', (store) => store.delete(id))
  notify()
}

/** Replays the queue oldest-first against `send`, stopping at the first
 * failure so a later write never lands before an earlier one. `send` is
 * injected (rather than importing apiFetch directly) to keep this module
 * free of any dependency on the auth/refresh logic in client.ts — client.ts
 * is the one that depends on this module, not the other way around. */
export async function replay(
  send: (entry: QueuedRequest) => Promise<void>,
): Promise<void> {
  for (const entry of await listPending()) {
    try {
      await send(entry)
    } catch {
      return
    }
    await remove(entry.id)
  }
}
