"""Tests for core.content_engine.pipeline_v13 — v1.3 pipeline orchestrator.

Tests the 6-stage async pipeline with mocked agents, workers, and evaluators.
Uses tmp_path for artifact directories.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.content_generation import (
    ContentGenerationOutput,
    ContentPiece,
    ContentStatus,
    FormattedContent,
    RevisionHistory,
)
from core.models.content_generation_v13 import (
    ContentBlueprint,
    ContentGenerationInputV13,
    EntryMode,
    StrategicPlannerOutput,
    TopicSelection,
    WorkerQueryContext,
)


# ── Helpers ───────────────────────────────────────────────────────────


def _make_input(
    tmp_path: Path,
    entry_mode: EntryMode = EntryMode.AUTONOMOUS,
    auto_approve: bool = True,
    skip_stages: list | None = None,
    manual_prompt: str | None = None,
) -> ContentGenerationInputV13:
    """Build a minimal ContentGenerationInputV13 with tmp_path artifacts."""
    # Create dummy artifacts
    analysis = {"gaps": [], "cluster_specs": []}
    analysis_path = tmp_path / "analysis.json"
    analysis_path.write_text(json.dumps(analysis))

    context_path = tmp_path / "context.md"
    context_path.write_text("Test company context")

    return ContentGenerationInputV13(
        company_name="Test Co",
        domain="test-co.com",
        company_slug="test-co",
        analysis_json_path=str(analysis_path),
        company_context_path=str(context_path),
        entry_mode=entry_mode,
        auto_approve=auto_approve,
        skip_stages=skip_stages or [],
        manual_prompt=manual_prompt,
        max_topics=3,
    )


def _make_blueprint(brief_id: str = "brief-001", title: str = "Test Brief") -> ContentBlueprint:
    return ContentBlueprint(
        brief_id=brief_id,
        title=title,
        content_format="long_blog",
        sections=[],
        key_topics=["equity"],
    )


def _make_formatted(brief_id: str = "brief-001", title: str = "Test Brief") -> FormattedContent:
    return FormattedContent(
        brief_id=brief_id,
        title=title,
        markdown="# Test Content\n\nThis is test content.",
        word_count=100,
    )


def _make_planner_output() -> StrategicPlannerOutput:
    return StrategicPlannerOutput(
        selections=[
            TopicSelection(
                rank=1,
                query_ids=["q-001"],
                query_texts=["test query"],
                cluster_name="equity",
                rationale="High gap",
            ),
        ],
        selection_metadata={"model": "test"},
    )


# ── Global Tracing Patches ───────────────────────────────────────────


_TRACING_PATCHES = {
    "configure_litellm_callbacks": "core.content_engine.pipeline_v13.configure_litellm_callbacks",
    "create_session": "core.content_engine.pipeline_v13.create_session",
    "create_pipeline_trace": "core.content_engine.pipeline_v13.create_pipeline_trace",
    "create_span": "core.content_engine.pipeline_v13.create_span",
    "end_span": "core.content_engine.pipeline_v13.end_span",
    "update_trace_output": "core.content_engine.pipeline_v13.update_trace_output",
    "flush": "core.content_engine.pipeline_v13.flush",
}


@pytest.fixture(autouse=True)
def _mock_tracing():
    """Disable all LangSmith tracing for pipeline tests."""
    with patch(_TRACING_PATCHES["configure_litellm_callbacks"]), \
         patch(_TRACING_PATCHES["create_session"], return_value="test-session"), \
         patch(_TRACING_PATCHES["create_pipeline_trace"], return_value=MagicMock()), \
         patch(_TRACING_PATCHES["create_span"], return_value=MagicMock()), \
         patch(_TRACING_PATCHES["end_span"]), \
         patch(_TRACING_PATCHES["update_trace_output"]), \
         patch(_TRACING_PATCHES["flush"]):
        yield


@pytest.fixture(autouse=True)
def _mock_project_root(tmp_path):
    """Redirect artifact directory to tmp_path."""
    with patch("core.content_engine.pipeline_v13._PROJECT_ROOT", tmp_path):
        yield


# ═══════════════════════════════════════════════════════════════════════
# Full Pipeline Tests
# ═══════════════════════════════════════════════════════════════════════


class TestAutonomousMode:
    """Tests for autonomous mode pipeline execution."""

    @pytest.mark.asyncio
    async def test_full_flow_returns_output(self, tmp_path):
        """Autonomous mode with auto_approve produces ContentGenerationOutput."""
        input_data = _make_input(tmp_path)
        blueprint = _make_blueprint()
        formatted = _make_formatted()
        history = RevisionHistory(brief_id="brief-001", final_passed=True)

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=_make_planner_output()), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       # HITL-1: topic approval
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       # HITL-2: brief approval
                       {"brief_decision": "approve"},
                       # HITL-3: content review
                       {"content_decision": "approve", "finalized": True},
                   ]), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]), \
             patch("core.content_engine.workers.dispatcher.dispatch_workers_v13",
                   new_callable=AsyncMock, return_value=([(formatted.brief_id, formatted)], [])), \
             patch("core.content_engine.evaluator.loop.evaluate_and_optimize",
                   new_callable=AsyncMock, return_value=(formatted, history, "pass")):
            result = await run_content_generation_v13(input_data)

        assert isinstance(result, ContentGenerationOutput)
        assert result.company_slug == "test-co"
        assert result.total_briefs == 1
        assert result.total_approved == 1

    @pytest.mark.asyncio
    async def test_topic_rejection_stops_pipeline(self, tmp_path):
        """When topics are rejected, pipeline returns empty output."""
        input_data = _make_input(tmp_path)

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=_make_planner_output()), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock,
                   return_value={"topic_decision": "reject"}), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()):
            result = await run_content_generation_v13(input_data)

        assert result.total_briefs == 0
        assert result.pieces == []

    @pytest.mark.asyncio
    async def test_skip_stage_1(self, tmp_path):
        """Skipping stage 1 loads planner output from file."""
        input_data = _make_input(tmp_path, skip_stages=[1])
        blueprint = _make_blueprint()
        formatted = _make_formatted()
        history = RevisionHistory(brief_id="brief-001", final_passed=True)

        # Pre-create planner selections file
        artifact_dir = tmp_path / "artifacts" / "content" / "test-co"
        artifact_dir.mkdir(parents=True)
        planner_output = _make_planner_output()
        (artifact_dir / "planner_selections.json").write_text(
            planner_output.model_dump_json(indent=2)
        )

        with patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"brief_decision": "approve"},
                       {"content_decision": "approve", "finalized": True},
                   ]), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]), \
             patch("core.content_engine.workers.dispatcher.dispatch_workers_v13",
                   new_callable=AsyncMock, return_value=([(formatted.brief_id, formatted)], [])), \
             patch("core.content_engine.evaluator.loop.evaluate_and_optimize",
                   new_callable=AsyncMock, return_value=(formatted, history, "pass")):
            result = await run_content_generation_v13(input_data)

        assert result.total_approved == 1

    @pytest.mark.asyncio
    async def test_skip_stage_1_no_file(self, tmp_path):
        """Skipping stage 1 without planner file results in 0 topics."""
        input_data = _make_input(tmp_path, skip_stages=[1])

        result = await run_content_generation_v13(input_data)

        assert result.total_briefs == 0
        assert result.pieces == []

    @pytest.mark.asyncio
    async def test_empty_approved_topics(self, tmp_path):
        """No approved topics results in no blueprints/content."""
        input_data = _make_input(tmp_path)
        planner = StrategicPlannerOutput(selections=[], selection_metadata={})

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=planner), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock,
                   return_value={"topic_decision": "approve", "approved_topic_ranks": []}), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()):
            result = await run_content_generation_v13(input_data)

        assert result.total_briefs == 0

    @pytest.mark.asyncio
    async def test_sse_events_published(self, tmp_path):
        """SSE events are published at each stage transition."""
        input_data = _make_input(tmp_path, skip_stages=[1, 2, 3, 4, 5])
        event_bus = MagicMock()
        task_store = MagicMock()

        result = await run_content_generation_v13(
            input_data,
            task_id="task-001",
            task_store=task_store,
            event_bus=event_bus,
        )

        # At minimum, pipeline_started and pipeline_complete events
        event_types = [call[0][1] for call in event_bus.publish.call_args_list]
        assert "pipeline_started" in event_types
        assert "pipeline_complete" in event_types

    @pytest.mark.asyncio
    async def test_run_metadata_includes_version(self, tmp_path):
        """Output run_metadata includes pipeline version 1.3."""
        input_data = _make_input(tmp_path, skip_stages=[1, 2, 3, 4, 5])

        result = await run_content_generation_v13(input_data)

        assert result.run_metadata["pipeline_version"] == "1.3"
        assert result.run_metadata["entry_mode"] == "autonomous"


class TestManualMode:
    """Tests for manual mode pipeline execution."""

    @pytest.mark.asyncio
    async def test_manual_skips_stage_1(self, tmp_path):
        """Manual mode skips the Strategic Planner entirely."""
        input_data = _make_input(
            tmp_path,
            entry_mode=EntryMode.MANUAL,
            manual_prompt="What is a 409A valuation?",
        )
        blueprint = _make_blueprint()
        formatted = _make_formatted()
        history = RevisionHistory(brief_id="brief-001", final_passed=True)

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]) as mock_build, \
             patch("core.content_engine.workers.dispatcher.dispatch_workers_v13",
                   new_callable=AsyncMock, return_value=([(formatted.brief_id, formatted)], [])), \
             patch("core.content_engine.evaluator.loop.evaluate_and_optimize",
                   new_callable=AsyncMock, return_value=(formatted, history, "pass")), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock,
                   return_value={"content_decision": "approve", "finalized": True}):
            result = await run_content_generation_v13(input_data)

        assert result.run_metadata["entry_mode"] == "manual"
        # build_briefs_parallel should have been called with manual topic
        mock_build.assert_called_once()

    @pytest.mark.asyncio
    async def test_manual_constructs_worker_context(self, tmp_path):
        """Manual mode without analysis_json creates inline WorkerQueryContext."""
        # Don't create analysis.json
        input_data = ContentGenerationInputV13(
            company_name="Test Co",
            domain="test-co.com",
            company_slug="test-co",
            entry_mode=EntryMode.MANUAL,
            manual_prompt="How does equity work?",
            manual_cluster="equity",
            auto_approve=True,
        )
        blueprint = _make_blueprint()
        formatted = _make_formatted()
        history = RevisionHistory(brief_id="brief-001", final_passed=True)

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]) as mock_build, \
             patch("core.content_engine.workers.dispatcher.dispatch_workers_v13",
                   new_callable=AsyncMock, return_value=([(formatted.brief_id, formatted)], [])), \
             patch("core.content_engine.evaluator.loop.evaluate_and_optimize",
                   new_callable=AsyncMock, return_value=(formatted, history, "pass")), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock,
                   return_value={"content_decision": "approve", "finalized": True}):
            result = await run_content_generation_v13(input_data)

        # Should pass inline worker_contexts
        call_kwargs = mock_build.call_args[1]
        contexts = call_kwargs["contexts"]
        assert "manual-1" in contexts
        assert contexts["manual-1"].query_gap["query_text"] == "How does equity work?"


class TestContentReview:
    """Tests for final content review decisions."""

    @pytest.mark.asyncio
    async def test_approved_content_saved_to_disk(self, tmp_path):
        """Approved content writes final.md to artifact directory."""
        input_data = _make_input(tmp_path, skip_stages=[1, 2, 3, 4])
        formatted = _make_formatted()
        history = RevisionHistory(brief_id="brief-001", final_passed=True)

        # The pipeline needs formatted_contents from stage 3
        # Skip stages 3 & 4 to produce evaluated = [(fc, history)] directly
        # But skip_stages=[1,2,3,4] means formatted_contents=[] and evaluated=[]
        # Instead skip only stages 1 and 2, mock stages 3 and 4
        input_data2 = _make_input(tmp_path, skip_stages=[1, 2])
        # We need approved_blueprints to be non-empty to enter stage 3
        # Since we skip stages 1 and 2, approved_blueprints stays empty.
        # Let's test a different way — skip only stages 1 and use full flow

        input_data3 = _make_input(tmp_path)
        blueprint = _make_blueprint()

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=_make_planner_output()), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]), \
             patch("core.content_engine.workers.dispatcher.dispatch_workers_v13",
                   new_callable=AsyncMock, return_value=([(formatted.brief_id, formatted)], [])), \
             patch("core.content_engine.evaluator.loop.evaluate_and_optimize",
                   new_callable=AsyncMock, return_value=(formatted, history, "pass")), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       {"brief_decision": "approve"},
                       {"content_decision": "approve", "finalized": True},
                   ]):
            result = await run_content_generation_v13(input_data3)

        assert result.pieces[0].status == ContentStatus.APPROVED
        # Check that final.md was written
        final_path = tmp_path / "artifacts" / "content" / "test-co" / "content" / "brief-001" / "final.md"
        assert final_path.exists()
        assert "Test Content" in final_path.read_text()

    @pytest.mark.asyncio
    async def test_rejected_content_no_artifact(self, tmp_path):
        """Rejected content has no artifact_path."""
        input_data = _make_input(tmp_path)
        blueprint = _make_blueprint()
        formatted = _make_formatted()
        history = RevisionHistory(brief_id="brief-001", final_passed=True)

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=_make_planner_output()), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]), \
             patch("core.content_engine.workers.dispatcher.dispatch_workers_v13",
                   new_callable=AsyncMock, return_value=([(formatted.brief_id, formatted)], [])), \
             patch("core.content_engine.evaluator.loop.evaluate_and_optimize",
                   new_callable=AsyncMock, return_value=(formatted, history, "pass")), \
             patch("core.content_engine.pipeline_v13._rebrief_and_rerun",
                   new_callable=AsyncMock, return_value=None), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       {"brief_decision": "approve"},
                       {"content_decision": "reject"},
                   ]):
            result = await run_content_generation_v13(input_data)

        assert result.pieces[0].status == ContentStatus.REJECTED
        assert result.pieces[0].artifact_path is None
        assert result.total_rejected == 1

    @pytest.mark.asyncio
    async def test_brief_rejection_excludes_from_pipeline(self, tmp_path):
        """Rejected briefs don't proceed to workers."""
        input_data = _make_input(tmp_path)
        blueprint = _make_blueprint()

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=_make_planner_output()), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       {"brief_decision": "reject"},  # Brief rejected
                   ]):
            result = await run_content_generation_v13(input_data)

        # No content pieces since brief was rejected, workers never called
        assert result.total_briefs == 0
        assert result.pieces == []


class TestArtifactPersistence:
    """Tests for artifact file persistence."""

    @pytest.mark.asyncio
    async def test_planner_output_saved(self, tmp_path):
        """Planner output is saved to planner_selections.json."""
        input_data = _make_input(tmp_path, skip_stages=[2, 3, 4, 5])
        planner_output = _make_planner_output()

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=planner_output), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock,
                   return_value={"topic_decision": "approve", "approved_topic_ranks": [0]}):
            await run_content_generation_v13(input_data)

        planner_path = tmp_path / "artifacts" / "content" / "test-co" / "planner_selections.json"
        assert planner_path.exists()
        saved = json.loads(planner_path.read_text())
        assert len(saved["selections"]) == 1

    @pytest.mark.asyncio
    async def test_run_metadata_saved(self, tmp_path):
        """run_metadata_v13.json is written at pipeline end."""
        input_data = _make_input(tmp_path, skip_stages=[1, 2, 3, 4, 5])

        result = await run_content_generation_v13(input_data)

        meta_path = tmp_path / "artifacts" / "content" / "test-co" / "run_metadata_v13.json"
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text())
        assert meta["run_metadata"]["pipeline_version"] == "1.3"


# ═══════════════════════════════════════════════════════════════════════
# HITL-3 Feedback Loop Tests
# ═══════════════════════════════════════════════════════════════════════


class TestHITL3Edit:
    """Tests for HITL-3 edit → drafter revision → re-present loop."""

    @pytest.mark.asyncio
    async def test_edit_applies_revision_and_reapproves(self, tmp_path):
        """Edit routes to drafter, then re-presents for approval."""
        input_data = _make_input(tmp_path)
        blueprint = _make_blueprint()
        formatted = _make_formatted()
        revised = _make_formatted(brief_id="brief-001", title="Revised Brief")
        history = RevisionHistory(brief_id="brief-001", final_passed=True)

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=_make_planner_output()), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]), \
             patch("core.content_engine.workers.dispatcher.dispatch_workers_v13",
                   new_callable=AsyncMock, return_value=([(formatted.brief_id, formatted)], [])), \
             patch("core.content_engine.evaluator.loop.evaluate_and_optimize",
                   new_callable=AsyncMock, return_value=(formatted, history, "pass")), \
             patch("core.content_engine.pipeline_v13._apply_human_edits",
                   new_callable=AsyncMock, return_value=revised), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       {"brief_decision": "approve"},
                       # First HITL-3: edit
                       {"content_decision": "edit", "editor_notes": "Add more stats"},
                       # Second HITL-3: approve (after revision)
                       {"content_decision": "approve", "finalized": True},
                   ]):
            result = await run_content_generation_v13(input_data)

        assert result.total_approved == 1
        assert result.pieces[0].status == ContentStatus.APPROVED

    @pytest.mark.asyncio
    async def test_edit_exhausted_then_rejected(self, tmp_path):
        """After max edit attempts, content is rejected."""
        input_data = _make_input(tmp_path)
        blueprint = _make_blueprint()
        formatted = _make_formatted()
        revised = _make_formatted(brief_id="brief-001")
        history = RevisionHistory(brief_id="brief-001", final_passed=True)

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=_make_planner_output()), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]), \
             patch("core.content_engine.workers.dispatcher.dispatch_workers_v13",
                   new_callable=AsyncMock, return_value=([(formatted.brief_id, formatted)], [])), \
             patch("core.content_engine.evaluator.loop.evaluate_and_optimize",
                   new_callable=AsyncMock, return_value=(formatted, history, "pass")), \
             patch("core.content_engine.pipeline_v13._apply_human_edits",
                   new_callable=AsyncMock, return_value=revised), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       {"brief_decision": "approve"},
                       # HITL-3 edit #1
                       {"content_decision": "edit", "editor_notes": "Fix tone"},
                       # HITL-3 edit #2
                       {"content_decision": "edit", "editor_notes": "Still not right"},
                       # HITL-3 edit #3 — max_edit_attempts=2 exhausted, falls to else
                       {"content_decision": "edit", "editor_notes": "Even more changes"},
                   ]):
            result = await run_content_generation_v13(input_data)

        # After 2 edit attempts exhausted, 3rd edit request → permanent rejection
        assert result.pieces[0].status == ContentStatus.REJECTED


class TestHITL3Reject:
    """Tests for HITL-3 reject → re-brief loop."""

    @pytest.mark.asyncio
    async def test_reject_with_rethink_triggers_rebrief(self, tmp_path):
        """H3 FIX: Reject + rethink=True routes to re-brief, then re-presents and approves."""
        input_data = _make_input(tmp_path)
        blueprint = _make_blueprint()
        formatted = _make_formatted()
        rebriefed_formatted = _make_formatted(brief_id="brief-001", title="Rebriefed")
        history = RevisionHistory(brief_id="brief-001", final_passed=True)

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=_make_planner_output()), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]), \
             patch("core.content_engine.workers.dispatcher.dispatch_workers_v13",
                   new_callable=AsyncMock, return_value=([(formatted.brief_id, formatted)], [])), \
             patch("core.content_engine.evaluator.loop.evaluate_and_optimize",
                   new_callable=AsyncMock, return_value=(formatted, history, "pass")), \
             patch("core.content_engine.pipeline_v13._rebrief_and_rerun",
                   new_callable=AsyncMock,
                   return_value=(rebriefed_formatted, history, "pass")), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       {"brief_decision": "approve"},
                       # First HITL-3: reject with rethink=True → triggers re-brief
                       {"content_decision": "reject", "rethink": True, "editor_notes": "Wrong direction"},
                       # Second HITL-3: approve (after re-brief)
                       {"content_decision": "approve", "finalized": True},
                   ]):
            result = await run_content_generation_v13(input_data)

        assert result.total_approved == 1
        assert result.pieces[0].status == ContentStatus.APPROVED

    @pytest.mark.asyncio
    async def test_reject_without_rethink_is_permanent(self, tmp_path):
        """H3 FIX: Reject without rethink=True → permanent rejection (no re-brief)."""
        input_data = _make_input(tmp_path)
        blueprint = _make_blueprint()
        formatted = _make_formatted()
        history = RevisionHistory(brief_id="brief-001", final_passed=True)

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=_make_planner_output()), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]), \
             patch("core.content_engine.workers.dispatcher.dispatch_workers_v13",
                   new_callable=AsyncMock, return_value=([(formatted.brief_id, formatted)], [])), \
             patch("core.content_engine.evaluator.loop.evaluate_and_optimize",
                   new_callable=AsyncMock, return_value=(formatted, history, "pass")), \
             patch("core.content_engine.pipeline_v13._rebrief_and_rerun",
                   new_callable=AsyncMock) as mock_rebrief, \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       {"brief_decision": "approve"},
                       # HITL-3: reject WITHOUT rethink → permanent rejection
                       {"content_decision": "reject", "editor_notes": "Not good enough"},
                   ]):
            result = await run_content_generation_v13(input_data)

        # _rebrief_and_rerun must NOT have been called
        mock_rebrief.assert_not_called()
        assert result.total_rejected == 1
        assert result.pieces[0].status == ContentStatus.REJECTED

    @pytest.mark.asyncio
    async def test_max_rebriefs_then_rejected(self, tmp_path):
        """After max re-briefs exhausted, further rejects are permanent."""
        input_data = _make_input(tmp_path)
        blueprint = _make_blueprint()
        formatted = _make_formatted()
        rebriefed = _make_formatted(brief_id="brief-001")
        history = RevisionHistory(brief_id="brief-001", final_passed=True)

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=_make_planner_output()), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]), \
             patch("core.content_engine.workers.dispatcher.dispatch_workers_v13",
                   new_callable=AsyncMock, return_value=([(formatted.brief_id, formatted)], [])), \
             patch("core.content_engine.evaluator.loop.evaluate_and_optimize",
                   new_callable=AsyncMock, return_value=(formatted, history, "pass")), \
             patch("core.content_engine.pipeline_v13._rebrief_and_rerun",
                   new_callable=AsyncMock,
                   return_value=(rebriefed, history, "pass")), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       {"brief_decision": "approve"},
                       # HITL-3 reject #1 with rethink → re-brief
                       {"content_decision": "reject", "rethink": True, "editor_notes": "Off topic"},
                       # HITL-3 reject #2 with rethink → re-brief
                       {"content_decision": "reject", "rethink": True, "editor_notes": "Still off topic"},
                       # HITL-3 reject #3 with rethink → max_rebriefs=2 exhausted → permanent reject
                       {"content_decision": "reject", "rethink": True, "editor_notes": "Nope"},
                   ]):
            result = await run_content_generation_v13(input_data)

        assert result.pieces[0].status == ContentStatus.REJECTED
        assert result.total_rejected == 1


class TestMajorChangeSignal:
    """Tests for evaluator major_change → re-brief."""

    @pytest.mark.asyncio
    async def test_major_change_triggers_rebrief(self, tmp_path):
        """Evaluator major_change signal triggers re-brief before HITL-3."""
        input_data = _make_input(tmp_path)
        blueprint = _make_blueprint()
        formatted = _make_formatted()
        rebriefed = _make_formatted(brief_id="brief-001", title="Rebriefed")
        history = RevisionHistory(brief_id="brief-001", final_passed=False)
        history_after = RevisionHistory(brief_id="brief-001", final_passed=True)

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=_make_planner_output()), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]), \
             patch("core.content_engine.workers.dispatcher.dispatch_workers_v13",
                   new_callable=AsyncMock, return_value=([(formatted.brief_id, formatted)], [])), \
             patch("core.content_engine.evaluator.loop.evaluate_and_optimize",
                   new_callable=AsyncMock,
                   return_value=(formatted, history, "major_change")), \
             patch("core.content_engine.pipeline_v13._rebrief_and_rerun",
                   new_callable=AsyncMock,
                   return_value=(rebriefed, history_after, "pass")) as mock_rebrief, \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       {"brief_decision": "approve"},
                       # HITL-3: approve (after automatic re-brief)
                       {"content_decision": "approve", "finalized": True},
                   ]):
            result = await run_content_generation_v13(input_data)

        # _rebrief_and_rerun should have been called
        mock_rebrief.assert_called_once()
        assert result.total_approved == 1


# ═══════════════════════════════════════════════════════════════════════
# C2 Regression: dispatcher return type + zip-mismatch safety
# ═══════════════════════════════════════════════════════════════════════


class TestDispatcherBriefIdMatching:
    """C2: dispatch_workers_v13 must return (brief_id, FormattedContent) tuples so
    Stage 4 can match by ID rather than by position.
    """

    @pytest.mark.asyncio
    async def test_dispatcher_returns_id_tuples(self, tmp_path):
        """dispatch_workers_v13() must return List[Tuple[str, FormattedContent]]."""
        from core.content_engine.workers.dispatcher import dispatch_workers_v13
        from core.models.content_generation_v13 import ContentGenerationInputV13

        analysis_path = tmp_path / "analysis.json"
        analysis_path.write_text("{}")
        context_path = tmp_path / "context.md"
        context_path.write_text("ctx")

        input_data = ContentGenerationInputV13(
            company_name="Test Co",
            domain="test-co.com",
            company_slug="test-co",
            analysis_json_path=str(analysis_path),
            company_context_path=str(context_path),
        )

        briefs = [
            _make_blueprint("brief-001"),
            _make_blueprint("brief-002"),
        ]
        fc1 = _make_formatted("brief-001")
        fc2 = _make_formatted("brief-002")

        with patch(
            "core.content_engine.workers.dispatcher._run_worker_chain_v13",
            new_callable=AsyncMock,
            side_effect=[fc1, fc2],
        ), patch(
            "core.content_engine.workers.dispatcher.create_span",
            return_value=MagicMock(),
        ), patch(
            "core.content_engine.workers.dispatcher.end_span",
        ):
            result, failures = await dispatch_workers_v13(
                briefs=briefs,
                input_data=input_data,
                style_guide_md="",
                company_context_md="",
                artifact_dir=tmp_path,
            )

        # Must return list of (brief_id, FormattedContent) tuples + empty failures
        assert len(result) == 2
        assert len(failures) == 0
        for item in result:
            assert isinstance(item, tuple), "Each result must be a (brief_id, FormattedContent) tuple"
            brief_id, content = item
            assert isinstance(brief_id, str)
            assert isinstance(content, FormattedContent)

        # IDs must match the input brief IDs in order
        ids = [item[0] for item in result]
        assert ids == ["brief-001", "brief-002"]

    @pytest.mark.asyncio
    async def test_worker_failure_does_not_corrupt_brief_pairing(self, tmp_path):
        """C2: When worker[0] fails, remaining content is still paired with the correct blueprint.

        Before the fix, formatted_contents was compacted so content[1] (brief-002)
        would be zipped against blueprint[0] (brief-001) — silent data corruption.
        After the fix, the (brief_id, content) tuple enables correct matching regardless.
        """
        from core.content_engine.workers.dispatcher import dispatch_workers_v13
        from core.models.content_generation_v13 import ContentGenerationInputV13

        analysis_path = tmp_path / "analysis.json"
        analysis_path.write_text("{}")
        context_path = tmp_path / "context.md"
        context_path.write_text("ctx")

        input_data = ContentGenerationInputV13(
            company_name="Test Co",
            domain="test-co.com",
            company_slug="test-co",
            analysis_json_path=str(analysis_path),
            company_context_path=str(context_path),
        )

        briefs = [
            _make_blueprint("brief-001"),
            _make_blueprint("brief-002"),
            _make_blueprint("brief-003"),
        ]
        fc2 = _make_formatted("brief-002")
        fc3 = _make_formatted("brief-003")

        with patch(
            "core.content_engine.workers.dispatcher._run_worker_chain_v13",
            new_callable=AsyncMock,
            side_effect=[RuntimeError("worker-1 failed"), fc2, fc3],
        ), patch(
            "core.content_engine.workers.dispatcher.create_span",
            return_value=MagicMock(),
        ), patch(
            "core.content_engine.workers.dispatcher.end_span",
        ):
            result, failures = await dispatch_workers_v13(
                briefs=briefs,
                input_data=input_data,
                style_guide_md="",
                company_context_md="",
                artifact_dir=tmp_path,
            )

        # Only 2 successes (brief-001 failed) + 1 failure
        assert len(result) == 2
        assert len(failures) == 1
        assert failures[0]["brief_id"] == "brief-001"

        # IDs must be brief-002 and brief-003 — NOT brief-001 and brief-002
        ids = [item[0] for item in result]
        assert "brief-001" not in ids, "Failed brief must not appear in results"
        assert "brief-002" in ids
        assert "brief-003" in ids

        # Contents must be paired with their correct brief_id
        by_id = {bid: fc for bid, fc in result}
        assert by_id["brief-002"].brief_id == "brief-002"
        assert by_id["brief-003"].brief_id == "brief-003"


# ═══════════════════════════════════════════════════════════════════════
# H1: _rebrief_and_rerun context extraction
# ═══════════════════════════════════════════════════════════════════════


class TestRebriefContextExtraction:
    """H1: _rebrief_and_rerun must use the full WorkerQueryContext from gap_context,
    not fall back to a minimal one due to isinstance(dict) always being False."""

    @pytest.mark.asyncio
    async def test_full_context_used_when_gap_context_set(self, tmp_path):
        """When blueprint.gap_context is a WorkerQueryContext, its full data is passed to Agent 2."""
        from core.content_engine.pipeline_v13 import _rebrief_and_rerun

        gap_ctx = WorkerQueryContext(
            query_gap={"query_id": "q-equity-001", "query_text": "equity dilution"},
            cluster_spec={"cluster": "equity"},
            exemplars=[{"url": "https://example.com", "title": "Example"}],
            company_best_text="We help companies manage equity.",
        )
        bp = ContentBlueprint(
            brief_id="brief-001",
            title="Equity Dilution Guide",
            content_format="long_blog",
            cluster_name="equity",
            gap_context=gap_ctx,
        )
        input_data = _make_input(tmp_path)
        formatted = _make_formatted()
        history = RevisionHistory(brief_id="brief-001", final_passed=True)

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[bp]) as mock_build, \
             patch("core.content_engine.workers.dispatcher.dispatch_workers_v13",
                   new_callable=AsyncMock, return_value=([(formatted.brief_id, formatted)], [])), \
             patch("core.content_engine.evaluator.loop.evaluate_and_optimize",
                   new_callable=AsyncMock, return_value=(formatted, history, "pass")):
            result = await _rebrief_and_rerun(
                blueprint=bp,
                user_comment="Focus on anti-dilution clauses",
                input_data=input_data,
                company_context_md="Company context",
                persona_mds=[],
                style_guide_md="",
                analysis_json={},
                artifact_dir=tmp_path,
                session_id="test-session",
            )

        assert result is not None
        # The contexts passed to Agent 2 must contain the full WorkerQueryContext
        call_kwargs = mock_build.call_args[1]
        contexts = call_kwargs["contexts"]
        assert "q-equity-001" in contexts, "Full query_id from gap_context.query_gap must be used"
        passed_ctx = contexts["q-equity-001"]
        assert passed_ctx.exemplars == gap_ctx.exemplars, "Exemplars must be preserved"
        assert passed_ctx.cluster_spec == gap_ctx.cluster_spec, "Cluster spec must be preserved"
        assert passed_ctx.company_best_text == gap_ctx.company_best_text

    @pytest.mark.asyncio
    async def test_fallback_used_when_gap_context_none(self, tmp_path):
        """When blueprint.gap_context is None, fallback minimal context is created."""
        from core.content_engine.pipeline_v13 import _rebrief_and_rerun

        bp = ContentBlueprint(
            brief_id="brief-002",
            title="Startup Funding Guide",
            content_format="long_blog",
            cluster_name="funding",
            gap_context=None,
        )
        input_data = _make_input(tmp_path)
        formatted = _make_formatted(brief_id="brief-002")
        history = RevisionHistory(brief_id="brief-002", final_passed=True)

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[bp]) as mock_build, \
             patch("core.content_engine.workers.dispatcher.dispatch_workers_v13",
                   new_callable=AsyncMock, return_value=([(formatted.brief_id, formatted)], [])), \
             patch("core.content_engine.evaluator.loop.evaluate_and_optimize",
                   new_callable=AsyncMock, return_value=(formatted, history, "pass")):
            result = await _rebrief_and_rerun(
                blueprint=bp,
                user_comment="Needs more detail",
                input_data=input_data,
                company_context_md="",
                persona_mds=[],
                style_guide_md="",
                analysis_json={},
                artifact_dir=tmp_path,
                session_id="test-session",
            )

        assert result is not None
        call_kwargs = mock_build.call_args[1]
        contexts = call_kwargs["contexts"]
        # Should have created a fallback context with rebrief- prefix
        fallback_qid = "rebrief-brief-002"
        assert fallback_qid in contexts, f"Fallback key '{fallback_qid}' must exist"
        assert contexts[fallback_qid].query_gap["query_text"] == "Startup Funding Guide"


# ═══════════════════════════════════════════════════════════════════════
# H3a: HITL-1 "retry" loop
# ═══════════════════════════════════════════════════════════════════════


class TestHITL1Retry:
    """H3a: HITL-1 'retry' decision must re-invoke the Strategic Planner with feedback."""

    @pytest.mark.asyncio
    async def test_retry_reruns_planner_with_feedback(self, tmp_path):
        """'retry' decision calls select_topics again with the user's feedback."""
        input_data = _make_input(tmp_path)
        blueprint = _make_blueprint()
        formatted = _make_formatted()
        history = RevisionHistory(brief_id="brief-001", final_passed=True)
        planner_output = _make_planner_output()

        mock_select = AsyncMock(return_value=planner_output)

        with patch("core.content_engine.pipeline_v13.select_topics", mock_select), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       # HITL-1: retry with feedback
                       {"topic_decision": "retry", "topic_feedback": "Focus on expense-tracking"},
                       # HITL-1 retry: approve
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       # HITL-2: approve
                       {"brief_decision": "approve"},
                       # HITL-3: approve
                       {"content_decision": "approve", "finalized": True},
                   ]), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]), \
             patch("core.content_engine.workers.dispatcher.dispatch_workers_v13",
                   new_callable=AsyncMock, return_value=([(formatted.brief_id, formatted)], [])), \
             patch("core.content_engine.evaluator.loop.evaluate_and_optimize",
                   new_callable=AsyncMock, return_value=(formatted, history, "pass")):
            result = await run_content_generation_v13(input_data)

        # select_topics must have been called twice (original + retry)
        assert mock_select.call_count == 2
        # Second call must include the feedback
        second_call_kwargs = mock_select.call_args_list[1][1]
        assert second_call_kwargs["user_feedback"] == "Focus on expense-tracking"
        # Pipeline still completes normally
        assert result.total_approved == 1

    @pytest.mark.asyncio
    async def test_retry_exhausted_stops_pipeline(self, tmp_path):
        """After _MAX_TOPIC_RETRIES retries, pipeline stops even without explicit reject."""
        input_data = _make_input(tmp_path)
        planner_output = _make_planner_output()

        # 3 retries = 1 initial + 2 retry iterations (all returning "retry")
        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=planner_output), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, return_value={
                       "topic_decision": "retry", "topic_feedback": "try again",
                   }), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()):
            result = await run_content_generation_v13(input_data)

        # Pipeline must stop — no content produced
        assert result.total_briefs == 0
        assert result.pieces == []

    @pytest.mark.asyncio
    async def test_retry_then_reject_stops_pipeline(self, tmp_path):
        """'retry' followed by 'reject' stops the pipeline cleanly."""
        input_data = _make_input(tmp_path)
        planner_output = _make_planner_output()

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=planner_output), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"topic_decision": "retry", "topic_feedback": "not right"},
                       {"topic_decision": "reject"},
                   ]), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()):
            result = await run_content_generation_v13(input_data)

        assert result.total_briefs == 0
        assert result.pieces == []


# ═══════════════════════════════════════════════════════════════════════
# H3b: HITL-2 "feedback" loop
# ═══════════════════════════════════════════════════════════════════════


class TestHITL2Feedback:
    """H3b: HITL-2 'feedback' decision must re-invoke Agent 2 with feedback, then re-present."""

    @pytest.mark.asyncio
    async def test_feedback_reruns_agent2_with_context(self, tmp_path):
        """'feedback' decision calls build_briefs_parallel again with feedback in rationale."""
        input_data = _make_input(tmp_path)
        gap_ctx = WorkerQueryContext(
            query_gap={"query_id": "q-001", "query_text": "equity dilution"},
            exemplars=[{"url": "https://example.com"}],
        )
        blueprint = ContentBlueprint(
            brief_id="brief-001",
            title="Equity Dilution Guide",
            content_format="long_blog",
            cluster_name="equity",
            gap_context=gap_ctx,
        )
        revised_blueprint = ContentBlueprint(
            brief_id="brief-001",
            title="Equity Dilution Guide (Revised)",
            content_format="long_blog",
            cluster_name="equity",
            gap_context=gap_ctx,
        )
        formatted = _make_formatted()
        history = RevisionHistory(brief_id="brief-001", final_passed=True)
        planner_output = _make_planner_output()

        mock_build = AsyncMock(side_effect=[
            [blueprint],        # Initial Agent 2 call (Stage 2)
            [revised_blueprint],  # Re-run after HITL-2 feedback
        ])

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=planner_output), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       # HITL-1: approve
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       # HITL-2 first: feedback
                       {"brief_decision": "feedback", "brief_feedback": "Emphasize anti-dilution"},
                       # HITL-2 second (after re-run): approve
                       {"brief_decision": "approve"},
                       # HITL-3: approve
                       {"content_decision": "approve", "finalized": True},
                   ]), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build), \
             patch("core.content_engine.workers.dispatcher.dispatch_workers_v13",
                   new_callable=AsyncMock, return_value=([(formatted.brief_id, formatted)], [])), \
             patch("core.content_engine.evaluator.loop.evaluate_and_optimize",
                   new_callable=AsyncMock, return_value=(formatted, history, "pass")):
            result = await run_content_generation_v13(input_data)

        # build_briefs_parallel must have been called twice
        assert mock_build.call_count == 2
        # Second call must include feedback in topic rationale
        second_call_kwargs = mock_build.call_args_list[1][1]
        topics = second_call_kwargs["topics"]
        assert len(topics) == 1
        assert "Emphasize anti-dilution" in topics[0].rationale
        # Pipeline must succeed normally
        assert result.total_approved == 1

    @pytest.mark.asyncio
    async def test_feedback_retries_exhausted_approves_original(self, tmp_path):
        """After _MAX_BRIEF_FEEDBACK_RETRIES, further feedback falls through to approve."""
        input_data = _make_input(tmp_path)
        gap_ctx = WorkerQueryContext(
            query_gap={"query_id": "q-001"},
        )
        blueprint = ContentBlueprint(
            brief_id="brief-001",
            title="Test Brief",
            content_format="long_blog",
            cluster_name="test",
            gap_context=gap_ctx,
        )
        revised = ContentBlueprint(
            brief_id="brief-001",
            title="Revised Brief",
            content_format="long_blog",
            cluster_name="test",
            gap_context=gap_ctx,
        )
        formatted = _make_formatted()
        history = RevisionHistory(brief_id="brief-001", final_passed=True)
        planner_output = _make_planner_output()

        mock_build = AsyncMock(side_effect=[
            [blueprint],  # Stage 2 initial
            [revised],    # First feedback re-run (count=1 = _MAX_BRIEF_FEEDBACK_RETRIES)
        ])

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=planner_output), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       # HITL-2 attempt 1: feedback (triggers re-run)
                       {"brief_decision": "feedback", "brief_feedback": "First feedback"},
                       # HITL-2 attempt 2: feedback again (retries exhausted → falls to else → break)
                       {"brief_decision": "feedback", "brief_feedback": "Second feedback"},
                   ]), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            result = await run_content_generation_v13(input_data)

        # Only 1 re-run (max retries=1), second feedback is rejected (no brief approved)
        # The brief gets rejected (loop breaks) so no content produced
        assert mock_build.call_count == 2  # initial + 1 re-run
        assert result.total_briefs == 0  # brief rejected after retries exhausted

    @pytest.mark.asyncio
    async def test_feedback_without_gap_context_still_approved(self, tmp_path):
        """'feedback' decision with gap_context=None still approves (no re-run possible)."""
        input_data = _make_input(tmp_path)
        blueprint = _make_blueprint()  # gap_context=None
        formatted = _make_formatted()
        history = RevisionHistory(brief_id="brief-001", final_passed=True)
        planner_output = _make_planner_output()

        mock_build = AsyncMock(return_value=[blueprint])

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=planner_output), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       # HITL-2 first: feedback, gap_context=None → counter incremented, no re-run, loop back
                       {"brief_decision": "feedback", "brief_feedback": "Expand section 2"},
                       # HITL-2 second: retries exhausted (count=1 == max=1) → else branch → break
                       {"brief_decision": "feedback", "brief_feedback": "Still not happy"},
                   ]), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            result = await run_content_generation_v13(input_data)

        # Retries exhausted with no re-run possible (gap_context=None) → brief rejected
        assert result.total_briefs == 0  # brief rejected when gap_context=None and retries exhausted


# ═══════════════════════════════════════════════════════════════════════
# H8: HITL-2 Brief Decision Audit Trail
# ═══════════════════════════════════════════════════════════════════════


class TestHITL2BriefDecisionLogging:
    """H8: persist_v13_brief_approval must record all decisions including rejects.

    Uses skip_stages=[3, 4, 5] to isolate stages 1+2 only.
    Patches persist_v13_brief_approval to capture what is actually passed.
    """

    # ── common patch helpers ──────────────────────────────────────────

    @staticmethod
    def _base_patches(blueprint, planner_output, hitl2_side_effects):
        """Return patch context list: [HITL-1 approve] + hitl2_side_effects."""
        return (
            patch(
                "core.content_engine.pipeline_v13.select_topics",
                new_callable=AsyncMock,
                return_value=planner_output,
            ),
            patch(
                "core.content_engine.pipeline_v13.run_hitl_checkpoint",
                new_callable=AsyncMock,
                side_effect=[
                    {"topic_decision": "approve", "approved_topic_ranks": [0]},
                    *hitl2_side_effects,
                ],
            ),
            patch(
                "core.content_engine.pipeline_v13.extract_scorecard",
                return_value=MagicMock(),
            ),
            patch(
                "core.content_engine.pipeline_v13.extract_worker_context",
                return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})},
            ),
            patch(
                "core.content_engine.pipeline_v13.build_briefs_parallel",
                new_callable=AsyncMock,
                return_value=[blueprint],
            ),
        )

    @pytest.mark.asyncio
    async def test_approve_logs_decision_with_approve_outcome(self, tmp_path):
        """Approve decision recorded in audit log with correct fields."""
        input_data = _make_input(tmp_path, skip_stages=[3, 4, 5])
        blueprint = _make_blueprint("brief-001")
        planner_output = _make_planner_output()

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=planner_output), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       {"brief_decision": "approve", "brief_feedback": ""},
                   ]), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]), \
             patch("core.content_engine.pipeline_v13.persist_v13_brief_approval",
                   new_callable=AsyncMock) as mock_persist, \
             patch("core.content_engine.pipeline_v13.persist_v13_planner_output",
                   new_callable=AsyncMock):
            result = await run_content_generation_v13(input_data)

        mock_persist.assert_called_once()
        decisions = mock_persist.call_args.kwargs["approval_decisions"]
        assert len(decisions) == 1
        assert decisions[0]["brief_id"] == "brief-001"
        assert decisions[0]["decision"] == "approve"
        assert decisions[0]["feedback_attempts"] == 0
        assert result.total_briefs == 1

    @pytest.mark.asyncio
    async def test_reject_logs_decision_with_reject_outcome(self, tmp_path):
        """Reject decision is captured in audit log."""
        input_data = _make_input(tmp_path, skip_stages=[3, 4, 5])
        blueprint = _make_blueprint("brief-001")
        planner_output = _make_planner_output()

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=planner_output), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       {"brief_decision": "reject"},
                   ]), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]), \
             patch("core.content_engine.pipeline_v13.persist_v13_brief_approval",
                   new_callable=AsyncMock) as mock_persist, \
             patch("core.content_engine.pipeline_v13.persist_v13_planner_output",
                   new_callable=AsyncMock):
            result = await run_content_generation_v13(input_data)

        mock_persist.assert_called_once()
        decisions = mock_persist.call_args.kwargs["approval_decisions"]
        assert len(decisions) == 1
        assert decisions[0]["decision"] == "reject"
        assert decisions[0]["brief_id"] == "brief-001"

    @pytest.mark.asyncio
    async def test_reject_excluded_from_approved_blueprints(self, tmp_path):
        """Rejected brief is NOT added to approved_blueprints → total_briefs == 0."""
        input_data = _make_input(tmp_path, skip_stages=[3, 4, 5])
        blueprint = _make_blueprint("brief-001")
        planner_output = _make_planner_output()

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=planner_output), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       {"brief_decision": "reject"},
                   ]), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]), \
             patch("core.content_engine.pipeline_v13.persist_v13_brief_approval",
                   new_callable=AsyncMock), \
             patch("core.content_engine.pipeline_v13.persist_v13_planner_output",
                   new_callable=AsyncMock):
            result = await run_content_generation_v13(input_data)

        assert result.total_briefs == 0

    @pytest.mark.asyncio
    async def test_feedback_retry_exhausted_logs_reject(self, tmp_path):
        """Feedback x2 (retries exhausted) must produce decision='reject', feedback_attempts=1."""
        input_data = _make_input(tmp_path, skip_stages=[3, 4, 5])
        gap_ctx = WorkerQueryContext(query_gap={"query_id": "q-001"})
        blueprint = ContentBlueprint(
            brief_id="brief-001",
            title="Test Brief",
            content_format="long_blog",
            cluster_name="test",
            gap_context=gap_ctx,
        )
        planner_output = _make_planner_output()

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=planner_output), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       # HITL-2: feedback (brief_feedback_count 0→1, re-run)
                       {"brief_decision": "feedback", "brief_feedback": "Too short"},
                       # HITL-2: feedback again (count==1==max, falls to else → reject)
                       {"brief_decision": "feedback", "brief_feedback": "Still too short"},
                   ]), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, side_effect=[
                       [blueprint],   # initial build
                       [blueprint],   # re-run after feedback
                   ]), \
             patch("core.content_engine.pipeline_v13.persist_v13_brief_approval",
                   new_callable=AsyncMock) as mock_persist, \
             patch("core.content_engine.pipeline_v13.persist_v13_planner_output",
                   new_callable=AsyncMock):
            result = await run_content_generation_v13(input_data)

        mock_persist.assert_called_once()
        decisions = mock_persist.call_args.kwargs["approval_decisions"]
        assert len(decisions) == 1
        assert decisions[0]["decision"] == "reject"
        assert decisions[0]["feedback_attempts"] == 1
        assert result.total_briefs == 0

    @pytest.mark.asyncio
    async def test_feedback_then_approve_logs_correct_attempts(self, tmp_path):
        """Feedback then approve: decision='approve', feedback_attempts=1."""
        input_data = _make_input(tmp_path, skip_stages=[3, 4, 5])
        gap_ctx = WorkerQueryContext(query_gap={"query_id": "q-001"})
        blueprint = ContentBlueprint(
            brief_id="brief-001",
            title="Test Brief",
            content_format="long_blog",
            cluster_name="test",
            gap_context=gap_ctx,
        )
        planner_output = _make_planner_output()

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=planner_output), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       # HITL-2: feedback once
                       {"brief_decision": "feedback", "brief_feedback": "Add examples"},
                       # HITL-2: approve after re-run
                       {"brief_decision": "approve"},
                   ]), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, side_effect=[
                       [blueprint],   # initial build
                       [blueprint],   # re-run after feedback
                   ]), \
             patch("core.content_engine.pipeline_v13.persist_v13_brief_approval",
                   new_callable=AsyncMock) as mock_persist, \
             patch("core.content_engine.pipeline_v13.persist_v13_planner_output",
                   new_callable=AsyncMock):
            result = await run_content_generation_v13(input_data)

        mock_persist.assert_called_once()
        decisions = mock_persist.call_args.kwargs["approval_decisions"]
        assert len(decisions) == 1
        assert decisions[0]["decision"] == "approve"
        assert decisions[0]["feedback_attempts"] == 1
        assert result.total_briefs == 1

    @pytest.mark.asyncio
    async def test_all_blueprints_passed_to_persist_including_rejected(self, tmp_path):
        """2 blueprints (1 approved, 1 rejected) → persist receives blueprints list len=2."""
        input_data = _make_input(tmp_path, skip_stages=[3, 4, 5])
        bp1 = _make_blueprint("brief-001", "Brief One")
        bp2 = _make_blueprint("brief-002", "Brief Two")
        planner_output = _make_planner_output()

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=planner_output), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       # HITL-2 for brief-001: approve
                       {"brief_decision": "approve"},
                       # HITL-2 for brief-002: reject
                       {"brief_decision": "reject"},
                   ]), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[bp1, bp2]), \
             patch("core.content_engine.pipeline_v13.persist_v13_brief_approval",
                   new_callable=AsyncMock) as mock_persist, \
             patch("core.content_engine.pipeline_v13.persist_v13_planner_output",
                   new_callable=AsyncMock):
            result = await run_content_generation_v13(input_data)

        mock_persist.assert_called_once()
        call_kwargs = mock_persist.call_args.kwargs
        # ALL blueprints (not just approved) must be passed
        assert len(call_kwargs["blueprints"]) == 2
        # Both decisions recorded
        assert len(call_kwargs["approval_decisions"]) == 2
        decision_map = {d["brief_id"]: d["decision"] for d in call_kwargs["approval_decisions"]}
        assert decision_map["brief-001"] == "approve"
        assert decision_map["brief-002"] == "reject"
        # Only 1 approved brief in result
        assert result.total_briefs == 1

    @pytest.mark.asyncio
    async def test_persist_called_with_feedback_text(self, tmp_path):
        """Feedback text from HITL-2 approve response is captured in the decision log."""
        input_data = _make_input(tmp_path, skip_stages=[3, 4, 5])
        blueprint = _make_blueprint("brief-001")
        planner_output = _make_planner_output()

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=planner_output), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       {"brief_decision": "approve", "brief_feedback": "Add ROI data"},
                   ]), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]), \
             patch("core.content_engine.pipeline_v13.persist_v13_brief_approval",
                   new_callable=AsyncMock) as mock_persist, \
             patch("core.content_engine.pipeline_v13.persist_v13_planner_output",
                   new_callable=AsyncMock):
            await run_content_generation_v13(input_data)

        decisions = mock_persist.call_args.kwargs["approval_decisions"]
        assert decisions[0]["feedback"] == "Add ROI data"


# ═══════════════════════════════════════════════════════════════════════
# H9: evaluated 4-tuple — brief_id must be threaded through
# ═══════════════════════════════════════════════════════════════════════


class TestEvaluatedTupleRouting:
    """H9: evaluated list must carry brief_id so Stage 5 can look up the blueprint by id,
    not by positional index (which drifts when a worker fails for one of N briefs).

    Three sub-scenarios:
    A. Stage 4 runs — evaluated built from evaluate_and_optimize results (line 809 path).
    B. Stage 4 skipped — evaluated built from fallback else branch (line 814-817 path).
    C. Stage 4+5 skipped — auto-approve else branch (line 1006+ path).
    """

    # ── scenario A: stage 4 runs ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_blueprint_matched_by_brief_id_not_position(self, tmp_path):
        """Stage 5 must use brief_id to look up blueprint, not positional index.

        Setup:
          approved_blueprints = [bp_001 (idx=0), bp_002 (idx=1)]
          formatted_contents  = [("brief-002", content_002)] only — bp_001 worker failed

        Bug (3-tuple): evaluated[0] is content_002, but blueprint = approved_blueprints[0] = bp_001 WRONG
        Fix (4-tuple): brief_id "brief-002" → blueprint_by_id["brief-002"] = bp_002  CORRECT

        The mismatch is detected through _rebrief_and_rerun: triggered by "major_change"
        feedback_route and receives the positionally-indexed blueprint.
        """
        input_data = _make_input(tmp_path)
        bp_001 = _make_blueprint("brief-001", "Brief One")
        bp_002 = _make_blueprint("brief-002", "Brief Two")
        content_002 = _make_formatted("brief-002", "Brief Two")
        history = RevisionHistory(brief_id="brief-002", final_passed=True)
        planner_output = _make_planner_output()

        mock_rebrief = AsyncMock(return_value=None)  # re-brief fails → content rejected

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=planner_output), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       # HITL-2 for bp_001
                       {"brief_decision": "approve"},
                       # HITL-2 for bp_002
                       {"brief_decision": "approve"},
                       # HITL-3 for content_002: reject with rethink (triggers re-brief with blueprint)
                       {"content_decision": "reject", "rethink": True},
                       # After re-brief fails, piece is permanently rejected → loop ends
                   ]), \
             patch("core.content_engine.pipeline_v13.extract_scorecard",
                   return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[bp_001, bp_002]), \
             patch("core.content_engine.workers.dispatcher.dispatch_workers_v13",
                   new_callable=AsyncMock,
                   return_value=([("brief-002", content_002)], [])), \
             patch("core.content_engine.evaluator.loop.evaluate_and_optimize",
                   new_callable=AsyncMock,
                   return_value=(content_002, history, "pass")), \
             patch("core.content_engine.pipeline_v13._rebrief_and_rerun", mock_rebrief):
            result = await run_content_generation_v13(input_data)

        # Re-brief must be called with bp_002 (brief-002), NOT bp_001 (positional-index=0)
        assert mock_rebrief.called, "_rebrief_and_rerun was not called"
        rebrief_blueprint = mock_rebrief.call_args.kwargs["blueprint"]
        assert rebrief_blueprint.brief_id == "brief-002", (
            f"Expected brief-002 but got {rebrief_blueprint.brief_id}; "
            "positional-index bug: approved_blueprints[0] is brief-001"
        )

    @pytest.mark.asyncio
    async def test_single_brief_still_correct_after_fix(self, tmp_path):
        """Single brief (no index drift possible) still works after 4-tuple change."""
        input_data = _make_input(tmp_path)
        blueprint = _make_blueprint("brief-001")
        content = _make_formatted("brief-001")
        history = RevisionHistory(brief_id="brief-001", final_passed=True)
        planner_output = _make_planner_output()

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=planner_output), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       {"brief_decision": "approve"},
                       {"content_decision": "approve", "finalized": True},
                   ]), \
             patch("core.content_engine.pipeline_v13.extract_scorecard",
                   return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]), \
             patch("core.content_engine.workers.dispatcher.dispatch_workers_v13",
                   new_callable=AsyncMock,
                   return_value=([("brief-001", content)], [])), \
             patch("core.content_engine.evaluator.loop.evaluate_and_optimize",
                   new_callable=AsyncMock,
                   return_value=(content, history, "pass")):
            result = await run_content_generation_v13(input_data)

        assert result.total_briefs == 1
        assert result.total_approved == 1
        assert result.pieces[0].brief_id == "brief-001"

    # ── scenario B: stage 4 skipped (fallback else branch) ──────────

    @pytest.mark.asyncio
    async def test_fallback_evaluated_built_correctly_when_stage4_skipped(self, tmp_path):
        """When stage 4 is skipped, evaluated is built from formatted_contents 2-tuples.

        The else branch (line 813-817) iterated `for fc in formatted_contents` but
        formatted_contents is List[Tuple[str, FormattedContent]] — so fc is a tuple.
        After fix: `for brief_id, fc in formatted_contents:` produces valid 4-tuples.
        """
        input_data = _make_input(tmp_path, skip_stages=[4])
        bp_001 = _make_blueprint("brief-001", "Brief One")
        bp_002 = _make_blueprint("brief-002", "Brief Two")
        content_002 = _make_formatted("brief-002", "Brief Two")
        planner_output = _make_planner_output()

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=planner_output), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       # HITL-2 for bp_001
                       {"brief_decision": "approve"},
                       # HITL-2 for bp_002
                       {"brief_decision": "approve"},
                       # HITL-3 for content_002: approve
                       {"content_decision": "approve", "finalized": True},
                   ]), \
             patch("core.content_engine.pipeline_v13.extract_scorecard",
                   return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[bp_001, bp_002]), \
             patch("core.content_engine.workers.dispatcher.dispatch_workers_v13",
                   new_callable=AsyncMock,
                   # Only brief-002 output; brief-001 worker failed
                   return_value=([("brief-002", content_002)], [])):
            result = await run_content_generation_v13(input_data)

        # Only brief-002 should produce a piece; correct blueprint must be attached
        assert result.total_approved == 1
        assert result.pieces[0].brief_id == "brief-002"

    # ── scenario C: stages 4+5 skipped (auto-approve path) ──────────

    @pytest.mark.asyncio
    async def test_auto_approve_path_handles_4tuple_correctly(self, tmp_path):
        """When stages 4 and 5 are both skipped, auto-approve unpacks 4-tuples correctly."""
        input_data = _make_input(tmp_path, skip_stages=[4, 5])
        blueprint = _make_blueprint("brief-001")
        content = _make_formatted("brief-001")
        planner_output = _make_planner_output()

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=planner_output), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       {"brief_decision": "approve"},
                   ]), \
             patch("core.content_engine.pipeline_v13.extract_scorecard",
                   return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]), \
             patch("core.content_engine.workers.dispatcher.dispatch_workers_v13",
                   new_callable=AsyncMock,
                   return_value=([("brief-001", content)], [])):
            result = await run_content_generation_v13(input_data)

        assert result.total_approved == 1
        assert result.pieces[0].brief_id == "brief-001"
        assert result.pieces[0].status == ContentStatus.APPROVED


# ═══════════════════════════════════════════════════════════════════════
# M4: _update_task progress translation — unit tests
# ═══════════════════════════════════════════════════════════════════════


class TestUpdateTask:
    """Unit tests for _update_task helper — M4 progress shape fix.

    Verifies that progress={"stage": N, "stage_name": "..."} is correctly
    translated into current_step and progress_pct fields on PipelineTask.
    """

    def test_progress_dict_sets_current_step_and_pct(self):
        """stage=3 → current_step='content_workers', progress_pct=60.0."""
        store = MagicMock()
        _update_task(store, "t-1", progress={"stage": 3, "stage_name": "Content Workers"})
        store.update_task.assert_called_once_with(
            "t-1", current_step="content_workers", progress_pct=60.0
        )

    def test_progress_stage_0_sets_zero_pct(self):
        """stage=0 → 0.0%; extra status= kwarg passes through alongside computed values."""
        store = MagicMock()
        _update_task(store, "t-1", status="running", progress={"stage": 0, "stage_name": "Entry Router"})
        store.update_task.assert_called_once_with(
            "t-1", status="running", current_step="entry_router", progress_pct=0.0
        )

    def test_progress_stage_5_sets_100_pct(self):
        """stage=5 → 100.0%."""
        store = MagicMock()
        _update_task(store, "t-1", progress={"stage": 5, "stage_name": "Final Review"})
        store.update_task.assert_called_once_with(
            "t-1", current_step="final_review", progress_pct=100.0
        )

    def test_explicit_current_step_takes_priority(self):
        """Explicit current_step= kwarg overrides the value computed from progress dict."""
        store = MagicMock()
        _update_task(
            store, "t-1",
            progress={"stage": 2, "stage_name": "Brief Builder"},
            current_step="custom_step",
        )
        call_kwargs = store.update_task.call_args.kwargs
        assert call_kwargs["current_step"] == "custom_step"
        assert call_kwargs["progress_pct"] == 40.0

    def test_no_progress_kwarg_passes_through_unchanged(self):
        """When no progress= kwarg is present, kwargs are forwarded as-is."""
        store = MagicMock()
        _update_task(store, "t-1", status="running", current_step="entry_router")
        store.update_task.assert_called_once_with(
            "t-1", status="running", current_step="entry_router"
        )

    def test_none_task_store_is_noop(self):
        """_update_task(None, ...) raises no exception."""
        _update_task(None, "t-1", progress={"stage": 1, "stage_name": "Planner"})

    def test_none_task_id_is_noop(self):
        """update_task is not called when task_id is None."""
        store = MagicMock()
        _update_task(store, None, progress={"stage": 1, "stage_name": "Planner"})
        store.update_task.assert_not_called()

    def test_stage_name_spaces_converted_to_underscores(self):
        """Spaces in stage_name are lowercased and replaced with underscores."""
        store = MagicMock()
        _update_task(store, "t-1", progress={"stage": 1, "stage_name": "Strategic Planner"})
        call_kwargs = store.update_task.call_args.kwargs
        assert call_kwargs["current_step"] == "strategic_planner"

    @pytest.mark.parametrize("stage, expected_pct", [
        (0, 0.0),
        (1, 20.0),
        (2, 40.0),
        (3, 60.0),
        (4, 80.0),
        (5, 100.0),
    ])
    def test_all_stages_produce_correct_pcts(self, stage: int, expected_pct: float):
        """Linear formula stage/5*100 is correct for all 6 stages."""
        store = MagicMock()
        _update_task(store, "t-1", progress={"stage": stage, "stage_name": f"Stage {stage}"})
        call_kwargs = store.update_task.call_args.kwargs
        assert call_kwargs["progress_pct"] == expected_pct


# ═══════════════════════════════════════════════════════════════════════
# H4: Manual mode context enrichment — regression tests
# ═══════════════════════════════════════════════════════════════════════


def _make_manual_input(
    tmp_path: Path,
    analysis_data: dict | None = None,
    manual_prompt: str = "What is equity dilution?",
    manual_cluster: str = "equity",
    skip_stages: list | None = None,
) -> ContentGenerationInputV13:
    """Build a ContentGenerationInputV13 in MANUAL mode with configurable gap analysis data."""
    analysis = analysis_data if analysis_data is not None else {"gaps": [], "cluster_specs": []}
    analysis_path = tmp_path / "analysis.json"
    analysis_path.write_text(json.dumps(analysis))

    context_path = tmp_path / "context.md"
    context_path.write_text("Test company context")

    return ContentGenerationInputV13(
        company_name="Test Co",
        domain="test-co.com",
        company_slug="test-co",
        analysis_json_path=str(analysis_path),
        company_context_path=str(context_path),
        entry_mode=EntryMode.MANUAL,
        auto_approve=True,
        skip_stages=skip_stages if skip_stages is not None else [3, 4, 5],
        manual_prompt=manual_prompt,
        manual_cluster=manual_cluster,
        max_topics=3,
    )


class TestManualModeH4:
    """Regression tests for H4 — manual mode producing zero blueprints.

    Root cause: extract_worker_context("manual-1") always returns {} since
    "manual-1" is synthetic and never present in real gap data.
    Fix: build context inline, enriched from analysis_json via cluster_name match.
    """

    @pytest.mark.asyncio
    async def test_manual_with_analysis_json_produces_blueprint(self, tmp_path):
        """Core H4 regression: blueprint is produced even when analysis_json is present.

        Before fix: extract_worker_context({}, ["manual-1"]) → {} → build_briefs_parallel
        gets empty contexts → returns [] → approved_blueprints = [].
        After fix: contexts["manual-1"] always exists → blueprint produced.
        """
        analysis_data = {
            "gaps": [
                {
                    "query_id": "q-real-1",
                    "cluster_name": "equity",
                    "top_cited_exemplars": [{"url": "https://example.com/equity"}],
                }
            ],
            "cluster_specs": [
                {"cluster_name": "equity", "dominant_content_type": "listicle"},
            ],
        }
        input_data = _make_manual_input(tmp_path, analysis_data=analysis_data)
        mock_build = AsyncMock(return_value=[_make_blueprint()])

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            await run_content_generation_v13(input_data)

        assert mock_build.called, "build_briefs_parallel was never called"
        contexts = mock_build.call_args.kwargs["contexts"]
        assert "manual-1" in contexts, (
            "contexts must contain 'manual-1' — empty contexts dict means H4 bug is present"
        )

    @pytest.mark.asyncio
    async def test_manual_with_analysis_json_enriches_cluster_spec(self, tmp_path):
        """When analysis_json has a matching cluster, cluster_spec is populated."""
        analysis_data = {
            "gaps": [],
            "cluster_specs": [
                {"cluster_name": "equity", "dominant_content_type": "listicle"},
            ],
        }
        input_data = _make_manual_input(tmp_path, analysis_data=analysis_data)
        mock_build = AsyncMock(return_value=[_make_blueprint()])

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            await run_content_generation_v13(input_data)

        contexts = mock_build.call_args.kwargs["contexts"]
        ctx = contexts["manual-1"]
        assert ctx.cluster_spec == {"cluster_name": "equity", "dominant_content_type": "listicle"}

    @pytest.mark.asyncio
    async def test_manual_with_analysis_json_enriches_exemplars(self, tmp_path):
        """When analysis_json has gaps for the cluster, exemplars are extracted."""
        analysis_data = {
            "gaps": [
                {
                    "query_id": "q-1",
                    "cluster_name": "equity",
                    "top_cited_exemplars": [
                        {"url": "https://a.com"},
                        {"url": "https://b.com"},
                    ],
                },
                {
                    "query_id": "q-2",
                    "cluster_name": "equity",
                    "top_cited_exemplars": [{"url": "https://c.com"}],
                },
            ],
            "cluster_specs": [],
        }
        input_data = _make_manual_input(tmp_path, analysis_data=analysis_data)
        mock_build = AsyncMock(return_value=[_make_blueprint()])

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            await run_content_generation_v13(input_data)

        contexts = mock_build.call_args.kwargs["contexts"]
        exemplars = contexts["manual-1"].exemplars
        assert len(exemplars) == 3
        urls = {ex["url"] for ex in exemplars}
        assert urls == {"https://a.com", "https://b.com", "https://c.com"}

    @pytest.mark.asyncio
    async def test_manual_without_analysis_json_uses_empty_spec(self, tmp_path):
        """When analysis_json is empty, cluster_spec={} and exemplars=[] — blueprint still produced."""
        analysis_data: dict = {}  # Falsy — no gap data
        input_data = _make_manual_input(tmp_path, analysis_data=analysis_data)
        mock_build = AsyncMock(return_value=[_make_blueprint()])

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            await run_content_generation_v13(input_data)

        contexts = mock_build.call_args.kwargs["contexts"]
        ctx = contexts["manual-1"]
        assert ctx.cluster_spec == {}
        assert ctx.exemplars == []
        assert ctx.query_gap["query_text"] == "What is equity dilution?"

    @pytest.mark.asyncio
    async def test_manual_no_matching_cluster_uses_empty_spec(self, tmp_path):
        """When cluster name doesn't match, graceful fallback to empty cluster_spec."""
        analysis_data = {
            "gaps": [],
            "cluster_specs": [
                {"cluster_name": "funding", "dominant_content_type": "guide"},
            ],
        }
        # manual_cluster="equity" won't match "funding"
        input_data = _make_manual_input(tmp_path, analysis_data=analysis_data, manual_cluster="equity")
        mock_build = AsyncMock(return_value=[_make_blueprint()])

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            await run_content_generation_v13(input_data)

        contexts = mock_build.call_args.kwargs["contexts"]
        ctx = contexts["manual-1"]
        assert ctx.cluster_spec == {}
        assert ctx.exemplars == []

    @pytest.mark.asyncio
    async def test_manual_exemplars_capped_at_5(self, tmp_path):
        """Exemplars from matching gaps are capped at 5 to keep context manageable."""
        analysis_data = {
            "gaps": [
                {
                    "query_id": f"q-{i}",
                    "cluster_name": "equity",
                    "top_cited_exemplars": [{"url": f"https://ex{i}.com"}],
                }
                for i in range(8)
            ],
            "cluster_specs": [],
        }
        input_data = _make_manual_input(tmp_path, analysis_data=analysis_data)
        mock_build = AsyncMock(return_value=[_make_blueprint()])

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            await run_content_generation_v13(input_data)

        contexts = mock_build.call_args.kwargs["contexts"]
        assert len(contexts["manual-1"].exemplars) == 5


# ═══════════════════════════════════════════════════════════════════════
# Import for direct invocation
# ═══════════════════════════════════════════════════════════════════════

from core.content_engine.pipeline_v13 import run_content_generation_v13, _update_task
