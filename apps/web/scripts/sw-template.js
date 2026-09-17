// Generated at build time by scripts/gen-sw.mjs into dist/sw.js — this file
// itself is never served, only its filled-in copy. Hand-rolled, no Workbox:
// this is exactly the "no dependency for a solved problem" discipline the
// rest of the app follows (no date lib, no chart lib, no TanStack Query).
//
// Scope: the app shell only (this file's own precache list, built from
// dist/assets/* plus the static public/ files). API responses are never
// cached here — the IndexedDB outbox (src/offline/) is the offline *data*
// story; this is only what lets the app boot with no network at all.
const CACHE_VERSION = '__CACHE_VERSION__'
const CACHE_NAME = `aigym-shell-${CACHE_VERSION}`
const PRECACHE_URLS = __PRECACHE_URLS__

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting()),
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const { request } = event
  const url = new URL(request.url)

  // Cross-origin (the API) is never intercepted — the outbox, not the
  // service worker, is the offline story for data.
  if (url.origin !== self.location.origin) return

  if (request.mode === 'navigate') {
    // Network-first: a reload with connectivity always gets the latest
    // shell. Only falls back to the cached shell when there is none —
    // the actual power-cut/dead-Wi-Fi case this exists for.
    event.respondWith(fetch(request).catch(() => caches.match('/index.html')))
    return
  }

  if (url.pathname.startsWith('/assets/')) {
    // Cache-first: Vite's hashed filenames are immutable, so a cache hit
    // is never stale.
    event.respondWith(
      caches.match(request).then(
        (cached) =>
          cached ||
          fetch(request).then((response) => {
            const copy = response.clone()
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy))
            return response
          }),
      ),
    )
  }
})
