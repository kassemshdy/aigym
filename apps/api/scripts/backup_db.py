"""Dump the database to the project's Railway Bucket, and prune old dumps.

The live Postgres had no backups at all — a raw image on a volume, which is
a database you are one deleted volume away from losing. Railway's managed
Postgres has its own scheduled backups, and this still exists, because a
provider-managed backup is (a) untested until the day you need it and (b) in
the same account whose loss is one of the things you are insuring against.
This writes a dump you can download and restore anywhere.

`pg_dump --format=custom` rather than plain SQL: it restores selectively,
in parallel, and is already compressed, so nothing here gzips anything.

Run it through the ops service (scripts/ops.sh), on a schedule or by hand:

    AIGYM_OPS_COMMAND="python scripts/backup_db.py"

Dumps as the migrations role, which owns the tables. The app role could not
do this: it is NOBYPASSRLS by design (decision 16), so a dump taken as that
role would silently contain only the rows visible under whatever `app.gym_id`
happened to be set — an empty backup that looks like a successful one.
"""

import subprocess
import sys
from datetime import UTC, datetime

from app.backup import PREFIX, bucket_from_settings, libpq_url, missing_backup_settings
from app.settings import get_settings


def main() -> int:
    settings = get_settings()
    missing = missing_backup_settings()
    if missing:
        # Loud and non-zero. A backup job that "succeeds" while storing
        # nothing is the single worst outcome available here.
        print(f"Not configured — set {', '.join(missing)}. No backup taken.", file=sys.stderr)
        return 1

    bucket = bucket_from_settings()

    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    key = f"{PREFIX}{stamp}.dump"

    print(f"Dumping to {bucket.name}/{key}…")
    dump = subprocess.run(
        [
            "pg_dump",
            "--format=custom",
            "--no-password",
            libpq_url(settings.database_url_migrations),
        ],
        capture_output=True,
        check=False,
    )
    if dump.returncode != 0:
        print(dump.stderr.decode(errors="replace"), file=sys.stderr)
        return dump.returncode
    if not dump.stdout:
        print("pg_dump produced no output — refusing to store an empty backup.", file=sys.stderr)
        return 1

    bucket.put(key, dump.stdout)
    print(f"Stored {key} ({len(dump.stdout) / 1_048_576:.1f} MB)")

    # Prune only after the new dump is safely stored, so a failed upload
    # never costs an old one.
    existing = sorted(bucket.list(PREFIX), key=lambda o: o.key)
    for stale in existing[: max(0, len(existing) - settings.backup_keep)]:
        bucket.delete(stale.key)
        print(f"Pruned {stale.key}")

    print(f"{min(len(existing), settings.backup_keep)} dumps retained.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
