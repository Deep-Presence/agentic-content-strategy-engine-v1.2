"""Unit tests for core.research.audience_persona.persistence — AP DB persistence hooks.

Pure unit tests — no real DB needed. All DB interaction is mocked via
AsyncMock session factories and patched repositories.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.research.audience_persona.persistence import (
    _sha256,
    _should_persist,
    _word_count,
    persist_persona_profile_doc,
    persist_persona_run,
    persist_persona_status_update,
)


# ── Shared fixtures ──────────────────────────────────────────────────────

RUN_ID = uuid.uuid4()
COMPANY_ID = uuid.uuid4()
PERSONA_RUN_DB_ID = uuid.uuid4()
SLUG = "test-co"
CONTENT_MD = "# CFO Persona\n\nEnterprise finance leader."


class _FakeSession:
    def __init__(self) -> None:
        self.commit = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def _make_session_factory() -> MagicMock:
    session = _FakeSession()
    factory = MagicMock()
    factory.return_value = session
    factory._session = session
    return factory


_PERSONA_RUN_REPO = "core.db.repositories.persona_repo.PersonaRunRepository"
_PERSONA_PROFILE_REPO = "core.db.repositories.persona_repo.PersonaProfileRepository"


# ── Guard Tests ──────────────────────────────────────────────────────────


class TestShouldPersist:
    def test_all_present_returns_true(self):
        assert _should_persist(MagicMock(), RUN_ID, COMPANY_ID) is True

    def test_none_session_factory_returns_false(self):
        assert _should_persist(None, RUN_ID, COMPANY_ID) is False

    def test_none_run_id_returns_false(self):
        assert _should_persist(MagicMock(), None, COMPANY_ID) is False


# ── persist_persona_run ──────────────────────────────────────────────────


class TestPersistPersonaRun:
    @patch(_PERSONA_RUN_REPO)
    async def test_returns_run_id(self, mock_repo_cls):
        factory = _make_session_factory()
        mock_run = MagicMock()
        mock_run.id = PERSONA_RUN_DB_ID
        mock_repo_cls.return_value.upsert_run = AsyncMock(return_value=mock_run)

        result = await persist_persona_run(
            factory, RUN_ID, COMPANY_ID, SLUG,
        )
        assert result == PERSONA_RUN_DB_ID
        factory._session.commit.assert_awaited_once()

    async def test_returns_none_when_not_configured(self):
        result = await persist_persona_run(None, RUN_ID, COMPANY_ID, SLUG)
        assert result is None

    @patch(_PERSONA_RUN_REPO)
    async def test_exception_returns_none(self, mock_repo_cls):
        factory = _make_session_factory()
        mock_repo_cls.return_value.upsert_run = AsyncMock(
            side_effect=RuntimeError("DB down")
        )
        result = await persist_persona_run(factory, RUN_ID, COMPANY_ID, SLUG)
        assert result is None


# ── persist_persona_profile_doc ──────────────────────────────────────────


class TestPersistPersonaProfileDoc:
    @patch(_PERSONA_PROFILE_REPO)
    async def test_persists_profile(self, mock_repo_cls):
        factory = _make_session_factory()
        upsert = AsyncMock()
        mock_repo_cls.return_value.upsert_profile = upsert

        await persist_persona_profile_doc(
            factory, RUN_ID, COMPANY_ID, PERSONA_RUN_DB_ID,
            "cfo-001", "CFO Persona", 1, CONTENT_MD,
            "audience_personas/test-co/cfo-001/v1.md",
            kind="icp",
        )
        upsert.assert_awaited_once()
        kwargs = upsert.call_args[1]
        assert kwargs["persona_id"] == "cfo-001"
        assert kwargs["persona_name"] == "CFO Persona"
        assert kwargs["kind"] == "icp"
        assert kwargs["content_hash"] == _sha256(CONTENT_MD)
        assert kwargs["word_count"] == _word_count(CONTENT_MD)

    async def test_no_persist_when_session_none(self):
        await persist_persona_profile_doc(
            None, RUN_ID, COMPANY_ID, PERSONA_RUN_DB_ID,
            "cfo-001", "CFO", 1, CONTENT_MD, "key",
        )

    async def test_no_persist_when_run_db_id_none(self):
        factory = _make_session_factory()
        await persist_persona_profile_doc(
            factory, RUN_ID, COMPANY_ID, None,
            "cfo-001", "CFO", 1, CONTENT_MD, "key",
        )
        factory._session.commit.assert_not_awaited()

    @patch(_PERSONA_PROFILE_REPO)
    async def test_exception_caught(self, mock_repo_cls):
        factory = _make_session_factory()
        mock_repo_cls.return_value.upsert_profile = AsyncMock(
            side_effect=RuntimeError("fail")
        )
        await persist_persona_profile_doc(
            factory, RUN_ID, COMPANY_ID, PERSONA_RUN_DB_ID,
            "cfo-001", "CFO", 1, CONTENT_MD, "key",
        )


# ── persist_persona_status_update ────────────────────────────────────────


class TestPersistPersonaStatusUpdate:
    @patch(_PERSONA_RUN_REPO)
    async def test_updates_status(self, mock_repo_cls):
        factory = _make_session_factory()
        mock_repo_cls.return_value.update_status = AsyncMock()

        await persist_persona_status_update(factory, PERSONA_RUN_DB_ID, "completed")
        mock_repo_cls.return_value.update_status.assert_awaited_once()
        factory._session.commit.assert_awaited_once()

    async def test_no_op_when_factory_none(self):
        await persist_persona_status_update(None, PERSONA_RUN_DB_ID, "completed")

    async def test_no_op_when_run_id_none(self):
        factory = _make_session_factory()
        await persist_persona_status_update(factory, None, "completed")
        factory._session.commit.assert_not_awaited()

    @patch(_PERSONA_RUN_REPO)
    async def test_exception_caught(self, mock_repo_cls):
        factory = _make_session_factory()
        mock_repo_cls.return_value.update_status = AsyncMock(
            side_effect=RuntimeError("fail")
        )
        await persist_persona_status_update(
            factory, PERSONA_RUN_DB_ID, "completed",
        )
