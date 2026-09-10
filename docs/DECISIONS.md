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

## 10. Chat agents answer and log, but never change the program

Two assistants the member can talk to: a **nutrition assistant** and a **bodybuilding
assistant**. Both answer freely and may log food the member reports. Neither can change
the training program or the calorie targets — a request like "add weight to my bench"
becomes a pending draft in the coach's inbox, and the member is told so in the reply.

This keeps the approval rule that already governs generated plans: nothing reaches a
member's body without a human coach seeing it. It also protects the coach's relationship
with their own clients — an assistant that quietly rewrites a program is competing with
the coach, not helping them.

*Enforced in code, not in the prompt.* The reply carries a `draft` flag and the store
routes it to the coach; the model is never the thing standing between a suggestion and the
member's program.

## 11. Progress photos are private by default

Members can add progress photos. Three rules, none of them opt-out:

1. **Private by default** — `shared_with_coach` starts false, always.
2. **Sharing is per-photo and explicit** — a separate confirm step, never a blanket
   setting, never a consequence of joining a gym.
3. **Delete really deletes** — including the stored file, not just the row.

Body photos are the most sensitive data in the product. A gym owner or coach browsing
members' bodies because the default allowed it is the kind of harm that ends a product,
and "the member could have turned it off" is not a defence.

Food photos carry none of this weight and are treated as ordinary log data.

## 12. Food photo estimates always get a confirm step

The member photographs a meal, the model estimates it, and **the member confirms or
corrects before anything is logged** — with a portion stepper for the common case where
the food is right and the amount is not.

An estimate that logs itself silently is a number nobody trusts and everybody stops
reading. The confirm step is also the cheapest training signal we will ever get: the
difference between what the model guessed and what the member corrected.

## 13. Member auth is phone + code, no email, no password

Most members here do not use email, and a password is one more thing to forget at the
door. The code goes over WhatsApp, which everyone already has open.

## 14. English is the default language, Arabic is equal

The app opens in English and LTR. Arabic remains fully supported — same key coverage, same
RTL layout rules, same plain-Levantine wording — and the toggle is one tap in the header.

This reverses the earlier Arabic-default choice. Nothing else changed: the RTL checks still
run in CI, seed content is still bilingual `{ ar, en }` pairs, and a layout that only works
in English still fails review. Defaulting to English is a starting point, not a demotion of
Arabic.
