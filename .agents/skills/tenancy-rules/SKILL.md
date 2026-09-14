---
name: tenancy-rules
description: Touching a gym-scoped table, a Row-Level Security policy, or anything that reads or writes across gyms. Tenant isolation is the highest-stakes correctness property in this product (decision 7) — read this before changing any of it.
---

# Tenant isolation

Every gym's data must be invisible to every other gym, enforced by Postgres itself
(Row-Level Security), not by remembering to add `WHERE gym_id = …` everywhere. The full
mechanism and the two traps it closes: decision 16 in `docs/DECISIONS.md`. This file is
the checklist for changing it without breaking it.

## Adding a new gym-scoped table

1. The model gets `GymScopedMixin` (`app/models/base.py`) for the `gym_id` column and FK.
2. The schema migration creates it as usual.
3. **A second migration** adds it to `GYM_SCOPED_TABLES` and runs the same `ENABLE` +
   `FORCE ROW LEVEL SECURITY` + `tenant_isolation` policy as every other one — copy the
   policy SQL from the most recent RLS migration
   (`alembic/versions/6290203bb295_*.py` or later) rather than retyping it; the exact
   `NULLIF(current_setting(...), '')` expression is the part that's easy to get subtly
   wrong.
4. Add the table to the isolation suite: seed a row in each of the two test gyms
   (`tests/test_tenancy_isolation.py`'s `two_gyms` fixture pattern) and assert gym A can't
   see or write gym B's row, through both the API and a raw query on the `aigym_app` role.

Skipping step 3 is invisible until someone actually tries a cross-gym request — the table
works perfectly for single-gym testing either way.

## The three exceptions, and why a fourth needs a decision written down

`gyms`, `staff_users`, `member_login_codes` are gym-adjacent tables with **no** RLS policy,
each for a specific, load-bearing reason (decision 16, 19) — not because it was simpler.
Before adding a fourth: the honest question is "does this table need to be read or written
before `app.gym_id` is known," and if the answer is no, it should be RLS-protected like
everything else. If the answer is yes, write down which of the two existing patterns it
follows — an elevated connection (decision 18) or unscoped-by-design (decision 19) — and
why, in `docs/DECISIONS.md`, not just a code comment.

## Testing isolation for real, not just running the suite once

**Never test through the owner/migrations connection.** It's a Postgres superuser locally
and in CI, and superusers bypass RLS regardless of `FORCE`. A test that queries through
`get_owner_sessionmaker()` and finds isolation holding has tested nothing — it would pass
identically with the policy deleted. `tests/test_tenancy_isolation.py`'s database-layer
tests explicitly use `get_sessionmaker()` (the `aigym_app` role) for this reason; match
that when adding more.

**If you changed a policy expression, prove the test would have caught the old bug.**
Stage 5 built this habit in: temporarily replace the policy with something obviously wrong
—

```sql
DROP POLICY tenant_isolation ON <table>;
CREATE POLICY tenant_isolation ON <table> USING (true) WITH CHECK (true);
```

— rerun `uv run pytest tests/test_tenancy_isolation.py -v`, confirm it goes red, then
restore the real policy and confirm green again. A policy nobody has watched fail is a
policy nobody has actually verified.

## What "isolated" covers

- **Reads** — a list endpoint never includes another gym's rows; a detail endpoint 404s
  for another gym's id rather than leaking a 403 (which confirms the id exists).
- **Writes** — `WITH CHECK`, not just `USING`: a request scoped to gym A cannot insert or
  update a row claiming gym B's `gym_id`, even when it knows gym B's id directly.
- **Auth** — a staff or member login always resolves to the gym that account actually
  belongs to; two logins from two different gyms never cross (see
  `test_staff_login_never_crosses_gyms`).

If a change touches any of the three, it needs a test for that specific case, not just "the
existing suite still passes."
