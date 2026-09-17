/**
 * A hand-rolled IndexedDB wrapper for the outbox — no library. One object
 * store, one autoincrement key, which is what gives the queue its strict
 * insertion order (see outbox.ts). Every call opens a fresh connection;
 * IndexedDB handles are cheap and this avoids holding one open across the
 * app's lifetime for a single small store.
 */

const DB_NAME = 'aigym-outbox'
const DB_VERSION = 1
export const STORE_NAME = 'requests'

export function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)
    request.onupgradeneeded = () => {
      request.result.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true })
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

export function withStore<T>(
  mode: IDBTransactionMode,
  run: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  return openDb().then(
    (db) =>
      new Promise<T>((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, mode)
        const req = run(tx.objectStore(STORE_NAME))
        tx.oncomplete = () => resolve(req.result)
        tx.onerror = () => reject(tx.error)
        tx.onabort = () => reject(tx.error)
      }),
  )
}
