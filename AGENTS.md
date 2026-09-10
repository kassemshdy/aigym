# AIGym — Development Guide for AI Agents

## Core principle

**AGENTS.md files are the source of truth for agent instructions.** When you change how
this project should be worked on, update the relevant `AGENTS.md` — the nearest one to the
code you touched. `CLAUDE.md` is a pointer to this file and holds no content of its own.

Area guides:

- `apps/web/AGENTS.md` — the React app
- `apps/api/AGENTS.md` — the FastAPI service (Phase 2)

## What this is

A multi-tenant SaaS gym platform for **Lebanese gyms**, with three surfaces — manager,
coach-on-an-iPad, and member — plus an AI layer that drafts training and nutrition plans
for a coach to approve, and two assistants the member can chat with.

## The five constraints that decide arguments

Every design question gets settled against these before anything else. They come from
the market, not from taste.

1. **Power cuts and dead internet are normal.** The client is a PWA; writes queue locally
   and replay. A generator kicking in mid-session must never lose a logged set.
2. **Cheap Android phones, not new iPhones.** Initial JS stays under **200 KB gzipped**,
   enforced by `npm run budget` in CI. A charting or animation library costs more than
   the feature it draws.
3. **Big buttons, few screens, no jargon.** One question per screen, 48px touch targets
   (56px on the coach's iPad), plain Levantine Arabic. A manager who has never used
   software should need no training.
4. **Minimal typing for the coach.** Tap, don't type: steppers pre-filled from last
   session, calorie *bands* instead of numbers. Free text is always optional.
5. **English default, Arabic equal.** English is the default language and LTR the default
   direction, but Arabic is a first-class language, not a translation bolted on: every RTL
   rule holds, and seed content ships as `{ ar, en }` pairs. A layout that only works in
   English is broken.

## Commands

```bash
cd apps/web
npm install
npm run dev        # http://localhost:5173
npm run verify     # typecheck + RTL check + build + bundle budget — run before every commit
```

Individually: `npm run typecheck`, `npm run rtl`, `npm run lint`, `npm run build`,
`npm run budget`.

Screenshot every screen in both languages (needs `npm run build` and a running
`npx vite preview --port 4173`):

```bash
node scripts/shots.mjs ./shots
```

It fails on a wrong `dir`, horizontal overflow, or any console error — treat it as a test,
not a screenshot tool.

## Hard rules

- **Never use physical-direction utilities.** `ms-*`/`me-*`/`ps-*`/`pe-*`/`start-*`/`end-*`,
  never `ml-*`/`pl-*`/`left-*`. `npm run rtl` fails the build on these.
- **Never hard-code user-facing text.** Every string goes through `t()`, and every key
  exists in both `en.json` and `ar.json`.
- **Never ship single-language seed content.** Data in `src/mocks/` is an `{ ar, en }`
  pair, read through `text(value, lang)`.
- **Never wrap mixed Arabic-and-number text in `dir="ltr"`.** Wrap only the numeric run,
  in `<bdi className="tnum">`. Putting an Arabic label inside an LTR run scrambles it.
- **Green, amber and red are reserved for payment state.** Never decorative.
- **Do not add a dependency without checking the budget.** `npm run budget` after.
- **Money is USD only.** No currency field, no exchange rate, no conversion. See
  `docs/DECISIONS.md`.
- **An assistant never changes a program or a calorie target.** It answers, and it may log
  food the member reports. Anything touching the plan becomes a draft for the coach —
  enforced by the `draft` flag in code, never by asking the model nicely. Decision 10.
- **Progress photos are private by default.** `sharedWithCoach` starts false, sharing is
  per-photo and explicit, deletion is real. Never add a bulk-share setting or a default
  that shows a member's body to anyone. Decision 11.
- **A food estimate is never logged without the member confirming it.** Decision 12.
- **Never hard-code the tab bar's height.** Use `var(--nav-total)` — it includes
  `env(safe-area-inset-bottom)`, which headless browsers report as `0`. Getting this wrong
  hides content on a real phone while every automated check passes.
- **Never write a literal `←`.** It does not mirror and points forward in Arabic. Use
  `BackLink`.

## Deploy

Live at **https://triple-a.up.railway.app** (Railway project `aigym`, service
`web`, region `europe-west4`). Pushing to `main` redeploys anything under `apps/web/**`.

`apps/web/Dockerfile` builds with Node and serves with Caddy; `apps/web/Caddyfile` carries the
SPA fallback, the `/health` endpoint, and the cache headers. **There is no `railway.json` and
there must not be** — Config as Code is deprecated, new services cannot opt into it, and
existing files stop being read on 2026-12-01. Service settings live on the service.

Full runbook, including how to test the serving layer without Docker: `docs/DEPLOY.md`.

## Skills

Task-specific guides live in `.agents/skills/<name>/SKILL.md` (`.claude/skills` is a
symlink to it). Read the matching skill before the task:

| Skill | Read it before |
|---|---|
| `setup-dev` | first run of the project |
| `design-system` | adding or restyling any component |
| `i18n-rtl` | adding user-facing text, or any layout with direction |
| `perf-budget` | adding a dependency or anything that ships JS |
| `offline-sync` | anything that writes data (Phase 3+) |

Backend skills (`backend-conventions`, `tenancy-rules`, `generate-migration`,
`ai-prompt-eval`) land with the API in Phase 2 — they are deliberately absent rather than
written against code that does not exist yet.

## Phases

See `docs/ROADMAP.md`. Phase 1 (clickable prototype, mock data, no backend) is the current
state. Do not add API calls, auth, or a database until Phase 2 is started.
