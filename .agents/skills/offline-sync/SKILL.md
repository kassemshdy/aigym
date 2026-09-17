---
name: offline-sync
description: Anything that writes data. Landed in Phase 3 (both server and client halves built) — this file is the contract every write, old or new, has to satisfy.
---

# Offline is the normal case

Power cuts and dead Wi-Fi are routine in Lebanese gyms. The coach must be able to log a
full session with no connection and lose nothing when the iPad reloads.

**Status: both halves are built.** Phase 2's `apps/api/app/middleware/idempotency.py`
enforces this contract on every POST/PATCH/DELETE — required, not optional. Phase 3 built
the client side: the IndexedDB outbox (`apps/web/src/offline/{db,outbox}.ts`), offline
detection and replay-on-reconnect (`OfflineProvider.tsx`), and `client.ts`'s
`offlineFetch()`, which every floor write (workout sessions/sets, nutrition logs, check-in
status — decisions 22–23 in `docs/DECISIONS.md`) goes through. Manager writes
(members/plans/payments) still fail visibly rather than queue — that scope boundary was a
deliberate Phase 3 decision, not a gap. `apps/web/scripts/test-offline.mjs` runs the exact
test method below against a live stack.

## The contract

**Every write carries a client-generated `idempotency_key` (UUID v4).** The client mints
it when the user taps, stores it with the queued write, and reuses the *same* key on every
replay. The server treats a repeat key as a no-op returning the original result — verified
in `apps/api/tests/test_idempotency.py`: the same check-in posted three times leaves one
row. Without this, one flaky connection turns one check-in into three.

**One ordered outbox.** A single IndexedDB queue, replayed oldest-first. Not one queue per
feature — a set logged after a check-in must never land before it.

**Conflict rule:**
- Member, plan, and payment data → **server wins**. The front desk is the source of truth.
- Session data (sets, reps, nutrition entries) → **client wins**. Exactly one coach is
  logging a given session; their device saw what happened.

**Visible state, always.** A pending count in the header (`common.pendingSync`) and an
offline marker (`common.offline`). Never let someone wonder whether their work was saved —
that uncertainty is what sends a coach back to a paper notebook.

## Testing it

Not "does the code look right" — kill the network and check:

1. Playwright `context.setOffline(true)`, log three sets, assert the pending badge reads 3.
2. Reload the page (this is the power-cut case), assert the three sets are still queued.
3. `setOffline(false)`, assert exactly three rows reach the server — not six.

`apps/web/scripts/test-offline.mjs` runs exactly this against a real running stack (its own
header comment has the setup steps — local Postgres, the API, a seeded gym, and the
frontend built and served via `vite preview`, not `vite dev`: the reload step only proves
anything because the service worker precached the shell). It is not part of `npm run
verify` — it needs infrastructure `verify` doesn't spin up — so run it by hand after
touching anything in `apps/web/src/offline/`, `client.ts`'s `offlineFetch`, or the service
worker.
