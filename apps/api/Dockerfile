# uv pinned to match .github/workflows/ci.yml and scripts/bootstrap_db.sh
FROM ghcr.io/astral-sh/uv:0.8.17 AS uv

FROM python:3.11-slim
COPY --from=uv /uv /uvx /bin/

# psql, for scripts/bootstrap_db.sh — creates the aigym_app role over
# Railway's private network so Postgres never needs a public TCP proxy —
# and pg_dump, for scripts/backup_db.py.
#
# From PGDG rather than Debian, which is the whole reason this is a dozen
# lines instead of one: **pg_dump refuses outright to dump a server newer
# than itself**, and every database this connects to is newer than what
# Debian packages (trixie ships 17; the managed Postgres is 18). Without
# this the nightly backup would have failed on its first run.
#
# The codename is read from the base image rather than written down. The
# first version of this said `bookworm` because python:3.11-slim used to be
# bookworm; it is trixie now, and a bookworm-pgdg libpq5 wants libldap-2.5-0
# where trixie has libldap2, so the build failed on an unmet dependency with
# nothing in it that said "wrong distro". Reading $VERSION_CODENAME means
# the next base-image bump cannot repeat that.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo "$VERSION_CODENAME")-pgdg main" \
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
