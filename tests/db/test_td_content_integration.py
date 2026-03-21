"""Tests for Phase 7: TD ↔ Content integration DB layer.

Covers:
- ORM model column existence (content_pieces.topic_assignment_id,
  run_queries.source_topic_ids, query_gaps.source_topic_ids)
- ContentRepository.list_by_topic_assignment()
- Persistence updates (source_topic_ids in s2/s6, topic_assignment_id in CE)
- TD persist_td_assignment_status_batch()
- Alembic migration file structure

All tests are pure unit tests — no real DB needed.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. ORM Model Column Existence
# ---------------------------------------------------------------------------


class TestContentPieceModelColumns:
    """ContentPieceModel should have the new topic_assignment_id column."""

    def test_has_topic_assignment_id_column(self):
        from core.db.models.content import ContentPieceModel

        assert hasattr(ContentPieceModel, "topic_assignment_id")

    def test_topic_assignment_id_in_table_columns(self):
        from core.db.models.content import ContentPieceModel

        col_names = [c.name for c in ContentPieceModel.__table__.columns]
        assert "topic_assignment_id" in col_names

    def test_topic_assignment_index_exists(self):
        from core.db.models.content import ContentPieceModel

        index_names = [idx.name for idx in ContentPieceModel.__table__.indexes]
        assert "ix_content_pieces_topic_assignment" in index_names


class TestRunQueryModelColumns:
    """RunQueryModel should have the new source_topic_ids column."""

    def test_has_source_topic_ids_column(self):
        from core.db.models.gap_analysis import RunQueryModel

        assert hasattr(RunQueryModel, "source_topic_ids")

    def test_source_topic_ids_in_table_columns(self):
        from core.db.models.gap_analysis import RunQueryModel

        col_names = [c.name for c in RunQueryModel.__table__.columns]
        assert "source_topic_ids" in col_names


class TestQueryGapModelColumns:
    """QueryGapModel should have the new source_topic_ids column."""

    def test_has_source_topic_ids_column(self):
        from core.db.models.gap_analysis import QueryGapModel

        assert hasattr(QueryGapModel, "source_topic_ids")

    def test_source_topic_ids_in_table_columns(self):
        from core.db.models.gap_analysis import QueryGapModel

        col_names = [c.name for c in QueryGapModel.__table__.columns]
        assert "source_topic_ids" in col_names


# ---------------------------------------------------------------------------
# 2. Alembic Migration Structure
# ---------------------------------------------------------------------------


class TestMigration0011:
    """Migration 0011 exists and has correct revision chain."""

    @staticmethod
    def _load_migration():
        import importlib

        return importlib.import_module(
            "core.db.migrations.versions.0011_td_content_integration"
        )

    def test_revision_chain(self):
        m = self._load_migration()
        assert m.revision == "0011"
        assert m.down_revision == "0010"

    def test_has_upgrade_and_downgrade(self):
        m = self._load_migration()
        assert callable(m.upgrade)
        assert callable(m.downgrade)


# ---------------------------------------------------------------------------
# 3. ContentRepository.list_by_topic_assignment()
# ---------------------------------------------------------------------------


class TestContentRepoListByTopicAssignment:
    """ContentRepository should expose list_by_topic_assignment()."""

    def test_method_exists(self):
        from core.db.repositories.content_repo import ContentRepository

        assert hasattr(ContentRepository, "list_by_topic_assignment")

    @pytest.mark.asyncio
    async def test_returns_filtered_results(self):
        """Verify the method builds the correct query."""
        from core.db.repositories.content_repo import ContentRepository

        ta_id = uuid.uuid4()

        # Build a mock session that tracks the query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["piece1", "piece2"]
        session = AsyncMock()
        session.execute.return_value = mock_result

        repo = ContentRepository(session)
        pieces = await repo.list_by_topic_assignment(ta_id)

        assert pieces == ["piece1", "piece2"]
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_accepts_string_id(self):
        """String UUIDs should be converted to UUID objects."""
        from core.db.repositories.content_repo import ContentRepository

        ta_id_str = str(uuid.uuid4())

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session = AsyncMock()
        session.execute.return_value = mock_result

        repo = ContentRepository(session)
        pieces = await repo.list_by_topic_assignment(ta_id_str)

        assert pieces == []
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_uuid_returns_empty(self):
        """M3 fix: malformed UUID string should return [] not raise."""
        from core.db.repositories.content_repo import ContentRepository

        session = AsyncMock()
        repo = ContentRepository(session)
        pieces = await repo.list_by_topic_assignment("not-a-uuid")

        assert pieces == []
        # No DB query should have been executed
        session.execute.assert_not_called()


# ---------------------------------------------------------------------------
# 4. persist_content_pieces includes topic_assignment_id
# ---------------------------------------------------------------------------


def _make_session_factory():
    """Return (factory, session) with async context manager protocol."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock()
    factory.return_value = ctx
    return factory, session


def _make_piece(
    *,
    title: str = "Test Article",
    status_value: str = "approved",
    final_markdown: str = "# Test content",
    topic_assignment_id: str | None = None,
) -> MagicMock:
    piece = MagicMock()
    piece.title = title
    piece.status = MagicMock()
    piece.status.value = status_value
    piece.final_markdown = final_markdown
    piece.artifact_path = "/test/path"
    piece.eval_summary = None
    piece.topic_assignment_id = topic_assignment_id
    return piece


class TestPersistContentPiecesTopicAssignment:
    """persist_content_pieces() should pass topic_assignment_id."""

    @pytest.mark.asyncio
    async def test_topic_assignment_id_passed(self):
        from core.content_engine.persistence import persist_content_pieces

        factory, session = _make_session_factory()
        ta_id = str(uuid.uuid4())
        piece = _make_piece(topic_assignment_id=ta_id)

        mock_repo = MagicMock()
        mock_repo.get_by_slug_and_brief_id = AsyncMock(return_value=None)
        mock_repo.create_piece = AsyncMock()

        import core.db.repositories.content_repo as repo_mod

        original_cls = repo_mod.ContentRepository
        repo_mod.ContentRepository = lambda sess: mock_repo
        try:
            await persist_content_pieces(
                factory, uuid.uuid4(), uuid.uuid4(), "test-co", [piece]
            )
        finally:
            repo_mod.ContentRepository = original_cls

        call_kwargs = mock_repo.create_piece.call_args.kwargs
        assert call_kwargs["topic_assignment_id"] == uuid.UUID(ta_id)

    @pytest.mark.asyncio
    async def test_topic_assignment_id_none_when_absent(self):
        from core.content_engine.persistence import persist_content_pieces

        factory, session = _make_session_factory()
        piece = _make_piece(topic_assignment_id=None)

        mock_repo = MagicMock()
        mock_repo.get_by_slug_and_brief_id = AsyncMock(return_value=None)
        mock_repo.create_piece = AsyncMock()

        import core.db.repositories.content_repo as repo_mod

        original_cls = repo_mod.ContentRepository
        repo_mod.ContentRepository = lambda sess: mock_repo
        try:
            await persist_content_pieces(
                factory, uuid.uuid4(), uuid.uuid4(), "test-co", [piece]
            )
        finally:
            repo_mod.ContentRepository = original_cls

        call_kwargs = mock_repo.create_piece.call_args.kwargs
        assert call_kwargs["topic_assignment_id"] is None

    @pytest.mark.asyncio
    async def test_invalid_uuid_topic_assignment_id_becomes_none(self):
        from core.content_engine.persistence import persist_content_pieces

        factory, session = _make_session_factory()
        piece = _make_piece(topic_assignment_id="not-a-uuid")

        mock_repo = MagicMock()
        mock_repo.get_by_slug_and_brief_id = AsyncMock(return_value=None)
        mock_repo.create_piece = AsyncMock()

        import core.db.repositories.content_repo as repo_mod

        original_cls = repo_mod.ContentRepository
        repo_mod.ContentRepository = lambda sess: mock_repo
        try:
            await persist_content_pieces(
                factory, uuid.uuid4(), uuid.uuid4(), "test-co", [piece]
            )
        finally:
            repo_mod.ContentRepository = original_cls

        call_kwargs = mock_repo.create_piece.call_args.kwargs
        assert call_kwargs["topic_assignment_id"] is None


# ---------------------------------------------------------------------------
# 5. persist_s2 includes source_topic_ids
# ---------------------------------------------------------------------------


def _mock_delete(model_cls):
    m = MagicMock()
    m.where.return_value = m
    return m


class TestPersistS2SourceTopicIds:
    """persist_s2() should include source_topic_ids in query rows."""

    @pytest.mark.asyncio
    async def test_source_topic_ids_included(self):
        from core.gap_analysis.persistence import persist_s2

        factory, session = _make_session_factory()
        mock_repo = MagicMock()
        mock_repo.bulk_insert_run_queries = AsyncMock()

        query = MagicMock()
        query.query_id = "q1"
        query.cluster_id = "C5"
        query.cluster_name = "Definition"
        query.query_text = "What is X?"
        query.buyer_stage = "tofu"
        query.persona_tag = None
        query.source_topic_ids = ["ta-1", "ta-2"]

        import core.db.repositories.gap_analysis_repo as repo_mod

        original_cls = repo_mod.GapAnalysisRepository
        repo_mod.GapAnalysisRepository = lambda sess: mock_repo
        try:
            with patch(
                "core.gap_analysis.persistence.delete",
                side_effect=_mock_delete,
            ):
                await persist_s2(
                    factory, uuid.uuid4(), uuid.uuid4(), "test-co", [query]
                )
        finally:
            repo_mod.GapAnalysisRepository = original_cls

        items = mock_repo.bulk_insert_run_queries.call_args[0][0]
        assert items[0]["source_topic_ids"] == ["ta-1", "ta-2"]

    @pytest.mark.asyncio
    async def test_empty_source_topic_ids_becomes_none(self):
        from core.gap_analysis.persistence import persist_s2

        factory, session = _make_session_factory()
        mock_repo = MagicMock()
        mock_repo.bulk_insert_run_queries = AsyncMock()

        query = MagicMock()
        query.query_id = "q1"
        query.cluster_id = "C5"
        query.cluster_name = "Definition"
        query.query_text = "What is X?"
        query.buyer_stage = None
        query.persona_tag = None
        query.source_topic_ids = []

        import core.db.repositories.gap_analysis_repo as repo_mod

        original_cls = repo_mod.GapAnalysisRepository
        repo_mod.GapAnalysisRepository = lambda sess: mock_repo
        try:
            with patch(
                "core.gap_analysis.persistence.delete",
                side_effect=_mock_delete,
            ):
                await persist_s2(
                    factory, uuid.uuid4(), uuid.uuid4(), "test-co", [query]
                )
        finally:
            repo_mod.GapAnalysisRepository = original_cls

        items = mock_repo.bulk_insert_run_queries.call_args[0][0]
        assert items[0]["source_topic_ids"] is None


# ---------------------------------------------------------------------------
# 6. persist_s6 includes source_topic_ids
# ---------------------------------------------------------------------------


class TestPersistS6SourceTopicIds:
    """persist_s6() should include source_topic_ids in gap rows."""

    @pytest.mark.asyncio
    async def test_source_topic_ids_included_in_gaps(self):
        from core.gap_analysis.persistence import persist_s6

        factory, session = _make_session_factory()
        mock_repo = MagicMock()
        mock_repo.bulk_insert_query_gaps = AsyncMock()
        mock_repo.bulk_insert_query_exemplars = AsyncMock()
        mock_repo.bulk_insert_cluster_specs = AsyncMock()
        mock_repo.bulk_insert_spa_results = AsyncMock()
        mock_repo.bulk_insert_centroid_results = AsyncMock()

        gap = MagicMock()
        gap.query_id = "q1"
        gap.cluster_id = "C5"
        gap.cluster_name = "Definition"
        gap.query_text = "What is X?"
        gap.best_company_similarity = 0.5
        gap.best_company_unit = None
        gap.best_company_unit_text = None
        gap.avg_citation_similarity = 0.7
        gap.gap = 0.2
        gap.interpretation = "gap_to_close"
        gap.content_brief = None
        gap.top_cited_exemplars = []
        gap.source_topic_ids = ["ta-1"]

        analysis = MagicMock()
        analysis.gaps = [gap]
        analysis.cluster_specs = []
        analysis.spa_results = []
        analysis.centroids = []

        # Mock ORM model classes to avoid real table introspection
        mock_model = MagicMock()
        mock_model.run_id = MagicMock()

        import core.db.repositories.gap_analysis_repo as repo_mod

        original_cls = repo_mod.GapAnalysisRepository
        repo_mod.GapAnalysisRepository = lambda sess: mock_repo
        try:
            with patch(
                "core.gap_analysis.persistence.delete",
                side_effect=_mock_delete,
            ), patch(
                "core.db.models.gap_analysis.QueryExemplarModel", mock_model,
            ), patch(
                "core.db.models.gap_analysis.QueryGapModel", mock_model,
            ), patch(
                "core.db.models.gap_analysis.ClusterSpecModel", mock_model,
            ), patch(
                "core.db.models.gap_analysis.SpaResultModel", mock_model,
            ), patch(
                "core.db.models.gap_analysis.CentroidResultModel", mock_model,
            ):
                await persist_s6(
                    factory, uuid.uuid4(), uuid.uuid4(), "test-co", analysis
                )
        finally:
            repo_mod.GapAnalysisRepository = original_cls

        gap_rows = mock_repo.bulk_insert_query_gaps.call_args[0][0]
        assert gap_rows[0]["source_topic_ids"] == ["ta-1"]


# ---------------------------------------------------------------------------
# 7. persist_td_assignment_status_batch
# ---------------------------------------------------------------------------


class TestPersistTdAssignmentStatusBatch:
    """Tests for the new batch status update function."""

    @pytest.mark.asyncio
    async def test_skips_when_factory_is_none(self):
        from core.topic_discovery.persistence import (
            persist_td_assignment_status_batch,
        )

        # Should not raise
        await persist_td_assignment_status_batch(None, ["ta-1"], "in_gap_analysis")

    @pytest.mark.asyncio
    async def test_skips_when_empty_ids(self):
        from core.topic_discovery.persistence import (
            persist_td_assignment_status_batch,
        )

        factory, _ = _make_session_factory()
        await persist_td_assignment_status_batch(factory, [], "in_gap_analysis")
        factory.assert_not_called()

    @pytest.mark.asyncio
    async def test_updates_each_assignment(self):
        from core.topic_discovery.persistence import (
            persist_td_assignment_status_batch,
        )

        factory, session = _make_session_factory()
        mock_repo = MagicMock()
        mock_repo.update_assignment_status = AsyncMock(return_value=MagicMock())

        import core.db.repositories.topic_discovery_repo as repo_mod

        original_cls = repo_mod.TopicAssignmentRepository
        repo_mod.TopicAssignmentRepository = lambda sess: mock_repo
        try:
            id1 = str(uuid.uuid4())
            id2 = str(uuid.uuid4())
            await persist_td_assignment_status_batch(
                factory, [id1, id2], "in_gap_analysis"
            )
        finally:
            repo_mod.TopicAssignmentRepository = original_cls

        assert mock_repo.update_assignment_status.call_count == 2
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_invalid_uuids(self):
        from core.topic_discovery.persistence import (
            persist_td_assignment_status_batch,
        )

        factory, session = _make_session_factory()
        mock_repo = MagicMock()
        mock_repo.update_assignment_status = AsyncMock(return_value=MagicMock())

        import core.db.repositories.topic_discovery_repo as repo_mod

        original_cls = repo_mod.TopicAssignmentRepository
        repo_mod.TopicAssignmentRepository = lambda sess: mock_repo
        try:
            await persist_td_assignment_status_batch(
                factory, ["not-a-uuid", str(uuid.uuid4())], "content_produced"
            )
        finally:
            repo_mod.TopicAssignmentRepository = original_cls

        # Only the valid UUID should have been processed
        assert mock_repo.update_assignment_status.call_count == 1

    @pytest.mark.asyncio
    async def test_exception_caught_not_raised(self):
        from core.topic_discovery.persistence import (
            persist_td_assignment_status_batch,
        )

        factory, session = _make_session_factory()
        session.commit.side_effect = RuntimeError("db down")

        mock_repo = MagicMock()
        mock_repo.update_assignment_status = AsyncMock()

        import core.db.repositories.topic_discovery_repo as repo_mod

        original_cls = repo_mod.TopicAssignmentRepository
        repo_mod.TopicAssignmentRepository = lambda sess: mock_repo
        try:
            # Should not raise
            await persist_td_assignment_status_batch(
                factory, [str(uuid.uuid4())], "in_gap_analysis"
            )
        finally:
            repo_mod.TopicAssignmentRepository = original_cls
