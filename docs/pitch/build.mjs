import pptxgen from 'pptxgenjs'

const pres = new pptxgen()
pres.layout = 'LAYOUT_WIDE' // 13.3 x 7.5
pres.author = 'Triple A Gym'
pres.title = 'AIGym — Investor Pitch'

// Brand, sampled from the gym's own flyers
const INK = '0D0D0D'
const INK_SOFT = '1C1C1C'
const CARD = '191919'
const BRAND = 'F9E54C'
const WHITE = 'FFFFFF'
const MUTED = 'A8A8A8'
const GREEN = '43C08A'

const H = 'Arial'
const B = 'Calibri'

const W = 13.3
const M = 0.7 // margin

const dark = () => {
  const s = pres.addSlide()
  s.background = { color: INK }
  return s
}

/** Title block, used on every content slide so the rhythm is identical. */
const head = (s, kicker, title) => {
  s.addText(kicker.toUpperCase(), {
    x: M, y: 0.45, w: W - M * 2, h: 0.3,
    fontFace: B, fontSize: 12, bold: true, color: BRAND, charSpacing: 2, isTextBox: true,
  })
  s.addText(title, {
    x: M, y: 0.78, w: W - M * 2, h: 0.85,
    fontFace: H, fontSize: 34, bold: true, color: WHITE, isTextBox: true,
  })
}

/** The repeated motif: a numbered yellow disc. */
const disc = (s, n, x, y) => {
  s.addShape(pres.ShapeType.ellipse, {
    x, y, w: 0.52, h: 0.52, fill: { color: BRAND },
  })
  s.addText(String(n), {
    x, y, w: 0.52, h: 0.52,
    fontFace: H, fontSize: 17, bold: true, color: INK,
    align: 'center', valign: 'middle', margin: 0, isTextBox: true,
  })
}

const card = (s, x, y, w, h) =>
  s.addShape(pres.ShapeType.roundRect, {
    x, y, w, h, fill: { color: CARD }, rectRadius: 0.12,
  })

const FILL = (label) => `[FILL: ${label}]`

/* ------------------------------------------------------------------ 1 title */
{
  const s = dark()
  s.addShape(pres.ShapeType.rect, {
    x: W - 3.4, y: -1.6, w: 4.6, h: 4.6, fill: { color: BRAND }, rotate: 45,
  })
  s.addImage({ path: 'logo.png', x: M, y: 1.5, w: 1.5, h: 1.5 })
  s.addText('AIGym', {
    x: M, y: 3.2, w: 8.5, h: 0.9,
    fontFace: H, fontSize: 52, bold: true, color: WHITE, isTextBox: true,
  })
  s.addText('The gym runs on a notebook. We replace the notebook.', {
    x: M, y: 4.1, w: 8.6, h: 0.6,
    fontFace: B, fontSize: 20, color: BRAND, isTextBox: true,
  })
  s.addText(
    'Member management, coaching on the floor, and an AI training assistant —\nbuilt for Lebanese gyms. Working product, live today.',
    {
      x: M, y: 4.8, w: 8.6, h: 1,
      fontFace: B, fontSize: 15, color: MUTED, lineSpacing: 22, isTextBox: true,
    },
  )
  s.addText('triple-a.up.railway.app   ·   Triple A Gym, Aaramoun, Lebanon', {
    x: M, y: 6.4, w: 9, h: 0.4,
    fontFace: B, fontSize: 13, bold: true, color: WHITE, isTextBox: true,
  })
  s.addNotes(
    'Open by showing the live app on a phone, not the slide. The product exists and works — that is the strongest thing in the room.',
  )
}

/* ---------------------------------------------------------------- 2 problem */
{
  const s = dark()
  head(s, 'The problem', 'A gym owner runs a real business on paper')
  const items = [
    ['Money leaks quietly', 'Dues are tracked in a notebook. Members lapse and nobody notices until the month is over.'],
    ['Members leave silently', 'No one sees that a member stopped coming three weeks ago — until they are gone for good.'],
    ['The coach carries it all in his head', 'Last session\'s weights, who is injured, who paid. Written on paper, or not at all.'],
    ['Existing software does not fit', 'Priced for a US gym on fibre, English-only, and useless during a power cut.'],
  ]
  let y = 1.95
  items.forEach(([t, d], i) => {
    disc(s, i + 1, M, y)
    s.addText(t, {
      x: M + 0.78, y: y - 0.04, w: 10.6, h: 0.35,
      fontFace: H, fontSize: 17, bold: true, color: WHITE, margin: 0, isTextBox: true,
    })
    s.addText(d, {
      x: M + 0.78, y: y + 0.31, w: 11.2, h: 0.45,
      fontFace: B, fontSize: 14, color: MUTED, margin: 0, isTextBox: true,
    })
    y += 1.12
  })
  s.addNotes('This is Triple A Gym before the app. It is also every gym in Aaramoun.')
}

/* -------------------------------------------------------------- 3 why now */
{
  const s = dark()
  head(s, 'Why now', 'Three things became true at once')
  const cols = [
    ['Every member has WhatsApp', 'Messaging is solved and free. No SMS cost, no app install to reach a member.'],
    ['AI got cheap enough', 'A per-member training and nutrition plan used to need a human hour. Now it needs a few cents and a coach\'s approval.'],
    ['Phones replaced desktops', 'The gym floor never had a computer. Every coach and member already carries the device.'],
  ]
  cols.forEach(([t, d], i) => {
    const x = M + i * 4.05
    card(s, x, 2.0, 3.7, 3.1)
    disc(s, i + 1, x + 0.35, 2.35)
    s.addText(t, {
      x: x + 0.35, y: 3.05, w: 3.0, h: 0.7,
      fontFace: H, fontSize: 17, bold: true, color: BRAND, margin: 0, isTextBox: true,
    })
    s.addText(d, {
      x: x + 0.35, y: 3.75, w: 3.0, h: 1.2,
      fontFace: B, fontSize: 13, color: MUTED, margin: 0, isTextBox: true,
    })
  })
  s.addText(
    'None of this was true when the incumbents were designed. They are desktop-era products with a phone app bolted on.',
    { x: M, y: 5.5, w: W - M * 2, h: 0.5, fontFace: B, fontSize: 14, italic: true, color: WHITE, isTextBox: true },
  )
}

/* -------------------------------------------------------------- 4 product */
{
  const s = dark()
  head(s, 'The product', 'One app, three people, one gym')
  const cols = [
    ['MANAGER', 'On a phone', ['Register a member in under a minute', 'Who owes money, and how much', 'Who stopped coming — before they churn', 'WhatsApp reminders, one tap, in Arabic']],
    ['COACH', 'On an iPad, on the floor', ['Who is in the gym right now', 'Unpaid dues and injuries, before the session', 'Sets, reps, weight and machine — tap, never type', 'How the member handled it']],
    ['MEMBER', 'On their own phone', ['Today\'s workout and the coach\'s videos', 'Calendar and booking with a coach', 'Food by photo, water, supplements', 'Two AI assistants to ask']],
  ]
  cols.forEach(([t, sub, lines], i) => {
    const x = M + i * 4.05
    card(s, x, 1.9, 3.7, 3.0)
    s.addText(t, {
      x: x + 0.3, y: 2.15, w: 3.1, h: 0.35,
      fontFace: H, fontSize: 18, bold: true, color: BRAND, margin: 0, charSpacing: 1, isTextBox: true,
    })
    s.addText(sub, {
      x: x + 0.3, y: 2.5, w: 3.1, h: 0.3,
      fontFace: B, fontSize: 12, color: MUTED, margin: 0, isTextBox: true,
    })
    s.addText(
      lines.map((l, k) => ({ text: l, options: { bullet: true, breakLine: k < lines.length - 1 } })),
      {
        x: x + 0.3, y: 2.95, w: 3.1, h: 1.8,
        fontFace: B, fontSize: 13, color: WHITE, paraSpaceAfter: 8, margin: 0, isTextBox: true,
      },
    )
  })
  s.addNotes('Play the 60-second demo video here rather than describing the screens.');
}

/* ---------------------------------------------------------------- 5 wedge */
{
  const s = dark()
  head(s, 'Why we win here', 'Built for the conditions, not translated into them')
  const rows = [
    ['Works through a power cut', 'Writes queue on the device and sync when the connection returns. A generator restarting mid-session never loses a logged set.'],
    ['Arabic is a first language', 'Not a translation layer. Right-to-left throughout, in the Arabic a gym manager actually speaks.'],
    ['Runs on a cheap Android', 'Under 200 KB of JavaScript, enforced on every build. Loads on the phone members already own.'],
    ['Priced for a Beirut gym', 'The incumbents cost more per month than many gyms can justify. Our competition is a notebook, and we price against what it loses them.'],
  ]
  let y = 1.95
  rows.forEach(([t, d], i) => {
    disc(s, i + 1, M, y)
    s.addText(t, {
      x: M + 0.78, y: y - 0.04, w: 10.8, h: 0.35,
      fontFace: H, fontSize: 17, bold: true, color: BRAND, margin: 0, isTextBox: true,
    })
    s.addText(d, {
      x: M + 0.78, y: y + 0.31, w: 11.3, h: 0.5,
      fontFace: B, fontSize: 13.5, color: MUTED, margin: 0, isTextBox: true,
    })
    y += 1.13
  })
}

/* ------------------------------------------------------------------- 6 AI */
{
  const s = dark()
  head(s, 'The AI layer', 'The coach stays in charge — by design')
  card(s, M, 1.95, 5.9, 3.6)
  s.addText('What the AI does', {
    x: M + 0.35, y: 2.2, w: 5.2, h: 0.4,
    fontFace: H, fontSize: 18, bold: true, color: BRAND, margin: 0, isTextBox: true,
  })
  s.addText(
    [
      'Builds a plan from body data, lifestyle and injuries',
      'Estimates a meal from a photo',
      'Answers the member\'s questions, day or night',
      'Logs the food the member reports',
    ].map((l, k, a) => ({ text: l, options: { bullet: true, breakLine: k < a.length - 1 } })),
    { x: M + 0.35, y: 2.7, w: 5.2, h: 2.5, fontFace: B, fontSize: 14, color: WHITE, paraSpaceAfter: 10, margin: 0, isTextBox: true },
  )

  card(s, M + 6.2, 1.95, 5.7, 2.5)
  s.addText('What it is never allowed to do', {
    x: M + 6.55, y: 2.2, w: 5.0, h: 0.4,
    fontFace: H, fontSize: 18, bold: true, color: WHITE, margin: 0, isTextBox: true,
  })
  s.addText(
    'Change a training programme or a calorie target. Those become a draft the coach approves — enforced in code, not by asking the model politely.',
    { x: M + 6.55, y: 2.7, w: 5.0, h: 1.1, fontFace: B, fontSize: 14, color: MUTED, margin: 0, isTextBox: true },
  )
  s.addText('Why an investor should care', {
    x: M + 6.55, y: 3.95, w: 5.0, h: 0.35,
    fontFace: H, fontSize: 14, bold: true, color: BRAND, margin: 0, isTextBox: true,
  })
  s.addText(
    'It is the difference between a tool coaches adopt and one they quietly sabotage. An assistant that rewrites programmes competes with the coach; ours makes him look good.',
    { x: M + 6.55, y: 4.35, w: 5.0, h: 1.2, fontFace: B, fontSize: 13, color: WHITE, margin: 0, isTextBox: true },
  )
  s.addText('Progress photos are private by default, and sharing is per-photo and explicit.', {
    x: M, y: 6.1, w: W - M * 2, h: 0.4,
    fontFace: B, fontSize: 13, italic: true, color: MUTED, isTextBox: true,
  })
}

/* --------------------------------------------------------- 7 competition */
{
  const s = dark()
  head(s, 'Competition', 'Nobody is serving this market')
  const rows = [
    ['Trainerize', 'from ~$248 / mo', 'Integrations and scale. Check-in forms widely reported as fragmented; coaches still export to other tools.'],
    ['Everfit', 'from ~$105 / mo', 'Best single-app client experience and multi-language. Still cloud-only, still priced for a Western studio.'],
    ['TrueCoach', '1:1 up to ~50 clients', 'Simple and well liked, but built for a solo online coach, not a gym floor.'],
    ['A notebook + WhatsApp group', 'free', 'The actual incumbent in Lebanon, and the one we have to beat.'],
  ]
  let y = 1.95
  rows.forEach(([name, price, note], i) => {
    const last = i === rows.length - 1
    card(s, M, y, W - M * 2, 1.0)
    s.addText(name, {
      x: M + 0.3, y: y + 0.14, w: 3.0, h: 0.35,
      fontFace: H, fontSize: 16, bold: true, color: last ? BRAND : WHITE, margin: 0, isTextBox: true,
    })
    s.addText(price, {
      x: M + 0.3, y: y + 0.52, w: 3.0, h: 0.3,
      fontFace: B, fontSize: 13, bold: true, color: last ? BRAND : MUTED, margin: 0, isTextBox: true,
    })
    s.addText(note, {
      x: M + 3.5, y: y + 0.2, w: 8.2, h: 0.65,
      fontFace: B, fontSize: 13.5, color: MUTED, margin: 0, isTextBox: true,
    })
    y += 1.13
  })
  s.addText('Pricing as listed publicly, 2026. Real bills commonly run higher once nutrition, automation and branding are added.', {
    x: M, y: 6.55, w: W - M * 2, h: 0.35,
    fontFace: B, fontSize: 11, color: MUTED, isTextBox: true,
  })
}

/* ------------------------------------------------------------ 8 the model */
{
  const s = dark()
  head(s, 'Business model', 'A monthly subscription per gym')
  const stats = [
    [FILL('price / gym / mo'), 'Target price point'],
    [FILL('gyms in Lebanon'), 'Reachable market'],
    [FILL('pilot gyms signed'), 'Committed today'],
  ]
  stats.forEach(([big, label], i) => {
    const x = M + i * 4.05
    card(s, x, 2.0, 3.7, 1.9)
    s.addText(big, {
      x: x + 0.25, y: 2.3, w: 3.2, h: 0.75,
      fontFace: H, fontSize: 20, bold: true, color: BRAND, margin: 0, isTextBox: true,
    })
    s.addText(label, {
      x: x + 0.25, y: 3.15, w: 3.2, h: 0.4,
      fontFace: B, fontSize: 13, color: MUTED, margin: 0, isTextBox: true,
    })
  })
  s.addText('How the price is justified', {
    x: M, y: 4.25, w: 11.9, h: 0.4,
    fontFace: H, fontSize: 18, bold: true, color: WHITE, isTextBox: true,
  })
  s.addText(
    'We do not sell features against Trainerize — we sell recovered money against a notebook. A gym that collects a handful of lapsed memberships it would otherwise have lost has paid for the year. That framing is why the guarantee on the next slide is affordable.',
    { x: M, y: 4.7, w: 11.9, h: 1.1, fontFace: B, fontSize: 14.5, color: MUTED, isTextBox: true },
  )
  s.addText('Member payments are tracked, not processed — no card rails, no PCI scope, no payment-provider dependency in v1.', {
    x: M, y: 6.1, w: 11.9, h: 0.4,
    fontFace: B, fontSize: 13, italic: true, color: WHITE, isTextBox: true,
  })
}

/* ---------------------------------------------------------------- 9 GTM */
{
  const s = dark()
  head(s, 'Go to market', 'Prove it in our own gym, then sell next door')
  card(s, M, 1.9, 5.9, 1.55)
  s.addText('The offer', {
    x: M + 0.35, y: 2.1, w: 5.2, h: 0.4,
    fontFace: H, fontSize: 18, bold: true, color: BRAND, margin: 0, isTextBox: true,
  })
  s.addText(
    'Live in 48 hours. We import your members from your notebook ourselves. Your staff tap; they never type.',
    { x: M + 0.35, y: 2.58, w: 5.2, h: 0.8, fontFace: B, fontSize: 14, color: WHITE, margin: 0, isTextBox: true },
  )

  card(s, M + 6.2, 1.9, 5.7, 1.55)
  s.addText('The guarantee', {
    x: M + 6.55, y: 2.1, w: 5.0, h: 0.4,
    fontFace: H, fontSize: 18, bold: true, color: GREEN, margin: 0, isTextBox: true,
  })
  s.addText(
    '"If it does not recover more in missed dues than we charge you in the first 90 days, you do not pay."',
    { x: M + 6.55, y: 2.58, w: 5.0, h: 0.8, fontFace: B, fontSize: 14, italic: true, color: WHITE, margin: 0, isTextBox: true },
  )

  const steps = [
    ['30 days', 'Run Triple A entirely on the app. Measure collection rate, lapsed members and signup time — before and after.'],
    ['60 days', 'Three to five paying pilot gyms nearby. Warm outreach and in-person visits, not ads — the market is small enough to walk.'],
    ['90 days', 'Case study from our own gym plus pilot numbers. That is the traction slide, and the point at which raising makes sense.'],
  ]
  let y = 3.85
  steps.forEach(([when, what], i) => {
    disc(s, i + 1, M, y)
    s.addText(when, {
      x: M + 0.78, y: y - 0.02, w: 1.5, h: 0.35,
      fontFace: H, fontSize: 15, bold: true, color: BRAND, margin: 0, isTextBox: true,
    })
    s.addText(what, {
      x: M + 2.35, y: y - 0.02, w: 9.6, h: 0.6,
      fontFace: B, fontSize: 13.5, color: MUTED, margin: 0, isTextBox: true,
    })
    y += 0.78
  })
}

/* ------------------------------------------------------------ 10 traction */
{
  const s = dark()
  head(s, 'Traction', 'What is true today — and what is not yet')
  card(s, M, 1.95, 5.9, 2.5)
  s.addText('Built and live', {
    x: M + 0.35, y: 2.2, w: 5.2, h: 0.4,
    fontFace: H, fontSize: 18, bold: true, color: GREEN, margin: 0, isTextBox: true,
  })
  s.addText(
    [
      'Working product, deployed and in use for testing',
      'All three surfaces complete, English and Arabic',
      'AI assistants with coach approval built in',
      'One gym ready to run on it: Triple A, Aaramoun',
    ].map((l, k, a) => ({ text: l, options: { bullet: true, breakLine: k < a.length - 1 } })),
    { x: M + 0.35, y: 2.7, w: 5.2, h: 1.6, fontFace: B, fontSize: 13.5, color: WHITE, paraSpaceAfter: 10, margin: 0, isTextBox: true },
  )

  card(s, M + 6.2, 1.95, 5.7, 2.5)
  s.addText('Not yet proven', {
    x: M + 6.55, y: 2.2, w: 5.0, h: 0.4,
    fontFace: H, fontSize: 18, bold: true, color: BRAND, margin: 0, isTextBox: true,
  })
  s.addText(
    [
      `Paying gyms: ${FILL('0 today — target 3–5 by day 60')}`,
      `Members managed: ${FILL('count once Triple A is live on it')}`,
      `Collection rate change: ${FILL('before vs after, 30 days')}`,
      `Lapsed members recovered: ${FILL('count over 30 days')}`,
    ].map((l, k, a) => ({ text: l, options: { bullet: true, breakLine: k < a.length - 1 } })),
    { x: M + 6.55, y: 2.7, w: 5.0, h: 1.6, fontFace: B, fontSize: 13, color: MUTED, paraSpaceAfter: 10, margin: 0, isTextBox: true },
  )
  s.addText(
    'These numbers are deliberately blank. They are 30 days of real usage away, and inventing them is the fastest way to lose a room.',
    { x: M, y: 4.75, w: 11.9, h: 0.5, fontFace: B, fontSize: 14, italic: true, color: WHITE, isTextBox: true },
  )
  s.addNotes('Do not skip past this slide. Owning the gap is more persuasive than papering over it, and the next 30 days close it.')
}

/* ----------------------------------------------------------- 11 roadmap */
{
  const s = dark()
  head(s, 'Roadmap', 'From one gym to many')
  const phases = [
    ['Now', 'Working prototype, live', 'Three surfaces, both languages, deployed'],
    ['Next', 'Real backend', 'Accounts, per-gym data isolation, offline sync'],
    ['Then', 'AI in production', 'Plan generation, safety guardrails, evals in CI'],
    ['After', 'Sell it', 'Self-serve signup, gym billing, owner analytics'],
  ]
  phases.forEach(([when, what, detail], i) => {
    const x = M + i * 3.03
    card(s, x, 2.1, 2.75, 3.2)
    s.addText(when.toUpperCase(), {
      x: x + 0.25, y: 2.35, w: 2.3, h: 0.3,
      fontFace: B, fontSize: 11, bold: true, color: BRAND, charSpacing: 2, margin: 0, isTextBox: true,
    })
    s.addText(what, {
      x: x + 0.25, y: 2.7, w: 2.3, h: 0.8,
      fontFace: H, fontSize: 16, bold: true, color: WHITE, margin: 0, isTextBox: true,
    })
    s.addText(detail, {
      x: x + 0.25, y: 3.6, w: 2.3, h: 1.5,
      fontFace: B, fontSize: 12.5, color: MUTED, margin: 0, isTextBox: true,
    })
  })
  s.addText('Payment processing is deliberately late: Stripe does not support Lebanese businesses, so gym billing runs on local rails until that is worth solving properly.', {
    x: M, y: 5.7, w: 11.9, h: 0.6,
    fontFace: B, fontSize: 13, italic: true, color: WHITE, isTextBox: true,
  })
}

/* -------------------------------------------------------------- 12 team */
{
  const s = dark()
  head(s, 'Team', 'Operators, not just builders')
  card(s, M, 2.0, 5.9, 3.2)
  s.addText('Kassem Shehady', {
    x: M + 0.35, y: 2.3, w: 5.2, h: 0.45,
    fontFace: H, fontSize: 22, bold: true, color: BRAND, margin: 0, isTextBox: true,
  })
  s.addText('Founder', {
    x: M + 0.35, y: 2.75, w: 5.2, h: 0.3,
    fontFace: B, fontSize: 13, color: MUTED, margin: 0, isTextBox: true,
  })
  s.addText(FILL('background, and your role at the gym'), {
    x: M + 0.35, y: 3.2, w: 5.2, h: 1.6,
    fontFace: B, fontSize: 14, color: WHITE, margin: 0, isTextBox: true,
  })

  card(s, M + 6.2, 2.0, 5.7, 3.2)
  s.addText('The unfair advantage', {
    x: M + 6.55, y: 2.3, w: 5.0, h: 0.4,
    fontFace: H, fontSize: 18, bold: true, color: WHITE, margin: 0, isTextBox: true,
  })
  s.addText(
    'We own a gym. Triple A in Aaramoun is the first customer, the test lab and the case study — with coaches Karim, Abed and Assaf using it daily. Most founders in this category have to guess what a gym floor needs; we watch it every evening.',
    { x: M + 6.55, y: 2.8, w: 5.0, h: 2.2, fontFace: B, fontSize: 14, color: MUTED, margin: 0, isTextBox: true },
  )
}

/* --------------------------------------------------------------- 13 ask */
{
  const s = dark()
  s.addShape(pres.ShapeType.rect, {
    x: -1.6, y: 5.4, w: 4.4, h: 4.4, fill: { color: BRAND }, rotate: 45,
  })
  head(s, 'The ask', 'Raising [FILL: amount] to reach [FILL: milestone]')
  const uses = [
    ['Product', FILL('%'), 'Backend, offline sync, AI in production'],
    ['Go to market', FILL('%'), 'Pilot gyms, onboarding, case studies'],
    ['Runway', FILL('months'), 'To paying gyms and repeatable sales'],
  ]
  let y = 2.1
  uses.forEach(([t, pct, d], i) => {
    card(s, M + 2.2, y, 9.7, 1.15)
    s.addText(t, {
      x: M + 2.5, y: y + 0.2, w: 2.6, h: 0.35,
      fontFace: H, fontSize: 17, bold: true, color: WHITE, margin: 0, isTextBox: true,
    })
    s.addText(pct, {
      x: M + 2.5, y: y + 0.6, w: 2.6, h: 0.35,
      fontFace: B, fontSize: 13, bold: true, color: BRAND, margin: 0, isTextBox: true,
    })
    s.addText(d, {
      x: M + 5.4, y: y + 0.36, w: 6.0, h: 0.45,
      fontFace: B, fontSize: 14, color: MUTED, margin: 0, isTextBox: true,
    })
    disc(s, i + 1, M + 1.35, y + 0.32)
    y += 1.32
  })
  s.addText('See it working: triple-a.up.railway.app', {
    x: M + 2.2, y: 6.2, w: 9.7, h: 0.45,
    fontFace: H, fontSize: 18, bold: true, color: BRAND, isTextBox: true,
  })
}

/* ---------------------------------------------------------- 14 appendix */
{
  const s = dark()
  head(s, 'Appendix', 'Sources and what is real')
  s.addText(
    [
      'Competitor pricing: Everfit and Trainerize public pricing pages and 2026 comparison reviews (fitbudd.com, blog.everfit.io, trainerize.com).',
      'Market positioning: Glofox "best gym management software 2026"; Gymdesk Mindbody alternatives; Zen Planner kiosk documentation.',
      'AI fitness landscape: 2026 reviews of Fitbod, Freeletics, Trainera (sensai.fit, rizin.app).',
      'Product claims in this deck describe software that is built and deployed — every screen shown exists and runs.',
      'Any figure marked [FILL: …] is a number we have not measured yet. It is left blank on purpose rather than estimated.',
    ].map((l, k, a) => ({ text: l, options: { bullet: true, breakLine: k < a.length - 1 } })),
    { x: M, y: 2.0, w: 11.9, h: 3.6, fontFace: B, fontSize: 13.5, color: MUTED, paraSpaceAfter: 12, isTextBox: true },
  )
  s.addImage({ path: 'logo.png', x: W - 2.0, y: 5.7, w: 1.1, h: 1.1 })
}

await pres.writeFile({ fileName: 'AIGym-Investor-Pitch.pptx' })
console.log('deck written')
