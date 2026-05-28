"""Tests for the TD → GA → CE orchestrator.

Phase 6 of TD → GA → CE integration.
Tests preflight validation and end-to-end flow with mocked pipelines.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.content_generation import ContentGenerationOutput
from core.models.gap_analysis import GapReport
from core.models.topic_discovery import (
    BuyerStage,
    IntentType,
    TopicAssignment,
    TopicAssignmentMatrix,
)
from core.models.content_generation_v13 import EntryMode
from core.orchestration.td_content_orchestrator import (
    TDContentPipelineError,
    _validate_preflight_db,
    run_td_to_content_pipeline,
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
# Preflight Validation
# ---------------------------------------------------------------------------


class TestPreflightValidation:
    @pytest.mark.asyncio
    async def test_missing_company_context(self, tmp_path):
        with patch(
            "core.orchestration.td_content_orchestrator._PROJECT_ROOT", tmp_path,
        ):
            with pytest.raises(TDContentPipelineError, match="Company context"):
                await _validate_preflight_db(AsyncMock(), "test-co", ["ta-1"])

    @pytest.mark.asyncio
    async def test_empty_company_context(self, tmp_path):
        ctx_dir = tmp_path / "artifacts" / "company_context"
        ctx_dir.mkdir(parents=True)
        (ctx_dir / "test-co.md").write_text("")

        with patch(
            "core.orchestration.td_content_orchestrator._PROJECT_ROOT", tmp_path,
        ):
            with pytest.raises(TDContentPipelineError, match="Company context"):
                await _validate_preflight_db(AsyncMock(), "test-co", ["ta-1"])

    @pytest.mark.asyncio
    async def test_missing_personas(self, tmp_path):
        ctx_dir = tmp_path / "artifacts" / "company_context"
        ctx_dir.mkdir(parents=True)
        (ctx_dir / "test-co.md").write_text("Company context here")

        with patch(
            "core.orchestration.td_content_orchestrator._PROJECT_ROOT", tmp_path,
        ), patch(
            "core.orchestration.td_content_orchestrator.PersonaStorage"
        ) as mock_ps:
            mock_ps.return_value.list_persona_paths.return_value = []
            with pytest.raises(TDContentPipelineError, match="persona"):
                await _validate_preflight_db(AsyncMock(), "test-co", ["ta-1"])

    @pytest.mark.asyncio
    async def test_missing_matrix(self, tmp_path):
        from core.models.topic_discovery import TopicDiscoveryManifest

        ctx_dir = tmp_path / "artifacts" / "company_context"
        ctx_dir.mkdir(parents=True)
        (ctx_dir / "test-co.md").write_text("Company context")

        empty_manifest = TopicDiscoveryManifest(slug="test-co", matrix_version=0)

        with patch(
            "core.orchestration.td_content_orchestrator._PROJECT_ROOT", tmp_path,
        ), patch(
            "core.orchestration.td_content_orchestrator.PersonaStorage"
        ) as mock_ps, patch(
            "core.orchestration.td_content_orchestrator.db_read_manifest",
            new_callable=AsyncMock,
            return_value=empty_manifest,
        ):
            mock_ps.return_value.list_persona_paths.return_value = ["p1.md"]
            with pytest.raises(TDContentPipelineError, match="matrix"):
                await _validate_preflight_db(AsyncMock(), "test-co", ["ta-1"])

    @pytest.mark.asyncio
    async def test_missing_assignment_ids(self, tmp_path):
        from core.models.topic_discovery import TopicDiscoveryManifest

        ctx_dir = tmp_path / "artifacts" / "company_context"
        ctx_dir.mkdir(parents=True)
        (ctx_dir / "test-co.md").write_text("Company context")

        matrix = _make_matrix([_make_assignment("ta-1")])
        manifest = TopicDiscoveryManifest(slug="test-co", matrix_version=1)

        with patch(
            "core.orchestration.td_content_orchestrator._PROJECT_ROOT", tmp_path,
        ), patch(
            "core.orchestration.td_content_orchestrator.PersonaStorage"
        ) as mock_ps, patch(
            "core.orchestration.td_content_orchestrator.db_read_manifest",
            new_callable=AsyncMock,
            return_value=manifest,
        ), patch(
            "core.orchestration.td_content_orchestrator.db_read_latest_matrix",
            new_callable=AsyncMock,
            return_value=matrix,
        ):
            mock_ps.return_value.list_persona_paths.return_value = ["p1.md"]
            with pytest.raises(TDContentPipelineError, match="not found"):
                await _validate_preflight_db(AsyncMock(), "test-co", ["ta-99"])

    @pytest.mark.asyncio
    async def test_passes_when_all_valid(self, tmp_path):
        from core.models.topic_discovery import TopicDiscoveryManifest

        ctx_dir = tmp_path / "artifacts" / "company_context"
        ctx_dir.mkdir(parents=True)
        (ctx_dir / "test-co.md").write_text("Company context")

        matrix = _make_matrix([_make_assignment("ta-1")])
        manifest = TopicDiscoveryManifest(slug="test-co", matrix_version=1)

        with patch(
            "core.orchestration.td_content_orchestrator._PROJECT_ROOT", tmp_path,
        ), patch(
            "core.orchestration.td_content_orchestrator.PersonaStorage"
        ) as mock_ps, patch(
            "core.orchestration.td_content_orchestrator.db_read_manifest",
            new_callable=AsyncMock,
            return_value=manifest,
        ), patch(
            "core.orchestration.td_content_orchestrator.db_read_latest_matrix",
            new_callable=AsyncMock,
            return_value=matrix,
        ):
            mock_ps.return_value.list_persona_paths.return_value = ["p1.md"]
            # Should not raise
            await _validate_preflight_db(AsyncMock(), "test-co", ["ta-1"])


# ---------------------------------------------------------------------------
# Orchestrator End-to-End
# ---------------------------------------------------------------------------


class TestRunTDToContentPipeline:
    @pytest.mark.asyncio
    async def test_excluded_combos_filtered(self, tmp_path):
        """Assignments with excluded combos should be filtered out."""
        # All topics are excluded combos → empty output
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
        ):
            output = await run_td_to_content_pipeline(
                effective_slug="test-co",
                topic_assignment_ids=["ta-1", "ta-2"],
                company_name="Test Co",
                domain="test.co",
                session_factory=mock_sf,
            )

        assert isinstance(output, ContentGenerationOutput)
        assert "error" in output.run_metadata

    @pytest.mark.asyncio
    async def test_full_flow_with_mocks(self, tmp_path):
        """End-to-end with all pipelines mocked."""
        matrix = _make_matrix([
            _make_assignment("ta-1", BuyerStage.TOFU, IntentType.informational),
        ])

        mock_report = GapReport(report_md="# Test")
        mock_tqm = {"ta-1": ["tq_1"]}
        mock_output = ContentGenerationOutput(
            company_slug="test-co",
            total_briefs=1,
            pieces=[],
        )

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
        ), patch(
            "core.orchestration.td_content_orchestrator.PersonaStorage"
        ) as mock_ps, patch(
            "core.orchestration.td_content_orchestrator.run_topic_scoped_gap_analysis",
            new_callable=AsyncMock,
            return_value=(mock_report, mock_tqm),
        ) as mock_ga, patch(
            "core.content_engine.pipeline_v13.run_content_generation_v13",
            new_callable=AsyncMock,
            return_value=mock_output,
        ) as mock_ce:
            mock_ps.return_value.list_persona_paths.return_value = ["p1.md"]

            output = await run_td_to_content_pipeline(
                effective_slug="test-co",
                topic_assignment_ids=["ta-1"],
                company_name="Test Co",
                domain="test.co",
                session_factory=mock_sf,
            )

        assert output is mock_output
        # GA was called with the valid assignment
        mock_ga.assert_called_once()
        ga_topics = mock_ga.call_args[1].get("topics") or mock_ga.call_args[0][0]
        assert len(ga_topics) == 1
        assert ga_topics[0].id == "ta-1"

        # CE was called in TOPIC_DISCOVERY mode
        mock_ce.assert_called_once()
        ce_input = mock_ce.call_args[0][0]
        assert ce_input.entry_mode == EntryMode.TOPIC_DISCOVERY
        assert ce_input.topic_assignment_ids == ["ta-1"]
