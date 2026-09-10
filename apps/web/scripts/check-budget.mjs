/**
 * Fails the build if the app outgrows a mid-range Android phone on a bad connection.
 * Lebanon assumption, not a nice-to-have: see docs/DECISIONS.md.
 */
import { gzipSync } from 'node:zlib'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

const LIMIT_KB = 200
const dir = 'dist/assets'
const js = readdirSync(dir).filter((f) => f.endsWith('.js'))
let total = 0

for (const file of js) {
  const size = gzipSync(readFileSync(join(dir, file))).length
  total += size
  console.log(`  ${file}  ${(size / 1024).toFixed(1)} KB gz`)
}

const kb = total / 1024
console.log(`\nTotal JS: ${kb.toFixed(1)} KB gzipped (budget ${LIMIT_KB} KB)`)
if (kb > LIMIT_KB) {
  console.error(`\nOver budget by ${(kb - LIMIT_KB).toFixed(1)} KB.`)
  process.exit(1)
}
console.log('Within budget.')
