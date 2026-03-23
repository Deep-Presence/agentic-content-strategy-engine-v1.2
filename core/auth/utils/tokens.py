"""JWT-like token creation and verification — pure functions, no I/O.

v0 format: base64-encoded JSON payload + HMAC-SHA256 signature.
Will be replaced by proper JWT or external auth provider later.

Extracted from ``api.auth.store.AuthStore`` so both the JSON-backed
and DB-backed auth services (and the ASGI middleware) share the same
token logic.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_secret_key() -> str:
    """Resolve the JWT signing secret.

    - If ``JWT_SECRET_KEY`` env var is set, use it.
    - In ``development`` / ``test`` environments (``ENVIRONMENT`` env var),
      auto-generate a random key.
    - Otherwise raise ``RuntimeError`` — production MUST set the key.
    """
    secret = os.environ.get("JWT_SECRET_KEY")
    if secret:
        return secret
    env = os.environ.get("ENVIRONMENT", "development")
    if env not in ("development", "test"):
        raise RuntimeError(
            "JWT_SECRET_KEY must be set in non-development environments"
        )
    return secrets.token_hex(32)


def create_access_token(
    secret_key: str,
    user_id: str,
    company_slug: str,
    expires_hours: int = 24,
) -> str:
    """Create a v0 access token (base64 payload + HMAC-SHA256 signature)."""
    payload: Dict[str, object] = {
        "user_id": user_id,
        "company_slug": company_slug,
        "exp": (_utcnow() + timedelta(hours=expires_hours)).isoformat(),
    }
    payload_bytes = json.dumps(payload).encode()
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode()
    sig = hmac.new(
        secret_key.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return f"{payload_b64}.{sig}"


def create_stream_token(
    secret_key: str,
    user_id: str,
    company_slug: str,
    expires_minutes: int = 60,
) -> str:
    """Create a stream token for SSE EventSource clients.

    Default TTL is 60 minutes to accommodate long-running pipelines
    (onboarding can exceed 30 minutes).  Includes ``stream_only: true``
    so the middleware prevents reuse on non-SSE endpoints (Codex C4).
    """
    payload: Dict[str, object] = {
        "user_id": user_id,
        "company_slug": company_slug,
        "stream_only": True,
        "exp": (_utcnow() + timedelta(minutes=expires_minutes)).isoformat(),
    }
    payload_bytes = json.dumps(payload).encode()
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode()
    sig = hmac.new(
        secret_key.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_token(secret_key: str, token: str) -> Optional[Dict[str, str]]:
    """Verify and decode a v0 token.

    Returns the payload dict if valid and not expired, else ``None``.
    """
    try:
        parts = token.split(".", 1)
        if len(parts) != 2:
            return None
        payload_b64, sig = parts
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        expected_sig = hmac.new(
            secret_key.encode(), payload_bytes, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        payload = json.loads(payload_bytes)
        exp = datetime.fromisoformat(payload["exp"])
        if _utcnow() > exp:
            return None
        return payload
    except Exception:
        return None
