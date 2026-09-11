/**
 * Records a captioned walkthrough of the real app.
 *
 *   npm run build && npx vite preview --port 4173 &   (or Caddy on :4173)
 *   node scripts/demo.mjs en ./out
 *
 * Playwright writes .webm (its bundled ffmpeg is VP8-only). Transcode to H.264 MP4
 * afterwards or it will not play on an iPhone or forward through WhatsApp on iOS.
 */
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'

const LANG = process.argv[2] === 'ar' ? 'ar' : 'en'
const OUT = process.argv[3] ?? './demo'
const BASE = process.env.BASE ?? 'http://localhost:4173'

// Under the 640px `sm:` breakpoint on purpose — this must film the phone layout.
const SIZE = { width: 600, height: 1300 }

const CAPTIONS = {
  en: {
    title: 'Triple A Gym — Aaramoun',
    subtitle: 'One app for the front desk, the floor, and the member',
    manager: 'The manager sees who came, who owes, and what was collected',
    dues: 'One tap sends a WhatsApp reminder — in Arabic, ready to send',
    lapsed: 'And who has quietly stopped coming, before you lose them',
    queue: 'The coach opens the iPad: who is in the gym right now',
    card: 'Before the session: unpaid membership, and recorded injuries',
    food: 'What did you eat today? Four taps, no keyboard',
    session: 'Logging a set — weight from last time, the machine, a rest timer',
    ai: 'AI drafts a plan. A human coach approves it before anyone sees it',
    today: 'The member gets their workout, and the coach’s own videos',
    calendar: 'Their calendar, and booking a session with Karim or Abed',
    meal: 'Photograph a meal for an estimate. Water and supplements, tapped',
    chat: 'Ask the assistant anything',
    escalate: 'Change the program? It goes to the coach. Never on its own',
    end: 'triple-a.up.railway.app',
  },
  ar: {
    title: 'نادي تريبل إي — عرمون',
    subtitle: 'تطبيق واحد للإدارة، وللكوتش، وللمشترك',
    manager: 'الإدارة بتشوف مين إجا، مين عليه دفع، وشو تحصّل',
    dues: 'دوسة وحدة وبيروح تذكير على واتساب، جاهز بالعربي',
    lapsed: 'ومين وقّف يجي بالهدول — قبل ما تخسرو',
    queue: 'الكوتش بيفتح الآيباد: مين موجود بالنادي هلق',
    card: 'قبل ما تبلّش: اشتراك غير مدفوع، وإصابات مسجّلة',
    food: 'شو أكلت اليوم؟ أربع دوسات، بدون كيبورد',
    session: 'تسجيل مجموعة — الوزن من آخر مرة، الجهاز، ووقت الراحة',
    ai: 'الذكاء الاصطناعي بيقترح، والكوتش بيوافق قبل ما يوصل لحدا',
    today: 'المشترك بيشوف تمرينه، وفيديوهات الكوتش',
    calendar: 'روزنامته، وحجز حصة مع كريم أو عبد',
    meal: 'صوّر الأكل وبيجيك تقدير. المي والمكمّلات بدوسة',
    chat: 'اسأل المساعد أي شي',
    escalate: 'بدك تغيّر البرنامج؟ بيروح للكوتش. ما بيقرر لحالو',
    end: 'triple-a.up.railway.app',
  },
}[LANG]

const caption = async (page, textValue) => {
  await page.evaluate((value) => {
    let bar = document.getElementById('demo-caption')
    if (!bar) {
      bar = document.createElement('div')
      bar.id = 'demo-caption'
      bar.style.cssText = [
        'position:fixed', 'inset-inline:0', 'bottom:0', 'z-index:2147483647',
        'background:#0d0d0d', 'color:#fff', 'padding:22px 24px 26px',
        'font:600 21px/1.35 system-ui,sans-serif', 'text-align:center',
        'border-top:4px solid #f9e54c', 'pointer-events:none',
      ].join(';')
      document.body.appendChild(bar)
    }
    bar.textContent = value
  }, textValue)
}

const card = async (page, heading, sub) => {
  await page.evaluate(
    ({ heading: h, sub: s }) => {
      const el = document.createElement('div')
      el.id = 'demo-card'
      el.style.cssText = [
        'position:fixed', 'inset:0', 'z-index:2147483647', 'background:#0d0d0d',
        'display:flex', 'flex-direction:column', 'align-items:center',
        'justify-content:center', 'gap:18px', 'text-align:center', 'padding:40px',
      ].join(';')
      el.innerHTML =
        `<img src="/logo.png" width="132" height="132" style="border-radius:28px">` +
        `<div style="font:800 34px/1.2 system-ui,sans-serif;color:#fff">${h}</div>` +
        `<div style="font:600 20px/1.4 system-ui,sans-serif;color:#f9e54c">${s}</div>`
      document.body.appendChild(el)
    },
    { heading, sub },
  )
}
const clearCard = (page) => page.evaluate(() => document.getElementById('demo-card')?.remove())

const beat = async (page, ms = 3400) => page.waitForTimeout(ms)

mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH ?? '/opt/pw-browsers/chromium',
})
const ctx = await browser.newContext({
  viewport: SIZE,
  recordVideo: { dir: OUT, size: SIZE },
  locale: LANG === 'ar' ? 'ar-LB' : 'en-GB',
})
const page = await ctx.newPage()
await page.addInitScript((l) => {
  localStorage.setItem('aigym.lang', l)
  localStorage.setItem('aigym.signedIn', '1')
}, LANG)

const go = async (path, text) => {
  await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle' })
  await caption(page, text)
  await beat(page)
}

// ---- title -----------------------------------------------------------------
await page.goto(`${BASE}/manager`, { waitUntil: 'networkidle' })
await card(page, CAPTIONS.title, CAPTIONS.subtitle)
await beat(page, 3000)
await clearCard(page)

// ---- manager ---------------------------------------------------------------
await go('/manager', CAPTIONS.manager)
await caption(page, CAPTIONS.dues)
await beat(page)
await go('/manager/lapsed', CAPTIONS.lapsed)

// ---- coach -----------------------------------------------------------------
await go('/coach', CAPTIONS.queue)
await go('/coach/member/m1', CAPTIONS.card)
await caption(page, CAPTIONS.food)
await page.getByRole('button').nth(4).click().catch(() => {})
await beat(page)

await go('/coach/session/m1', CAPTIONS.session)
for (const _ of [0, 1]) {
  await page.getByRole('button').filter({ hasText: /\d/ }).last().click().catch(() => {})
  await page.waitForTimeout(700)
}
await beat(page, 2600)
await go('/coach/ai', CAPTIONS.ai)

// ---- member ----------------------------------------------------------------
await go('/member', CAPTIONS.today)
await go('/member/calendar', CAPTIONS.calendar)
await go('/member/food', CAPTIONS.meal)
await go('/member/chat/training', CAPTIONS.chat)
await caption(page, CAPTIONS.escalate)
await page.getByRole('button').nth(3).click().catch(() => {})
await beat(page, 4200)

// ---- end card --------------------------------------------------------------
await card(page, CAPTIONS.title, CAPTIONS.end)
await beat(page, 3000)

await ctx.close()
await browser.close()
console.log(`recorded ${LANG} → ${OUT}`)
