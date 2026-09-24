"""Passwords and login tokens.

Passwords: we never store the password itself, only a salted scrypt hash. scrypt is deliberately
slow and memory-hungry, so even if the database leaks, guessing passwords is very expensive.
A random salt per user means two users with the same password get different hashes.

Tokens: after login the server hands out a JWT - a small signed JSON document saying "this is
user 7, valid until <date>". The browser sends it with every request. The server only needs to
check the signature (made with a secret key only the server knows), so no session table is needed.
"""

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt

# In production JWT_SECRET must be set to a long random value. The development fallback is
# fine locally, but anyone who knows it could forge tokens - never deploy with it.
# `or`, not a getenv default: an empty JWT_SECRET= line in .env must also fall back.
JWT_SECRET = os.getenv("JWT_SECRET") or "dev-only-insecure-secret-change-me"
JWT_ALGORITHM = "HS256"
TOKEN_LIFETIME = timedelta(days=7)

# scrypt cost parameters (the values recommended for interactive logins)
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1


def hash_password(password: str) -> str:
    """Returns "salt$hash" (both hex). The salt must be stored to verify later."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$")
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    # compare_digest takes the same time whether the first or last byte differs,
    # so an attacker can't learn the hash byte-by-byte by measuring response times.
    return hmac.compare_digest(digest.hex(), digest_hex)


def create_token(user_id: int, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + TOKEN_LIFETIME}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def user_id_from_token(token: str) -> int | None:
    """The user id inside a valid token, or None if the token is forged, malformed or expired."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])  # also checks "exp"
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None
