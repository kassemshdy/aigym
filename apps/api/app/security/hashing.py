"""Bcrypt hashing shared by staff PINs and member login codes, plus the
generator for the one secret this service mints itself.

Both PINs and codes are short, low-entropy secrets (a 4-6 digit PIN, a
6-digit code), so the defense is never the hash alone — it's hashing plus
single-use plus a short expiry plus rate-limiting on the request side
(app/api/auth.py).
"""

import secrets

import bcrypt


def hash_secret(secret: str) -> str:
    return bcrypt.hashpw(secret.encode(), bcrypt.gensalt()).decode()


def verify_secret(secret: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(secret.encode(), hashed.encode())
    except ValueError:
        return False


def generate_password() -> str:
    """A fresh staff password, for the two places that mint one: the
    self-service reset (app/api/auth.py) and a manager resetting someone
    else's (app/api/staff.py). Lives here so both cannot drift apart.

    8 hex chars ~ 32 bits of entropy — short enough to read off a phone
    screen and type, long enough that this isn't just a renamed 4-digit PIN.
    """
    return secrets.token_hex(4)
