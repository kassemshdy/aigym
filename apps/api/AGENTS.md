# apps/api — FastAPI service

FastAPI + SQLAlchemy 2.0 (async, `psycopg`) + Alembic + Postgres 16, managed with `uv`.
Backs every surface — manager, coach, member — plus the Phase 5 AI layer under `app/ai/`
and the Phase 6 selling surface (owner analytics, staff permissions, plan CRUD, branding,
member import, operator billing).

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
│                     money/floor/training/plumbing/auth) — import every model in
│                     models/__init__.py or Alembic autogenerate will not see it
├── domain/           business logic with no HTTP or SQLAlchemy-session awareness:
│                     dues.py (derived status), workout.py (today's-workout resolution,
│                     also derived), whatsapp.py (wa.me links), analytics.py (the numbers
│                     the sales guarantee is settled on — decision 35), csv_import.py
│                     (a notebook export, normalized — decision 37), guardrails.py,
│                     ai_context.py, evals.py
├── security/         jwt.py (encode/decode), hashing.py (bcrypt for PINs and codes)
├── api/              route modules, aggregated in router.py — auth.py, onboarding.py
│                     (creating a gym AND its billing: operator-only, gated by
│                     X-Onboarding-Secret and never by a role, decision 36), gyms.py
│                     (/gyms/me — branding only, never billing), staff.py, members.py,
│                     member_import.py, payments.py, plans.py, analytics.py, checkins.py,
│                     exercises.py, machines.py, programs.py, sessions.py, nutrition.py,
│                     media.py, chat.py, ai_drafts.py; schemas.py holds request models
│                     shared by more than one of them
└── middleware/        idempotency.py — the Idempotency-Key contract

alembic/versions/      migrations, in order: schema → RLS policies → auth tables →
                        RLS for refresh_tokens → username/password → the Phase 3 floor
                        tables → their RLS policy. Read .agents/skills/generate-migration
                        before adding one.
scripts/
├── bootstrap_db.sh     creates the local/CI database and the aigym_app role
├── seed.py             loads Triple A Gym's real content — mirrors
│                        apps/web/src/mocks/data.ts member-for-member. Refuses the
│                        destructive path when the gym has real members; --no-demo is the
│                        default in production
├── set_staff_password.py   operator-run password reset
├── set_gym_plans.py        the gym's real prices, before anyone has logged in
└── set_gym_billing.py      what a gym pays us — tracked, never processed (decision 38)

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
uv run ruff check .                       # the local loop is these two
uv run mypy app scripts
uv run pytest -q tests/test_thing.py      # one file, when you just wrote it
```

`uv run pytest` with no arguments is CI's job, not the local loop's — see the root
`AGENTS.md`'s "Where tests run". Postgres is not running by default in a fresh sandbox:
`service postgresql start`.

Local Postgres, not Docker: Docker Hub is unreachable from some sandboxes but
`apt-get install postgresql-16` always is — see `.agents/skills/setup-dev`.

## Three tables deliberately sit outside RLS, and one of them now carries billing

`gyms`, `staff_users` and `member_login_codes` are decision 16's documented exceptions —
each is looked up *before* a request knows which gym it belongs to. That makes them the
only places in this codebase where a missing `WHERE` clause is a cross-tenant bug rather
than a no-op, so every query against them filters by hand and there is a test for it.

Since Phase 6 `gyms` also holds what **we** charge the gym (`billing_status`,
`monthly_usd`, `paid_through`, `billing_notes`). There is no RLS to lean on and no role
that helps — `super_admin` means owner of one gym (decision 36) — so the only wall is
which fields the staff-facing response models select. `tests/test_billing.py` walks the
whole OpenAPI schema on every CI run to keep that true. If you add a field to any response
model that touches a gym, that test is what will tell you.

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
against. `CMD` is just `uvicorn` — `bootstrap_db.sh`, `alembic upgrade head`, and
`scripts/seed.py` all run as the Railway service's **Pre-Deploy Command** instead, in that
order, on the new image, before `CMD` ever starts. They have to run there, and in that
order, not in `CMD`: Pre-Deploy Command runs in its own container *before* the new `CMD`
starts, so a migration and a seed.py change that depends on it must land in the same
Pre-Deploy Command, or seed.py hits a column that doesn't exist yet (see decision 21 and
`docs/DEPLOY.md`, which both document a real deploy that failed exactly this way). Correct
at one replica; if this service is ever scaled to more than one, concurrent replicas would
race to bootstrap/migrate/seed identically — same constraint as when this lived in `CMD`,
just relocated.

The three commands must be one array entry wrapped as `sh -c "cmd1 && cmd2 && cmd3"`, not a
bare `cmd1 && cmd2 && cmd3` string: Railway execs each entry directly, not through a shell,
so without `sh -c` the `&&` becomes literal trailing arguments to the first command, which
silently ignores them and exits 0 — `alembic` and `seed.py` never run, and the deploy still
reports `SUCCESS`. Also: `update-service` changing this value has no effect until a real git
push triggers a genuine new build — `redeploy` and a Railway variable change both replay
whatever was captured at the image's original build time. Verify any future change to this
command with an actual push, not a redeploy. Full writeup: `docs/DEPLOY.md`.

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

There isn't one any more: manager (Phase 2), coach (Phase 3), member (Phase 4) and the AI
layer (Phase 5) all read and write the real API. `apps/web` still falls back to mocks with
`VITE_API_URL` unset, and that fallback is expected to keep working — every new query
function gets both branches.

The AI layer is the one part with a runtime prerequisite: with `AIGYM_ANTHROPIC_API_KEY`
unset, `app/ai/client.py` raises `AnthropicNotConfigured` and its routes answer **503, not
500** — a keyless deployment is a supported state, not a bug (decision 29). Keep it that
way when adding a route that calls Claude.

Read `.agents/skills/ai-prompt-eval` before changing a prompt or a guardrail, and note that
the golden set costs real money to run, so it is not in the default CI path (decision 32).

## Maintenance scripts and the `ops` service

`scripts/` holds the one-off admin tools. Non-interactive ones run on the `ops` Railway
service — same image, same database, no port and no domain — by setting
`AIGYM_OPS_COMMAND` and deploying. Interactive ones (`set_staff_password.py`,
`set_gym_billing.py`) prompt on stdin and still need `railway ssh -s api`, because a
deploy has no terminal. See `docs/DEPLOY.md`.

Two rules for anything new in here:

- **Connect as the migrations role, not the app role.** The app role is `NOBYPASSRLS`
  (decision 16) and no `app.gym_id` is set outside a request, so a gym-scoped read as
  that role returns nothing — which looks exactly like an empty database rather than
  like a permissions problem. `scripts/backup_db.py` would have written empty backups.
- **Do not import one script from another.** `scripts/` is not a package: `python
  scripts/x.py` puts `scripts/` on the path, not the directory above it. Shared helpers
  go in `app/` (see `app/backup.py`), which is installed and importable from both.

`app/integrations/object_storage.py` signs its own S3 requests rather than depending on
boto3, for three operations in an image the API also ships. If it ever needs multipart
upload — a dump approaching a gigabyte — that is the moment to take the dependency
rather than grow that file.

