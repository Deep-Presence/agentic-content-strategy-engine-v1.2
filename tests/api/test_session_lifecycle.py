"""Tests verifying DB session lifecycle in DI layer.

Every async-generator DI function that creates a DB session must:
1. Commit on success
2. Rollback on error
3. Always close the session (finally)
4. Skip session creation when an override is set on app.state
5. Fall through to JSON service when db_session_factory is absent
6. Close the session even if service construction fails
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.dependencies import (
    get_analytics_service,
    get_auth_service,
    get_brand_data_service,
    get_content_data_service,
    get_gap_data_service,
    get_kb_data_service,
    get_persona_data_service,
    get_prompt_library_service,
    get_site_audit_data_service,
    get_td_data_service,
    get_vsg_data_service,
)


# ── Helpers ──────────────────────────────────────────────────


def _make_mock_session() -> AsyncMock:
    """Return a mock AsyncSession with commit/rollback/close."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


def _make_mock_request(
    *,
    db_session_factory: Any = None,
    artifacts_root: Path | None = None,
    task_store: Any = None,
    secret_key: str | None = "test-secret",
    storage_backend: Any = None,
    **overrides: Any,
) -> MagicMock:
    """Build a mock Request with configurable app.state attributes."""
    request = MagicMock()
    state = MagicMock()
    state.db_session_factory = db_session_factory
    state.artifacts_root = artifacts_root or Path("/tmp/test-artifacts")
    state.task_store = task_store or MagicMock()
    state.secret_key = secret_key
    state.storage_backend = storage_backend
    state.auth_store = MagicMock()
    # Apply overrides (e.g., gap_data_service, brand_data_service)
    for key, val in overrides.items():
        setattr(state, key, val)
    request.app.state = state
    return request


async def _exhaust_generator(gen: Any) -> Any:
    """Advance an async generator, return the yielded value, then finalize."""
    value = await gen.__anext__()
    try:
        await gen.__anext__()
    except StopAsyncIteration:
        pass
    return value


async def _exhaust_generator_with_error(gen: Any, error: Exception) -> None:
    """Advance an async generator, then throw an error into it."""
    await gen.__anext__()
    try:
        await gen.athrow(error)
    except type(error):
        pass
    except StopAsyncIteration:
        pass


# ── Parametrized data service tests ─────────────────────────


# Each entry: (di_function, builder_patch_path, override_attr)
_DATA_SERVICE_CASES = [
    pytest.param(
        get_brand_data_service,
        "api.dependencies._build_db_brand_data_service",
        "brand_data_service",
        id="brand_data",
    ),
    pytest.param(
        get_content_data_service,
        "api.dependencies._build_db_content_data_service",
        "content_data_service",
        id="content_data",
    ),
    pytest.param(
        get_site_audit_data_service,
        "api.dependencies._build_db_site_audit_data_service",
        "site_audit_data_service",
        id="site_audit_data",
    ),
    pytest.param(
        get_kb_data_service,
        "api.dependencies._build_db_kb_data_service",
        "kb_data_service",
        id="kb_data",
    ),
    pytest.param(
        get_persona_data_service,
        "api.dependencies._build_db_persona_data_service",
        "persona_data_service",
        id="persona_data",
    ),
    pytest.param(
        get_vsg_data_service,
        "api.dependencies._build_db_vsg_data_service",
        "vsg_data_service",
        id="vsg_data",
    ),
    pytest.param(
        get_td_data_service,
        "api.dependencies._build_db_td_data_service",
        "td_data_service",
        id="td_data",
    ),
    pytest.param(
        get_gap_data_service,
        "api.dependencies._build_db_gap_data_service",
        "gap_data_service",
        id="gap_data",
    ),
]


class TestSessionCommitAndClose:
    """Verify session.commit() + session.close() on successful request."""

    @pytest.mark.parametrize("di_func,builder_path,override_attr", _DATA_SERVICE_CASES)
    @pytest.mark.asyncio
    async def test_session_committed_and_closed_on_success(
        self, di_func, builder_path, override_attr
    ):
        session = _make_mock_session()
        sf = MagicMock(return_value=session)
        mock_service = MagicMock()
        request = _make_mock_request(db_session_factory=sf)
        # Remove any override so the DB path is taken
        setattr(request.app.state, override_attr, None)

        with patch(builder_path, return_value=mock_service):
            gen = di_func(request)
            await _exhaust_generator(gen)

        session.commit.assert_awaited_once()
        session.close.assert_awaited()
        session.rollback.assert_not_awaited()

    @pytest.mark.parametrize("di_func,builder_path,override_attr", _DATA_SERVICE_CASES)
    @pytest.mark.asyncio
    async def test_session_rolled_back_and_closed_on_error(
        self, di_func, builder_path, override_attr
    ):
        session = _make_mock_session()
        sf = MagicMock(return_value=session)
        mock_service = MagicMock()
        request = _make_mock_request(db_session_factory=sf)
        setattr(request.app.state, override_attr, None)

        with patch(builder_path, return_value=mock_service):
            gen = di_func(request)
            await _exhaust_generator_with_error(gen, RuntimeError("boom"))

        session.rollback.assert_awaited_once()
        session.close.assert_awaited()
        session.commit.assert_not_awaited()


class TestConstructionFailureClosesSession:
    """When _build_db_* returns None, the session must still be closed."""

    @pytest.mark.parametrize("di_func,builder_path,override_attr", _DATA_SERVICE_CASES)
    @pytest.mark.asyncio
    async def test_session_closed_when_construction_fails(
        self, di_func, builder_path, override_attr
    ):
        session = _make_mock_session()
        sf = MagicMock(return_value=session)
        request = _make_mock_request(db_session_factory=sf)
        setattr(request.app.state, override_attr, None)

        # Builder returns None (construction failed)
        with patch(builder_path, return_value=None):
            gen = di_func(request)
            value = await _exhaust_generator(gen)

        # Should yield a JSON fallback service
        assert value is not None
        # Session must have been closed
        session.close.assert_awaited()


class TestOverrideBypassesSession:
    """When app.state has a pre-built override, no session should be created."""

    @pytest.mark.parametrize("di_func,builder_path,override_attr", _DATA_SERVICE_CASES)
    @pytest.mark.asyncio
    async def test_override_yields_service_without_session(
        self, di_func, builder_path, override_attr
    ):
        override_service = MagicMock()
        sf = MagicMock()
        request = _make_mock_request(
            db_session_factory=sf,
            **{override_attr: override_service},
        )

        with patch(builder_path) as mock_builder:
            gen = di_func(request)
            value = await _exhaust_generator(gen)

        assert value is override_service
        mock_builder.assert_not_called()
        sf.assert_not_called()


class TestJsonFallback:
    """When db_session_factory is None, the JSON service path is taken."""

    @pytest.mark.parametrize("di_func,builder_path,override_attr", _DATA_SERVICE_CASES)
    @pytest.mark.asyncio
    async def test_json_fallback_when_no_db(
        self, di_func, builder_path, override_attr
    ):
        request = _make_mock_request(db_session_factory=None)
        setattr(request.app.state, override_attr, None)

        gen = di_func(request)
        value = await _exhaust_generator(gen)

        # Should get a service (JSON fallback), not None
        assert value is not None


# ── Auth service specific tests ──────────────────────────────


class TestAuthServiceSessionLifecycle:
    """Auth service uses the same async generator pattern."""

    @pytest.mark.asyncio
    async def test_auth_session_committed_and_closed(self):
        session = _make_mock_session()
        sf = MagicMock(return_value=session)
        mock_service = MagicMock()
        request = _make_mock_request(db_session_factory=sf)
        setattr(request.app.state, "auth_service", None)

        with patch(
            "api.dependencies._build_db_auth_service",
            return_value=mock_service,
        ):
            gen = get_auth_service(request)
            await _exhaust_generator(gen)

        session.commit.assert_awaited_once()
        session.close.assert_awaited()

    @pytest.mark.asyncio
    async def test_auth_session_rolled_back_on_error(self):
        session = _make_mock_session()
        sf = MagicMock(return_value=session)
        mock_service = MagicMock()
        request = _make_mock_request(db_session_factory=sf)
        setattr(request.app.state, "auth_service", None)

        with patch(
            "api.dependencies._build_db_auth_service",
            return_value=mock_service,
        ):
            gen = get_auth_service(request)
            await _exhaust_generator_with_error(gen, RuntimeError("auth fail"))

        session.rollback.assert_awaited_once()
        session.close.assert_awaited()

    @pytest.mark.asyncio
    async def test_auth_secret_key_none_closes_session(self):
        """When secret_key is None, session is still closed."""
        session = _make_mock_session()
        sf = MagicMock(return_value=session)
        request = _make_mock_request(db_session_factory=sf, secret_key=None)
        setattr(request.app.state, "auth_service", None)

        gen = get_auth_service(request)
        value = await _exhaust_generator(gen)
        # Should fall through to JSON auth service
        assert value is not None
        # Session must have been closed
        session.close.assert_awaited()


# ── Analytics service specific tests ─────────────────────────


class TestAnalyticsServiceSessionLifecycle:
    """Analytics service creates session inline, not via a builder."""

    @pytest.mark.asyncio
    async def test_analytics_session_committed_and_closed(self):
        session = _make_mock_session()
        sf = MagicMock(return_value=session)
        request = _make_mock_request(db_session_factory=sf)
        setattr(request.app.state, "analytics_service", None)

        with patch("api.dependencies.AnalyticsService", create=True), \
             patch("api.dependencies.DailyRunResponseRepository", create=True), \
             patch("api.dependencies.DailyRunRepository", create=True):
            gen = get_analytics_service(request)
            await _exhaust_generator(gen)

        session.commit.assert_awaited_once()
        session.close.assert_awaited()

    @pytest.mark.asyncio
    async def test_analytics_override_skips_session(self):
        override = MagicMock()
        sf = MagicMock()
        request = _make_mock_request(
            db_session_factory=sf,
            analytics_service=override,
        )

        gen = get_analytics_service(request)
        value = await _exhaust_generator(gen)

        assert value is override
        sf.assert_not_called()
