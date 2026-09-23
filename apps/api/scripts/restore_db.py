"""Restore a dump from the backup bucket into a database.

A backup nobody has ever restored is a hope, not a backup — so this exists
for the same reason scripts/backup_db.py does, and the two are only worth
anything together. It is also the tool that moves the database between
servers: restoring last night's dump onto a new Postgres is the same
operation as recovering from losing the old one.

    AIGYM_OPS_COMMAND="python scripts/restore_db.py --into <url>"
    AIGYM_OPS_COMMAND="python scripts/restore_db.py --into <url> --key db/2026-09-23T02-00-00Z.dump"

`--into` is a full SQLAlchemy or libpq URL for the target, as the owner —
not the app role, which is NOBYPASSRLS and cannot create tables or policies.
The target database and the app role must already exist, because the dump's
GRANTs and RLS policies name that role: run scripts/bootstrap_db.sh against
the target first.

**It refuses to restore into a database that already holds rows** unless
--force is passed. Restoring over live data is the one irreversible thing in
this file, and "I pointed it at the wrong URL" is the likeliest way anyone
ever does it.
"""

import argparse
import subprocess
import sys
import tempfile

from app.backup import PREFIX, bucket_from_settings, libpq_url, missing_backup_settings


def row_count(target: str) -> int:
    """Every row in every public table. psql rather than SQLAlchemy because
    the target is a URL from the command line, not the app's own database,
    and this must work before anything has been restored into it."""
    sql = """
        SELECT coalesce(sum(n), 0) FROM (
          SELECT (xpath('/row/c/text()',
            query_to_xml(format('SELECT count(*) AS c FROM %I.%I', table_schema, table_name),
                         false, true, '')))[1]::text::bigint AS n
          FROM information_schema.tables
          WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ) counts
    """
    result = subprocess.run(
        ["psql", "--no-password", "-tAX", "-c", sql, target],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        # An empty target that does not exist yet is a real error here:
        # bootstrap_db.sh is meant to have created it already.
        raise SystemExit(result.stderr.decode(errors="replace"))
    return int(result.stdout.decode().strip() or 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--into", required=True, help="target database URL, as the owner")
    parser.add_argument("--key", default="latest", help="bucket key, or 'latest'")
    parser.add_argument(
        "--force",
        action="store_true",
        help="restore even though the target already holds rows",
    )
    args = parser.parse_args()
    target = libpq_url(args.into)

    existing = row_count(target)
    if existing and not args.force:
        print(
            f"Target already holds {existing} rows. Refusing without --force.",
            file=sys.stderr,
        )
        return 1

    missing = missing_backup_settings()
    if missing:
        print(f"Not configured — set {', '.join(missing)}.", file=sys.stderr)
        return 1
    bucket = bucket_from_settings()
    if args.key == "latest":
        dumps = sorted(bucket.list(PREFIX), key=lambda o: o.key)
        if not dumps:
            print(f"No dumps under {PREFIX} in {bucket.name}.", file=sys.stderr)
            return 1
        key = dumps[-1].key
    else:
        key = args.key

    print(f"Restoring {bucket.name}/{key} into {target.split('@')[-1]}…")
    body = bucket._send("GET", key).content

    with tempfile.NamedTemporaryFile(suffix=".dump") as handle:
        handle.write(body)
        handle.flush()
        restore = subprocess.run(
            [
                "pg_restore",
                "--no-password",
                # The dump is owned by the migrations role and its policies
                # name the app role. Both exist on the target already
                # (bootstrap_db.sh), so ownership and grants carry over as
                # they are rather than being flattened with --no-owner.
                "--dbname",
                target,
                handle.name,
            ],
            capture_output=True,
            check=False,
        )

    stderr = restore.stderr.decode(errors="replace")
    if stderr:
        print(stderr, file=sys.stderr)
    if restore.returncode != 0:
        return restore.returncode

    restored = row_count(target)
    print(f"Restored. Target now holds {restored} rows.")
    if restored == 0:
        # pg_restore exits 0 having done nothing useful more readily than
        # you would like. Counting is the only claim worth making.
        print("Nothing landed — treat this restore as failed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
