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
    async def test_skips_latest_run_lookup_when_slug_pieces_exist(self, tmp_path):
        piece = MagicMock()
        piece.brief_id = "WE-105"
        piece.id = uuid.uuid4()
        piece.title = "Visual Web Design 101"
        piece.status = SimpleNamespace(value="planned")
        piece.content_type = "long_blog"
        piece.word_count = 1200
        piece.citability_score = 0.61
        piece.cluster_name = "Definition"
        piece.run_id = uuid.uuid4()
        piece.created_at = None
        piece.updated_at = None
        piece.published_url = None
        piece.published_at = None

        content_repo = AsyncMock()
        content_repo.list_by_slug = AsyncMock(return_value=[piece])
        content_repo.list_by_run = AsyncMock(return_value=[])
        pipeline_repo = AsyncMock()
        pipeline_repo.get_latest_completed = AsyncMock(return_value=None)

        svc = DbContentDataService(
            content_repo=content_repo,
            pipeline_repo=pipeline_repo,
            artifacts_root=tmp_path,
            backend=MagicMock(),
        )

        with patch(
            "core.services.db_content_data.load_analysis_json",
            return_value=None,
        ), patch(
            "core.config.settings.settings.redis_pipeline_state", False,
        ), patch(
            "core.config.settings.settings.redis_url", None,
        ):
            resp = await svc.get_briefs("test-co")

        assert resp.total == 1
        pipeline_repo.get_latest_completed.assert_not_awaited()
        content_repo.list_by_run.assert_not_awaited()

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

    @pytest.mark.asyncio
    async def test_load_ga_phase_cards_includes_gap_context(self, tmp_path):
        """GA queue cards expose topic-specific gap_context for the detail view."""
        assignment_id = str(uuid.uuid4())
        svc = DbContentDataService(
            content_repo=AsyncMock(),
            pipeline_repo=AsyncMock(),
            artifacts_root=tmp_path,
            backend=MagicMock(),
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
                        status=SimpleNamespace(value="gap_analysis_complete"),
                    ),
                ]

        gap_context = {
            "gap_score": 0.37,
            "classification": "significant_gap",
            "company_similarity": 0.22,
            "citation_similarity": 0.59,
            "company_cited": False,
            "company_best_url": "https://test.co/pricing",
            "why_picked": ["Large citation gap"],
            "success_indicators": [{"label": "Gap Score", "value": "0.3700", "sub": "significant gap"}],
            "exemplars": [{"url": "https://example.com/pricing"}],
        }

        with patch("core.config.settings.settings.redis_pipeline_state", True), patch(
            "core.config.settings.settings.redis_url", "redis://localhost:6379/0",
        ), patch(
            "core.redis.get_redis_or_none", return_value=object(),
        ), patch(
            "core.content_engine.state_redis.read_ga_phase_cards_async",
            AsyncMock(return_value=[{
                "id": f"ta-{assignment_id}",
                "status": "gap_analysis_complete",
                "title": "Pricing for agencies",
                "display_id": "WE-205",
                "topic_assignment_id": assignment_id,
                "created_at": "2026-04-10T07:00:00+00:00",
                "updated_at": "2026-04-10T07:05:00+00:00",
                "gap_context": gap_context,
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
        assert cards[0].gap_context is not None
        assert cards[0].gap_context.gap_score == 0.37
        assert cards[0].gap_context.company_best_url == "https://test.co/pricing"

    @pytest.mark.asyncio
    async def test_db_backed_piece_uses_embedded_topic_gap_context(self, tmp_path):
        """DB-backed CE cards preserve topic-specific gap metrics from persisted blueprint gap_context."""
        mock_backend = MagicMock()
        piece = MagicMock()
        piece.id = uuid.uuid4()
        piece.brief_id = "WE-001"
        piece.title = "No-Code Web Development in the Enterprise"
        piece.status = SimpleNamespace(value="drafting")
        piece.content_type = "how_to"
        piece.word_count = 1800
        piece.citability_score = 0.54
        piece.cluster_name = "Definition"
        piece.run_id = uuid.uuid4()
        piece.created_at = None
        piece.updated_at = None
        piece.published_url = None
        piece.published_at = None
        piece.topic_assignment_id = uuid.uuid4()
        piece.evaluation_results = {
            "gap_context": {
                "query_gap": {
                    "gap": 0.28,
                    "interpretation": "significant_gap",
                    "best_company_similarity": 0.12,
                    "avg_citation_similarity": 0.49,
                    "company_cited": False,
                    "best_company_url": "https://test.co/no-code",
                },
                "exemplars": [
                    {
                        "url": "https://competitor.example/no-code",
                        "domain": "competitor.example",
                        "similarity": 0.52,
                        "word_count": 2100,
                        "authority_type": "editorial",
                    }
                ],
                "cluster_spec": {
                    "word_count_range": [1600, 2200],
                },
            }
        }

        content_repo = AsyncMock()
        content_repo.list_by_slug = AsyncMock(return_value=[piece])
        content_repo.list_by_run = AsyncMock(return_value=[])
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
            return_value=None,
        ), patch(
            "core.config.settings.settings.redis_pipeline_state", False,
        ), patch(
            "core.config.settings.settings.redis_url", None,
        ):
            resp = await svc.get_briefs("test-co")

        assert resp.total == 1
        assert resp.briefs[0].gap_context is not None
        assert resp.briefs[0].gap_context.gap_score == 0.28
        assert resp.briefs[0].gap_context.classification == "significant_gap"
        assert resp.briefs[0].gap_context.company_best_url == "https://test.co/no-code"

    @pytest.mark.asyncio
    async def test_db_backed_piece_includes_topic_assignment_sidebar_metadata(self, tmp_path):
        """DB-backed CE cards retain planner/topic-assignment details after leaving Queue."""
        assignment_id = uuid.uuid4()
        piece = MagicMock()
        piece.id = uuid.uuid4()
        piece.brief_id = "WE-040"
        piece.title = "What Is Visual Web Design and Why It's Changing How Sites Get Built"
        piece.status = SimpleNamespace(value="drafting")
        piece.content_type = "how_to"
        piece.word_count = 1800
        piece.citability_score = 0.54
        piece.cluster_name = "Definition"
        piece.run_id = uuid.uuid4()
        piece.created_at = None
        piece.updated_at = None
        piece.published_url = None
        piece.published_at = None
        piece.topic_assignment_id = assignment_id
        piece.evaluation_results = {
            "gap_context": {
                "query_gap": {
                    "gap": 0.31,
                    "interpretation": "significant_gap",
                    "best_company_similarity": 0.14,
                    "avg_citation_similarity": 0.46,
                    "company_cited": False,
                    "best_company_url": "https://test.co/visual-web-design",
                },
                "exemplars": [
                    {
                        "url": "https://competitor.example/visual-web-design",
                        "domain": "competitor.example",
                        "similarity": 0.55,
                        "word_count": 2300,
                        "authority_type": "editorial",
                    }
                ],
            }
        }

        content_repo = AsyncMock()
        content_repo.list_by_slug = AsyncMock(return_value=[piece])
        content_repo.list_by_run = AsyncMock(return_value=[])
        pipeline_repo = AsyncMock()
        pipeline_repo.get_latest_completed = AsyncMock(return_value=None)

        svc = DbContentDataService(
            content_repo=content_repo,
            pipeline_repo=pipeline_repo,
            artifacts_root=tmp_path,
            backend=MagicMock(),
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
                assert ta_ids == [assignment_id]
                return [
                    SimpleNamespace(
                        id=assignment_id,
                        buyer_stage=SimpleNamespace(value="mofu"),
                        intent_type=SimpleNamespace(value="informational"),
                        persona_name="David",
                        persona_id="persona-david",
                        persona_affinity_json={"persona-david": 0.92},
                        priority_factors={"intent_weight": 0.8, "citation_opportunity": 0.63},
                        priority_score=0.71,
                        metadata_json={
                            "description": "Explain visual web design in plain language for non-technical teams.",
                            "target_keywords": {
                                "primary": "visual web design",
                                "secondary": ["no-code web design", "visual website builder"],
                            },
                            "angle": "Cut through confusion between visual builders and no-code tools.",
                            "content_format": "how_to",
                            "estimated_word_count": 2800,
                        },
                    ),
                ]

        with patch(
            "core.services.db_content_data.load_analysis_json",
            return_value=None,
        ), patch(
            "core.config.settings.settings.redis_pipeline_state", True,
        ), patch(
            "core.config.settings.settings.redis_url", "redis://localhost:6379/0",
        ), patch(
            "core.redis.get_redis_or_none", return_value=object(),
        ), patch(
            "core.content_engine.state_redis.read_ga_phase_cards_async",
            AsyncMock(return_value=[]),
        ), patch(
            "core.content_engine.state_redis.read_pipeline_state_redis_async",
            AsyncMock(return_value={"WE-040": "pending_brief_approval"}),
        ), patch(
            "core.db.engine.get_session_factory",
            return_value=lambda: _SessionContext(),
        ), patch(
            "core.db.repositories.topic_discovery_repo.TopicAssignmentRepository",
            _Repo,
        ):
            resp = await svc.get_briefs("test-co")

        assert resp.total == 1
        item = resp.briefs[0]
        assert item.status == "pending_brief_approval"
        assert item.topic_assignment_id == str(assignment_id)
        assert item.buyer_stage == "mofu"
        assert item.intent_type == "informational"
        assert item.persona_name == "David"
        assert item.persona_id == "persona-david"
        assert item.persona_affinity == {"persona-david": 0.92}
        assert item.priority_factors == {"intent_weight": 0.8, "citation_opportunity": 0.63}
        assert item.citation_opportunity == 0.63
        assert item.description == "Explain visual web design in plain language for non-technical teams."
        assert item.target_keywords == {
            "primary": "visual web design",
            "secondary": ["no-code web design", "visual website builder"],
        }
        assert item.content_angle == "Cut through confusion between visual builders and no-code tools."
        assert item.content_format == "how_to"
        assert item.estimated_word_count == 2800
        assert item.gap_context is not None
        assert item.gap_context.gap_score == 0.31
        assert item.gap_context.company_best_url == "https://test.co/visual-web-design"


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

    @pytest.mark.asyncio
    async def test_get_brief_detail_returns_cps_from_evaluation_results(self, tmp_path):
        """Review/completed detail payloads should expose persisted CPS metrics."""
        mock_piece = MagicMock()
        mock_piece.brief_id = "brief-001"
        mock_piece.id = uuid.uuid4()
        mock_piece.title = "Test Brief"
        mock_piece.status = MagicMock(value="review")
        mock_piece.content_type = "long_blog"
        mock_piece.evaluation_results = {
            "key_topics": ["topic-a"],
            "key_angles": ["angle-1"],
            "eval_history": [
                {
                    "cycle": 1,
                    "overall_passed": True,
                    "overall_score": 0.82,
                    "dimensions": [],
                }
            ],
            "final_passed": True,
            "cps": {
                "cps_score": 0.58,
                "per_engine": {
                    "chatgpt_search": 0.6,
                    "perplexity": 0.56,
                },
            },
        }
        mock_piece.citability_score = None
        mock_piece.cluster_name = ""
        mock_piece.word_count = 0
        mock_piece.run_id = None
        mock_piece.created_at = None
        mock_piece.updated_at = None

        content_repo = AsyncMock()
        content_repo.get_by_slug_and_brief_id = AsyncMock(return_value=mock_piece)
        artifact_repo = AsyncMock()
        artifact_repo.list_by_piece = AsyncMock(return_value=[])

        svc = DbContentDataService(
            content_repo=content_repo,
            pipeline_repo=AsyncMock(),
            artifacts_root=tmp_path,
            artifact_repo=artifact_repo,
            backend=MagicMock(),
        )

        resp = await svc.get_brief_detail("test-co", "brief-001")
        assert resp.final_passed is True
        assert resp.cps is not None
        assert resp.cps.cps_score == 0.58
        assert resp.cps.per_engine == {
            "chatgpt_search": 0.6,
            "perplexity": 0.56,
        }


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
