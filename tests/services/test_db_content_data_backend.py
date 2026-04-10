"""Unit tests for DbContentDataService StorageBackend injection (Phase 7).

These tests verify that DbContentDataService correctly uses StorageBackend
instead of raw filesystem Path operations.  They do NOT require a database
(mock repos throughout).
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.services.db_content_data import DbContentDataService
from core.storage.backends.local import LocalStorageBackend


# ── Constructor tests ────────────────────────────────────────────────


class TestConstructor:
    """Verify StorageBackend injection in constructor."""

    def test_backend_none_defaults_to_local(self, tmp_path):
        svc = DbContentDataService(
            content_repo=MagicMock(),
            pipeline_repo=MagicMock(),
            artifacts_root=tmp_path,
        )
        assert isinstance(svc._backend, LocalStorageBackend)

    def test_backend_injected_is_used(self, tmp_path):
        mock_backend = MagicMock()
        svc = DbContentDataService(
            content_repo=MagicMock(),
            pipeline_repo=MagicMock(),
            artifacts_root=tmp_path,
            backend=mock_backend,
        )
        assert svc._backend is mock_backend


# ── Gap context loading ──────────────────────────────────────────────


class TestGapContextUsesBackend:
    """Verify get_briefs() passes StorageBackend to load_analysis_json."""

    @pytest.mark.asyncio
    async def test_passes_backend_not_path(self, tmp_path):
        mock_backend = MagicMock()
        content_repo = AsyncMock()
        content_repo.list_by_slug = AsyncMock(return_value=[])
        pipeline_repo = AsyncMock()
        pipeline_repo.get_latest_completed = AsyncMock(return_value=None)

        svc = DbContentDataService(
            content_repo=content_repo,
            pipeline_repo=pipeline_repo,
            artifacts_root=tmp_path,
            backend=mock_backend,
        )

        with patch(
            "core.services.db_content_data.load_analysis_json",
        ) as mock_load:
            mock_load.return_value = None
            await svc.get_briefs("test-co")
            # Should be called with the backend, not a Path
            if mock_load.called:
                first_arg = mock_load.call_args[0][0]
                assert first_arg is mock_backend, (
                    f"Expected StorageBackend, got {type(first_arg)}"
                )

    @pytest.mark.asyncio
    async def test_load_ga_phase_cards_includes_timestamps(self, tmp_path):
        """GA cards returned from Redis carry timestamps through to the brief list contract."""
        assignment_id = str(uuid.uuid4())
        mock_backend = MagicMock()
        svc = DbContentDataService(
            content_repo=AsyncMock(),
            pipeline_repo=AsyncMock(),
            artifacts_root=tmp_path,
            backend=mock_backend,
        )

        class _SessionContext:
            async def __aenter__(self):
                return MagicMock()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class _Repo:
            def __init__(self, session):
                self.session = session

            async def get_by_ids(self, ta_ids):
                return [
                    SimpleNamespace(
                        id=uuid.UUID(assignment_id),
                        status=SimpleNamespace(value="in_gap_analysis"),
                    ),
                ]

        with patch("core.config.settings.settings.redis_pipeline_state", True), patch(
            "core.config.settings.settings.redis_url", "redis://localhost:6379/0",
        ), patch(
            "core.redis.get_redis_or_none", return_value=object(),
        ), patch(
            "core.content_engine.state_redis.read_ga_phase_cards_async",
            AsyncMock(return_value=[{
                "id": f"ta-{assignment_id}",
                "status": "gap_analysis_complete",
                "title": "How AP Works",
                "display_id": "WE-101",
                "topic_assignment_id": assignment_id,
                "created_at": "2026-04-10T07:00:00+00:00",
                "updated_at": "2026-04-10T07:05:00+00:00",
            }]),
        ), patch(
            "core.db.engine.get_session_factory",
            return_value=lambda: _SessionContext(),
        ), patch(
            "core.db.repositories.topic_discovery_repo.TopicAssignmentRepository",
            _Repo,
        ):
            cards = await svc._load_ga_phase_cards("test-co")

        assert len(cards) == 1
        assert cards[0].created_at == "2026-04-10T07:00:00+00:00"
        assert cards[0].updated_at == "2026-04-10T07:05:00+00:00"


# ── Blueprint fallback ───────────────────────────────────────────────


class TestBlueprintFallbackUsesBackend:
    """Verify get_brief_detail() reads blueprints.json via StorageBackend."""

    @pytest.mark.asyncio
    async def test_reads_blueprints_via_backend(self, tmp_path):
        """When DB has no key_topics/key_angles, blueprint fallback uses backend."""
        backend = LocalStorageBackend(tmp_path)

        # Write blueprints.json via StorageBackend (not raw Path)
        bp_data = [
            {
                "brief_id": "brief-001",
                "title": "Test Brief",
                "key_topics": ["topic-a", "topic-b"],
                "key_angles": ["angle-1"],
                "priority_score": 0.9,
                "word_count_range": [1000, 2000],
                "structural_targets": {"headers": 3},
            }
        ]
        backend.write(
            "content/test-co/blueprints.json",
            json.dumps(bp_data),
        )

        # Mock the piece with no eval data (triggers blueprint fallback)
        mock_piece = MagicMock()
        mock_piece.brief_id = "brief-001"
        mock_piece.id = "00000000-0000-0000-0000-000000000001"
        mock_piece.title = "Test Brief"
        mock_piece.status = MagicMock(value="planned")
        mock_piece.content_type = "long_blog"
        mock_piece.evaluation_results = {}  # No key_topics/key_angles
        mock_piece.citability_score = None
        mock_piece.cluster_name = ""
        mock_piece.word_count = 0
        mock_piece.run_id = None
        mock_piece.created_at = None
        mock_piece.updated_at = None

        content_repo = AsyncMock()
        content_repo.get_by_slug_and_brief_id = AsyncMock(return_value=mock_piece)
        pipeline_repo = AsyncMock()
        pipeline_repo.get_latest_completed = AsyncMock(return_value=None)
        artifact_repo = AsyncMock()
        artifact_repo.list_by_piece = AsyncMock(return_value=[])

        svc = DbContentDataService(
            content_repo=content_repo,
            pipeline_repo=pipeline_repo,
            artifacts_root=tmp_path,
            artifact_repo=artifact_repo,
            backend=backend,
        )

        resp = await svc.get_brief_detail("test-co", "brief-001")
        assert resp.key_topics == ["topic-a", "topic-b"]
        assert resp.key_angles == ["angle-1"]
        assert resp.priority_score == 0.9


# ── Stage content fallback ───────────────────────────────────────────


class TestStageContentFallbackPassesBackend:
    """Verify get_brief_stage_content() passes StorageBackend to delegate."""

    @pytest.mark.asyncio
    async def test_fallback_passes_storage_kwarg(self, tmp_path):
        """When DB artifact lookup fails, fallback passes storage= to delegate."""
        mock_backend = MagicMock()

        svc = DbContentDataService(
            content_repo=AsyncMock(),
            pipeline_repo=AsyncMock(),
            artifacts_root=tmp_path,
            artifact_repo=None,  # No artifact repo → always falls back
            backend=mock_backend,
        )

        with patch(
            "api.services.content_data_service.get_brief_stage_content",
        ) as mock_fn:
            from api.schemas.content_data import StageContentResponse
            mock_fn.return_value = StageContentResponse(
                brief_id="brief-001", stage="draft",
                content_type="text/markdown", content="# Draft",
            )
            await svc.get_brief_stage_content("test-co", "brief-001", "draft")
            mock_fn.assert_called_once()
            call_kwargs = mock_fn.call_args
            assert call_kwargs.kwargs.get("storage") is mock_backend

    @pytest.mark.asyncio
    async def test_primary_path_uses_backend(self, tmp_path):
        """DB primary path reads artifact via self._backend."""
        backend = LocalStorageBackend(tmp_path)
        backend.write(
            "content/test-co/content/brief-001/draft.md",
            "# Draft content",
        )

        # Mock artifact with storage_key
        mock_artifact = MagicMock()
        mock_artifact.storage_key = "content/test-co/content/brief-001/draft.md"
        mock_artifact.content_type = "text/markdown"

        mock_piece = MagicMock()
        mock_piece.id = "00000000-0000-0000-0000-000000000001"

        content_repo = AsyncMock()
        content_repo.get_by_slug_and_brief_id = AsyncMock(return_value=mock_piece)

        artifact_repo = AsyncMock()
        artifact_repo.get_by_piece_and_stage = AsyncMock(return_value=mock_artifact)

        svc = DbContentDataService(
            content_repo=content_repo,
            pipeline_repo=AsyncMock(),
            artifacts_root=tmp_path,
            artifact_repo=artifact_repo,
            backend=backend,
        )

        resp = await svc.get_brief_stage_content("test-co", "brief-001", "draft")
        assert resp.content == "# Draft content"
        assert resp.content_type == "text/markdown"


# ── Add brief delegation ─────────────────────────────────────────────


class TestAddBriefPassesBackend:
    """Verify add_brief() passes StorageBackend to delegate function."""

    @pytest.mark.asyncio
    async def test_passes_storage_kwarg(self, tmp_path):
        mock_backend = MagicMock()

        content_repo = AsyncMock()
        content_repo.create_piece = AsyncMock()

        svc = DbContentDataService(
            content_repo=content_repo,
            pipeline_repo=AsyncMock(),
            artifacts_root=tmp_path,
            backend=mock_backend,
        )

        with patch(
            "api.services.content_data_service.add_brief",
        ) as mock_fn:
            from api.schemas.content_data import ContentBriefListItem
            mock_fn.return_value = ContentBriefListItem(
                id="brief-001", title="Test", status="suggested",
                content_type="blog", cluster="",
            )
            await svc.add_brief("test-co", "Test Brief")
            mock_fn.assert_called_once()
            call_kwargs = mock_fn.call_args
            assert call_kwargs.kwargs.get("storage") is mock_backend
