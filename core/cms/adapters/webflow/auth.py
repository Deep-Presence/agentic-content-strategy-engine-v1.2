"""Webflow credential envelope helpers (Site Token v1, OAuth-ready)."""
from __future__ import annotations

import json
from typing import Any

from core.cms.webflow_models import WebflowAuthKind

# Stored inside encrypted_credentials alongside legacy username/api_key keys.
AUTH_TYPE_KEY = "auth_type"
ACCESS_TOKEN_KEY = "access_token"
REFRESH_TOKEN_KEY = "refresh_token"
TOKEN_EXPIRES_AT_KEY = "token_expires_at"


def webflow_auth_kind_from_payload(payload: dict[str, Any]) -> WebflowAuthKind:
    raw = payload.get(AUTH_TYPE_KEY, WebflowAuthKind.site_token.value)
    try:
        return WebflowAuthKind(str(raw))
    except ValueError:
        return WebflowAuthKind.site_token


def resolve_webflow_access_token(payload: dict[str, Any]) -> str:
    """Return bearer token for Webflow API calls."""
    kind = webflow_auth_kind_from_payload(payload)
    if kind == WebflowAuthKind.oauth:
        token = str(payload.get(ACCESS_TOKEN_KEY, "")).strip()
        if token:
            return token
    # Site token v1: stored as api_key (legacy envelope) or access_token
    return str(payload.get(ACCESS_TOKEN_KEY, "") or payload.get("api_key", "")).strip()


def build_webflow_site_token_payload(*, api_key: str) -> dict[str, str]:
    return {
        "username": "",
        "api_key": api_key,
        AUTH_TYPE_KEY: WebflowAuthKind.site_token.value,
        ACCESS_TOKEN_KEY: api_key,
    }


def build_webflow_oauth_payload(
    *,
    access_token: str,
    refresh_token: str = "",
    expires_at: str = "",
) -> dict[str, str]:
    """Build encrypted credential payload for OAuth (future WF-2)."""
    payload: dict[str, str] = {
        "username": "",
        "api_key": "",
        AUTH_TYPE_KEY: WebflowAuthKind.oauth.value,
        ACCESS_TOKEN_KEY: access_token,
    }
    if refresh_token:
        payload[REFRESH_TOKEN_KEY] = refresh_token
    if expires_at:
        payload[TOKEN_EXPIRES_AT_KEY] = expires_at
    return payload


def encrypt_credential_payload(payload: dict[str, Any], *, fernet_key: str) -> str:
    from cryptography.fernet import Fernet

    return Fernet(fernet_key.encode()).encrypt(json.dumps(payload).encode()).decode()


def decrypt_credential_payload(encrypted: str, *, fernet_key: str) -> dict[str, Any]:
    from cryptography.fernet import Fernet

    decrypted = Fernet(fernet_key.encode()).decrypt(encrypted.encode())
    data = json.loads(decrypted)
    if not isinstance(data, dict):
        return {}
    return data
