# uv pinned to match .github/workflows/ci.yml and scripts/bootstrap_db.sh
FROM ghcr.io/astral-sh/uv:0.8.17 AS uv

FROM python:3.11-slim
COPY --from=uv /uv /uvx /bin/

# psql, for scripts/bootstrap_db.sh — creates the aigym_app role over
# Railway's private network so Postgres never needs a public TCP proxy —
# and pg_dump, for scripts/backup_db.py.
#
# From PGDG rather than Debian, which is the whole reason this is five lines
# instead of one: bookworm ships postgresql-client 15, and while psql 15
# talks to a newer server fine, **pg_dump refuses outright to dump a server
# newer than itself**. Every database this connects to is newer (16 today,
# 18 on the managed service), so Debian's client would have made the nightly
# backup fail on its first run. Pinned to the newest major we run; bump it
# when the server majors move past it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-18 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# Bootstrap, migrate, and seed all run as this service's Railway
# Pre-Deploy Command instead (see docs/DEPLOY.md) — a separate one-off
# container that runs BEFORE this CMD, on the OLD image, meaning
# seed.py needs the new migration applied first or it 500s on a column
# that doesn't exist yet. Putting migrate+seed here, after the new
# image is already live, got that ordering backwards. This CMD is just
# the app.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
