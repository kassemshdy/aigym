# Roadmap

Six phases. Each one ends with something you can use, not a layer you cannot see.

---

## Phase 0 — Repo foundation ✅ done

`AGENTS.md` / `CLAUDE.md` / `.agents/skills` (with `.claude/skills` symlinked), monorepo
layout, docs, GitHub Actions CI running typecheck, the RTL check, translation-key parity,
build, and the bundle budget.

## Phase 1 — Clickable prototype ✅ done, deployed

**Live: https://trpa.up.railway.app** — see `docs/DEPLOY.md`.

React + Vite + TS + Tailwind, mock data, no backend. Arabic default with RTL, English
toggle. Eleven screens across three surfaces:

- **Manager** — home (who came, who owes, what's ending, what was collected), member list
  with paid/unpaid chips, member detail with a WhatsApp reminder, 4-step add-member wizard,
  plans, payment log. All USD.
- **Coach iPad** — check-in queue, member card with a payment banner and injury warning,
  tap-to-answer calorie bands with quick meals, live set logger with pre-filled steppers
  and a rest timer, session summary, AI draft inbox with approve/reject.
- **Member** — phone + code sign-in, today's workout, coach's video library with muscle
  filters and an embedded player, **food tracking with photo auditing** (photograph a meal,
  get an estimate, correct the portion, confirm), **two chat assistants** (nutrition and
  bodybuilding) that answer and log but escalate program changes to the coach, **private
  progress photos**, progress, profile.

Verified: 17 screens × 2 languages screenshot clean, no direction errors, no overflow, no
console errors, 120 KB gzipped against a 200 KB budget.

## Phase 2 — Backend core: tenancy, auth, members, money ✅ done

FastAPI + SQLAlchemy 2.0 + Alembic + Postgres. Tenancy tables with Row-Level Security
(`ENABLE` + `FORCE`, enforced against a non-owning, non-superuser role — see decision 16),
JWT auth with rotating refresh tokens, username + password for staff (decision 21, amended
by decision 25 — `POST /staff` lets a manager create coach accounts, super_admin still
required for another manager or super_admin) and phone + 6-digit WhatsApp
code for members, gym onboarding, member CRUD, plans, subscriptions, manual USD payments,
derived dues status (decision 17, never stored), **Idempotency-Key middleware** (the
contract `.agents/skills/offline-sync` already promised Phase 3), a WhatsApp message
composer, self-service staff password reset over the real WhatsApp Business API (decision
20, the one deliberate exception to decision 4), and a cross-tenant isolation test suite
with its own CI job (decision 7). Manager screens read through `apps/web/src/data/` instead
of `apps/web/src/mocks/`, with a mock fallback when `VITE_API_URL` is unset — coach and
member screens stay on mocks until Phase 3. See `apps/api/AGENTS.md` and decisions 16–21.

## Phase 3 — The floor: check-in, nutrition, set logging, offline ✅ done

Exercise catalog, member programs (with a real coach/manager assign-and-edit UI, not just
seeded data — decision from the build), workout sessions and sets, tap-first nutrition
logging, manual check-in (QR check-in was planned and dropped — decision 24). Today's-workout
resolution (`app/domain/workout.py`) merges a program's exercises with each one's most
recently logged weight, derived on read like dues (decision 17), never stored.

**Offline lands here**: a hand-rolled IndexedDB outbox (`apps/web/src/offline/`), one ordered
queue covering workout sessions/sets, nutrition logs, and check-in status (decisions 22–23),
replayed oldest-first on reconnect; a hand-rolled service worker precaches the app shell so a
reload mid-power-cut still boots. `scripts/test-offline.mjs` runs the skill's own test method
against a live stack — kill the network, log 3 sets, reload, reconnect, confirm exactly 3 rows
land — and passes. Coach screens (Queue, member card, session logging) read and write the real
API; the mock fallback still works with `VITE_API_URL` unset. Member and AI-draft-inbox screens
stay on mocks (Phases 4–5).

## Phase 4 — Members, content, and self-service ✅ done, deployed

**Live: https://trpa.up.railway.app** — member screens now read and write the real API.

Self-service member login (phone + 6-digit WhatsApp code, no staff needed to request one —
decision 28), alongside the staff-assisted flow Phase 2 already shipped. Every new
member-facing write is scoped to the signed-in member's own id, never a URL parameter
(decision 28) — including three existing staff endpoints broadened, not duplicated, to also
serve a member asking about themselves.

**Video library** — coach-managed catalog (title, muscle group, equipment, a YouTube
link/id pasted in), view tracking, a member-facing browse-and-watch screen. Video embedding
stays decision 5's hand-built iframe: no live oEmbed fetch, and no `Exercise`↔`Video` link —
those were in this phase's original scope but cut (decision 28), since the two catalogs
turned out to serve different purposes (an exercise's own `video_url` vs. a member browsing
technique videos on their own).

**The member's own data**: food entries with a confirm-before-logging step (decision 12 —
the vision estimate itself is still fake, Phase 5's job), and progress photos with the
privacy rules in decision 11 (private by default, per-photo sharing, real deletion —
proven by a test that the stored file is actually gone, not just the row). Both go through
a Railway Volume (decision 28), the same no-new-vendor pattern Postgres already uses on
this project.

**Booking and calendar** — coaches, the fixed class schedule, and a member's own
private/intro session bookings (with cancel), reusing models Phase 3 had already seeded;
no new schema. Today, Progress, and Profile switched from mocks to real member-scoped
reads to close out the phase.

Verified stage by stage: the full backend test suite (tenancy isolation, cross-member
isolation, and the RLS-actually-blocks proof ritual for every new table), `npm run verify`,
and the screenshot suite clean in both languages throughout. Deployed by merging straight
to `main` once the whole phase was solid, rather than the two-milestone split originally
planned — Stage 7 turned out to depend on Stage 6's attendance endpoint, so the stages
weren't cleanly separable after all.

## Phase 5 — AI ✅ built

Runs on **Anthropic Claude** — Haiku 4.5 for the high-volume member-facing surfaces,
Sonnet 5 for coach-facing plan generation only (decision 29). Every call goes through one
wrapper, `app/ai/client.py`'s `run_structured()`, using structured outputs rather than
prompt-begged JSON.

- **Intake** — `MemberProfile`'s body and lifestyle fields finally have a member-facing way
  to be set (`PATCH /members/me/profile` plus an edit screen), and the manager's add-member
  wizard fills in the three fields it used to hardcode. `injuries` became a structured
  shape so the guardrails can reason about it deterministically (decision 30).
- **Context** — body data, lifestyle, recorded injuries, recent sessions, and today's food
  are assembled per turn; the gym's own exercises and Coach Assaf's videos are retrieved so
  answers reference what the gym actually has. Split at a `cache_control` breakpoint —
  stable catalog first, volatile member data after — with the caching payoff to be measured
  on real traffic rather than assumed (decision 29).
- **Authority, enforced in code** — the reply schema carries a `draft` flag; anything
  touching the program or targets is written to `ai_plan_drafts` and surfaced in the
  coach's inbox, which now runs on real data with edit-before-approve. The model never gets
  to be the gate. See decision 10. A coach's own "suggest a plan" action goes through the
  exact same mechanism (decision 31).
- **Safety** — injury contraindications and a calorie floor are checked before a reply is
  sent, not requested in the prompt. Medical questions are caught by a deterministic
  pre-filter *before* any API call, and referred rather than answered.
- **Food vision** — meal photo in, estimate out, member confirms. Both the estimate and
  the correction are stored (decision 12). The photo now uploads on selection rather than
  at confirm time, since the vision call needs it server-side first.
- **Evals** — 27 golden-set cases in both languages, covering refusals as well as answers:
  an assistant that agrees to change a program fails the suite. The paid run is its own
  path-filtered job, never on every push (decision 32); the grader and runner are covered
  for free in the normal suite.

**Explicitly cut, and why:** Sentry AI tracing — no Sentry exists anywhere in this backend
yet, and choosing an observability vendor was not this phase's call to make in passing;
structured JSON logging covers it for now (decision 29). And no server-side chat-history
table — the client carries enough turn history for a stateless per-turn call, and a durable
transcript (gym-scoped, RLS, retention questions) isn't asked for by any requirement here.

**Before the AI works in production**, `AIGYM_ANTHROPIC_API_KEY` must be set on the Railway
`api` service — until it is, every AI route answers 503 by design rather than 500. Same for
the GitHub Actions secret of the same name before the eval job can run. See `docs/DEPLOY.md`.

## Phase 6 — Sell it ✅

Built. The scope came from `docs/GTM.md` rather than from a missing capability: a working
product and zero paying gyms, sold by walking in with a conditional guarantee ("if it does
not recover more in missed dues than we charge you in the first 90 days, you do not pay").

**What shipped**

- **The owner dashboard** (`/manager/insights`, `GET /analytics/summary`) — the on-time
  renewal rate, money collected and still owed, a 12-week trend, and member counts, each
  against the preceding equal window because the guarantee is a before/after claim. No
  charting library: `Sparkline` and a ~30-line `Meter`.
- **Staff permissions** — role changes, revoking access at one gym without touching the
  account or another gym's role, and operator-run password resets. Every one of them
  revokes the person's refresh tokens, which turns a demoted manager's window from 30 days
  down to the 15-minute access-token lifetime.
- **A gym sets its own prices** — `POST`/`PATCH`/`DELETE /plans`. This was the pilot
  blocker nobody had listed: every gym was stuck with onboarding's $30/$80/$280 forever,
  and the guarantee is settled on dues arithmetic that reads those numbers.
- **Branding** — `gyms.logo_key`, `GET`/`PATCH /gyms/me`, and the gym-logo branch
  `GET /media/{key}` was missing. Name and logo only.
- **The frontend reads its own identity** — `GymProvider` replaced a `gym` const in
  `src/mocks/data` that nine files imported directly, which is what made a multi-tenant
  product render one tenant's name everywhere.
- **Member import** — a notebook export in, parsed on the server, previewed and corrected
  row by row, committed all-or-nothing.
- **Operator provisioning and billing** — 409s where `POST /gyms` used to crash, billing
  columns on `gyms`, and `scripts/set_gym_billing.py`.

Decisions 34–38 in `docs/DECISIONS.md` record why each of those took the shape it did.

**What was cut, and why**

- **Self-serve signup**, which this phase's one-line scope originally called for. Wrong
  channel for this market, and a public form would add an abuse surface to serve a channel
  we do not use — decision 34.
- **Per-gym colour theming.** It collides with two documented guarantees: green/amber/red
  mean payment state and nothing else, and the `#f9e54c` contrast rule is specific to
  yellow on black. Branding stops at name and logo.
- **A cross-gym admin UI.** At three to five pilot gyms a script is the honest tool, and
  building one would mean a second call site for `get_owner_sessionmaker()` (decision 18)
  for no gain — decision 36.
- **A payment processor.** Decision 3's "nothing may assume a card is on file" holds, so
  billing is tracked and not processed — decision 38.
- **Real video access control.** Decision 5's other carried open question stays carried:
  an unlisted link is already documented as not being access control, and nothing about it
  blocks selling to a pilot gym.

**Known limitations, written down rather than discovered later**

Two things distort the numbers the guarantee is settled on, both recorded in decision 35,
in the endpoint docstrings, and in `docs/DEPLOY.md`'s go-live sequence:

1. ~~**A price edit is retroactive.**~~ **Fixed** — `subscriptions` now records the price
   and length a period was sold at, and dues and analytics read those instead of joining
   to `plans`. Decision 42. Done while the table still held zero rows, which is the only
   time the backfill is free rather than a guess.
2. **Nothing can mark a member as having left.** "Lapsed" and "still not collected" both
   drift upward as people quit. Fix: a member lifecycle.

The second is the remaining one, and it is bigger than the stage that surfaced it — which
is why it was not smuggled in either.

**Still carried:** how to bill gym owners from Lebanon (decision 3 — tracked, not
processed, is the interim answer), and whether video needs real access control
(decision 5).
