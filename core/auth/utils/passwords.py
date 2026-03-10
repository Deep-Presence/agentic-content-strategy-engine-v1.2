"""Password hashing and verification — pure functions, no I/O.

Uses PBKDF2-HMAC-SHA256 with random salt.  Extracted from
``api.auth.store.AuthStore`` so both the JSON-backed and DB-backed
auth services share the same hashing logic.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets


# Constant-time dummy hash for login timing-oracle prevention (Codex W7).
# Used when a login attempt references a non-existent email — we still run
# verify_password against this so the timing is indistinguishable from a
# real password check.
DUMMY_HASH: str = "0" * 32 + ":" + "0" * 64


def hash_password(password: str) -> str:
    """Hash *password* with a random salt using PBKDF2-HMAC-SHA256.

    Returns ``"{salt_hex}:{hash_hex}"`` where *salt_hex* is 32 hex chars
    (16 bytes) and *hash_hex* is 64 hex chars (32 bytes / SHA-256).
    """
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 100_000
    )
    return f"{salt}:{hashed.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify *password* against a ``hash_password()``-produced hash.

    Uses ``hmac.compare_digest`` for constant-time comparison.
    Returns ``False`` on any parse error (malformed hash string).
    """
    try:
        salt, hash_hex = stored_hash.split(":", 1)
        expected = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), 100_000
        )
        return hmac.compare_digest(expected.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False
