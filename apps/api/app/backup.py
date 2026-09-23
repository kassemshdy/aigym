"""What scripts/backup_db.py and scripts/restore_db.py both need.

It lives here rather than in one of the scripts because `scripts/` is not a
package — `python scripts/restore_db.py` puts `scripts/` on the path, not
the directory above it, so one script cannot import another. `app` is
installed, so this is importable from both.
"""

from app.integrations.object_storage import Bucket
from app.settings import get_settings

#: Every dump lives under this prefix, so retention can list them without
#: touching anything else that may end up in the same bucket later.
PREFIX = "db/"

_REQUIRED = (
    "backup_bucket",
    "backup_endpoint",
    "backup_access_key_id",
    "backup_secret_access_key",
)


def libpq_url(url: str) -> str:
    """SQLAlchemy carries its driver in the scheme; pg_dump and pg_restore
    do not know what `+psycopg` means and reject the whole URL."""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def missing_backup_settings() -> list[str]:
    """The environment-variable names that are not set, in the form a person
    reading a deploy log can act on."""
    settings = get_settings()
    return [
        f"AIGYM_{name.upper()}" for name in _REQUIRED if not getattr(settings, name, None)
    ]


def bucket_from_settings() -> Bucket:
    settings = get_settings()
    return Bucket(
        name=settings.backup_bucket or "",
        endpoint=settings.backup_endpoint or "",
        region=settings.backup_region,
        access_key_id=settings.backup_access_key_id or "",
        secret_access_key=settings.backup_secret_access_key or "",
    )
