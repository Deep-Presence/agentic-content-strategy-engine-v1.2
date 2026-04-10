"""Unit tests for core.content_engine.persistence.

Tests the two DB persistence hooks:
- persist_content_pieces()
- persist_content_run_summary()

All tests use mocked session_factory and repos — no real DB required.

The persistence module uses lazy imports inside function bodies, so we
patch at the *source* locations (core.db.models.*, core.db.repositories.*,
core.db.enums.*) rather than on the persistence module namespace.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.content_engine.persistence import (
    _map_content_status,
    _should_persist,
    persist_content_pieces,
    persist_content_run_summary,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def run_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def company_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def slug() -> str:
    return "test-co"


def _make_piece(
    *,
    title: str = "Test Article",
    status_value: str = "approved",
    final_markdown: str = "# Test\n\nSome content here.",
    artifact_path: str = "/artifacts/content/test-co/content/brief-1/final.md",
    eval_summary: object | None = None,
) -> MagicMock:
    """Build a mock ContentPiece with the expected attributes."""
    piece = MagicMock()
    piece.title = title
    piece.status = MagicMock()
    piece.status.value = status_value
    piece.final_markdown = final_markdown
    piece.artifact_path = artifact_path
    piece.eval_summary = eval_summary
    return piece


def _make_session_factory() -> tuple[MagicMock, AsyncMock]:
    """Return (factory, session).

    The factory, when called, returns an async context manager that yields
    the mock session.
    """
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.get = AsyncMock(return_value=None)

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock()
    factory.return_value = ctx
    return factory, session


# ---------------------------------------------------------------------------
# _should_persist
# ---------------------------------------------------------------------------

class TestShouldPersist:
    """Guard function returns False when any required arg is None."""

    def test_all_provided(self) -> None:
        assert _should_persist(MagicMock(), uuid.uuid4(), uuid.uuid4()) is True

    def test_none_session_factory(self) -> None:
        assert _should_persist(None, uuid.uuid4(), uuid.uuid4()) is False

    def test_none_run_id(self) -> None:
        assert _should_persist(MagicMock(), None, uuid.uuid4()) is False

    def test_none_company_id(self) -> None:
        assert _should_persist(MagicMock(), uuid.uuid4(), None) is False

    def test_all_none(self) -> None:
        assert _should_persist(None, None, None) is False


# ---------------------------------------------------------------------------
# _map_content_status
# ---------------------------------------------------------------------------

class TestMapContentStatus:
    """Status mapping from Pydantic string to ORM ContentPieceStatus."""

    def test_approved(self) -> None:
        from core.db.enums import ContentPieceStatus

        result = _map_content_status("approved")
        assert result == ContentPieceStatus.approved

    def test_rejected_maps_to_review(self) -> None:
        from core.db.enums import ContentPieceStatus

        result = _map_content_status("rejected")
        assert result == ContentPieceStatus.review

    def test_edited_maps_to_approved(self) -> None:
        from core.db.enums import ContentPieceStatus

        result = _map_content_status("edited")
        assert result == ContentPieceStatus.approved

    def test_draft_maps_to_drafting(self) -> None:
        from core.db.enums import ContentPieceStatus

        result = _map_content_status("draft")
        assert result == ContentPieceStatus.drafting

    def test_unknown_maps_to_planned(self) -> None:
        from core.db.enums import ContentPieceStatus

        result = _map_content_status("some_unknown_status")
        assert result == ContentPieceStatus.planned

    def test_case_insensitive(self) -> None:
        from core.db.enums import ContentPieceStatus

        result = _map_content_status("APPROVED")
        assert result == ContentPieceStatus.approved


# ---------------------------------------------------------------------------
# persist_content_pieces
# ---------------------------------------------------------------------------

class TestPersistContentPieces:
    """Tests for persist_content_pieces()."""

    @pytest.mark.asyncio
    async def test_skips_when_session_factory_is_none(
        self, run_id: uuid.UUID, company_id: uuid.UUID, slug: str
    ) -> None:
        """No DB calls when session_factory is None."""
        piece = _make_piece()
        # Should return immediately without raising
        await persist_content_pieces(None, run_id, company_id, slug, [piece])

    @pytest.mark.asyncio
    async def test_skips_when_run_id_is_none(
        self, company_id: uuid.UUID, slug: str
    ) -> None:
        factory, _ = _make_session_factory()
        piece = _make_piece()
        await persist_content_pieces(factory, None, company_id, slug, [piece])
        factory.assert_not_called()

    @pytest.mark.asyncio
    async def test_happy_path_single_piece(
        self, run_id: uuid.UUID, company_id: uuid.UUID, slug: str
    ) -> None:
        """One piece is deleted-then-inserted and session is committed."""
        factory, session = _make_session_factory()
        piece = _make_piece()
        mock_repo = MagicMock()
        mock_repo.create_piece = AsyncMock()

        with patch(
            "core.db.models.content.ContentPieceModel"
        ) as mock_model, patch(
            "core.db.repositories.content_repo.ContentRepository",
            return_value=mock_repo,
        ):
            # The lazy import inside persist_content_pieces will pick up the
            # patched ContentPieceModel from core.db.models.content. But the
            # `from X import Y` inside the function creates a local binding.
            # We need to ensure the function's `from` picks up our mock.
            # Easiest: patch at module level with create=True.
            pass

        # The above approach won't work because of how `from X import Y`
        # binds locally. Instead, we'll intercept the session's execute
        # and the ContentRepository constructor.
        factory2, session2 = _make_session_factory()
        mock_repo2 = MagicMock()
        mock_repo2.get_by_slug_and_brief_id = AsyncMock(return_value=None)
        mock_repo2.create_piece = AsyncMock()

        # We need to patch where the names are *looked up* at import time.
        # Since the function does `from core.db.models.content import ContentPieceModel`
        # and `from core.db.repositories.content_repo import ContentRepository`,
        # the easiest way is to temporarily inject into those modules.
        import core.db.models.content as content_mod
        import core.db.repositories.content_repo as repo_mod

        original_repo_cls = repo_mod.ContentRepository
        repo_mod.ContentRepository = lambda sess: mock_repo2

        try:
            await persist_content_pieces(factory2, run_id, company_id, slug, [piece])
        finally:
            repo_mod.ContentRepository = original_repo_cls

        # Session entered and committed
        factory2.assert_called_once()
        session2.commit.assert_called_once()
        # Repo create_piece called once
        mock_repo2.create_piece.assert_called_once()
        call_kwargs = mock_repo2.create_piece.call_args.kwargs
        assert call_kwargs["run_id"] == run_id
        assert call_kwargs["title"] == "Test Article"
        assert call_kwargs["storage_key"] == piece.artifact_path
        assert call_kwargs["revision_count"] == 0

    @pytest.mark.asyncio
    async def test_happy_path_multiple_pieces(
        self, run_id: uuid.UUID, company_id: uuid.UUID, slug: str
    ) -> None:
        """Multiple pieces produce one create_piece call each."""
        factory, session = _make_session_factory()
        pieces = [
            _make_piece(title="Article A", status_value="approved"),
            _make_piece(title="Article B", status_value="draft"),
            _make_piece(title="Article C", status_value="rejected"),
        ]
        mock_repo = MagicMock()
        mock_repo.get_by_slug_and_brief_id = AsyncMock(return_value=None)
        mock_repo.create_piece = AsyncMock()

        import core.db.repositories.content_repo as repo_mod

        original_cls = repo_mod.ContentRepository
        repo_mod.ContentRepository = lambda sess: mock_repo
        try:
            await persist_content_pieces(factory, run_id, company_id, slug, pieces)
        finally:
            repo_mod.ContentRepository = original_cls

        assert mock_repo.create_piece.call_count == 3
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_word_count_computed_from_markdown(
        self, run_id: uuid.UUID, company_id: uuid.UUID, slug: str
    ) -> None:
        """word_count is derived from final_markdown.split()."""
        factory, session = _make_session_factory()
        piece = _make_piece(final_markdown="one two three four five")
        mock_repo = MagicMock()
        mock_repo.get_by_slug_and_brief_id = AsyncMock(return_value=None)
        mock_repo.create_piece = AsyncMock()

        import core.db.repositories.content_repo as repo_mod

        original_cls = repo_mod.ContentRepository
        repo_mod.ContentRepository = lambda sess: mock_repo
        try:
            await persist_content_pieces(factory, run_id, company_id, slug, [piece])
        finally:
            repo_mod.ContentRepository = original_cls

        call_kwargs = mock_repo.create_piece.call_args.kwargs
        assert call_kwargs["word_count"] == 5

    @pytest.mark.asyncio
    async def test_word_count_zero_when_no_markdown(
        self, run_id: uuid.UUID, company_id: uuid.UUID, slug: str
    ) -> None:
        """word_count is 0 when final_markdown is falsy."""
        factory, session = _make_session_factory()
        piece = _make_piece(final_markdown=None)
        mock_repo = MagicMock()
        mock_repo.get_by_slug_and_brief_id = AsyncMock(return_value=None)
        mock_repo.create_piece = AsyncMock()

        import core.db.repositories.content_repo as repo_mod

        original_cls = repo_mod.ContentRepository
        repo_mod.ContentRepository = lambda sess: mock_repo
        try:
            await persist_content_pieces(factory, run_id, company_id, slug, [piece])
        finally:
            repo_mod.ContentRepository = original_cls

        call_kwargs = mock_repo.create_piece.call_args.kwargs
        assert call_kwargs["word_count"] == 0

    @pytest.mark.asyncio
    async def test_eval_summary_model_dump_called(
        self, run_id: uuid.UUID, company_id: uuid.UUID, slug: str
    ) -> None:
        """eval_summary with model_dump() is serialized to dict."""
        factory, session = _make_session_factory()
        eval_mock = MagicMock()
        eval_mock.model_dump.return_value = {"score": 0.9, "dimensions": []}
        piece = _make_piece(eval_summary=eval_mock)
        mock_repo = MagicMock()
        mock_repo.get_by_slug_and_brief_id = AsyncMock(return_value=None)
        mock_repo.create_piece = AsyncMock()

        import core.db.repositories.content_repo as repo_mod

        original_cls = repo_mod.ContentRepository
        repo_mod.ContentRepository = lambda sess: mock_repo
        try:
            await persist_content_pieces(factory, run_id, company_id, slug, [piece])
        finally:
            repo_mod.ContentRepository = original_cls

        eval_mock.model_dump.assert_called_once_with(mode="json")
        call_kwargs = mock_repo.create_piece.call_args.kwargs
        assert call_kwargs["evaluation_results"] == {"score": 0.9, "dimensions": []}

    @pytest.mark.asyncio
    async def test_eval_summary_none_passed_through(
        self, run_id: uuid.UUID, company_id: uuid.UUID, slug: str
    ) -> None:
        """eval_summary=None is stored as None in evaluation_results."""
        factory, session = _make_session_factory()
        piece = _make_piece(eval_summary=None)
        mock_repo = MagicMock()
        mock_repo.get_by_slug_and_brief_id = AsyncMock(return_value=None)
        mock_repo.create_piece = AsyncMock()

        import core.db.repositories.content_repo as repo_mod

        original_cls = repo_mod.ContentRepository
        repo_mod.ContentRepository = lambda sess: mock_repo
        try:
            await persist_content_pieces(factory, run_id, company_id, slug, [piece])
        finally:
            repo_mod.ContentRepository = original_cls

        call_kwargs = mock_repo.create_piece.call_args.kwargs
        assert call_kwargs["evaluation_results"] is None

    @pytest.mark.asyncio
    async def test_existing_gap_context_is_preserved_on_update(
        self, run_id: uuid.UUID, company_id: uuid.UUID, slug: str
    ) -> None:
        """DB-backed CE updates must preserve persisted topic gap_context."""
        factory, session = _make_session_factory()
        piece = _make_piece(eval_summary={"score": 0.91})
        piece.brief_id = "WE-001"
        piece.content_format = "how_to"
        piece.target_cluster = "Definition"
        piece.topic_assignment_id = uuid.uuid4()

        existing = MagicMock()
        existing.evaluation_results = {
            "gap_context": {
                "query_gap": {
                    "gap": 0.28,
                    "interpretation": "significant_gap",
                    "best_company_url": "https://test.co/no-code",
                },
            },
        }

        mock_repo = MagicMock()
        mock_repo.get_by_slug_and_brief_id = AsyncMock(return_value=existing)
        mock_repo.create_piece = AsyncMock()

        import core.db.repositories.content_repo as repo_mod

        original_cls = repo_mod.ContentRepository
        repo_mod.ContentRepository = lambda sess: mock_repo
        try:
            await persist_content_pieces(factory, run_id, company_id, slug, [piece])
        finally:
            repo_mod.ContentRepository = original_cls

        mock_repo.create_piece.assert_not_called()
        assert existing.evaluation_results == {
            "score": 0.91,
            "gap_context": {
                "query_gap": {
                    "gap": 0.28,
                    "interpretation": "significant_gap",
                    "best_company_url": "https://test.co/no-code",
                },
            },
        }
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_exception_logged_not_raised(
        self, run_id: uuid.UUID, company_id: uuid.UUID, slug: str
    ) -> None:
        """DB errors are caught and logged — never propagated."""
        factory, session = _make_session_factory()
        piece = _make_piece()
        # Make the DELETE execute call blow up
        session.execute.side_effect = RuntimeError("db connection lost")

        with patch(
            "core.content_engine.persistence.logger"
        ) as mock_logger:
            # Should NOT raise
            await persist_content_pieces(factory, run_id, company_id, slug, [piece])
            mock_logger.warning.assert_called_once()
            assert "persist_content_pieces failed" in mock_logger.warning.call_args[0][0]


# ---------------------------------------------------------------------------
# persist_content_run_summary
# ---------------------------------------------------------------------------

class TestPersistContentRunSummary:
    """Tests for persist_content_run_summary()."""

    @pytest.mark.asyncio
    async def test_skips_when_session_factory_is_none(
        self, run_id: uuid.UUID, company_id: uuid.UUID, slug: str
    ) -> None:
        await persist_content_run_summary(None, run_id, company_id, slug, 5, 3, 1)

    @pytest.mark.asyncio
    async def test_skips_when_run_id_is_none(
        self, company_id: uuid.UUID, slug: str
    ) -> None:
        factory, _ = _make_session_factory()
        await persist_content_run_summary(factory, None, company_id, slug, 5, 3, 1)
        factory.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_not_found_returns_early(
        self, run_id: uuid.UUID, company_id: uuid.UUID, slug: str
    ) -> None:
        """When session.get returns None, log warning and return without commit."""
        factory, session = _make_session_factory()
        session.get.return_value = None

        with patch(
            "core.content_engine.persistence.logger"
        ) as mock_logger:
            await persist_content_run_summary(
                factory, run_id, company_id, slug, 5, 3, 1
            )
            mock_logger.warning.assert_called_once()
            assert "not found" in mock_logger.warning.call_args[0][0]
            session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_happy_path_updates_run(
        self, run_id: uuid.UUID, company_id: uuid.UUID, slug: str
    ) -> None:
        """Run model is updated with summary, status, completed_at, stages."""
        factory, session = _make_session_factory()
        mock_run = MagicMock()
        session.get.return_value = mock_run

        from core.db.enums import PipelineStatus

        await persist_content_run_summary(
            factory, run_id, company_id, slug, 10, 7, 2
        )

        assert mock_run.summary == {
            "total_briefs": 10,
            "total_approved": 7,
            "total_rejected": 2,
        }
        assert mock_run.status == PipelineStatus.completed
        assert isinstance(mock_run.completed_at, datetime)
        assert mock_run.completed_at.tzinfo == timezone.utc
        assert mock_run.stages_executed == [
            "stage1_planner",
            "stage2_workers",
            "stage3_evaluator",
            "stage4_review",
        ]
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_exception_logged_not_raised(
        self, run_id: uuid.UUID, company_id: uuid.UUID, slug: str
    ) -> None:
        """DB errors are caught and logged — never propagated."""
        factory, session = _make_session_factory()
        session.get.side_effect = RuntimeError("db down")

        with patch(
            "core.content_engine.persistence.logger"
        ) as mock_logger:
            await persist_content_run_summary(
                factory, run_id, company_id, slug, 5, 3, 1
            )
            mock_logger.warning.assert_called_once()
            assert "persist_content_run_summary failed" in mock_logger.warning.call_args[0][0]
