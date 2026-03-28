"""Shared fixtures for API tests.

All fixtures that return a ``TestClient`` inject a valid auth token
automatically so that the default-deny middleware does not block
requests.  Use ``public_client`` for testing 401 enforcement.

Phase 6: Switched from JSON TaskStore + in-memory EventBus to
DbTaskStore (mocked session) + InMemoryEventBus (test-only) +
TestAuthService (test-only).
"""
from __future__ import annotations

from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from api.app import create_app
from api.auth.store import AuthStore
from core.models.organization import Company, UserProfile
from core.storage.backends.local import LocalStorageBackend
from tests._support.auth_service import TestAuthService
from tests._support.event_bus import InMemoryEventBus


# ── Infrastructure fixtures ────────────────────────────────


@pytest.fixture
def event_bus() -> InMemoryEventBus:
    return InMemoryEventBus()


@pytest.fixture
def task_store():
    """DbTaskStore with mocked session_factory — no real DB needed.

    Follows the same pattern as tests/services/test_db_task_store.py.
    All in-memory operations (CRUD, locks, approval) work normally.
    DB write-through is suppressed by the _patch_db_writes autouse fixture.
    """
    from core.services.db_task_store import DbTaskStore

    return DbTaskStore(session_factory=MagicMock(), max_concurrent=10)


@pytest.fixture(autouse=True)
def _patch_db_writes(monkeypatch):
    """Prevent DbTaskStore background DB writes in tests.

    DbTaskStore.create_task() and update_task() schedule DB writes via
    ``asyncio.create_task(self._db_create/update(...))``.  In tests:
    - ``_db_create`` / ``_db_update`` are replaced with instant no-ops
    - The ``asyncio.create_task`` call may fail in sync tests (no event loop),
      so we proxy it to gracefully degrade on failure.

    Uses a module-level proxy so only db_task_store's asyncio reference is
    affected — the real ``asyncio.create_task`` remains intact for routers.
    """
    import asyncio as _aio
    from unittest.mock import AsyncMock
    from core.services import db_task_store as _mod

    _real_create_task = _aio.create_task

    def _safe_create_task(coro, **kwargs):
        """Try real create_task; if no event loop (sync test), close and fake."""
        try:
            return _real_create_task(coro, **kwargs)
        except RuntimeError:
            coro.close()
            return MagicMock()

    class _AsyncioProxy:
        """Proxy that delegates to real asyncio but overrides create_task."""
        create_task = staticmethod(_safe_create_task)

        def __getattr__(self, name):
            return getattr(_aio, name)

    monkeypatch.setattr(_mod, "asyncio", _AsyncioProxy())
    monkeypatch.setattr(_mod.DbTaskStore, "_db_create", AsyncMock())
    monkeypatch.setattr(_mod.DbTaskStore, "_db_update", AsyncMock())


@pytest.fixture
def artifacts_root(tmp_path: Path) -> Path:
    root = tmp_path / "artifacts"
    root.mkdir(exist_ok=True)
    return root


@pytest.fixture
def auth_store(artifacts_root: Path) -> AuthStore:
    return AuthStore(base_dir=artifacts_root)


# ── Auth fixtures ──────────────────────────────────────────


@pytest.fixture
def test_company(auth_store: AuthStore) -> Company:
    """Create a standard test company and return it."""
    auth_store.create_company("test-co", "Test Co", "testco.com")
    company = auth_store.get_company_by_slug("test-co")
    assert company is not None
    return company


@pytest.fixture
def test_user(auth_store: AuthStore, test_company: Company) -> UserProfile:
    """Create a test user (member role) in the test company."""
    return auth_store.create_user(
        company_id=test_company.id,
        email="dev@testco.com",
        password="testpassword123",
        first_name="Test",
        last_name="User",
        role="member",
    )


@pytest.fixture
def auth_token(auth_store: AuthStore, test_user: UserProfile, test_company: Company) -> str:
    """Return a valid Bearer token for the test user."""
    return auth_store.create_access_token(test_user.id, test_company.slug)


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    """Return Authorization header dict for the test user."""
    return {"Authorization": f"Bearer {auth_token}"}


# ── App fixture ────────────────────────────────────────────


@pytest.fixture
def app(
    task_store,
    event_bus,
    artifacts_root: Path,
    auth_store: AuthStore,
) -> FastAPI:
    application = create_app()
    application.state.task_store = task_store
    application.state.event_bus = event_bus
    application.state.artifacts_root = artifacts_root
    application.state.auth_store = auth_store
    # Pin local storage backend — prevents R2 usage if STORAGE_BACKEND=r2 in env
    application.state.storage_backend = LocalStorageBackend(artifacts_root)
    # Expose secret_key for ASGI middleware (decoupled from AuthStore)
    application.state.secret_key = auth_store._secret_key
    # Pre-build auth service for test isolation (bypasses DB-backed get_auth_service() DI)
    application.state.auth_service = TestAuthService(auth_store)
    return application


# ── TestClient fixtures ────────────────────────────────────


class _AuthTestClient(TestClient):
    """TestClient that auto-injects auth headers on every request.

    If the caller explicitly provides an ``Authorization`` header,
    the auto-injected one is NOT used (allows per-test overrides).

    Default headers are passed via ``httpx.Client(headers=...)`` so they
    apply to both ``request()`` and ``stream()`` calls automatically.
    """

    def __init__(self, app: FastAPI, default_headers: dict[str, str], **kwargs):
        super().__init__(app, headers=default_headers, **kwargs)
        self._default_auth_headers = default_headers

    def request(self, method: str, url: str, **kwargs):  # type: ignore[override]
        headers = dict(kwargs.pop("headers", None) or {})
        if "Authorization" not in headers:
            headers.update(self._default_auth_headers)
        return super().request(method, url, headers=headers, **kwargs)


@pytest.fixture
def client(app: FastAPI, auth_headers: dict[str, str]) -> TestClient:
    """Authenticated test client — requests include a valid Bearer token.

    Use ``public_client`` for testing unauthenticated access.
    """
    return _AuthTestClient(app, default_headers=auth_headers)


@pytest.fixture
def public_client(app: FastAPI) -> TestClient:
    """Unauthenticated test client for testing 401/403 enforcement."""
    return TestClient(app)


@pytest.fixture
def viewer_client(
    app: FastAPI,
    auth_store: AuthStore,
    test_company: Company,
) -> TestClient:
    """Viewer-role test client for RBAC tests (read-only access)."""
    viewer = auth_store.create_user(
        company_id=test_company.id,
        email="viewer@testco.com",
        password="viewerpass123",
        first_name="View",
        last_name="Only",
        role="viewer",
    )
    token = auth_store.create_access_token(viewer.id, test_company.slug)
    return _AuthTestClient(app, default_headers={"Authorization": f"Bearer {token}"})


@pytest.fixture
def superuser_client(
    app: FastAPI,
    auth_store: AuthStore,
    test_company: Company,
) -> TestClient:
    """Superuser-role test client for admin tests."""
    su = auth_store.create_user(
        company_id=test_company.id,
        email="admin@testco.com",
        password="adminpass123",
        first_name="Admin",
        last_name="User",
        role="superuser",
    )
    token = auth_store.create_access_token(su.id, test_company.slug)
    return _AuthTestClient(app, default_headers={"Authorization": f"Bearer {token}"})


# ── Async client fixtures ─────────────────────────────────


@pytest.fixture
async def async_client(
    app: FastAPI, auth_headers: dict[str, str]
) -> AsyncGenerator[AsyncClient, None]:
    """Authenticated async client for SSE / streaming tests."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers,
    ) as ac:
        yield ac


@pytest.fixture
async def async_public_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Unauthenticated async client for testing 401 enforcement."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
