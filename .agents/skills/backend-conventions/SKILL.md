---
name: backend-conventions
description: Working in apps/api. Covers the layout, the two database roles, request lifecycle, and the commands to run before committing.
---

# apps/api conventions

FastAPI + SQLAlchemy 2.0 (async) + Alembic + Postgres 16, `uv`-managed, `ruff` + `mypy
--strict` + `pytest`. Full layout and commands: `apps/api/AGENTS.md`. This file is the
patterns behind them.

## Two database roles, never confused

- **`aigym_app`** (`AIGYM_DATABASE_URL`) — what the running app connects as. Owns nothing,
  `NOBYPASSRLS`. Row-Level Security actually applies to everything this role touches.
- **the owner role** (`AIGYM_DATABASE_URL_MIGRATIONS`) — what Alembic and
  `scripts/seed.py` connect as. Owns the tables, and in local/CI is the Postgres
  superuser, which means it **bypasses RLS entirely, regardless of policy**. Never use
  this connection to test whether isolation holds — see `.agents/skills/tenancy-rules`.

`app/db.py`'s `get_owner_sessionmaker()` is a third, narrow case: a second live pool on
the owner role, used from exactly one place in the running app (staff login's gym
resolution, decision 18) because that one query structurally cannot be scoped by
`app.gym_id` — it's what determines the gym. Don't reach for it as a general-purpose
"skip RLS" escape hatch; if a new query seems to need it, that's a sign to re-read
decisions 16–19 before adding a fourth pattern.

## Request lifecycle

A route that needs the database depends on `CurrentSession` (`app/deps.py`), not
`get_sessionmaker()` directly:

```python
@router.get("/members")
async def list_members(session: CurrentSession) -> list[MemberOut]:
    ...
```

`CurrentSession` → `get_access_claims` decodes the bearer token → `get_session` opens one
transaction via `tenant_session(claims.gym_id)`, which calls
`set_config('app.gym_id', …, true)` before the route body runs. Every RLS-protected table
the route touches is already scoped; there is no manual `WHERE gym_id = …` to remember,
and no meaningful way to forget it. `require_role("manager", "coach")` gates the same
claims when an endpoint is a staff-only write — see `app/api/members.py` for the pattern.

**The transaction commits on clean exit, not on an explicit `session.commit()`.** `CurrentSession`
wraps the whole request in `session.begin()`; calling `session.commit()` yourself inside a
route ends that transaction early and the outer context manager errors trying to close it
again. `session.flush()` is what you want when you need a generated value (an inserted
row's id) visible to a later statement in the same handler.

**Flush between dependent inserts if there's no `relationship()`.** Nothing in
`app/models/` declares `relationship()` — plain FK columns only — so SQLAlchemy's
unit-of-work has no dependency graph to order inserts across different mapper classes by
itself, even within one `flush()`/commit. `scripts/seed.py` and `app/api/onboarding.py`
both flush explicitly between (e.g.) inserting a `Gym` and inserting rows that FK to it.
Skipping this shows up as a `ForeignKeyViolation` on data that looks like it should exist.

## Idempotency is not opt-in

`app/middleware/idempotency.py` requires an `Idempotency-Key` on every POST/PATCH/DELETE
except `/auth/*`, `/gyms`, `/health`. A new mutating route gets this automatically — there
is nothing to add to the route itself. See `.agents/skills/offline-sync` for the contract
this satisfies.

## Numeric columns: `asdecimal=False`

Every `Numeric` column in `app/models/` is declared `Numeric(precision, scale,
asdecimal=False)`, not just `Numeric(precision, scale)`. Without it, SQLAlchemy returns
`decimal.Decimal` at runtime even when the column is typed `Mapped[float]` — mypy trusts
the annotation and won't catch the mismatch, so it surfaces later as a subtly wrong
comparison or an unexpected type in a response body. Match this for any new money or
body-metric column.

## Before committing

```bash
uv run ruff check . && uv run mypy app scripts
```

That is the local loop. **The full suite runs in CI on every push to `develop`**, so
pushing is what verifies a change end to end — see the root `AGENTS.md`'s "Where tests
run" for why it is split this way. Run one test file directly when you have just written
it (a test nobody has executed turns one CI round trip into two), and run
`tests/test_tenancy_isolation.py` by hand when you have changed an RLS policy itself
rather than merely used one — that is the property decision 7 calls the highest-stakes in
the product, and it is worth not learning about it from a red build.

`apps/api/AGENTS.md` has the full command list including local Postgres setup
(`service postgresql start` — it is not running by default).
