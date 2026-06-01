"""API regression: daily tracker prompt routes enforce workspace tenant scope."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app import create_app
from api.auth.store import AuthStore
from core.models.daily_tracker import PromptSource, TrackedPrompt
from core.services.db_task_store import DbTaskStore
from tests._support.auth_service import TestAuthService
from tests._support.event_bus import InMemoryEventBus
from tests._support.workspace_service import TestWorkspaceService

_NOW = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)


def _sample_prompt(prompt_id: str = "p-1", company_id: str = "test-co") -> TrackedPrompt:
    return TrackedPrompt(
        id=prompt_id,
        company_id=company_id,
        text="What is the best expense tool?",
        category="product_comparison",
        tags=["expense"],
        source=PromptSource.MANUAL,
        active=True,
        created_at=_NOW,
        updated_at=_NOW,
    )


@pytest.fixture()
def mock_prompt_service() -> AsyncMock:
    service = AsyncMock()
    service.get_prompt_for_company = AsyncMock(return_value=None)
    service.update_prompt_for_company = AsyncMock()
    return service


@pytest.fixture()
def dt_scope_app(tmp_path, mock_prompt_service: AsyncMock) -> FastAPI:
    application = create_app()
    event_bus = InMemoryEventBus()
    application.state.event_bus = event_bus
    application.state.task_store = DbTaskStore(
        session_factory=MagicMock(),
        max_concurrent=10,
    )
    artifacts_root = tmp_path / "artifacts"
    artifacts_root.mkdir(exist_ok=True)
    application.state.artifacts_root = artifacts_root
    auth_store = AuthStore(base_dir=artifacts_root)
    application.state.auth_store = auth_store
    application.state.secret_key = auth_store._secret_key
    application.state.auth_service = TestAuthService(auth_store)
    application.state.workspace_service = TestWorkspaceService(auth_store)

    auth_store.create_company("test-co", "Test Co", "testco.com")
    company = auth_store.get_company_by_slug("test-co")
    assert company is not None
    user = auth_store.create_user(
        company_id=company.id,
        email="dev@testco.com",
        password="testpassword123",
        first_name="Test",
        last_name="User",
        role="member",
    )
    token = auth_store.create_access_token(user.id, company.slug)
    application.state.prompt_library_service = mock_prompt_service
    application.state._test_token = token
    return application


class _AuthTestClient(TestClient):
    def __init__(self, app: FastAPI, token: str, **kwargs) -> None:
        super().__init__(app, headers={"Authorization": f"Bearer {token}"}, **kwargs)


@pytest.fixture()
def dt_client(dt_scope_app: FastAPI) -> TestClient:
    return _AuthTestClient(dt_scope_app, dt_scope_app.state._test_token)


def test_get_prompt_returns_404_when_prompt_belongs_to_other_workspace(
    dt_client: TestClient,
    mock_prompt_service: AsyncMock,
) -> None:
    prompt_id = str(uuid.uuid4())
    mock_prompt_service.get_prompt_for_company.return_value = None

    resp = dt_client.get(
        f"/api/v1/daily-tracker/prompts/{prompt_id}",
        params={"workspace_slug": "test-co"},
    )

    assert resp.status_code == 404
    mock_prompt_service.get_prompt_for_company.assert_awaited_once_with(
        prompt_id, "test-co"
    )


def test_get_prompt_analytics_requires_workspace_and_scoped_lookup(
    dt_client: TestClient,
    mock_prompt_service: AsyncMock,
) -> None:
    prompt_id = str(uuid.uuid4())
    mock_prompt_service.get_prompt_for_company.return_value = None

    resp = dt_client.get(
        f"/api/v1/daily-tracker/prompts/{prompt_id}/analytics",
        params={"workspace_slug": "test-co"},
    )

    assert resp.status_code == 404
    mock_prompt_service.get_prompt_for_company.assert_awaited_once_with(
        prompt_id, "test-co"
    )


def test_viewer_cannot_update_prompt_in_workspace(
    dt_scope_app: FastAPI,
    mock_prompt_service: AsyncMock,
) -> None:
    ws_service = dt_scope_app.state.workspace_service
    user = dt_scope_app.state.auth_store.get_user_by_email("dev@testco.com")
    assert user is not None
    ws_service._membership_roles.setdefault(user["id"], {})["test-co"] = "viewer"

    client = _AuthTestClient(dt_scope_app, dt_scope_app.state._test_token)
    prompt_id = str(uuid.uuid4())

    resp = client.put(
        f"/api/v1/daily-tracker/prompts/{prompt_id}",
        params={"workspace_slug": "test-co"},
        json={"text": "updated"},
    )

    assert resp.status_code == 403
    mock_prompt_service.update_prompt_for_company.assert_not_awaited()
