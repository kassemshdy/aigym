#!/usr/bin/env bash
set -euo pipefail

# Creates the local/CI database and the app's runtime role.
#
# When this is chained with other commands in Railway's Pre-Deploy Command
# (e.g. "bash scripts/bootstrap_db.sh && alembic upgrade head && ..."), the
# WHOLE chain must be wrapped as a single sh -c "..." string. Railway execs
# each array entry directly rather than through a shell, so a bare
# "cmd1 && cmd2" is passed to cmd1 as literal trailing arguments instead of
# being interpreted as shell chaining — bootstrap_db.sh silently ignores
# them (it takes none), runs fine on its own, and cmd2 never runs at all.
# See docs/DEPLOY.md's Pre-Deploy Command section.
#
# The app role is deliberately NOT the table owner and does not get
# BYPASSRLS: Postgres lets a table's owner (and any BYPASSRLS role) skip
# Row-Level Security entirely, silently. Migrations run as $PGUSER (the
# owner); the API connects as $APP_ROLE, so the RLS policies created in
# stage 2 actually apply to every request. Idempotent — safe to re-run.

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
APP_DB="${AIGYM_DB:-aigym}"
APP_ROLE="${AIGYM_APP_ROLE:-aigym_app}"
APP_PASSWORD="${AIGYM_APP_PASSWORD:-aigym_app}"

export PGPASSWORD="${PGPASSWORD:-postgres}"

psql -v ON_ERROR_STOP=1 -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres <<SQL
SELECT 'CREATE DATABASE $APP_DB'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$APP_DB')\gexec
SQL

psql -v ON_ERROR_STOP=1 -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$APP_ROLE') THEN
    CREATE ROLE $APP_ROLE LOGIN PASSWORD '$APP_PASSWORD' NOSUPERUSER NOBYPASSRLS;
  END IF;
END
\$\$;
SQL

psql -v ON_ERROR_STOP=1 -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$APP_DB" <<SQL
GRANT CONNECT ON DATABASE $APP_DB TO $APP_ROLE;
GRANT USAGE ON SCHEMA public TO $APP_ROLE;
ALTER DEFAULT PRIVILEGES FOR ROLE $PGUSER IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO $APP_ROLE;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO $APP_ROLE;
ALTER DEFAULT PRIVILEGES FOR ROLE $PGUSER IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO $APP_ROLE;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO $APP_ROLE;
SQL

echo "Bootstrapped database '$APP_DB' and role '$APP_ROLE' on $PGHOST:$PGPORT"
