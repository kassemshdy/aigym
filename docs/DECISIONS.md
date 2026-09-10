# Decisions

Each entry is a decision that is expensive to reverse, with the reason and the cost of
being wrong. Add to it rather than rewriting history.

## 1. Lebanon is the target market

Everything else follows from this. Lebanese gyms run through power cuts, on patchy
internet, on mid-range Android phones, in Arabic, and their real alternative to this
product is a WhatsApp group and a paper notebook — not Trainerize at $248/month.

## 2. USD only

Plans, payments, and reports are one currency. No exchange-rate field, no dual display, no
re-pricing as a rate moves, no conversion bugs.

*Cost if wrong:* adding LBP later means a currency column on `payments` and a per-gym rate
table. Contained, because money is only formatted in one place (`lib/format.ts`).

## 3. Membership payments are tracked, not processed

The manager marks paid/unpaid. No cards, no PCI scope, no processor account.

*Open question for Phase 6:* billing gym owners for the SaaS itself. Stripe does not
support Lebanese businesses, so the realistic options are collecting via Whish/OMT/bank
transfer and marking gyms paid manually, or incorporating elsewhere. Nothing in Phases 1–5
may assume a card is on file.

## 4. WhatsApp deep links, sent by a human

The app composes an Arabic message and opens `wa.me`; a person taps send. No Business API,
no template approval, no per-message cost, and the gym's number does not get reported for
automated blasts. Automation is a Phase 6 question, only if gyms ask for it.

## 5. Video is unlisted YouTube/Vimeo embeds

Zero hosting cost, zero transcoding, works on day one.

**Known limitation, stated plainly:** an unlisted link is not access control. Anyone who
gets the link can watch forever, including ex-members. `videos.provider` +
`videos.external_id` keep this reversible — moving to Cloudflare Stream with signed URLs
is a provider change, not a rewrite.

## 6. FastAPI + React, not Next.js

Python backend for the AI layer, React SPA frontend, deployed as separate Railway
services. Explicitly chosen over Next.js.

## 7. Multi-tenant from day one, defended twice

Every tenant table carries `gym_id`, enforced in the service layer **and** by Postgres
Row-Level Security. A service-layer bug then returns an empty set instead of leaking
another gym's members. This is the highest-stakes correctness property in the product and
it gets its own test job in CI.

## 8. 200 KB gzipped JS budget

Enforced in CI. Raising it requires an entry in this file saying what users get in
exchange. This is why there is no charting library — `Sparkline` is hand-written SVG.

## 9. Agent tooling follows Sentry's layout

`AGENTS.md` is the source of truth, `CLAUDE.md` is a one-line pointer to it, skills live in
`.agents/skills/` with `.claude/skills` symlinked to that directory.
