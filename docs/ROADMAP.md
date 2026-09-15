# Roadmap

Six phases. Each one ends with something you can use, not a layer you cannot see.

---

## Phase 0 — Repo foundation ✅ done

`AGENTS.md` / `CLAUDE.md` / `.agents/skills` (with `.claude/skills` symlinked), monorepo
layout, docs, GitHub Actions CI running typecheck, the RTL check, translation-key parity,
build, and the bundle budget.

## Phase 1 — Clickable prototype ✅ done, deployed

**Live: https://triple-a.up.railway.app** — see `docs/DEPLOY.md`.

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
JWT auth with rotating refresh tokens, username + password for staff (decision 21 — a
super_admin-gated `POST /staff` creates additional accounts) and phone + 6-digit WhatsApp
code for members, gym onboarding, member CRUD, plans, subscriptions, manual USD payments,
derived dues status (decision 17, never stored), **Idempotency-Key middleware** (the
contract `.agents/skills/offline-sync` already promised Phase 3), a WhatsApp message
composer, self-service staff password reset over the real WhatsApp Business API (decision
20, the one deliberate exception to decision 4), and a cross-tenant isolation test suite
with its own CI job (decision 7). Manager screens read through `apps/web/src/data/` instead
of `apps/web/src/mocks/`, with a mock fallback when `VITE_API_URL` is unset — coach and
member screens stay on mocks until Phase 3. See `apps/api/AGENTS.md` and decisions 16–21.

## Phase 3 — The floor: check-in, nutrition, set logging, offline

Check-in (manual + QR), today's-workout resolution, tap-first nutrition logging, workout
sessions and sets. **Offline lands properly here**: service worker, precached shell,
IndexedDB outbox with ordered replay, visible pending count, conflict rules. Tested by
killing the network mid-session. Coach screens go live.

## Phase 4 — Members, content, and self-service

Member auth (phone + code over WhatsApp — most members have no email), video library CRUD
for coaches, oEmbed metadata, view tracking, exercise↔video linking, progress and history.

Also the member's own data: **food entries** with a small local food table (manqoushe,
labneh, shawarma — not a US database), **progress photos** with the privacy rules in
decision 11 (private by default, per-photo sharing, real deletion), and object storage for
both. Member screens go live.

## Phase 5 — AI

Body and lifestyle intake, plan generation, per-session coach recommendations, nutrition
guidance, guardrails, coach approval flow, eval harness in CI, Sentry AI tracing, and
capture of coach edits as feedback signal.

Plus the two member-facing assistants, which are the hardest part of this phase because
they talk to members directly rather than through a coach:

- **Context** — body data, lifestyle, recorded injuries, recent sessions, and today's food
  are assembled per turn; the gym's own exercises and Coach Assaf's videos are retrieved so
  answers reference what the gym actually has.
- **Authority, enforced in code** — the reply schema carries a `draft` flag; anything
  touching the program or targets is written to `ai_plan_drafts` and surfaced in the
  coach's inbox. The model never gets to be the gate. See decision 10.
- **Safety** — injury contraindications and a calorie floor are checked before a reply is
  sent, not requested in the prompt. Medical questions get referred, not answered.
- **Food vision** — meal photo in, estimate out, member confirms. Both the estimate and
  the correction are stored (decision 12).
- **Evals** — the golden set covers refusals as well as answers: an assistant that agrees
  to change a program fails the suite.

## Phase 6 — Sell it

Gym self-serve signup, per-gym branding, owner analytics, CSV/notebook import for gyms
migrating off paper, staff permissions. Two open questions carried in `docs/DECISIONS.md`:
how to bill gym owners from Lebanon, and whether video needs real access control.
