---
name: generate-migration
description: Adding or changing an Alembic migration in apps/api. Covers model registration, autogenerate's blind spots, and why a new gym-scoped table needs two migrations, not one.
---

# Generating a migration

## Register the model first

`alembic/env.py` imports `app.models` (which imports every model module) before
autogenerate runs. A model class that exists but isn't imported in
`app/models/__init__.py` is invisible to `alembic revision --autogenerate` — it silently
generates an empty migration, not an error. Add the new model to `models/__init__.py`'s
imports and `__all__` before generating.

## Generate, then read it — autogenerate gets some things right and some wrong

```bash
cd apps/api
uv run alembic revision --autogenerate -m "add gym_class attendance caps"
```

Read the generated file before applying it:

- **Table/column diffs** — usually correct. Still check column types against what you
  actually wrote (`Numeric(8, 2, asdecimal=False)`, not bare `Numeric`, for anything
  money or a body metric — see `.agents/skills/backend-conventions`).
- **Row-Level Security** — autogenerate never sees this. A new gym-scoped table needs a
  **second, hand-written migration** enabling and forcing RLS and adding the
  `tenant_isolation` policy — see `.agents/skills/tenancy-rules` for the exact SQL to
  copy. Forgetting this is a table that works fine until someone tries a cross-gym
  request.
- **Line length in the generated file** — `alembic/versions/*.py` is exempted from
  ruff's `E501` in `pyproject.toml`, since its formatting follows SQLAlchemy's own
  `op.create_table` layout, not this codebase's. Don't hand-reformat it to satisfy a
  linter that isn't checking it.

## Apply and verify locally before committing

```bash
uv run alembic upgrade head              # apply
uv run alembic downgrade -1              # confirm the downgrade doesn't error
uv run alembic upgrade head              # and reapply cleanly

# the migration must also work from a completely empty database — this is
# what CI does on every run:
uv run alembic downgrade base && uv run alembic upgrade head
```

A migration that only works starting from today's local database (because a manual `ALTER`
was run out-of-band, or a previous migration was hand-edited after being applied) fails
the moment CI or a fresh Railway deploy runs it against an empty one.

## Naming and ordering

Migration messages describe what changed, not the ticket or the session: `"row level
security for refresh tokens"`, not `"fix bug"` or `"stage 3 changes"`. Alembic chains
migrations by `down_revision`, so there's no need to manually number them — but keep
schema changes and their RLS policy in separate, sequential migrations (schema first) so a
partial rollback never leaves a table exposed without its policy.
