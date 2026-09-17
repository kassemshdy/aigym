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
  ['manager-lapsed', '/manager/lapsed', 'phone'],
  ['manager-staff', '/manager/staff', 'phone'],
  ['coach-queue', '/coach', 'ipad'],
  ['coach-checkin', '/coach/check-in', 'ipad'],
  ['coach-card', '/coach/member/m1', 'ipad'],
  ['coach-session', '/coach/session/m1', 'ipad'],
  ['coach-ai', '/coach/ai', 'ipad'],
  ['program-editor', '/coach/programs/m1', 'ipad'],
  ['member-today', '/member', 'phone'],
  ['member-calendar', '/member/calendar', 'phone'],
  ['member-book', '/member/book', 'phone'],
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

for (const lang of ['en', 'ar']) {
  for (const [name, path, size, prepare] of SCREENS) {
    const ctx = await browser.newContext({ viewport: SIZES[size], deviceScaleFactor: 2 })
    const page = await ctx.newPage()
    page.on('pageerror', (e) => errors.push(`${lang} ${path}: ${e.message}`))
    page.on('console', (m) => m.type() === 'error' && errors.push(`${lang} ${path}: ${m.text()}`))

    await page.addInitScript((l) => {
      localStorage.setItem('aigym.lang', l)
      localStorage.setItem('aigym.signedIn', '1')
      // These screens capture steady state, not the one-time onboarding
      // overlay — same reason aigym.signedIn is pre-seeded above.
      localStorage.setItem('aigym.tour.manager.seen', '1')
      localStorage.setItem('aigym.tour.coach.seen', '1')
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

    // The tab bar is a flex child of an h-dvh column, so two things must hold on every
    // screen: the PAGE must not scroll (only <main> does), and the bar must sit exactly at
    // the bottom of the viewport. The previous guard only measured padding, which is why
    // the bar-floating-mid-screen bug reached a real phone.
    if (size === 'phone') {
      const shell = await page.evaluate(() => {
        const nav = document.querySelector('[data-tabbar]')
        const main = document.querySelector('main')
        if (!nav || !main) return null
        main.scrollTop = main.scrollHeight
        return {
          pageScrolls: document.documentElement.scrollHeight > window.innerHeight + 1,
          navGap: Math.round(window.innerHeight - nav.getBoundingClientRect().bottom),
          mainScrolls: main.scrollHeight > main.clientHeight,
        }
      })
      if (shell?.pageScrolls) {
        errors.push(`${lang} ${path}: the page scrolls — only <main> should`)
      }
      if (shell && Math.abs(shell.navGap) > 1) {
        errors.push(`${lang} ${path}: tab bar is ${shell.navGap}px off the viewport bottom`)
      }
    }

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
