"""Unit tests for core.research.voice_style_guide.persistence — VSG DB persistence hooks.

Pure unit tests — no real DB needed. All DB interaction is mocked via
AsyncMock session factories and patched repositories.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.research.voice_style_guide.persistence import (
    _sha256,
    _should_persist,
    _word_count,
    persist_vsg_author_doc,
    persist_vsg_guide_doc,
    persist_vsg_run,
    persist_vsg_status_update,
)


# ── Shared fixtures ──────────────────────────────────────────────────────

RUN_ID = uuid.uuid4()
COMPANY_ID = uuid.uuid4()
VSG_RUN_DB_ID = uuid.uuid4()
SLUG = "test-co"
CONTENT_MD = "# Voice Style Guide\n\nAuthoritative yet approachable."


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


_VSG_RUN_REPO = "core.db.repositories.vsg_repo.VSGRunRepository"
_VSG_AUTHOR_REPO = "core.db.repositories.vsg_repo.VSGAuthorRepository"
_VSG_GUIDE_REPO = "core.db.repositories.vsg_repo.VSGGuideRepository"


# ── Guard Tests ──────────────────────────────────────────────────────────


class TestShouldPersist:
    def test_all_present_returns_true(self):
        assert _should_persist(MagicMock(), RUN_ID, COMPANY_ID) is True

    def test_none_session_factory_returns_false(self):
        assert _should_persist(None, RUN_ID, COMPANY_ID) is False

    def test_none_run_id_returns_false(self):
        assert _should_persist(MagicMock(), None, COMPANY_ID) is False


# ── persist_vsg_run ──────────────────────────────────────────────────────


class TestPersistVSGRun:
    @patch(_VSG_RUN_REPO)
    async def test_returns_run_id(self, mock_repo_cls):
        factory = _make_session_factory()
        mock_run = MagicMock()
        mock_run.id = VSG_RUN_DB_ID
        mock_repo_cls.return_value.upsert_run = AsyncMock(return_value=mock_run)

        result = await persist_vsg_run(
            factory, RUN_ID, COMPANY_ID, SLUG,
        )
        assert result == VSG_RUN_DB_ID
        factory._session.commit.assert_awaited_once()

    async def test_returns_none_when_not_configured(self):
        result = await persist_vsg_run(None, RUN_ID, COMPANY_ID, SLUG)
        assert result is None

    @patch(_VSG_RUN_REPO)
    async def test_exception_returns_none(self, mock_repo_cls):
        factory = _make_session_factory()
        mock_repo_cls.return_value.upsert_run = AsyncMock(
            side_effect=RuntimeError("DB down")
        )
        result = await persist_vsg_run(factory, RUN_ID, COMPANY_ID, SLUG)
        assert result is None


# ── persist_vsg_author_doc ───────────────────────────────────────────────


class TestPersistVSGAuthorDoc:
    @patch(_VSG_AUTHOR_REPO)
    async def test_persists_author(self, mock_repo_cls):
        factory = _make_session_factory()
        upsert = AsyncMock()
        mock_repo_cls.return_value.upsert_author = upsert

        await persist_vsg_author_doc(
            factory, RUN_ID, COMPANY_ID, VSG_RUN_DB_ID,
            "author-001", "Jane Doe", 1, CONTENT_MD,
            "voice_style_guide/test-co/author-001/v1.md",
        )
        upsert.assert_awaited_once()
        kwargs = upsert.call_args[1]
        assert kwargs["author_id"] == "author-001"
        assert kwargs["name"] == "Jane Doe"
        assert kwargs["content_hash"] == _sha256(CONTENT_MD)
        assert kwargs["word_count"] == _word_count(CONTENT_MD)

    async def test_no_persist_when_session_none(self):
        await persist_vsg_author_doc(
            None, RUN_ID, COMPANY_ID, VSG_RUN_DB_ID,
            "author-001", "Jane Doe", 1, CONTENT_MD, "key",
        )

    async def test_no_persist_when_run_db_id_none(self):
        factory = _make_session_factory()
        await persist_vsg_author_doc(
            factory, RUN_ID, COMPANY_ID, None,
            "author-001", "Jane Doe", 1, CONTENT_MD, "key",
        )
        factory._session.commit.assert_not_awaited()

    @patch(_VSG_AUTHOR_REPO)
    async def test_exception_caught(self, mock_repo_cls):
        factory = _make_session_factory()
        mock_repo_cls.return_value.upsert_author = AsyncMock(
            side_effect=RuntimeError("fail")
        )
        await persist_vsg_author_doc(
            factory, RUN_ID, COMPANY_ID, VSG_RUN_DB_ID,
            "author-001", "Jane Doe", 1, CONTENT_MD, "key",
        )


# ── persist_vsg_guide_doc ───────────────────────────────────────────────


class TestPersistVSGGuideDoc:
    @patch(_VSG_GUIDE_REPO)
    async def test_persists_guide(self, mock_repo_cls):
        factory = _make_session_factory()
        upsert = AsyncMock()
        mock_repo_cls.return_value.upsert_guide = upsert

        await persist_vsg_guide_doc(
            factory, RUN_ID, COMPANY_ID, VSG_RUN_DB_ID,
            1, CONTENT_MD,
            "voice_style_guide/test-co/guide/v1.md",
            source_authors=["Jane Doe", "John Smith"],
        )
        upsert.assert_awaited_once()
        kwargs = upsert.call_args[1]
        assert kwargs["content_hash"] == _sha256(CONTENT_MD)
        assert kwargs["source_authors"] == ["Jane Doe", "John Smith"]

    async def test_no_persist_when_run_db_id_none(self):
        factory = _make_session_factory()
        await persist_vsg_guide_doc(
            factory, RUN_ID, COMPANY_ID, None,
            1, CONTENT_MD, "key",
        )
        factory._session.commit.assert_not_awaited()

    @patch(_VSG_GUIDE_REPO)
    async def test_exception_caught(self, mock_repo_cls):
        factory = _make_session_factory()
        mock_repo_cls.return_value.upsert_guide = AsyncMock(
            side_effect=RuntimeError("fail")
        )
        await persist_vsg_guide_doc(
            factory, RUN_ID, COMPANY_ID, VSG_RUN_DB_ID,
            1, CONTENT_MD, "key",
        )


# ── persist_vsg_status_update ────────────────────────────────────────────


class TestPersistVSGStatusUpdate:
    @patch(_VSG_RUN_REPO)
    async def test_updates_status(self, mock_repo_cls):
        factory = _make_session_factory()
        mock_repo_cls.return_value.update_status = AsyncMock()

        await persist_vsg_status_update(factory, VSG_RUN_DB_ID, "completed")
        mock_repo_cls.return_value.update_status.assert_awaited_once()
        factory._session.commit.assert_awaited_once()

    async def test_no_op_when_factory_none(self):
        await persist_vsg_status_update(None, VSG_RUN_DB_ID, "completed")

    async def test_no_op_when_run_id_none(self):
        factory = _make_session_factory()
        await persist_vsg_status_update(factory, None, "completed")
        factory._session.commit.assert_not_awaited()

    @patch(_VSG_RUN_REPO)
    async def test_exception_caught(self, mock_repo_cls):
        factory = _make_session_factory()
        mock_repo_cls.return_value.update_status = AsyncMock(
            side_effect=RuntimeError("fail")
        )
        await persist_vsg_status_update(factory, VSG_RUN_DB_ID, "completed")
