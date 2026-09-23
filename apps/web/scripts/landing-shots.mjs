/**
 * Regenerates the screenshots on the public landing page, in both languages.
 *
 * Deliberately not `shots.mjs`: that script is a test — it scrolls `main` to the
 * bottom to prove the tab bar stays put, which is exactly the wrong frame to sell
 * with. This one captures the top of each screen and encodes for page weight.
 *
 *   npm run build && npx vite preview --port 4173
 *   node scripts/landing-shots.mjs
 *
 * Run it against a build with no VITE_API_URL, so the app is in mock mode and the
 * shots carry the seeded Lebanese gym rather than whatever is in a real database.
 * Committed output lives in public/landing/ — regenerate it when a screen changes,
 * or the landing page is advertising a version of the product that no longer exists.
 */
import { chromium } from 'playwright'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, rmSync, mkdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const BASE = process.env.BASE ?? 'http://localhost:4173'
const OUT = 'public/landing'

/** [name, path, viewport, optional interaction to reach a meaningful state] */
const SHOTS = [
  ['home', '/manager', 'phone'],
  ['insights', '/manager/insights', 'phone'],
  ['lapsed', '/manager/lapsed', 'phone'],
  ['import', '/manager/import', 'phone'],
  ['member', '/member', 'phone'],
  [
    'chat',
    '/member/chat/nutrition',
    'phone',
    // The second suggestion is the one the assistant answers by logging a meal —
    // an empty chat screen shows nothing worth showing.
    async (page) => {
      await page.getByRole('button').nth(2).click()
      await page.waitForTimeout(400)
    },
  ],
  ['session', '/coach/session/m1', 'ipad'],
]

const SIZES = { phone: { width: 390, height: 844 }, ipad: { width: 1024, height: 768 } }
/** Rendered widths on the landing page, doubled for retina. Anything larger is
 * bytes a phone on a congested network pays for and cannot see. */
const TARGET_WIDTH = { phone: 520, ipad: 1120 }

mkdirSync(OUT, { recursive: true })
const raw = mkdtempSync(join(tmpdir(), 'landing-shots-'))
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH ?? '/opt/pw-browsers/chromium',
})

const made = []
for (const lang of ['en', 'ar']) {
  for (const [name, path, size, prepare] of SHOTS) {
    const ctx = await browser.newContext({ viewport: SIZES[size], deviceScaleFactor: 2 })
    const page = await ctx.newPage()
    await page.addInitScript((l) => {
      localStorage.setItem('aigym.lang', l)
      localStorage.setItem('aigym.tour.manager.seen', '1')
      localStorage.setItem('aigym.tour.coach.seen', '1')
    }, lang)
    await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(250)
    if (prepare) await prepare(page)
    // Not fullPage: the app scrolls inside <main>, so the viewport already is
    // the whole screen, and the top of it is the part worth showing.
    await page.screenshot({ path: `${raw}/${name}-${lang}.png` })
    await ctx.close()
    made.push([name, lang, size])
  }
}
await browser.close()

const py = `
import sys
from PIL import Image
src, dst, width = sys.argv[1], sys.argv[2], int(sys.argv[3])
im = Image.open(src).convert('RGB')
im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
im.save(dst, 'WEBP', quality=72, method=6)
print(dst, im.size)
`
for (const [name, lang, size] of made) {
  execFileSync(
    'python3',
    ['-c', py, `${raw}/${name}-${lang}.png`, `${OUT}/${name}-${lang}.webp`, String(TARGET_WIDTH[size])],
    { stdio: 'inherit' },
  )
}
rmSync(raw, { recursive: true, force: true })
console.log(`\n${made.length} screenshots written to ${OUT}/`)
