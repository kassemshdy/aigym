"""Bcrypt hashing shared by staff PINs and member login codes.

Both are short, low-entropy secrets (a 4-6 digit PIN, a 6-digit code), so the
defense is never the hash alone — it's hashing plus single-use plus a short
expiry plus rate-limiting on the request side (app/api/auth.py).
"""

import bcrypt


def hash_secret(secret: str) -> str:
    return bcrypt.hashpw(secret.encode(), bcrypt.gensalt()).decode()


def verify_secret(secret: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(secret.encode(), hashed.encode())
    except ValueError:
        return False
