"""Tests for the two-phase TD → GA → CE pipeline split.

Tests run_td_gap_analysis_only (Phase 1) and run_td_content_production_only
(Phase 2) from core.orchestration.td_content_orchestrator.

Follows the same patterns as test_td_content_orchestrator.py: mock all
real pipeline functions, validate preflight checks, and verify status updates.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.gap_analysis import GapReport
from core.models.content_generation import ContentGenerationOutput
from core.models.topic_discovery import (
    BuyerStage,
    IntentType,
    TopicAssignment,
    TopicAssignmentMatrix,
    TopicAssignmentStatus,
)
from core.orchestration.td_content_orchestrator import (
    GapAnalysisOnlyResult,
    TDContentPipelineError,
    run_td_gap_analysis_only,
    run_td_content_production_only,
)


def _make_assignment(
    assignment_id: str = "ta-1",
    buyer_stage: BuyerStage = BuyerStage.TOFU,
    intent_type: IntentType = IntentType.informational,
) -> TopicAssignment:
    return TopicAssignment(
        id=assignment_id,
        subdomain_id="sd-1",
        subdomain_name="AP Automation",
        topic_text="How AP Automation Works",
        buyer_stage=buyer_stage,
        intent_type=intent_type,
        audience_segment="AP Manager",
    )


def _make_matrix(assignments: list[TopicAssignment]) -> TopicAssignmentMatrix:
    return TopicAssignmentMatrix(
        assignments=assignments,
        total_assignments=len(assignments),
    )


# ---------------------------------------------------------------------------
# Phase 1: GA-only preflight
# ---------------------------------------------------------------------------


class TestGaOnlyPreflight:
    @pytest.mark.asyncio
    async def test_fails_without_company_context(self, tmp_path: Path) -> None:
        """Missing company context file raises TDContentPipelineError."""
        mock_sf = AsyncMock()

        with patch(
            "core.orchestration.td_content_orchestrator._PROJECT_ROOT", tmp_path,
        ):
            with pytest.raises(TDContentPipelineError, match="Company context"):
                await run_td_gap_analysis_only(
                    effective_slug="test-co",
                    topic_assignment_ids=["ta-1"],
                    company_name="Test Co",
                    domain="test.co",
                    session_factory=mock_sf,
                )

    @pytest.mark.asyncio
    async def test_fails_without_personas(self, tmp_path: Path) -> None:
        """Missing persona artifacts raises TDContentPipelineError."""
        ctx_dir = tmp_path / "artifacts" / "company_context"
        ctx_dir.mkdir(parents=True)
        (ctx_dir / "test-co.md").write_text("Company context here")

        mock_sf = AsyncMock()

        with patch(
            "core.orchestration.td_content_orchestrator._PROJECT_ROOT", tmp_path,
        ), patch(
            "core.orchestration.td_content_orchestrator.PersonaStorage"
        ) as mock_ps:
            mock_ps.return_value.list_persona_paths.return_value = []
            with pytest.raises(TDContentPipelineError, match="persona"):
                await run_td_gap_analysis_only(
                    effective_slug="test-co",
                    topic_assignment_ids=["ta-1"],
                    company_name="Test Co",
                    domain="test.co",
                    session_factory=mock_sf,
                )


# ---------------------------------------------------------------------------
# Phase 1: GA-only filtering + execution
# ---------------------------------------------------------------------------


class TestGaOnlyExecution:
    @pytest.mark.asyncio
    async def test_excluded_combos_filtered(self, tmp_path: Path) -> None:
        """Assignments with excluded buyer_stage x intent combos return empty result."""
        matrix = _make_matrix([
            _make_assignment("ta-1", BuyerStage.TOFU, IntentType.transactional),
            _make_assignment("ta-2", BuyerStage.BOFU, IntentType.navigational),
        ])

        mock_sf = AsyncMock()

        with patch(
            "core.orchestration.td_content_orchestrator._PROJECT_ROOT", tmp_path,
        ), patch(
            "core.orchestration.td_content_orchestrator._validate_preflight_db",
            new_callable=AsyncMock,
            return_value=matrix,
        ), patch(
            "core.orchestration.td_content_orchestrator._write_ga_phase_redis",
        ):
            result = await run_td_gap_analysis_only(
                effective_slug="test-co",
                topic_assignment_ids=["ta-1", "ta-2"],
                company_name="Test Co",
                domain="test.co",
                session_factory=mock_sf,
            )

        assert isinstance(result, GapAnalysisOnlyResult)
        assert result.valid_assignment_ids == []
        assert result.analysis_path == ""

    @pytest.mark.asyncio
    async def test_returns_ga_result(self, tmp_path: Path) -> None:
        """Happy path: mock GA pipeline and verify GapAnalysisOnlyResult returned."""
        matrix = _make_matrix([
            _make_assignment("ta-1", BuyerStage.TOFU, IntentType.informational),
        ])

        mock_report = GapReport(report_md="# Test")
        mock_tqm = {"ta-1": ["tq_1"]}
        mock_sf = AsyncMock()

        with patch(
            "core.orchestration.td_content_orchestrator._PROJECT_ROOT", tmp_path,
        ), patch(
            "core.orchestration.td_content_orchestrator._validate_preflight_db",
            new_callable=AsyncMock,
            return_value=matrix,
        ), patch(
            "core.orchestration.td_content_orchestrator._update_assignment_statuses_db",
            new_callable=AsyncMock,
        ) as mock_update, patch(
            "core.orchestration.td_content_orchestrator.PersonaStorage"
        ) as mock_ps, patch(
            "core.orchestration.td_content_orchestrator.run_topic_scoped_gap_analysis",
            new_callable=AsyncMock,
            return_value=(mock_report, mock_tqm),
        ) as mock_ga, patch(
            "core.orchestration.td_content_orchestrator._write_ga_phase_redis",
        ):
            mock_ps.return_value.list_persona_paths.return_value = ["p1.md"]

            result = await run_td_gap_analysis_only(
                effective_slug="test-co",
                topic_assignment_ids=["ta-1"],
                company_name="Test Co",
                domain="test.co",
                session_factory=mock_sf,
            )

        assert isinstance(result, GapAnalysisOnlyResult)
        assert result.valid_assignment_ids == ["ta-1"]
        assert result.topic_query_map == mock_tqm
        assert result.ga_run_id  # Non-empty UUID string
        assert "analysis.json" in result.analysis_path

        # GA pipeline was called with the valid assignment
        mock_ga.assert_called_once()

    @pytest.mark.asyncio
    async def test_updates_status_to_gap_analysis_complete(self, tmp_path: Path) -> None:
        """Verify DB status updated to gap_analysis_complete on success."""
        matrix = _make_matrix([
            _make_assignment("ta-1", BuyerStage.MOFU, IntentType.commercial),
        ])

        mock_report = GapReport(report_md="# Test")
        mock_tqm = {"ta-1": ["tq_1"]}
        mock_sf = AsyncMock()

        with patch(
            "core.orchestration.td_content_orchestrator._PROJECT_ROOT", tmp_path,
        ), patch(
            "core.orchestration.td_content_orchestrator._validate_preflight_db",
            new_callable=AsyncMock,
            return_value=matrix,
        ), patch(
            "core.orchestration.td_content_orchestrator._update_assignment_statuses_db",
            new_callable=AsyncMock,
        ) as mock_update, patch(
            "core.orchestration.td_content_orchestrator.PersonaStorage"
        ) as mock_ps, patch(
            "core.orchestration.td_content_orchestrator.run_topic_scoped_gap_analysis",
            new_callable=AsyncMock,
            return_value=(mock_report, mock_tqm),
        ), patch(
            "core.orchestration.td_content_orchestrator._write_ga_phase_redis",
        ):
            mock_ps.return_value.list_persona_paths.return_value = ["p1.md"]

            await run_td_gap_analysis_only(
                effective_slug="test-co",
                topic_assignment_ids=["ta-1"],
                company_name="Test Co",
                domain="test.co",
                session_factory=mock_sf,
            )

        # Should be called at least twice: once for in_gap_analysis, once for gap_analysis_complete
        assert mock_update.call_count >= 2
        # Last call should be gap_analysis_complete
        last_call = mock_update.call_args_list[-1]
        assert last_call[0][1] == ["ta-1"]
        assert last_call[0][2] == TopicAssignmentStatus.gap_analysis_complete

    @pytest.mark.asyncio
    async def test_gap_analysis_complete_write_includes_topic_gap_context(self, tmp_path: Path) -> None:
        """Final GA Redis write should carry a summarized topic-level gap_context payload."""
        assignment = _make_assignment("ta-1", BuyerStage.MOFU, IntentType.commercial)
        matrix = _make_matrix([assignment])
        mock_report = GapReport(report_md="# Test")
        mock_tqm = {"ta-1": ["tq_1"]}
        mock_sf = AsyncMock()
        mock_storage = MagicMock()
        mock_storage.read.return_value = json.dumps({"gaps": [], "cluster_specs": []})
        fake_ctx = MagicMock()
        fake_ctx.model_dump.return_value = {
            "query_gap": {
                "gap": 0.34,
                "interpretation": "significant_gap",
                "best_company_similarity": 0.21,
                "avg_citation_similarity": 0.57,
                "company_cited": False,
                "best_company_url": "https://test.co/page",
            },
            "cluster_spec": {"avg_word_count": 1600},
            "exemplars": [{"url": "https://example.com"}],
            "gap_content_brief": None,
            "company_best_text": "",
            "company_best_url": "https://test.co/page",
        }

        with patch(
            "core.orchestration.td_content_orchestrator._PROJECT_ROOT", tmp_path,
        ), patch(
            "core.orchestration.td_content_orchestrator._validate_preflight_db",
            new_callable=AsyncMock,
            return_value=matrix,
        ), patch(
            "core.orchestration.td_content_orchestrator._update_assignment_statuses_db",
            new_callable=AsyncMock,
        ), patch(
            "core.orchestration.td_content_orchestrator.PersonaStorage"
        ) as mock_ps, patch(
            "core.orchestration.td_content_orchestrator.run_topic_scoped_gap_analysis",
            new_callable=AsyncMock,
            return_value=(mock_report, mock_tqm),
        ), patch(
            "core.orchestration.td_content_orchestrator.get_storage_backend",
            return_value=mock_storage,
        ), patch(
            "core.orchestration.td_content_orchestrator.extract_topic_contexts",
            return_value={"tq_1": fake_ctx},
        ), patch(
            "core.orchestration.td_content_orchestrator._write_ga_phase_redis",
        ) as mock_write:
            mock_ps.return_value.list_persona_paths.return_value = ["p1.md"]

            await run_td_gap_analysis_only(
                effective_slug="test-co",
                topic_assignment_ids=["ta-1"],
                company_name="Test Co",
                domain="test.co",
                session_factory=mock_sf,
            )

        final_call = mock_write.call_args_list[-1]
        assert final_call.args[2] == "gap_analysis_complete"
        gap_ctx = final_call.kwargs["gap_context_by_assignment"]["ta-1"]
        assert gap_ctx["gap_score"] == 0.34
        assert gap_ctx["classification"] == "significant_gap"
        assert gap_ctx["company_best_url"] == "https://test.co/page"


# ---------------------------------------------------------------------------
# Phase 2: Content production-only
# ---------------------------------------------------------------------------


class TestContentProductionOnly:
    @pytest.mark.asyncio
    async def test_validates_analysis_exists(self, tmp_path: Path) -> None:
        """Missing analysis.json raises TDContentPipelineError."""
        mock_sf = AsyncMock()
        ga_run_id = str(uuid.uuid4())

        with patch(
            "core.orchestration.td_content_orchestrator._PROJECT_ROOT", tmp_path,
        ), patch(
            "core.storage.get_storage_backend",
        ) as mock_storage_factory:
            mock_storage = MagicMock()
            mock_storage.exists.return_value = False
            mock_storage_factory.return_value = mock_storage

            with pytest.raises(TDContentPipelineError, match="analysis.json not found"):
                await run_td_content_production_only(
                    effective_slug="test-co",
                    topic_assignment_ids=["ta-1"],
                    company_name="Test Co",
                    domain="test.co",
                    ga_run_id=ga_run_id,
                    session_factory=mock_sf,
                )

    @pytest.mark.asyncio
    async def test_cleans_up_ga_state(self, tmp_path: Path) -> None:
        """Verify _cleanup_ga_phase_redis called during production."""
        mock_sf = AsyncMock()
        ga_run_id = str(uuid.uuid4())
        mock_output = ContentGenerationOutput(
            company_slug="test-co",
            total_briefs=1,
            pieces=[],
        )

        with patch(
            "core.orchestration.td_content_orchestrator._PROJECT_ROOT", tmp_path,
        ), patch(
            "core.storage.get_storage_backend",
        ) as mock_storage_factory, patch(
            "core.orchestration.td_content_orchestrator._cleanup_ga_phase_redis",
        ) as mock_cleanup, patch(
            "core.orchestration.td_content_orchestrator.PersonaStorage",
        ) as mock_ps, patch(
            "core.content_engine.pipeline_v13.run_content_generation_v13",
            new_callable=AsyncMock,
            return_value=mock_output,
        ), patch(
            "core.orchestration.td_content_orchestrator._update_assignment_statuses_db",
            new_callable=AsyncMock,
        ):
            mock_storage = MagicMock()
            mock_storage.exists.return_value = True
            mock_storage_factory.return_value = mock_storage
            mock_ps.return_value.list_persona_paths.return_value = ["p1.md"]

            output = await run_td_content_production_only(
                effective_slug="test-co",
                topic_assignment_ids=["ta-1"],
                company_name="Test Co",
                domain="test.co",
                ga_run_id=ga_run_id,
                session_factory=mock_sf,
            )

        assert output is mock_output
        mock_cleanup.assert_called_once_with("test-co", ["ta-1"])

    @pytest.mark.asyncio
    async def test_requires_session_factory(self) -> None:
        """session_factory=None raises TDContentPipelineError."""
        ga_run_id = str(uuid.uuid4())

        with pytest.raises(TDContentPipelineError, match="session_factory"):
            await run_td_content_production_only(
                effective_slug="test-co",
                topic_assignment_ids=["ta-1"],
                company_name="Test Co",
                domain="test.co",
                ga_run_id=ga_run_id,
            )

    @pytest.mark.asyncio
    async def test_updates_status_to_content_produced(self, tmp_path: Path) -> None:
        """Verify status updated to content_produced after CE completes."""
        mock_sf = AsyncMock()
        ga_run_id = str(uuid.uuid4())
        mock_output = ContentGenerationOutput(
            company_slug="test-co",
            total_briefs=1,
            pieces=[],
        )

        with patch(
            "core.orchestration.td_content_orchestrator._PROJECT_ROOT", tmp_path,
        ), patch(
            "core.storage.get_storage_backend",
        ) as mock_storage_factory, patch(
            "core.orchestration.td_content_orchestrator._cleanup_ga_phase_redis",
        ), patch(
            "core.orchestration.td_content_orchestrator.PersonaStorage",
        ) as mock_ps, patch(
            "core.content_engine.pipeline_v13.run_content_generation_v13",
            new_callable=AsyncMock,
            return_value=mock_output,
        ), patch(
            "core.orchestration.td_content_orchestrator._update_assignment_statuses_db",
            new_callable=AsyncMock,
        ) as mock_update:
            mock_storage = MagicMock()
            mock_storage.exists.return_value = True
            mock_storage_factory.return_value = mock_storage
            mock_ps.return_value.list_persona_paths.return_value = ["p1.md"]

            await run_td_content_production_only(
                effective_slug="test-co",
                topic_assignment_ids=["ta-1"],
                company_name="Test Co",
                domain="test.co",
                ga_run_id=ga_run_id,
                session_factory=mock_sf,
            )

        mock_update.assert_called_once()
        call_args = mock_update.call_args[0]
        assert call_args[1] == ["ta-1"]
        assert call_args[2] == TopicAssignmentStatus.content_produced
