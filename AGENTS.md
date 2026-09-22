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
- **Never make the tab bar `fixed`, and never use `h-full` for the shell.** It is
  `h-dvh flex flex-col` with `main` as `flex-1 min-h-0 overflow-y-auto`. Safari's collapsing
  address bar breaks `height:100%`, which left the bar floating mid-screen on a real phone.
- **Yellow is identity, not status.** Chrome, logo, and one headline action per screen.
  Green/amber/red still mean payment state only.
- **Never write a literal `←`.** It does not mirror and points forward in Arabic. Use
  `BackLink`.

## Branching

| Branch | Job |
|---|---|
| `develop` | All work. Commit here. |
| `main` | What is deployed. Only ever reached by a merge from `develop`. |

**A push to `develop` deploys nothing. A merge to `main` deploys.** That separation is the
whole point: the live URL is in the investor deck and goes out to gym owners, so it should
only move when someone decides it should.

```bash
# releasing
git checkout main && git merge --no-ff develop && git push origin main
git checkout develop
```

`--no-ff` keeps a visible release point instead of a flat history, so "what shipped, and
when" stays answerable from the log.

`claude/gym-management-app-3wvw97` is an old session branch, four commits behind and fully
merged. Ignore it; it is kept only because deleting someone's branch is not ours to do.

## Deploy

Live at **https://triple-a.up.railway.app** (Railway project `aigym`, service
`web`, region `europe-west4`). Railway watches **`main`** and redeploys anything under
`apps/web/**` — so a deploy follows a merge from `develop`, not a direct push.

`apps/web/Dockerfile` builds with Node and serves with Caddy; `apps/web/Caddyfile` carries the
SPA fallback, the `/health` endpoint, and the cache headers. **There is no `railway.json` and
there must not be** — Config as Code is deprecated, new services cannot opt into it, and
existing files stop being read on 2026-12-01. Service settings live on the service.

`apps/api` runs as a second Railway service (`api`) plus a Postgres service, both in the
same project — provisioned and live, and `web`'s `VITE_API_URL` now points at it, so
manager screens on the live URL read and write real data. No real manager account exists
on the live database yet (seeding is still manual, see `docs/DEPLOY.md`). Setup and
current status: `docs/DEPLOY.md`.

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
| `offline-sync` | anything that writes data — the server half is built (Phase 2), the client outbox is Phase 3+ |
| `backend-conventions` | working in `apps/api` |
| `tenancy-rules` | touching a gym-scoped table, a Row-Level Security policy, or anything that reads/writes across gyms |
| `generate-migration` | adding or changing an Alembic migration |
| `ai-prompt-eval` | changing a prompt, a guardrail, or anything under `app/ai/` |

## Phases

See `docs/ROADMAP.md`. Phase 2 (backend: tenancy, auth, members, money) is done — manager
screens run on the API when `VITE_API_URL` is set, mocks otherwise. Coach and member
screens are still Phase 1: mock data, no backend, no auth. Do not add API calls to a coach
or member screen until Phase 3/4 gives that surface a reason to.
