"""Tests for Webflow OAuth helpers and CMSService OAuth flows."""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from core.cms.adapters.webflow.oauth import (
    build_webflow_authorize_url,
    create_webflow_oauth_state,
    exchange_webflow_authorization_code,
    verify_webflow_oauth_state,
    verify_webflow_webhook_signature,
)
from core.cms.exceptions import CMSError
from core.services.cms_service import CMSService


def test_create_and_verify_oauth_state() -> None:
    state = create_webflow_oauth_state(
        secret_key="test-secret",
        company_slug="test-co",
        return_url="https://app.example/settings?tab=integrations",
    )
    payload = verify_webflow_oauth_state("test-secret", state)
    assert payload is not None
    assert payload["company_slug"] == "test-co"
    assert payload["purpose"] == "webflow_oauth"


def test_build_authorize_url_contains_client_and_scope() -> None:
    url = build_webflow_authorize_url(
        client_id="client-123",
        redirect_uri="http://localhost:8000/callback",
        state="signed-state",
    )
    assert "client_id=client-123" in url
    assert "cms%3Aread" in url
    assert "state=signed-state" in url


@pytest.mark.asyncio
async def test_exchange_authorization_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert body["grant_type"] == "authorization_code"
        assert body["code"] == "auth-code"
        return httpx.Response(
            200,
            json={"access_token": "wf-access", "token_type": "bearer"},
        )

    transport = httpx.MockTransport(handler)
    data = await exchange_webflow_authorization_code(
        client_id="cid",
        client_secret="secret",
        redirect_uri="http://localhost/cb",
        code="auth-code",
        transport=transport,
    )
    assert data["access_token"] == "wf-access"


def test_verify_webhook_signature() -> None:
    body = b'{"triggerType":"collection_item_changed","payload":{}}'
    timestamp = "1710000000"
    secret = "wh-secret"
    message = f"{timestamp}:{body.decode('utf-8')}"
    signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    assert verify_webflow_webhook_signature(
        client_secret=secret,
        timestamp=timestamp,
        body=body,
        signature=signature,
    )


def _make_cms_service(**overrides: Any) -> CMSService:
    defaults: dict[str, Any] = {
        "connection_repo": MagicMock(),
        "publish_repo": MagicMock(),
        "synced_post_repo": MagicMock(),
        "storage": MagicMock(),
        "fernet_key": "dGVzdF9rZXlfMTIzNDU2Nzg5MDEyMzQ1Ng==",
        "webflow_oauth_client_id": "cid",
        "webflow_oauth_client_secret": "secret",
        "webflow_oauth_redirect_uri": "http://localhost/cb",
        "webflow_webhook_public_url": "http://localhost/hook",
    }
    defaults.update(overrides)
    return CMSService(**defaults)


def test_generate_authorize_url_requires_config() -> None:
    svc = _make_cms_service(webflow_oauth_client_id=None)
    with pytest.raises(CMSError):
        svc.generate_webflow_authorize_url(
            secret_key="s",
            company_slug="test-co",
        )


def test_generate_authorize_url_success() -> None:
    svc = _make_cms_service()
    url = svc.generate_webflow_authorize_url(
        secret_key="secret",
        company_slug="test-co",
    )
    assert "webflow.com/oauth/authorize" in url
