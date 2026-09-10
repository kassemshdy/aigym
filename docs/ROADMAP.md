# Roadmap

Six phases. Each one ends with something you can use, not a layer you cannot see.

---

## Phase 0 — Repo foundation ✅ done

`AGENTS.md` / `CLAUDE.md` / `.agents/skills` (with `.claude/skills` symlinked), monorepo
layout, docs, GitHub Actions CI running typecheck, the RTL check, translation-key parity,
build, and the bundle budget.

## Phase 1 — Clickable prototype ✅ done

React + Vite + TS + Tailwind, mock data, no backend. Arabic default with RTL, English
toggle. Eleven screens across three surfaces:

- **Manager** — home (who came, who owes, what's ending, what was collected), member list
  with paid/unpaid chips, member detail with a WhatsApp reminder, 4-step add-member wizard,
  plans, payment log. All USD.
- **Coach iPad** — check-in queue, member card with a payment banner and injury warning,
  tap-to-answer calorie bands with quick meals, live set logger with pre-filled steppers
  and a rest timer, session summary, AI draft inbox with approve/reject.
- **Member** — today's workout, coach's video library with muscle filters, embedded
  player, progress, profile.

Verified: 11 screens × 2 languages screenshot clean, no direction errors, no overflow, no
console errors, 115 KB gzipped against a 200 KB budget.

## Phase 2 — Backend core: tenancy, auth, members, money

FastAPI + SQLAlchemy 2.0 + Alembic + Postgres. Tenancy tables with Row-Level Security, JWT
auth with refresh, gym onboarding, member CRUD, plans, subscriptions, manual USD payments,
derived dues status, **idempotency-key middleware** (required before any offline work),
WhatsApp message composer, and a cross-tenant isolation test suite. Manager screens move
off mocks.

## Phase 3 — The floor: check-in, nutrition, set logging, offline

Check-in (manual + QR), today's-workout resolution, tap-first nutrition logging, workout
sessions and sets. **Offline lands properly here**: service worker, precached shell,
IndexedDB outbox with ordered replay, visible pending count, conflict rules. Tested by
killing the network mid-session. Coach screens go live.

## Phase 4 — Members and content

Member auth (phone + OTP — most members have no email), video library CRUD for coaches,
oEmbed metadata, view tracking, exercise↔video linking, progress and history. Member
screens go live.

## Phase 5 — AI

Body and lifestyle intake, plan generation, per-session coach recommendations, nutrition
guidance, guardrails, coach approval flow, eval harness in CI, Sentry AI tracing, and
capture of coach edits as feedback signal.

## Phase 6 — Sell it

Gym self-serve signup, per-gym branding, owner analytics, CSV/notebook import for gyms
migrating off paper, staff permissions. Two open questions carried in `docs/DECISIONS.md`:
how to bill gym owners from Lebanon, and whether video needs real access control.
