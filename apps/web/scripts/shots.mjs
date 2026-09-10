import { chromium } from 'playwright'

const BASE = 'http://localhost:4173'
const OUT = process.argv[2]

const SCREENS = [
  ['manager-home', '/manager', 'phone'],
  ['manager-members', '/manager/members', 'phone'],
  ['manager-member', '/manager/members/m1', 'phone'],
  ['manager-add', '/manager/members/new', 'phone'],
  ['coach-queue', '/coach', 'ipad'],
  ['coach-card', '/coach/member/m1', 'ipad'],
  ['coach-session', '/coach/session/m1', 'ipad'],
  ['coach-ai', '/coach/ai', 'ipad'],
  ['member-today', '/member', 'phone'],
  ['member-videos', '/member/videos', 'phone'],
  ['member-progress', '/member/progress', 'phone'],
]

const SIZES = { phone: { width: 390, height: 844 }, ipad: { width: 1024, height: 768 } }

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH ?? '/opt/pw-browsers/chromium' })
const errors = []

for (const lang of ['ar', 'en']) {
  for (const [name, path, size] of SCREENS) {
    const ctx = await browser.newContext({ viewport: SIZES[size], deviceScaleFactor: 2 })
    const page = await ctx.newPage()
    page.on('pageerror', (e) => errors.push(`${lang} ${path}: ${e.message}`))
    page.on('console', (m) => m.type() === 'error' && errors.push(`${lang} ${path}: ${m.text()}`))
    await page.addInitScript((l) => localStorage.setItem('aigym.lang', l), lang)
    await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(200)

    const dir = await page.evaluate(() => document.documentElement.dir)
    const expected = lang === 'ar' ? 'rtl' : 'ltr'
    if (dir !== expected) errors.push(`${lang} ${path}: dir=${dir}, expected ${expected}`)

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    )
    if (overflow) errors.push(`${lang} ${path}: horizontal overflow`)

    await page.screenshot({ path: `${OUT}/${name}-${lang}.png`, fullPage: true })
    await ctx.close()
  }
}

await browser.close()

const real = errors.filter((e) => !/img\.youtube\.com|ERR_|net::/.test(e))
console.log(real.length ? `PROBLEMS:\n${real.join('\n')}` : 'All screens rendered clean: dir correct, no overflow, no JS errors.')
process.exit(real.length ? 1 : 0)
