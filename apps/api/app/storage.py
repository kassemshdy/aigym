"""Local-disk object storage for member-uploaded photos (progress photos,
food photos) — a Railway Volume mounted at AIGYM_MEDIA_ROOT, not S3/R2
(decision 28: no new vendor, same pattern Postgres already uses on this
project). A key is an opaque, freshly-minted filename; nothing about it
reveals which gym or member it belongs to — that access check happens one
layer up, against the database row that references it (photo_key), before
this module is ever touched. Every function here validates key format
itself too, so a value that somehow bypassed that check still can't be
used for path traversal.
"""

import re
import uuid
from pathlib import Path

from app.settings import get_settings

# Deliberately narrow — this is a photo-upload feature, not a general file
# store. Anything else in a multipart body is rejected before it reaches
# disk.
ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

_KEY_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp)$")


class UnsupportedContentType(ValueError):
    pass


class InvalidKey(ValueError):
    pass


def _path_for(key: str) -> Path:
    if not _KEY_RE.match(key):
        raise InvalidKey(key)
    root = Path(get_settings().media_root)
    root.mkdir(parents=True, exist_ok=True)
    return root / key


def save(data: bytes, content_type: str) -> str:
    """Writes `data` under a fresh random key and returns it."""
    extension = ALLOWED_CONTENT_TYPES.get(content_type)
    if extension is None:
        raise UnsupportedContentType(content_type)
    key = f"{uuid.uuid4().hex}.{extension}"
    _path_for(key).write_bytes(data)
    return key


def read(key: str) -> bytes | None:
    path = _path_for(key)
    if not path.is_file():
        return None
    return path.read_bytes()


def delete(key: str) -> None:
    """Idempotent — deleting an already-gone key is not an error, since
    decision 11 wants deletion to actually happen, including on a retry."""
    _path_for(key).unlink(missing_ok=True)


def content_type_for(key: str) -> str:
    match = _KEY_RE.match(key)
    if not match:
        raise InvalidKey(key)
    extension = match.group(1)
    return next(ct for ct, ext in ALLOWED_CONTENT_TYPES.items() if ext == extension)
