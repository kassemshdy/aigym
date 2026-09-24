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

## Where tests run

**The full test suite runs in CI, not in the local loop.** CI fires on every push to
`develop` and `main` (`.github/workflows/ci.yml`), so pushing is how a change gets
verified end to end — the whole suite, the isolation suite in its own job, and the web
build and budget.

Locally, per change:

```bash
cd apps/api && uv run ruff check . && uv run mypy app scripts   # seconds
cd apps/web && npm run typecheck && npm run lint                # seconds
```

Run a *specific* test file when you have just written it or are working against a
failure — committing a test that was never executed is worse than no test, because it
turns one CI round trip into two. Do not run `uv run pytest` with no arguments; that is
what CI is for. `npm run verify` and `node scripts/shots.mjs` are still worth running by
hand after layout work, since a wrong `dir` or an overflow is not something CI can show
you a picture of.

The local Postgres a targeted test needs is not running by default: `service postgresql
start`.

## Deploy

Live at **https://trpa.up.railway.app** (Railway project `aigym`, service
`web`, region `europe-west4`). Railway watches **`main`** and redeploys anything under
`apps/web/**` — so a deploy follows a merge from `develop`, not a direct push.

`apps/web/Dockerfile` builds with Node and serves with Caddy; `apps/web/Caddyfile` carries the
SPA fallback, the `/health` endpoint, and the cache headers. **There is no `railway.json` and
there must not be** — Config as Code is deprecated, new services cannot opt into it, and
existing files stop being read on 2026-12-01. Service settings live on the service.

`apps/api` runs as a second Railway service (`api`), and `web`'s `VITE_API_URL` points at
it, so manager screens on the live URL read and write real data. No real manager account
exists on the live database yet (seeding is still manual, see `docs/DEPLOY.md`).

Two more services sit alongside them:

- **The database is Railway's managed Postgres** (`postgres-ssl:18`), not a raw Docker
  image — so it has scheduled backups, pooling and a data panel. Same PostgreSQL: RLS,
  `DISTINCT ON` and every migration are unchanged. Decision 40.
- **`ops`** shares the `api` image and database and has **no port, no healthcheck and no
  domain** — it is not reachable from the internet. Set `AIGYM_OPS_COMMAND` and press
  Deploy to run one maintenance script. `set_staff_password.py` takes
  `AIGYM_SET_PASSWORD_USER`/`_VALUE` so it works here; anything still prompting on stdin
  needs `railway ssh -s api`, because a deploy has no terminal.
- **`backup`** is the same image on a `0 2 * * *` cron, running `scripts/backup_db.py`
  into the `aigym-backups` bucket. **It is deliberately a second service**: a cron
  schedule turns a Railway service into a cron job that no longer runs on deploy, so
  putting the schedule on `ops` disables `ops`. It holds only the database URL and the
  bucket credentials — not the JWT or onboarding secrets.

**Anything new in `apps/api/scripts/` connects as the migrations role, never the app
role.** The app role is `NOBYPASSRLS` and no `app.gym_id` is set outside a request, so a
gym-scoped read as it returns nothing — which looks like an empty database, not a
permissions error. That trap would have made `backup_db.py` write empty backups that
reported success.

Setup, runbooks and current status: `docs/DEPLOY.md`.

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

See `docs/ROADMAP.md`. Phases 2–6 are built: tenancy/auth/money (2), the coach's floor
tools and the offline outbox (3), member self-service and content (4), the AI layer (5),
and everything needed to sell to a gym (6) — the owner dashboard, staff permissions,
a gym's own prices, branding, member import, and operator billing. Every surface reads and
writes the real API when `VITE_API_URL` is set, and falls back to mocks when it isn't —
keep both branches working for anything new.

Phase 5's AI needs `AIGYM_ANTHROPIC_API_KEY`. Without it the AI routes answer 503 by
design, and nothing else is affected (decision 29). It is **not set on the live service
yet** — see `docs/DEPLOY.md`.

`/` is the **public landing page** (`apps/web/src/features/public/Landing.tsx`), not a
redirect into `/manager`. Its screenshots are the real app, one set per language, committed
under `apps/web/public/landing/` — **regenerate them with `scripts/landing-shots.mjs` when
you change a screen it shows**, or it is advertising a version that no longer exists.
Decision 39.

**Two limitations Phase 6 wrote down rather than fixed** (decision 35), because both are
bigger than the stage that surfaced them and both distort the numbers the sales guarantee
is settled on:

1. ~~A plan's price edit is retroactive.~~ **Fixed by decision 42**: `subscriptions`
   records `price_usd` and `days` as sold, and dues and analytics read those rather than
   joining to `plans`. **Anything new that creates a `Subscription` must set both** — they
   are NOT NULL, and getting the price from the plan at read time is the bug itself.
2. ~~Nothing can mark a member as having left.~~ **Fixed by decision 43**: `members`
   carries `status` (`active` | `left`) and `left_at`. **Any new query that lists or
   counts members must filter to `status == "active"`** — the lapsed list, the roster and
   the analytics counts all do, and forgetting it is the drift itself. History is kept
   deliberately: a leaver is never deleted.

Both of Phase 6's written-down limitations are now closed.
