"""Tests for core.content_engine.pipeline_v13 — v1.3 pipeline orchestrator.

Tests the 6-stage async pipeline with mocked agents, workers, and evaluators.
Uses tmp_path for artifact directories.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langgraph.checkpoint.memory import MemorySaver

from core.models.content_generation import (
    ContentGenerationOutput,
    ContentPiece,
    ContentStatus,
    DimensionResult,
    EvalResult,
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


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _use_memory_checkpointer(monkeypatch):
    """Use in-memory checkpointer so tests don't require Redis."""
    monkeypatch.setattr(
        "core.content_engine.graph_v13.get_checkpointer",
        lambda override=None: override if override is not None else MemorySaver(),
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
    "configure_litellm_callbacks": "core.content_engine.pipeline_v13.configure_openrouter",
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
        manual_key = next(k for k in contexts if k.startswith("manual-"))
        assert manual_key is not None
        assert contexts[manual_key].query_gap["query_text"] == "How does equity work?"


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
    async def test_approved_content_uses_edited_markdown_from_review_state(self, tmp_path):
        """HITL-3 approve with edited markdown should promote that edited content to final.md."""
        input_data = _make_input(tmp_path)
        blueprint = _make_blueprint()
        formatted = _make_formatted()
        history = RevisionHistory(brief_id="brief-001", final_passed=True)
        edited_markdown = "# Edited Title\n\nApproved edited body."

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
                       {
                           "content_decision": "approve",
                           "finalized": True,
                           "content_markdown": edited_markdown,
                       },
                   ]):
            result = await run_content_generation_v13(input_data)

        final_path = tmp_path / "artifacts" / "content" / "test-co" / "content" / "brief-001" / "final.md"
        assert final_path.exists()
        assert final_path.read_text() == edited_markdown
        assert result.pieces[0].final_markdown == edited_markdown

    @pytest.mark.asyncio
    async def test_pending_content_review_persists_eval_snapshot_for_sidebar_metrics(self, tmp_path):
        """Review-state DB snapshot should carry eval_history + CPS for sidebar metrics."""
        input_data = _make_input(tmp_path)
        blueprint = _make_blueprint()
        formatted = _make_formatted()
        history = RevisionHistory(
            brief_id="brief-001",
            final_passed=True,
            cycles=[
                EvalResult(
                    brief_id="brief-001",
                    cycle=1,
                    overall_passed=True,
                    overall_score=0.84,
                    dimensions=[
                        DimensionResult(
                            dimension="structural",
                            passed=True,
                            score=0.8,
                            details={
                                "header_count": {"actual": 7, "target": 6},
                                "citation_count": {"actual": 5, "target": 4},
                                "word_count": {"word_count": 2200, "range": [1800, 2400]},
                            },
                        ),
                        DimensionResult(
                            dimension="eeat",
                            passed=True,
                            score=0.86,
                            details={
                                "dimension_scores": {
                                    "experience": 0.8,
                                    "expertise": 0.9,
                                    "authoritativeness": 0.83,
                                    "trustworthiness": 0.91,
                                }
                            },
                        ),
                        DimensionResult(
                            dimension="style",
                            passed=True,
                            score=0.88,
                            details={},
                        ),
                    ],
                )
            ],
        )
        cps_data = {
            "cps_score": 0.63,
            "per_engine": {
                "chatgpt_search": 0.61,
                "perplexity": 0.66,
            },
        }
        persist_pieces = AsyncMock()

        with patch("core.content_engine.pipeline_v13.select_topics",
                   new_callable=AsyncMock, return_value=_make_planner_output()), \
             patch("core.content_engine.pipeline_v13.extract_scorecard", return_value=MagicMock()), \
             patch("core.content_engine.pipeline_v13.extract_worker_context",
                   return_value={"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}), \
             patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]), \
             patch("core.content_engine.pipeline_v13.persist_blueprints_early",
                   new_callable=AsyncMock), \
             patch("core.content_engine.pipeline_v13._merge_and_write_blueprints"), \
             patch("core.content_engine.workers.dispatcher.dispatch_workers_v13",
                   new_callable=AsyncMock, return_value=([(formatted.brief_id, formatted)], [])), \
             patch("core.content_engine.evaluator.loop.evaluate_and_optimize",
                   new_callable=AsyncMock, return_value=(formatted, history, "pass")), \
             patch("core.content_engine.pipeline_v13._score_cps_batch",
                   new_callable=AsyncMock, return_value={"brief-001": cps_data}), \
             patch("core.content_engine.pipeline_v13.persist_content_pieces", persist_pieces), \
             patch("core.content_engine.pipeline_v13.persist_content_run_summary",
                   new_callable=AsyncMock), \
             patch("core.content_engine.pipeline_v13._cleanup_pipeline_state_async",
                   new_callable=AsyncMock), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       {"topic_decision": "approve", "approved_topic_ranks": [0]},
                       {"brief_decision": "approve"},
                       {"content_decision": "approve", "finalized": True},
                   ]):
            await run_content_generation_v13(
                input_data,
                session_factory=MagicMock(),
                run_id=uuid.uuid4(),
                company_id=uuid.uuid4(),
            )

        snapshot_call = next(
            call for call in persist_pieces.await_args_list
            if call.kwargs["pieces"] and call.kwargs["pieces"][0].status == ContentStatus.PENDING
        )
        snapshot_piece = snapshot_call.kwargs["pieces"][0]
        assert snapshot_piece.eval_summary["final_passed"] is True
        assert snapshot_piece.eval_summary["cps"] == cps_data
        assert snapshot_piece.eval_summary["eval_history"][0]["dimensions"][1]["dimension"] == "eeat"

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

    @pytest.mark.asyncio
    async def test_td_rebrief_preserves_brief_id_and_threads_session_factory(self, tmp_path):
        """TD rebriefs must keep the stable brief/display id and forward session_factory."""
        from core.content_engine.pipeline_v13 import _rebrief_and_rerun

        gap_ctx = WorkerQueryContext(
            query_gap={"query_id": "q-equity-001", "query_text": "equity dilution"},
        )
        bp = ContentBlueprint(
            brief_id="WE-003",
            title="Equity Dilution Guide",
            content_format="long_blog",
            cluster_name="equity",
            gap_context=gap_ctx,
        )
        input_data = _make_input(tmp_path, entry_mode=EntryMode.TOPIC_DISCOVERY)
        input_data.topic_assignment_ids = ["ta-1"]
        formatted = _make_formatted(brief_id="WE-003")
        history = RevisionHistory(brief_id="WE-003", final_passed=True)
        session_factory = MagicMock()

        with patch(
            "core.content_engine.pipeline_v13.build_briefs_parallel",
            new_callable=AsyncMock,
            return_value=[bp],
        ) as mock_build, patch(
            "core.content_engine.workers.dispatcher.dispatch_workers_v13",
            new_callable=AsyncMock,
            return_value=[[(formatted.brief_id, formatted)], []],
        ) as mock_dispatch, patch(
            "core.content_engine.evaluator.loop.evaluate_and_optimize",
            new_callable=AsyncMock,
            return_value=(formatted, history, "pass"),
        ) as mock_evaluate:
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
                session_factory=session_factory,
                task_id="task-1",
                slug="test-co",
            )

        assert result is not None
        assert mock_build.call_args.kwargs["brief_id_overrides"] == ["WE-003"]
        assert mock_dispatch.call_args.kwargs["session_factory"] is session_factory
        assert mock_evaluate.call_args.kwargs["session_factory"] is session_factory

    @pytest.mark.asyncio
    async def test_td_worker_failure_writes_explicit_failed_state(self, tmp_path):
        assignment = MagicMock()
        assignment.id = "ta-1"
        assignment.display_id = "WE-003"
        assignment.topic_text = "Equity Dilution Guide"

        worker_context = WorkerQueryContext(
            query_gap={"query_id": "q-equity-001", "query_text": "equity dilution"},
        )
        blueprint = ContentBlueprint(
            brief_id="WE-003",
            title="Equity Dilution Guide",
            content_format="long_blog",
            cluster_name="equity",
        )
        input_data = _make_input(tmp_path, entry_mode=EntryMode.TOPIC_DISCOVERY)
        input_data.topic_assignment_ids = ["ta-1"]

        with patch(
            "core.content_engine.pipeline_v13._ensure_artifact_dir",
            return_value=tmp_path,
        ), patch(
            "core.topic_discovery.db_ops.db_read_assignments_by_ids",
            new_callable=AsyncMock,
            return_value=[assignment],
        ), patch(
            "core.content_engine.context_router.extract_topic_contexts",
            return_value={"q-equity-001": worker_context},
        ), patch(
            "core.content_engine.context_router.topic_assignment_to_selection",
            return_value=TopicSelection(
                rank=0,
                query_ids=["q-equity-001"],
                query_texts=["equity dilution"],
                cluster_name="equity",
                rationale="High gap",
            ),
        ), patch(
            "core.content_engine.pipeline_v13.build_briefs_parallel",
            new_callable=AsyncMock,
            return_value=[blueprint],
        ), patch(
            "core.content_engine.pipeline_v13.persist_blueprints_early",
            new_callable=AsyncMock,
        ), patch(
            "core.content_engine.pipeline_v13._merge_and_write_blueprints",
        ), patch(
            "core.redis.get_sync_redis_or_none",
            return_value=None,
        ), patch(
            "core.content_engine.pipeline_v13.persist_content_pieces",
            new_callable=AsyncMock,
        ), patch(
            "core.content_engine.pipeline_v13.persist_content_run_summary",
            new_callable=AsyncMock,
        ), patch(
            "core.content_engine.pipeline_v13._cleanup_pipeline_state_async",
            new_callable=AsyncMock,
        ), patch(
            "core.content_engine.workers.dispatcher.dispatch_workers_v13",
            new_callable=AsyncMock,
            return_value=([], [{"brief_id": "WE-003", "error": "worker exploded"}]),
        ), patch(
            "core.content_engine.pipeline_v13._write_pipeline_state_async",
            new_callable=AsyncMock,
        ) as mock_write_state:
            result = await run_content_generation_v13(
                input_data,
                task_id="task-1",
                session_factory=MagicMock(),
                run_id=uuid.uuid4(),
                company_id=uuid.uuid4(),
            )

        assert result.total_rejected == 1
        assert any(
            call.args[1] == ["WE-003"] and call.args[2] == "failed"
            for call in mock_write_state.await_args_list
        )


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
    manual_description: str | None = None,
    gap_query_id: str | None = None,
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
        manual_description=manual_description,
        gap_query_id=gap_query_id,
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
        After fix: list(contexts.values())[0] always exists → blueprint produced.
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
        manual_key = next((k for k in contexts if k.startswith("manual-")), None)
        assert manual_key is not None, (
            "contexts must contain a 'manual-*' key — empty contexts dict means H4 bug is present"
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
        ctx = list(contexts.values())[0]
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
        exemplars = list(contexts.values())[0].exemplars
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
        ctx = list(contexts.values())[0]
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
        ctx = list(contexts.values())[0]
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
        assert len(list(contexts.values())[0].exemplars) == 5


# ═══════════════════════════════════════════════════════════════════════
# C3-fix: manual_description injected into TopicSelection.rationale
# ═══════════════════════════════════════════════════════════════════════


class TestManualModeC3Description:
    """C3-fix: manual_description must flow into Brief Builder via topic rationale."""

    @pytest.mark.asyncio
    async def test_manual_description_injected_into_rationale(self, tmp_path):
        """When manual_description is set, it appears in the topic's rationale."""
        input_data = _make_manual_input(
            tmp_path,
            manual_description="Gap query (significant gap). Gap score: 0.8234.",
        )
        mock_build = AsyncMock(return_value=[_make_blueprint()])

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            await run_content_generation_v13(input_data)

        topics = mock_build.call_args.kwargs["topics"]
        assert len(topics) == 1
        assert "Gap score: 0.8234" in topics[0].rationale
        assert "User-specified topic" in topics[0].rationale

    @pytest.mark.asyncio
    async def test_manual_no_description_default_rationale(self, tmp_path):
        """When manual_description is None, rationale defaults to 'User-specified topic'."""
        input_data = _make_manual_input(tmp_path, manual_description=None)
        mock_build = AsyncMock(return_value=[_make_blueprint()])

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            await run_content_generation_v13(input_data)

        topics = mock_build.call_args.kwargs["topics"]
        assert topics[0].rationale == "User-specified topic"


# ═══════════════════════════════════════════════════════════════════════
# H1-fix: 3-tier gap data lookup + H2-fix: case-insensitive cluster match
# ═══════════════════════════════════════════════════════════════════════


class TestManualModeH1GapLookup:
    """H1-fix: query_id → query_text → cluster fallback for full gap context."""

    @pytest.mark.asyncio
    async def test_gap_query_id_lookup_extracts_full_context(self, tmp_path):
        """Tier 1: gap_query_id directly matches a gap entry — all 6 fields populated."""
        analysis_data = {
            "gaps": [{
                "query_id": "q-42",
                "query_text": "What is equity dilution?",
                "cluster_name": "equity",
                "gap": 0.82,
                "interpretation": "significant_gap",
                "top_cited_exemplars": [{"url": "https://ex.com", "similarity": 0.9}],
                "content_brief": {"format": "listicle", "angle": "comparison"},
                "best_company_unit_text": "Carta helps companies manage equity tables and 409A valuations...",
                "best_company_url": "https://carta.com/equity",
                "company_cited": False,
            }],
            "cluster_specs": [{"cluster_name": "equity", "dominant_content_type": "listicle"}],
        }
        input_data = _make_manual_input(tmp_path, analysis_data=analysis_data, gap_query_id="q-42")
        mock_build = AsyncMock(return_value=[_make_blueprint()])

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            await run_content_generation_v13(input_data)

        ctx = list(mock_build.call_args.kwargs["contexts"].values())[0]
        assert ctx.query_gap["gap"] == 0.82
        assert ctx.query_gap["interpretation"] == "significant_gap"
        assert ctx.gap_content_brief == {"format": "listicle", "angle": "comparison"}
        assert ctx.company_best_url == "https://carta.com/equity"
        assert ctx.company_best_text.startswith("Carta helps")
        assert len(ctx.exemplars) == 1
        assert ctx.cluster_spec["dominant_content_type"] == "listicle"

    @pytest.mark.asyncio
    async def test_query_text_fallback_when_no_query_id(self, tmp_path):
        """Tier 2: no gap_query_id, falls back to query_text matching."""
        analysis_data = {
            "gaps": [{
                "query_id": "q-99",
                "query_text": "What is equity dilution?",
                "cluster_name": "equity",
                "gap": 0.75,
                "content_brief": {"format": "guide"},
                "top_cited_exemplars": [],
            }],
            "cluster_specs": [],
        }
        input_data = _make_manual_input(tmp_path, analysis_data=analysis_data)
        # No gap_query_id — should match by query_text
        mock_build = AsyncMock(return_value=[_make_blueprint()])

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            await run_content_generation_v13(input_data)

        ctx = list(mock_build.call_args.kwargs["contexts"].values())[0]
        assert ctx.query_gap["gap"] == 0.75
        assert ctx.gap_content_brief == {"format": "guide"}

    @pytest.mark.asyncio
    async def test_query_text_match_case_insensitive(self, tmp_path):
        """Tier 2: case-insensitive query_text matching."""
        analysis_data = {
            "gaps": [{
                "query_id": "q-1",
                "query_text": "HOW DOES Equity Dilution Work?",
                "cluster_name": "equity",
                "gap": 0.6,
                "content_brief": {"format": "faq"},
                "top_cited_exemplars": [],
            }],
            "cluster_specs": [],
        }
        input_data = _make_manual_input(
            tmp_path,
            analysis_data=analysis_data,
            manual_prompt="how does equity dilution work?",
        )
        mock_build = AsyncMock(return_value=[_make_blueprint()])

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            await run_content_generation_v13(input_data)

        ctx = list(mock_build.call_args.kwargs["contexts"].values())[0]
        assert ctx.query_gap["gap"] == 0.6

    @pytest.mark.asyncio
    async def test_no_match_falls_back_to_cluster(self, tmp_path):
        """Tier 3: neither query_id nor query_text match — cluster fallback used."""
        analysis_data = {
            "gaps": [{
                "query_id": "q-other",
                "query_text": "completely different query",
                "cluster_name": "equity",
                "top_cited_exemplars": [{"url": "https://fallback.com"}],
            }],
            "cluster_specs": [{"cluster_name": "equity", "dominant_content_type": "blog"}],
        }
        input_data = _make_manual_input(tmp_path, analysis_data=analysis_data)
        mock_build = AsyncMock(return_value=[_make_blueprint()])

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            await run_content_generation_v13(input_data)

        ctx = list(mock_build.call_args.kwargs["contexts"].values())[0]
        # Cluster fallback: gap_content_brief is NOT set (only tier 1/2 set it)
        assert ctx.gap_content_brief is None
        # But exemplars are extracted from cluster
        assert len(ctx.exemplars) == 1
        assert ctx.cluster_spec["dominant_content_type"] == "blog"

    @pytest.mark.asyncio
    async def test_gap_query_id_populates_company_best_truncated(self, tmp_path):
        """company_best_text is truncated to 200 chars."""
        long_text = "x" * 300
        analysis_data = {
            "gaps": [{
                "query_id": "q-1",
                "query_text": "What is equity dilution?",
                "cluster_name": "equity",
                "best_company_unit_text": long_text,
                "best_company_url": "https://carta.com/page",
                "top_cited_exemplars": [],
            }],
            "cluster_specs": [],
        }
        input_data = _make_manual_input(tmp_path, analysis_data=analysis_data, gap_query_id="q-1")
        mock_build = AsyncMock(return_value=[_make_blueprint()])

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            await run_content_generation_v13(input_data)

        ctx = list(mock_build.call_args.kwargs["contexts"].values())[0]
        assert len(ctx.company_best_text) == 200
        assert ctx.company_best_url == "https://carta.com/page"


class TestManualModeH2ClusterMatch:
    """H2-fix: case-insensitive cluster matching in the fallback path."""

    @pytest.mark.asyncio
    async def test_cluster_match_case_insensitive(self, tmp_path):
        """'Equity Management' (analysis) matches 'equity management' (user input)."""
        analysis_data = {
            "gaps": [],
            "cluster_specs": [{"cluster_name": "Equity Management", "dominant_content_type": "guide"}],
        }
        input_data = _make_manual_input(
            tmp_path,
            analysis_data=analysis_data,
            manual_prompt="something completely different",
            manual_cluster="equity management",
        )
        mock_build = AsyncMock(return_value=[_make_blueprint()])

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            await run_content_generation_v13(input_data)

        ctx = list(mock_build.call_args.kwargs["contexts"].values())[0]
        assert ctx.cluster_spec["dominant_content_type"] == "guide"

    @pytest.mark.asyncio
    async def test_cluster_match_with_whitespace(self, tmp_path):
        """' equity ' (with whitespace) matches 'equity' in analysis."""
        analysis_data = {
            "gaps": [],
            "cluster_specs": [{"cluster_name": "equity", "dominant_content_type": "listicle"}],
        }
        input_data = _make_manual_input(
            tmp_path,
            analysis_data=analysis_data,
            manual_prompt="some other topic entirely",
            manual_cluster=" equity ",
        )
        mock_build = AsyncMock(return_value=[_make_blueprint()])

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            await run_content_generation_v13(input_data)

        ctx = list(mock_build.call_args.kwargs["contexts"].values())[0]
        assert ctx.cluster_spec["dominant_content_type"] == "listicle"


class TestManualModeH4SSEEvents:
    """H4-fix: manual mode emits Stage 2 progress events."""

    @pytest.mark.asyncio
    async def test_manual_mode_emits_stage_2_started(self, tmp_path):
        """Manual mode should call _emit with stage_started for Stage 2."""
        input_data = _make_manual_input(tmp_path, skip_stages=[3, 4, 5])
        mock_build = AsyncMock(return_value=[_make_blueprint()])
        mock_emit = MagicMock()

        with (
            patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build),
            patch("core.content_engine.pipeline_v13._emit", mock_emit),
        ):
            await run_content_generation_v13(input_data)

        # Find the stage_started call for stage 2
        stage_started_calls = [
            c for c in mock_emit.call_args_list
            if len(c.args) >= 3 and c.args[2] == "stage_started"
            and isinstance(c.args[3], dict) and c.args[3].get("stage") == 2
        ]
        assert len(stage_started_calls) >= 1, (
            f"Expected _emit(..., 'stage_started', {{stage: 2}}) call. "
            f"All calls: {mock_emit.call_args_list}"
        )

    @pytest.mark.asyncio
    async def test_manual_mode_emits_stage_2_complete(self, tmp_path):
        """Manual mode should call _emit with stage_complete for Stage 2."""
        input_data = _make_manual_input(tmp_path, skip_stages=[3, 4, 5])
        mock_build = AsyncMock(return_value=[_make_blueprint()])
        mock_emit = MagicMock()

        with (
            patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build),
            patch("core.content_engine.pipeline_v13._emit", mock_emit),
        ):
            await run_content_generation_v13(input_data)

        stage_complete_calls = [
            c for c in mock_emit.call_args_list
            if len(c.args) >= 3 and c.args[2] == "stage_complete"
            and isinstance(c.args[3], dict) and c.args[3].get("stage") == 2
        ]
        assert len(stage_complete_calls) >= 1
        assert stage_complete_calls[0].args[3]["briefs_approved"] == 1


# ═══════════════════════════════════════════════════════════════════════
# H7-fix: stages_actually_executed tracking
# ═══════════════════════════════════════════════════════════════════════


class TestStagesExecutedH7:
    """H7-fix: stages_executed metadata must reflect actually-executed stages."""

    @pytest.mark.asyncio
    async def test_manual_mode_stages_executed_skips_stage_1(self, tmp_path):
        """Manual mode never executes stage 1 (Strategic Planner) — must not appear."""
        input_data = _make_manual_input(tmp_path, skip_stages=[3, 4, 5])
        mock_build = AsyncMock(return_value=[_make_blueprint()])

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            output = await run_content_generation_v13(input_data)

        stages = output.run_metadata.get("stages_executed", [])
        assert 1 not in stages, f"Stage 1 should not be in stages_executed for manual mode: {stages}"

    @pytest.mark.asyncio
    async def test_manual_mode_stages_executed_includes_stage_0_and_2(self, tmp_path):
        """Manual mode executes stage 0 (Entry Router) and stage 2 (Brief Builder)."""
        input_data = _make_manual_input(tmp_path, skip_stages=[3, 4, 5])
        mock_build = AsyncMock(return_value=[_make_blueprint()])

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            output = await run_content_generation_v13(input_data)

        stages = output.run_metadata.get("stages_executed", [])
        assert 0 in stages
        assert 2 in stages


# ═══════════════════════════════════════════════════════════════════════
# H8-fix: exemplar ranking by similarity + deduplication
# ═══════════════════════════════════════════════════════════════════════


class TestExemplarRankingH8:
    """H8-fix: cluster fallback must rank exemplars by similarity and deduplicate."""

    @pytest.mark.asyncio
    async def test_cluster_fallback_exemplars_ranked_by_similarity(self, tmp_path):
        """Exemplars should be returned in descending similarity order."""
        analysis_data = {
            "gaps": [
                {
                    "query_id": f"q-{i}",
                    "cluster_name": "equity",
                    "top_cited_exemplars": [
                        {"url": f"https://ex{i}.com", "similarity": sim}
                    ],
                }
                for i, sim in enumerate([0.3, 0.9, 0.5, 0.7, 0.1, 0.8])
            ],
            "cluster_specs": [],
        }
        input_data = _make_manual_input(
            tmp_path,
            analysis_data=analysis_data,
            manual_prompt="something totally different from any gap query",
        )
        mock_build = AsyncMock(return_value=[_make_blueprint()])

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            await run_content_generation_v13(input_data)

        ctx = list(mock_build.call_args.kwargs["contexts"].values())[0]
        sims = [ex.get("similarity", 0) for ex in ctx.exemplars]
        assert sims == sorted(sims, reverse=True), f"Exemplars not sorted by similarity: {sims}"
        assert len(ctx.exemplars) == 5  # capped at 5

    @pytest.mark.asyncio
    async def test_cluster_fallback_exemplars_deduplicated(self, tmp_path):
        """Duplicate URLs across gaps should be deduplicated."""
        analysis_data = {
            "gaps": [
                {
                    "query_id": "q-1",
                    "cluster_name": "equity",
                    "top_cited_exemplars": [
                        {"url": "https://shared.com", "similarity": 0.9},
                        {"url": "https://unique1.com", "similarity": 0.8},
                    ],
                },
                {
                    "query_id": "q-2",
                    "cluster_name": "equity",
                    "top_cited_exemplars": [
                        {"url": "https://shared.com", "similarity": 0.7},  # duplicate
                        {"url": "https://unique2.com", "similarity": 0.6},
                    ],
                },
            ],
            "cluster_specs": [],
        }
        input_data = _make_manual_input(
            tmp_path,
            analysis_data=analysis_data,
            manual_prompt="unrelated prompt for cluster fallback",
        )
        mock_build = AsyncMock(return_value=[_make_blueprint()])

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            await run_content_generation_v13(input_data)

        ctx = list(mock_build.call_args.kwargs["contexts"].values())[0]
        urls = [ex["url"] for ex in ctx.exemplars]
        assert len(urls) == len(set(urls)), f"Duplicate URLs found: {urls}"
        assert len(ctx.exemplars) == 3  # shared + unique1 + unique2


# ═══════════════════════════════════════════════════════════════════════
# H9-fix: estimated_impact derived from gap data
# ═══════════════════════════════════════════════════════════════════════


class TestEstimatedImpactH9:
    """H9-fix: estimated_impact derived from gap score, not hardcoded 'high'."""

    @pytest.mark.asyncio
    async def test_high_gap_score_sets_high_impact(self, tmp_path):
        """gap score >= 0.6 → estimated_impact='high'."""
        analysis_data = {
            "gaps": [{
                "query_id": "q-1",
                "query_text": "What is equity dilution?",
                "cluster_name": "equity",
                "gap": 0.82,
                "top_cited_exemplars": [],
            }],
            "cluster_specs": [],
        }
        input_data = _make_manual_input(tmp_path, analysis_data=analysis_data, gap_query_id="q-1")
        mock_build = AsyncMock(return_value=[_make_blueprint()])

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            await run_content_generation_v13(input_data)

        topics = mock_build.call_args.kwargs["topics"]
        assert topics[0].estimated_impact == "high"

    @pytest.mark.asyncio
    async def test_medium_gap_score_sets_medium_impact(self, tmp_path):
        """gap score >= 0.3 and < 0.6 → estimated_impact='medium'."""
        analysis_data = {
            "gaps": [{
                "query_id": "q-1",
                "query_text": "What is equity dilution?",
                "cluster_name": "equity",
                "gap": 0.4,
                "top_cited_exemplars": [],
            }],
            "cluster_specs": [],
        }
        input_data = _make_manual_input(tmp_path, analysis_data=analysis_data, gap_query_id="q-1")
        mock_build = AsyncMock(return_value=[_make_blueprint()])

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            await run_content_generation_v13(input_data)

        topics = mock_build.call_args.kwargs["topics"]
        assert topics[0].estimated_impact == "medium"

    @pytest.mark.asyncio
    async def test_no_gap_data_defaults_to_medium(self, tmp_path):
        """No gap match → estimated_impact defaults to 'medium' (not inflated 'high')."""
        input_data = _make_manual_input(tmp_path)
        # No gap_query_id, prompt won't match any gap
        mock_build = AsyncMock(return_value=[_make_blueprint()])

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            await run_content_generation_v13(input_data)

        topics = mock_build.call_args.kwargs["topics"]
        assert topics[0].estimated_impact == "medium"


# ═══════════════════════════════════════════════════════════════════════
# L1-fix: unique manual query ID per run
# ═══════════════════════════════════════════════════════════════════════


class TestManualQueryIdL1:
    """L1-fix: manual query ID must be unique per run, not hardcoded 'manual-1'."""

    @pytest.mark.asyncio
    async def test_manual_query_id_is_unique_per_run(self, tmp_path):
        """Two manual runs should produce different query IDs."""
        ids: list[str] = []

        for _ in range(2):
            input_data = _make_manual_input(tmp_path, skip_stages=[3, 4, 5])
            mock_build = AsyncMock(return_value=[_make_blueprint()])
            with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
                await run_content_generation_v13(input_data)
            ctx = list(mock_build.call_args.kwargs["contexts"].values())[0]
            ids.append(ctx.query_gap.get("query_id", ""))

        assert ids[0] != ids[1], f"Query IDs should be unique across runs: {ids}"
        assert all(qid.startswith("manual-") for qid in ids)


# ═══════════════════════════════════════════════════════════════════════
# C1-fix: _merge_and_write_blueprints preserves externally-added entries
# ═══════════════════════════════════════════════════════════════════════


class TestMergeAndWriteBlueprints:
    """C1-fix: pipeline writes must not destroy manually-added brief entries."""

    def test_merge_preserves_manual_entries(self, tmp_path):
        """Manually-added briefs (with _source) survive a pipeline write."""
        bp_path = tmp_path / "blueprints.json"
        manual_entry = {
            "brief_id": "brief-099",
            "title": "Manual topic",
            "_source": "citation",
            "_created_at": "2026-03-19T00:00:00Z",
        }
        bp_path.write_text(json.dumps([manual_entry]), encoding="utf-8")

        pipeline_bp = _make_blueprint(brief_id="brief-001")
        _merge_and_write_blueprints(bp_path, [pipeline_bp])

        result = json.loads(bp_path.read_text(encoding="utf-8"))
        assert len(result) == 2
        # Pipeline briefs come first, manual entries preserved at end
        assert result[0]["brief_id"] == "brief-001"
        assert result[1]["brief_id"] == "brief-099"
        assert result[1]["_source"] == "citation"

    def test_merge_preserves_multiple_sources(self, tmp_path):
        """Multiple manual + citation entries are all preserved."""
        bp_path = tmp_path / "blueprints.json"
        existing = [
            {"brief_id": "brief-010", "title": "From citation", "_source": "citation"},
            {"brief_id": "brief-011", "title": "From manual", "_source": "manual"},
        ]
        bp_path.write_text(json.dumps(existing), encoding="utf-8")

        pipeline_bp = _make_blueprint(brief_id="brief-001")
        _merge_and_write_blueprints(bp_path, [pipeline_bp])

        result = json.loads(bp_path.read_text(encoding="utf-8"))
        assert len(result) == 3
        sourced = [e for e in result if e.get("_source")]
        assert len(sourced) == 2

    def test_merge_empty_file(self, tmp_path):
        """When no existing file, writes pipeline briefs cleanly."""
        bp_path = tmp_path / "blueprints.json"
        assert not bp_path.exists()

        pipeline_bp = _make_blueprint(brief_id="brief-001")
        _merge_and_write_blueprints(bp_path, [pipeline_bp])

        result = json.loads(bp_path.read_text(encoding="utf-8"))
        assert len(result) == 1
        assert result[0]["brief_id"] == "brief-001"

    def test_merge_corrupt_file(self, tmp_path):
        """Corrupt JSON is handled gracefully — pipeline briefs still written."""
        bp_path = tmp_path / "blueprints.json"
        bp_path.write_text("not valid json{{{", encoding="utf-8")

        pipeline_bp = _make_blueprint(brief_id="brief-001")
        _merge_and_write_blueprints(bp_path, [pipeline_bp])

        result = json.loads(bp_path.read_text(encoding="utf-8"))
        assert len(result) == 1
        assert result[0]["brief_id"] == "brief-001"


# ═══════════════════════════════════════════════════════════════════════
# C6-fix: zero-blueprint guard for manual/TD modes
# ═══════════════════════════════════════════════════════════════════════


class TestZeroBlueprintGuardC6:
    """C6-fix: manual/TD modes must fail explicitly when zero blueprints produced."""

    @pytest.mark.asyncio
    async def test_manual_zero_blueprints_returns_failed(self, tmp_path):
        """Manual mode with zero blueprints must return error in run_metadata."""
        input_data = _make_manual_input(tmp_path, skip_stages=[3, 4, 5])
        mock_build = AsyncMock(return_value=[])  # Zero blueprints

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build):
            output = await run_content_generation_v13(input_data)

        assert output.total_briefs == 0
        assert "error" in output.run_metadata
        assert "zero blueprints" in output.run_metadata["error"]

    @pytest.mark.asyncio
    async def test_autonomous_zero_blueprints_completes_normally(self, tmp_path):
        """Autonomous mode with zero approved blueprints should NOT error.

        This can happen legitimately when user rejects all briefs at HITL-2.
        """
        analysis_path = tmp_path / "analysis.json"
        analysis_path.write_text(json.dumps({"gaps": [], "cluster_specs": []}))
        context_path = tmp_path / "context.md"
        context_path.write_text("Test company context")

        input_data = ContentGenerationInputV13(
            company_name="Test Co",
            domain="test-co.com",
            company_slug="test-co",
            analysis_json_path=str(analysis_path),
            company_context_path=str(context_path),
            entry_mode=EntryMode.AUTONOMOUS,
            auto_approve=True,
            skip_stages=[1, 2, 3, 4, 5],  # Skip everything — simulates zero approvals
            max_topics=3,
        )

        output = await run_content_generation_v13(input_data)

        # Autonomous mode with zero blueprints completes without error
        assert output.total_briefs == 0
        assert "error" not in output.run_metadata


# ═══════════════════════════════════════════════════════════════════════
# Import for direct invocation
# ═══════════════════════════════════════════════════════════════════════

from core.content_engine.pipeline_v13 import (
    run_content_generation_v13,
    _merge_and_write_blueprints,
    _update_task,
    _write_pipeline_state,
    _cleanup_pipeline_state,
)


# ═══════════════════════════════════════════════════════════════════════
# _write_pipeline_state Tests
# ═══════════════════════════════════════════════════════════════════════


class TestWritePipelineState:
    """Tests for the _write_pipeline_state helper."""

    def test_creates_file(self, tmp_path: Path):
        """Creates pipeline_state.json with brief statuses."""
        _write_pipeline_state(tmp_path, ["brief-001", "brief-002"], "approved")
        state = json.loads((tmp_path / "pipeline_state.json").read_text())
        assert state == {"brief-001": "approved", "brief-002": "approved"}

    def test_merges_with_existing(self, tmp_path: Path):
        """Merges new statuses with existing pipeline_state.json."""
        (tmp_path / "pipeline_state.json").write_text(
            json.dumps({"brief-001": "approved"})
        )
        _write_pipeline_state(tmp_path, ["brief-002"], "in_progress")
        state = json.loads((tmp_path / "pipeline_state.json").read_text())
        assert state == {"brief-001": "approved", "brief-002": "in_progress"}

    def test_overwrites_existing_brief(self, tmp_path: Path):
        """Updates status for a brief that already has an entry."""
        _write_pipeline_state(tmp_path, ["brief-001"], "approved")
        _write_pipeline_state(tmp_path, ["brief-001"], "in_progress")
        state = json.loads((tmp_path / "pipeline_state.json").read_text())
        assert state == {"brief-001": "in_progress"}

    def test_handles_corrupted_file(self, tmp_path: Path):
        """Recovers from corrupted pipeline_state.json."""
        (tmp_path / "pipeline_state.json").write_text("not valid json{{{")
        _write_pipeline_state(tmp_path, ["brief-001"], "review")
        state = json.loads((tmp_path / "pipeline_state.json").read_text())
        assert state == {"brief-001": "review"}

    def test_empty_brief_ids(self, tmp_path: Path):
        """Empty brief_ids list doesn't crash, writes empty or existing dict."""
        _write_pipeline_state(tmp_path, [], "approved")
        state = json.loads((tmp_path / "pipeline_state.json").read_text())
        assert state == {}

    def test_all_kanban_phases(self, tmp_path: Path):
        """All expected phase strings are written correctly."""
        phases = ["approved", "in_progress", "review", "completed"]
        for i, phase in enumerate(phases):
            _write_pipeline_state(tmp_path, [f"brief-{i:03d}"], phase)
        state = json.loads((tmp_path / "pipeline_state.json").read_text())
        assert state == {
            "brief-000": "approved",
            "brief-001": "in_progress",
            "brief-002": "review",
            "brief-003": "completed",
        }

    def test_non_dict_json_array(self, tmp_path: Path):
        """Recovers from valid JSON that is not a dict (e.g. [])."""
        (tmp_path / "pipeline_state.json").write_text("[]")
        _write_pipeline_state(tmp_path, ["brief-001"], "review")
        state = json.loads((tmp_path / "pipeline_state.json").read_text())
        assert state == {"brief-001": "review"}

    def test_non_dict_json_string(self, tmp_path: Path):
        """Recovers from valid JSON that is a string."""
        (tmp_path / "pipeline_state.json").write_text('"hello"')
        _write_pipeline_state(tmp_path, ["brief-001"], "approved")
        state = json.loads((tmp_path / "pipeline_state.json").read_text())
        assert state == {"brief-001": "approved"}


# ═══════════════════════════════════════════════════════════════════════
# _cleanup_pipeline_state Tests
# ═══════════════════════════════════════════════════════════════════════


class TestCleanupPipelineState:
    """Tests for the _cleanup_pipeline_state helper."""

    def test_removes_specified_briefs(self, tmp_path: Path):
        """Removes only the specified brief IDs from state."""
        _write_pipeline_state(tmp_path, ["brief-001", "brief-002", "brief-003"], "in_progress")
        _cleanup_pipeline_state(tmp_path, ["brief-001", "brief-003"])
        state = json.loads((tmp_path / "pipeline_state.json").read_text())
        assert state == {"brief-002": "in_progress"}

    def test_deletes_file_when_empty(self, tmp_path: Path):
        """Deletes file when all entries are removed."""
        _write_pipeline_state(tmp_path, ["brief-001"], "review")
        _cleanup_pipeline_state(tmp_path, ["brief-001"])
        assert not (tmp_path / "pipeline_state.json").exists()

    def test_noop_when_no_file(self, tmp_path: Path):
        """Does nothing when file doesn't exist."""
        _cleanup_pipeline_state(tmp_path, ["brief-001"])
        assert not (tmp_path / "pipeline_state.json").exists()

    def test_handles_unknown_brief_ids(self, tmp_path: Path):
        """Removing nonexistent brief IDs doesn't crash."""
        _write_pipeline_state(tmp_path, ["brief-001"], "in_progress")
        _cleanup_pipeline_state(tmp_path, ["brief-999"])
        state = json.loads((tmp_path / "pipeline_state.json").read_text())
        assert state == {"brief-001": "in_progress"}

    def test_handles_corrupted_file(self, tmp_path: Path):
        """Recovers from corrupted JSON."""
        (tmp_path / "pipeline_state.json").write_text("corrupted{{{")
        _cleanup_pipeline_state(tmp_path, ["brief-001"])
        # Corrupted file with no valid entries → deleted
        assert not (tmp_path / "pipeline_state.json").exists()

    def test_handles_non_dict_json(self, tmp_path: Path):
        """Recovers from valid JSON that is not a dict."""
        (tmp_path / "pipeline_state.json").write_text("[]")
        _cleanup_pipeline_state(tmp_path, ["brief-001"])
        assert not (tmp_path / "pipeline_state.json").exists()

    def test_concurrent_run_preservation(self, tmp_path: Path):
        """Simulates two concurrent runs — one finishing preserves the other's state."""
        # Run A writes brief-001, Run B writes brief-002
        _write_pipeline_state(tmp_path, ["brief-001"], "in_progress")
        _write_pipeline_state(tmp_path, ["brief-002"], "review")
        # Run A finishes, cleans up its brief
        _cleanup_pipeline_state(tmp_path, ["brief-001"])
        state = json.loads((tmp_path / "pipeline_state.json").read_text())
        assert state == {"brief-002": "review"}


# ═══════════════════════════════════════════════════════════════════════
# Manual Mode HITL-2: Brief Approval
# ═══════════════════════════════════════════════════════════════════════


class TestManualHITL2:
    """Manual mode must pause at HITL-2 for brief approval, same as autonomous."""

    @pytest.mark.asyncio
    async def test_manual_hitl2_approve_proceeds_to_workers(self, tmp_path):
        """Manual mode: HITL-2 approve lets the blueprint through to Stage 3."""
        input_data = _make_manual_input(tmp_path)
        # auto_approve=True by default in _make_manual_input, override to test real HITL
        input_data.auto_approve = False
        input_data.skip_stages = []  # run full pipeline

        blueprint = _make_blueprint()
        formatted = _make_formatted()
        history = RevisionHistory(brief_id="brief-001", final_passed=True)

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]) as mock_build, \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       # HITL-2: approve
                       {"brief_decision": "approve"},
                       # HITL-3: approve
                       {"content_decision": "approve", "finalized": True},
                   ]) as mock_hitl, \
             patch("core.content_engine.workers.dispatcher.dispatch_workers_v13",
                   new_callable=AsyncMock, return_value=([(formatted.brief_id, formatted)], [])) as mock_dispatch, \
             patch("core.content_engine.evaluator.loop.evaluate_and_optimize",
                   new_callable=AsyncMock, return_value=(formatted, history, "pass")):
            result = await run_content_generation_v13(input_data)

        # HITL checkpoint called twice: once for HITL-2, once for HITL-3
        assert mock_hitl.call_count == 2
        # HITL-2 call must pass the blueprint and stage_name containing "Brief Approval"
        hitl2_call = mock_hitl.call_args_list[0]
        assert "Brief Approval" in hitl2_call.kwargs.get("stage_name", hitl2_call[1].get("stage_name", ""))
        # Workers must have been called (blueprint approved)
        mock_dispatch.assert_called_once()
        assert result.total_approved == 1

    @pytest.mark.asyncio
    async def test_manual_hitl2_reject_skips_workers(self, tmp_path):
        """Manual mode: HITL-2 reject means zero approved blueprints → no workers run."""
        input_data = _make_manual_input(tmp_path, skip_stages=[])
        input_data.auto_approve = False

        blueprint = _make_blueprint()

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       # HITL-2: reject
                       {"brief_decision": "reject"},
                   ]), \
             patch("core.content_engine.workers.dispatcher.dispatch_workers_v13",
                   new_callable=AsyncMock, return_value=([], [])) as mock_dispatch, \
             patch("core.content_engine.evaluator.loop.evaluate_and_optimize",
                   new_callable=AsyncMock, return_value=None):
            result = await run_content_generation_v13(input_data)

        # Workers never called — blueprint was rejected
        mock_dispatch.assert_not_called()
        assert result.total_approved == 0

    @pytest.mark.asyncio
    async def test_manual_hitl2_feedback_reruns_brief_builder(self, tmp_path):
        """Manual mode: HITL-2 feedback re-invokes build_briefs_parallel with user notes."""
        input_data = _make_manual_input(tmp_path, skip_stages=[])
        input_data.auto_approve = False

        gap_ctx = WorkerQueryContext(
            query_gap={"query_id": "manual-abc", "query_text": "What is equity dilution?"},
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

        mock_build = AsyncMock(side_effect=[
            [blueprint],           # Initial Agent 2 call
            [revised_blueprint],   # Re-run after HITL-2 feedback
        ])

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel", mock_build), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=[
                       # HITL-2 first: feedback
                       {"brief_decision": "feedback", "brief_feedback": "Focus more on anti-dilution protections"},
                       # HITL-2 second (after re-run): approve
                       {"brief_decision": "approve"},
                       # HITL-3: approve
                       {"content_decision": "approve", "finalized": True},
                   ]), \
             patch("core.content_engine.workers.dispatcher.dispatch_workers_v13",
                   new_callable=AsyncMock, return_value=([(formatted.brief_id, formatted)], [])), \
             patch("core.content_engine.evaluator.loop.evaluate_and_optimize",
                   new_callable=AsyncMock, return_value=(formatted, history, "pass")):
            result = await run_content_generation_v13(input_data)

        # build_briefs_parallel called twice: initial + feedback re-run
        assert mock_build.call_count == 2
        # Second call must include feedback in topic rationale
        second_call_kwargs = mock_build.call_args_list[1][1]
        topics = second_call_kwargs["topics"]
        assert "Focus more on anti-dilution protections" in topics[0].rationale
        assert result.total_approved == 1

    @pytest.mark.asyncio
    async def test_manual_hitl2_auto_approve_skips_pause(self, tmp_path):
        """Manual mode with auto_approve=True: HITL-2 graph auto-approves (no block)."""
        input_data = _make_manual_input(tmp_path, skip_stages=[3, 4, 5])
        input_data.auto_approve = True

        blueprint = _make_blueprint()

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock,
                   return_value={"brief_decision": "approve"}) as mock_hitl:
            result = await run_content_generation_v13(input_data)

        # HITL checkpoint called once for HITL-2 (stages 3-5 skipped)
        assert mock_hitl.call_count == 1
        hitl2_call = mock_hitl.call_args_list[0]
        # auto_approve must be passed through to the graph
        initial_state = hitl2_call.kwargs.get("initial_state", hitl2_call[1].get("initial_state", {}))
        assert initial_state.get("auto_approve") is True

    @pytest.mark.asyncio
    async def test_manual_hitl2_writes_pipeline_state(self, tmp_path):
        """After HITL-2 approve, _write_pipeline_state_async is called with 'approved'."""
        input_data = _make_manual_input(tmp_path, skip_stages=[3, 4, 5])
        input_data.auto_approve = False

        blueprint = _make_blueprint()

        # Track calls via a wrapping mock
        write_calls: list = []

        async def _tracking_write(artifact_dir, brief_ids, phase, **kwargs):
            write_calls.append((list(brief_ids), phase))

        with patch("core.content_engine.pipeline_v13.build_briefs_parallel",
                   new_callable=AsyncMock, return_value=[blueprint]), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock,
                   return_value={"brief_decision": "approve"}), \
             patch("core.content_engine.pipeline_v13._write_pipeline_state_async",
                   side_effect=_tracking_write):
            await run_content_generation_v13(input_data)

        # Verify "approved" was written for brief-001 at some point
        approved_calls = [(bids, phase) for bids, phase in write_calls
                          if "brief-001" in bids and phase == "approved"]
        assert len(approved_calls) >= 1, f"Expected 'approved' write for brief-001, got: {write_calls}"
