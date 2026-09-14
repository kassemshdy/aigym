# uv pinned to match .github/workflows/ci.yml and scripts/bootstrap_db.sh
FROM ghcr.io/astral-sh/uv:0.8.17 AS uv

FROM python:3.11-slim
COPY --from=uv /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# Migrations run at container start, before the app accepts traffic. Safe at
# one replica (Triple A Gym's scale); if this service ever runs more than
# one, move this to Railway's release-command instead of the start command
# so concurrent replicas don't race to apply the same migration.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
