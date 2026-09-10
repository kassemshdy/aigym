import { chromium } from 'playwright'

const BASE = process.env.BASE ?? 'http://localhost:4173'
const OUT = process.argv[2]

/** [name, path, viewport, optional interaction to reach a meaningful state] */
const SCREENS = [
  ['login', '/login', 'phone'],
  ['manager-home', '/manager', 'phone'],
  ['manager-members', '/manager/members', 'phone'],
  ['manager-member', '/manager/members/m1', 'phone'],
  ['manager-add', '/manager/members/new', 'phone'],
  ['coach-queue', '/coach', 'ipad'],
  ['coach-card', '/coach/member/m1', 'ipad'],
  ['coach-session', '/coach/session/m1', 'ipad'],
  ['coach-ai', '/coach/ai', 'ipad'],
  ['member-today', '/member', 'phone'],
  ['member-food', '/member/food', 'phone'],
  ['member-chat-pick', '/member/chat', 'phone'],
  [
    'member-chat-nutrition',
    '/member/chat/nutrition',
    'phone',
    // Ask the second suggestion, which is the one the agent answers by logging a meal.
    async (page) => {
      await page.getByRole('button').nth(2).click()
      await page.waitForTimeout(300)
    },
  ],
  [
    'member-chat-training',
    '/member/chat/training',
    'phone',
    // Third suggestion asks for a program change — the agent must escalate, not act.
    async (page) => {
      await page.getByRole('button').nth(3).click()
      await page.waitForTimeout(300)
    },
  ],
  ['member-photos', '/member/photos', 'phone'],
  ['member-videos', '/member/videos', 'phone'],
  ['member-progress', '/member/progress', 'phone'],
]

const SIZES = { phone: { width: 390, height: 844 }, ipad: { width: 1024, height: 768 } }

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH ?? '/opt/pw-browsers/chromium',
})
const errors = []

for (const lang of ['ar', 'en']) {
  for (const [name, path, size, prepare] of SCREENS) {
    const ctx = await browser.newContext({ viewport: SIZES[size], deviceScaleFactor: 2 })
    const page = await ctx.newPage()
    page.on('pageerror', (e) => errors.push(`${lang} ${path}: ${e.message}`))
    page.on('console', (m) => m.type() === 'error' && errors.push(`${lang} ${path}: ${m.text()}`))

    await page.addInitScript((l) => {
      localStorage.setItem('aigym.lang', l)
      localStorage.setItem('aigym.signedIn', '1')
    }, lang)

    await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(200)
    if (prepare) await prepare(page)

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

// External thumbnails are expected to fail where the network is restricted.
const real = errors.filter((e) => !/img\.youtube\.com|ERR_|net::/.test(e))
console.log(
  real.length
    ? `PROBLEMS:\n${real.join('\n')}`
    : `All ${SCREENS.length * 2} screens rendered clean: dir correct, no overflow, no JS errors.`,
)
process.exit(real.length ? 1 : 0)
