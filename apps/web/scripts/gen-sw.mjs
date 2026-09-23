// Runs after `vite build` (see package.json's build script). No
// build.manifest — dist/assets/* is small enough to just list directly
// rather than pull in Vite's manifest machinery for one script.
import { readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptsDir = fileURLToPath(new URL('.', import.meta.url))
const distDir = join(scriptsDir, '..', 'dist')
const publicDir = join(scriptsDir, '..', 'public')

const assetFiles = readdirSync(join(distDir, 'assets')).map((f) => `/assets/${f}`)
// Files only, deliberately not recursive: public/landing/ holds the
// screenshots on the marketing page, and an offline shell should carry the
// app, not its advertising. A directory name in this list would also cache
// the SPA fallback under a path that is not a real asset.
const publicFiles = readdirSync(publicDir, { withFileTypes: true })
  .filter((entry) => entry.isFile())
  .map((entry) => `/${entry.name}`)

const precacheUrls = ['/', '/index.html', ...publicFiles, ...assetFiles]

// Changes every build, which is what forces an already-installed service
// worker to see a new version and swap its cache — a stale worker serving
// last week's shell is worse than no worker at all.
const cacheVersion = Date.now().toString(36)

const template = readFileSync(join(scriptsDir, 'sw-template.js'), 'utf8')
const output = template
  .replace('__CACHE_VERSION__', cacheVersion)
  .replace('__PRECACHE_URLS__', JSON.stringify(precacheUrls))

writeFileSync(join(distDir, 'sw.js'), output)
console.log(`Generated dist/sw.js — cache ${cacheVersion}, ${precacheUrls.length} precached URLs`)
