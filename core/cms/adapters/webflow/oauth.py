"""Webflow OAuth helpers — authorize URL, state tokens, code exchange, webhooks."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from core.cms.exceptions import CMSAuthError, CMSConnectionError

logger = logging.getLogger(__name__)

WEBFLOW_OAUTH_AUTHORIZE_URL = "https://webflow.com/oauth/authorize"
WEBFLOW_OAUTH_TOKEN_URL = "https://api.webflow.com/oauth/access_token"
WEBFLOW_OAUTH_SCOPES = "sites:read cms:read cms:write authorized_user:read assets:write"
WEBFLOW_OAUTH_STATE_PURPOSE = "webflow_oauth"
WEBFLOW_OAUTH_STATE_EXPIRY_MINUTES = 10


def create_webflow_oauth_state(
    *,
    secret_key: str,
    company_slug: str,
    return_url: str = "",
) -> str:
    """Create a signed, time-limited OAuth state token."""
    payload = {
        "company_slug": company_slug,
        "return_url": return_url,
        "purpose": WEBFLOW_OAUTH_STATE_PURPOSE,
        "exp": (
            datetime.now(timezone.utc)
            + timedelta(minutes=WEBFLOW_OAUTH_STATE_EXPIRY_MINUTES)
        ).isoformat(),
    }
    payload_bytes = json.dumps(payload).encode()
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode()
    sig = hmac.new(
        secret_key.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_webflow_oauth_state(secret_key: str, state: str) -> dict[str, Any] | None:
    """Verify and decode a Webflow OAuth state token."""
    try:
        parts = state.split(".", 1)
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
        exp = datetime.fromisoformat(payload.get("exp", ""))
        if datetime.now(timezone.utc) > exp:
            return None
        if payload.get("purpose") != WEBFLOW_OAUTH_STATE_PURPOSE:
            return None
        return payload
    except Exception:
        return None


def build_webflow_authorize_url(
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
) -> str:
    """Build the Webflow OAuth consent URL."""
    params = {
        "client_id": client_id,
        "response_type": "code",
        "scope": WEBFLOW_OAUTH_SCOPES,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"{WEBFLOW_OAUTH_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_webflow_authorization_code(
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """Exchange an authorization code for OAuth tokens."""
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    kwargs: dict[str, Any] = {"timeout": 30.0}
    if transport is not None:
        kwargs["transport"] = transport
    try:
        async with httpx.AsyncClient(**kwargs) as client:
            resp = await client.post(WEBFLOW_OAUTH_TOKEN_URL, json=payload)
    except httpx.ConnectError as exc:
        raise CMSConnectionError(f"Cannot reach Webflow OAuth: {exc}") from exc
    except httpx.TimeoutException as exc:
        raise CMSConnectionError(f"Webflow OAuth timeout: {exc}") from exc

    if resp.status_code >= 400:
        raise CMSAuthError(
            f"Webflow OAuth token exchange failed ({resp.status_code}): "
            f"{resp.text[:300]}"
        )
    data = resp.json()
    if not isinstance(data, dict) or not data.get("access_token"):
        raise CMSAuthError("Webflow OAuth response missing access_token")
    return data


def verify_webflow_webhook_signature(
    *,
    client_secret: str,
    timestamp: str,
    body: bytes,
    signature: str,
) -> bool:
    """Verify ``x-webflow-signature`` for an incoming webhook request."""
    if not client_secret or not timestamp or not signature:
        return False
    try:
        message = f"{timestamp}:{body.decode('utf-8')}"
        expected = hmac.new(
            client_secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception:
        logger.debug("webflow.webhook_signature_verify_failed", exc_info=True)
        return False
