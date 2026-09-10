---
name: offline-sync
description: Anything that writes data. Lands in Phase 3 — this file is the contract that Phase 2 endpoints must already satisfy.
---

# Offline is the normal case

Power cuts and dead Wi-Fi are routine in Lebanese gyms. The coach must be able to log a
full session with no connection and lose nothing when the iPad reloads.

**Status: not built yet.** Phase 1 keeps writes in component state. This file exists now
because Phase 2 endpoints have to be designed for it — retrofitting idempotency after the
API is written is far more expensive than building it in.

## The contract

**Every write carries a client-generated `idempotency_key` (UUID v4).** The client mints
it when the user taps, stores it with the queued write, and reuses the *same* key on every
replay. The server treats a repeat key as a no-op returning the original result. Without
this, one flaky connection turns one check-in into three.

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
