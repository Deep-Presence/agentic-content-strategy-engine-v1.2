"""Unit tests for core.research.knowledge_base.persistence — KB DB persistence hooks.

Pure unit tests — no real DB needed. All DB interaction is mocked via
AsyncMock session factories and patched repositories.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.research.knowledge_base.persistence import (
    _sha256,
    _should_persist,
    _word_count,
    persist_kb_document,
    persist_kb_run,
    persist_kb_status_update,
    persist_kb_synthesis_doc,
)


# ── Shared fixtures ──────────────────────────────────────────────────────

RUN_ID = uuid.uuid4()
COMPANY_ID = uuid.uuid4()
KB_RUN_DB_ID = uuid.uuid4()
SLUG = "test-co"
CONTENT_MD = "# Company Overview\n\nTest Co is a fintech company."


class _FakeSession:
    """Async context manager that yields itself and tracks calls."""

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


_KB_RUN_REPO = "core.db.repositories.kb_repo.KBRunRepository"
_KB_DOC_REPO = "core.db.repositories.kb_repo.KBDocumentRepository"
_KB_SYNTH_REPO = "core.db.repositories.kb_repo.KBSynthesisRepository"


# ── Guard Tests ──────────────────────────────────────────────────────────


class TestShouldPersist:
    def test_all_present_returns_true(self):
        assert _should_persist(MagicMock(), RUN_ID, COMPANY_ID) is True

    def test_none_session_factory_returns_false(self):
        assert _should_persist(None, RUN_ID, COMPANY_ID) is False

    def test_none_run_id_returns_false(self):
        assert _should_persist(MagicMock(), None, COMPANY_ID) is False

    def test_none_company_id_returns_false(self):
        assert _should_persist(MagicMock(), RUN_ID, None) is False


# ── Helper Tests ─────────────────────────────────────────────────────────


class TestHelpers:
    def test_sha256_deterministic(self):
        assert _sha256("hello") == _sha256("hello")
        assert len(_sha256("hello")) == 64

    def test_word_count(self):
        assert _word_count("one two three") == 3
        assert _word_count("") == 0


# ── persist_kb_run ───────────────────────────────────────────────────────


class TestPersistKBRun:
    @patch(_KB_RUN_REPO)
    async def test_returns_run_id(self, mock_repo_cls):
        factory = _make_session_factory()
        mock_run = MagicMock()
        mock_run.id = KB_RUN_DB_ID
        mock_repo_cls.return_value.upsert_run = AsyncMock(return_value=mock_run)

        result = await persist_kb_run(
            factory, RUN_ID, COMPANY_ID, SLUG,
        )
        assert result == KB_RUN_DB_ID
        factory._session.commit.assert_awaited_once()

    async def test_returns_none_when_not_configured(self):
        result = await persist_kb_run(None, RUN_ID, COMPANY_ID, SLUG)
        assert result is None

    @patch(_KB_RUN_REPO)
    async def test_exception_returns_none(self, mock_repo_cls):
        factory = _make_session_factory()
        mock_repo_cls.return_value.upsert_run = AsyncMock(
            side_effect=RuntimeError("DB down")
        )
        result = await persist_kb_run(factory, RUN_ID, COMPANY_ID, SLUG)
        assert result is None


# ── persist_kb_document ──────────────────────────────────────────────────


class TestPersistKBDocument:
    @patch(_KB_DOC_REPO)
    async def test_persists_document(self, mock_repo_cls):
        factory = _make_session_factory()
        upsert = AsyncMock()
        mock_repo_cls.return_value.upsert_document = upsert

        await persist_kb_document(
            factory, RUN_ID, COMPANY_ID, KB_RUN_DB_ID,
            "company_overview", 1, CONTENT_MD,
            "knowledge_base/test-co/company_overview/v1.md",
        )
        upsert.assert_awaited_once()
        kwargs = upsert.call_args[1]
        assert kwargs["doc_type"] == "company_overview"
        assert kwargs["content_hash"] == _sha256(CONTENT_MD)
        assert kwargs["word_count"] == _word_count(CONTENT_MD)

    async def test_no_persist_when_session_none(self):
        await persist_kb_document(
            None, RUN_ID, COMPANY_ID, KB_RUN_DB_ID,
            "company_overview", 1, CONTENT_MD, "key",
        )

    async def test_no_persist_when_kb_run_db_id_none(self):
        factory = _make_session_factory()
        await persist_kb_document(
            factory, RUN_ID, COMPANY_ID, None,
            "company_overview", 1, CONTENT_MD, "key",
        )
        factory._session.commit.assert_not_awaited()

    @patch(_KB_DOC_REPO)
    async def test_exception_caught(self, mock_repo_cls):
        factory = _make_session_factory()
        mock_repo_cls.return_value.upsert_document = AsyncMock(
            side_effect=RuntimeError("fail")
        )
        await persist_kb_document(
            factory, RUN_ID, COMPANY_ID, KB_RUN_DB_ID,
            "company_overview", 1, CONTENT_MD, "key",
        )


# ── persist_kb_synthesis_doc ─────────────────────────────────────────────


class TestPersistKBSynthesisDoc:
    @patch(_KB_RUN_REPO)
    @patch(_KB_SYNTH_REPO)
    async def test_persists_synthesis(self, mock_synth_cls, mock_run_cls):
        factory = _make_session_factory()
        synth_upsert = AsyncMock()
        mock_synth_cls.return_value.upsert_synthesis = synth_upsert
        mock_run_cls.return_value.update_synthesis_version = AsyncMock()

        await persist_kb_synthesis_doc(
            factory, RUN_ID, COMPANY_ID, KB_RUN_DB_ID,
            2, CONTENT_MD,
            "knowledge_base/test-co/synthesis/v2.md",
        )
        synth_upsert.assert_awaited_once()
        mock_run_cls.return_value.update_synthesis_version.assert_awaited_once_with(
            KB_RUN_DB_ID, 2,
        )

    async def test_no_persist_when_run_db_id_none(self):
        factory = _make_session_factory()
        await persist_kb_synthesis_doc(
            factory, RUN_ID, COMPANY_ID, None,
            1, CONTENT_MD, "key",
        )
        factory._session.commit.assert_not_awaited()

    @patch(_KB_RUN_REPO)
    @patch(_KB_SYNTH_REPO)
    async def test_exception_caught(self, mock_synth_cls, mock_run_cls):
        factory = _make_session_factory()
        mock_synth_cls.return_value.upsert_synthesis = AsyncMock(
            side_effect=RuntimeError("fail")
        )
        await persist_kb_synthesis_doc(
            factory, RUN_ID, COMPANY_ID, KB_RUN_DB_ID,
            1, CONTENT_MD, "key",
        )


# ── persist_kb_status_update ─────────────────────────────────────────────


class TestPersistKBStatusUpdate:
    @patch(_KB_RUN_REPO)
    async def test_updates_status(self, mock_repo_cls):
        factory = _make_session_factory()
        mock_repo_cls.return_value.update_status = AsyncMock()

        await persist_kb_status_update(factory, KB_RUN_DB_ID, "completed")
        mock_repo_cls.return_value.update_status.assert_awaited_once()
        factory._session.commit.assert_awaited_once()

    async def test_no_op_when_factory_none(self):
        await persist_kb_status_update(None, KB_RUN_DB_ID, "completed")

    async def test_no_op_when_run_id_none(self):
        factory = _make_session_factory()
        await persist_kb_status_update(factory, None, "completed")
        factory._session.commit.assert_not_awaited()

    @patch(_KB_RUN_REPO)
    async def test_exception_caught(self, mock_repo_cls):
        factory = _make_session_factory()
        mock_repo_cls.return_value.update_status = AsyncMock(
            side_effect=RuntimeError("fail")
        )
        await persist_kb_status_update(factory, KB_RUN_DB_ID, "completed")
