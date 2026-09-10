/**
 * Physical-direction Tailwind utilities break Arabic layout silently — the page still
 * renders, it is just wrong. Cheaper to fail the build than to spot it in review.
 *
 * Only class-list strings are inspected; English prose in comments and data ("left-hand
 * side", "left-shoulder injury") is not a layout bug.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

const BANNED = /^(ml|mr|pl|pr|left|right|border-l|border-r|rounded-(t|b)?(l|r))-[a-z0-9.[\]]+$/
const LOOKS_LIKE_CLASSES = /(^|\s)(flex|grid|block|hidden|absolute|relative|sticky|truncate|(bg|text|border|rounded|p|px|py|m|mx|my|ms|me|w|h|size|min-h|gap|inset)-[a-z0-9[])/
const STRINGS = /(['"`])((?:\\.|(?!\1)[^\\])*)\1/g
const ALLOW = /rtl-ok/

const files = []
const walk = (dir) => {
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry)
    if (statSync(path).isDirectory()) walk(path)
    else if (/\.tsx?$/.test(path)) files.push(path)
  }
}
walk('src')

let bad = 0
for (const file of files) {
  readFileSync(file, 'utf8')
    .split('\n')
    .forEach((line, i) => {
      if (ALLOW.test(line)) return
      for (const [, , body] of line.matchAll(STRINGS)) {
        if (!LOOKS_LIKE_CLASSES.test(body)) continue
        const hits = body.split(/\s+/).filter((token) => BANNED.test(token))
        if (hits.length) {
          bad++
          console.error(
            `${file}:${i + 1}  ${hits.join(', ')}  → use logical utilities (ms/me/ps/pe/start/end)`,
          )
        }
      }
    })
}

if (bad) {
  console.error(`\n${bad} physical-direction utilities found.`)
  process.exit(1)
}
console.log(`RTL check clean across ${files.length} files.`)
