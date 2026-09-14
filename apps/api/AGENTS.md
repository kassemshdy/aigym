# apps/api — FastAPI service

FastAPI + SQLAlchemy 2.0 (async, `psycopg`) + Alembic + Postgres 16, managed with `uv`.
Backs the manager surface only — coach and member endpoints land in Phase 3/4.

## Layout

```
app/
├── main.py           creates the FastAPI app, wires middleware and the router
├── settings.py       pydantic-settings — every env var this service reads
├── db.py             engine/session setup, tenant_session() (RLS scoping),
│                     get_owner_sessionmaker() (the one deliberate RLS exception)
├── deps.py           FastAPI dependencies: current claims, current session, require_role()
├── logging.py        structured JSON logging
├── models/           SQLAlchemy models, one module per table group (tenancy/people/
│                     money/floor/plumbing/auth) — import every model in models/__init__.py
│                     or Alembic autogenerate will not see it
├── domain/           business logic with no HTTP or SQLAlchemy-session awareness:
│                     dues.py (derived status), whatsapp.py (wa.me links)
├── security/         jwt.py (encode/decode), hashing.py (bcrypt for PINs and codes)
├── api/              route modules — auth.py, onboarding.py, members.py, payments.py,
│                     plans.py, checkins.py — aggregated in router.py
└── middleware/        idempotency.py — the Idempotency-Key contract

alembic/versions/      migrations, in order: schema → RLS policies → auth tables →
                        RLS for refresh_tokens. Read .agents/skills/generate-migration
                        before adding one.
scripts/
├── bootstrap_db.sh     creates the local/CI database and the aigym_app role
└── seed.py             loads Triple A Gym's real content — mirrors
                         apps/web/src/mocks/data.ts member-for-member

tests/
├── conftest.py             clean_db fixture (TRUNCATE via the owner role) + httpx client
├── test_tenancy_isolation.py  its own file, its own CI job — see below
└── test_*.py                everything else
```

## Commands

```bash
cd apps/api
uv sync
cp .env.example .env                     # then point it at a real local Postgres
bash scripts/bootstrap_db.sh              # creates the aigym database + aigym_app role
uv run alembic upgrade head
uv run python scripts/seed.py             # optional — Triple A Gym's real content

uv run uvicorn app.main:app --reload      # http://localhost:8000
uv run pytest -q                          # everything except the isolation suite's own job
uv run ruff check .
uv run mypy app scripts
```

Local Postgres, not Docker: Docker Hub is unreachable from some sandboxes but
`apt-get install postgresql-16` always is — see `.agents/skills/setup-dev`.

## Row-Level Security is the load-bearing wall — read `.agents/skills/tenancy-rules`

Before touching anything that reads or writes a gym-scoped table, or before adding a new
one. Decision 16 in `docs/DECISIONS.md` explains the two traps (owner bypass, the
reset-to-empty-string cast error) that make "it compiles" insufficient evidence that
isolation holds.

**The one-sentence version:** every gym-scoped table needs `ENABLE` + `FORCE ROW LEVEL
SECURITY` and the `tenant_isolation` policy, added to `GYM_SCOPED_TABLES` in a migration —
nothing enforces that automatically, so a new table without it is invisible to Postgres's
own protection and to `tests/test_tenancy_isolation.py`. `gyms`, `staff_users`, and
`member_login_codes` are the three deliberate exceptions (decisions 16, 19); anything else
gym-scoped and unprotected is a bug, not a third exception you get to add without writing
down why.

## Migrations — read `.agents/skills/generate-migration`

Before running `alembic revision --autogenerate`. Covers why every model has to be
imported in `models/__init__.py` first, and why a new gym-scoped table needs a *second*
migration for its RLS policy, not inline in the schema migration.

## Idempotency

Every POST/PATCH/DELETE except `/auth/*`, `/gyms`, and `/health` requires an
`Idempotency-Key` header (`app/middleware/idempotency.py`) — a repeat with the same body
replays the stored response, a repeat with a different body is a 409. This is the contract
`.agents/skills/offline-sync` holds Phase 3's outbox to; a new mutating endpoint gets this
for free from the middleware, nothing to opt into.

## Auth

JWT access tokens (15 min) + rotating refresh tokens (30 days), both carrying
`gym_id`/`subject_type`/`role` (`app/security/jwt.py`). `CurrentSession`
(`app/deps.py`) decodes the caller's token and opens one Row-Level-Security-scoped
transaction from its `gym_id` claim — a route depending on it never sees another gym's
rows, by construction, not by remembering to filter. `require_role("manager", "coach")`
gates staff-only mutations; a member token never satisfies it (different `subject_type`,
not a different role).

Two auth flows read from tables *before* `app.gym_id` is known, and take different
approaches (decisions 18, 19) — read the docstrings on `get_owner_sessionmaker()` in
`db.py` and on `MemberLoginCode` in `models/auth.py` before adding a third pattern.

## Before committing

```bash
uv run ruff check . && uv run mypy app scripts && uv run pytest -q
```

If you touched a gym-scoped table or an RLS policy, also run the isolation suite on its
own and read its module docstring:

```bash
uv run pytest tests/test_tenancy_isolation.py -v
```

If you are not sure a new policy actually blocks anything, prove it the way stage 5 did:
temporarily swap the policy for `USING (true) WITH CHECK (true)` on a local database and
confirm the isolation suite goes red, then put the real policy back. A policy that passes
whether or not the real expression is used is not tested.

## Deploy

Dockerfile: `uv sync` (cached in its own layer, dependencies before source so a
source-only change doesn't reinstall everything), then the same source tree the tests run
against. `CMD` runs `alembic upgrade head` before `uvicorn` starts — correct at one
replica; if this service is ever scaled to more than one, move that to Railway's
release-command so concurrent replicas don't race to apply the same migration.

Two required env vars with no safe default in production: `AIGYM_JWT_SECRET` (32+ bytes —
PyJWT warns below that for HS256) and `AIGYM_ONBOARDING_SECRET` (the only thing gating
`POST /gyms`, which has no JWT to check since nothing exists yet when it runs). Generate
both with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` and set them on
the Railway service directly — never commit a real value, `.env.example`'s are dev-only
placeholders. `AIGYM_DATABASE_URL` is the app's own role (`aigym_app`);
`AIGYM_DATABASE_URL_MIGRATIONS` is the owning role migrations and `scripts/seed.py` run
as — see decision 16 for why they must differ.

Full runbook: `docs/DEPLOY.md`.

## Phase boundary

Coach and member endpoints (check-in queue beyond the minimal `POST /check-ins`, workout
sessions, nutrition, AI drafts, video library) are Phase 3/4 — `apps/web`'s coach and
member screens stay on mocks until then. Do not add auth or data-layer plumbing here for
screens that are not switching over yet.
