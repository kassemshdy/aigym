# uv pinned to match .github/workflows/ci.yml and scripts/bootstrap_db.sh
FROM ghcr.io/astral-sh/uv:0.8.17 AS uv

FROM python:3.11-slim
COPY --from=uv /uv /uvx /bin/

# psql, for scripts/bootstrap_db.sh — creates the aigym_app role over
# Railway's private network so Postgres never needs a public TCP proxy.
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# Bootstrap (idempotent — safe to run on every deploy) then migrate, both
# before uvicorn starts accepting traffic. Safe at one replica (Triple A
# Gym's scale); if this service ever runs more than one, move this to
# Railway's release-command instead of the start command so concurrent
# replicas don't race to apply the same migration or bootstrap.
CMD ["sh", "-c", "bash scripts/bootstrap_db.sh && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
