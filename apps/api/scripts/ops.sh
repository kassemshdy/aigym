#!/usr/bin/env bash
set -euo pipefail

# Entrypoint for the `ops` Railway service: run one maintenance command
# against production, then exit.
#
# The service shares this image and this repo with `api`, so every script in
# scripts/ is already here and already pointed at the right database. What it
# does not share is a port, a healthcheck or a domain — it is not reachable
# from the internet at all. That is deliberate: the alternative shape, an HTTP
# endpoint that runs a named script, is remote code execution on production
# guarded by one shared secret.
#
# To run something once: set AIGYM_OPS_COMMAND on the service and press
# Deploy. To run something nightly: give the service a cron schedule in
# Railway and leave the command set.
#
#   AIGYM_OPS_COMMAND="python scripts/backup_db.py"
#   AIGYM_OPS_COMMAND="python scripts/db_report.py"
#   AIGYM_OPS_COMMAND="python scripts/set_gym_billing.py"
#
# Set the service's restart policy to NEVER. Railway's default restarts a
# container that exits, which for a one-shot job is an infinite loop that
# reruns your maintenance command until you notice.

if [ -z "${AIGYM_OPS_COMMAND:-}" ]; then
  # Not an error: this is what the service looks like at rest, between jobs.
  # Failing here would make every idle deploy show up as a red deployment.
  echo "ops: AIGYM_OPS_COMMAND is unset — nothing to run."
  exit 0
fi

echo "ops: $AIGYM_OPS_COMMAND"
echo "---"
sh -c "$AIGYM_OPS_COMMAND"
status=$?
echo "---"
echo "ops: exited $status"
exit $status
