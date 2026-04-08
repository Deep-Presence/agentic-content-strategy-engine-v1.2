"""Exhaustive tests for TOPIC_DISCOVERY mode HITL-2 brief approval.

Tests the TD-specific HITL-2 path in ``_run_pipeline_stages`` (pipeline_v13.py):
  - Early DB persist (persist_blueprints_early) before HITL-2
  - GA-phase card cleanup before HITL-2
  - Approve / reject / feedback decision flows
  - Feedback loop with build_briefs_parallel re-invocation
  - Pipeline state writes (brief_review → pending_brief_approval → approved)
  - Company SSE event emissions
  - Decision audit trail via persist_v13_brief_approval
  - Multiple-blueprint handling (independent per-brief decisions)
  - Auto-approve bypass
  - Edge cases: no gap_context, empty feedback, max retries exceeded
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from core.content_engine.pipeline_v13 import run_content_generation_v13
from core.models.content_generation_v13 import (
    ContentBlueprint,
    ContentGenerationInputV13,
    EntryMode,
    TopicSelection,
    WorkerQueryContext,
)
from core.models.content_generation import FormattedContent
from core.models.topic_discovery import TopicAssignment, BuyerStage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_session_factory():
    """Build a session_factory mock that works with ``async with session_factory() as sess:``."""
    mock_session = AsyncMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=mock_ctx)
    factory._mock_session = mock_session  # expose for assertions
    return factory


_ASSIGNMENT_ID_1 = "ta-aaaa-1111"
_ASSIGNMENT_ID_2 = "ta-bbbb-2222"
_GA_RUN_ID = "ga-run-001"
_QUERY_ID_1 = "q-001"
_QUERY_ID_2 = "q-002"


def _make_td_input(
    tmp_path: Path,
    *,
    auto_approve: bool = False,
    skip_stages: list | None = None,
    assignment_ids: list[str] | None = None,
) -> ContentGenerationInputV13:
    """Build a ContentGenerationInputV13 in TOPIC_DISCOVERY mode."""
    analysis_path = tmp_path / "analysis.json"
    analysis_path.write_text(json.dumps({"gaps": [], "cluster_specs": []}))

    context_path = tmp_path / "context.md"
    context_path.write_text("Test company context")

    return ContentGenerationInputV13(
        company_name="Test Co",
        domain="test-co.com",
        company_slug="test-co",
        analysis_json_path=str(analysis_path),
        company_context_path=str(context_path),
        entry_mode=EntryMode.TOPIC_DISCOVERY,
        auto_approve=auto_approve,
        skip_stages=skip_stages if skip_stages is not None else [],
        topic_assignment_ids=assignment_ids or [_ASSIGNMENT_ID_1],
        td_ga_run_id=_GA_RUN_ID,
        max_topics=3,
    )


def _make_assignment(
    assignment_id: str = _ASSIGNMENT_ID_1,
    topic_text: str = "GSAP Animation Patterns",
) -> TopicAssignment:
    """Build a minimal TopicAssignment for DB read mock."""
    return TopicAssignment(
        id=assignment_id,
        topic_text=topic_text,
        buyer_stage=BuyerStage.TOFU,
        priority_score=0.85,
        subdomain_name="animations",
    )


def _make_gap_context(query_id: str = _QUERY_ID_1) -> WorkerQueryContext:
    return WorkerQueryContext(
        query_gap={"query_id": query_id, "query_text": "How to use GSAP animations?"},
        exemplars=[{"url": "https://example.com/gsap"}],
    )


def _make_blueprint(
    brief_id: str = "brief-001",
    title: str = "GSAP Animation Guide",
    *,
    gap_context: WorkerQueryContext | None = None,
    target_cluster: str = "animations",
) -> ContentBlueprint:
    return ContentBlueprint(
        brief_id=brief_id,
        title=title,
        content_format="long_blog",
        cluster_name=target_cluster,
        target_cluster=target_cluster,
        gap_context=gap_context or _make_gap_context(),
        sections=[],
    )


def _make_formatted(brief_id: str = "brief-001", title: str = "GSAP Animation Guide") -> FormattedContent:
    return FormattedContent(
        brief_id=brief_id,
        title=title,
        markdown="# GSAP Animation Guide\n\nContent here.",
        word_count=200,
    )


def _make_td_analysis_json(
    assignment_id: str = _ASSIGNMENT_ID_1,
    query_id: str = _QUERY_ID_1,
) -> dict:
    """Build a minimal scoped analysis.json for TD mode."""
    return {
        "topic_query_map": {assignment_id: [query_id]},
        "gaps": [{"query_id": query_id, "query_text": "How to use GSAP animations?"}],
        "cluster_specs": [{"cluster_name": "animations"}],
    }


# ---------------------------------------------------------------------------
# Shared patches — every TD HITL-2 test needs these mocks
# ---------------------------------------------------------------------------

def _td_base_patches(
    tmp_path: Path,
    *,
    assignments: list[TopicAssignment] | None = None,
    analysis_json: dict | None = None,
    worker_contexts: dict | None = None,
    blueprints: list[ContentBlueprint] | None = None,
    build_side_effect: list | None = None,
    hitl_side_effect: list | None = None,
    hitl_return: dict | None = None,
    run_workers: bool = False,
):
    """Return a dict of patch context managers for TD mode tests.

    All patches target ``core.content_engine.pipeline_v13.*``.
    """
    _assignments = assignments if assignments is not None else [_make_assignment()]
    _analysis = analysis_json if analysis_json is not None else _make_td_analysis_json()
    _ctx = worker_contexts if worker_contexts is not None else {_QUERY_ID_1: _make_gap_context()}
    _bps = blueprints if blueprints is not None else [_make_blueprint()]

    if build_side_effect:
        mock_build = AsyncMock(side_effect=build_side_effect)
    else:
        mock_build = AsyncMock(return_value=_bps)

    if hitl_side_effect:
        mock_hitl = AsyncMock(side_effect=hitl_side_effect)
    elif hitl_return:
        mock_hitl = AsyncMock(return_value=hitl_return)
    else:
        mock_hitl = AsyncMock(return_value={"brief_decision": "approve"})

    formatted = _make_formatted()
    from core.models.content_generation import RevisionHistory
    history = RevisionHistory(brief_id="brief-001", final_passed=True)

    patches = {
        # DB: read topic assignments (lazy import from core.topic_discovery.db_ops)
        "db_read": patch(
            "core.topic_discovery.db_ops.db_read_assignments_by_ids",
            new_callable=AsyncMock, return_value=_assignments,
        ),
        # Context router (lazy import from core.content_engine.context_router)
        "extract_ctx": patch(
            "core.content_engine.context_router.extract_topic_contexts",
            return_value=_ctx,
        ),
        "ta_to_sel": patch(
            "core.content_engine.context_router.topic_assignment_to_selection",
            side_effect=lambda a, qids, qtexts, rank=0: TopicSelection(
                rank=rank,
                query_ids=qids,
                query_texts=qtexts,
                cluster_name=a.subdomain_name,
                rationale=f"Topic: {a.topic_text}",
            ),
        ),
        # Brief builder
        "build_briefs": patch(
            "core.content_engine.pipeline_v13.build_briefs_parallel",
            mock_build,
        ),
        # HITL graph
        "build_graph": patch(
            "core.content_engine.pipeline_v13.build_brief_approval_graph",
            return_value=MagicMock(),
        ),
        "hitl": patch(
            "core.content_engine.pipeline_v13.run_hitl_checkpoint",
            mock_hitl,
        ),
        # Early persist (TD-fix)
        "persist_early": patch(
            "core.content_engine.pipeline_v13.persist_blueprints_early",
            new_callable=AsyncMock,
        ),
        # Audit trail persist
        "persist_approval": patch(
            "core.content_engine.pipeline_v13.persist_v13_brief_approval",
            new_callable=AsyncMock,
        ),
        # GA-phase cleanup (lazy imports inside try block)
        "get_sync_redis": patch(
            "core.redis.get_sync_redis_or_none",
            return_value=MagicMock(),
        ),
        "cleanup_ga": patch(
            "core.content_engine.state_redis.cleanup_ga_phase_state",
        ),
        # Company SSE
        "emit_company": patch(
            "core.content_engine.pipeline_v13._emit_company",
        ),
        # Pipeline state writes
        "write_state": patch(
            "core.content_engine.pipeline_v13._write_pipeline_state_async",
            new_callable=AsyncMock,
        ),
        # Scoped analysis load — write file so the TD code can read it
        "analysis_file": None,  # handled via fixture
    }

    if run_workers:
        patches["dispatch"] = patch(
            "core.content_engine.workers.dispatcher.dispatch_workers_v13",
            new_callable=AsyncMock,
            return_value=([(formatted.brief_id, formatted)], []),
        )
        patches["evaluate"] = patch(
            "core.content_engine.evaluator.loop.evaluate_and_optimize",
            new_callable=AsyncMock,
            return_value=(formatted, history, "pass"),
        )
    else:
        # Skip stages 3-5 to isolate HITL-2 testing
        pass

    return patches


def _write_scoped_analysis(tmp_path: Path, slug: str = "test-co", ga_run_id: str = _GA_RUN_ID, data: dict | None = None):
    """Write the topic-scoped analysis.json that TD mode reads."""
    analysis_dir = tmp_path / "artifacts" / "gap_analysis" / slug / "topic_scoped" / ga_run_id
    analysis_dir.mkdir(parents=True, exist_ok=True)
    analysis_file = analysis_dir / "analysis.json"
    analysis_file.write_text(json.dumps(data or _make_td_analysis_json()))


@pytest.fixture(autouse=True)
def _mock_infra(monkeypatch):
    """Disable Redis cache, tracing, and storage for all tests in this module."""
    # Disable Redis globally (lazy imports use core.redis directly)
    monkeypatch.setattr(
        "core.redis.get_sync_redis_or_none",
        lambda: None,
    )
    monkeypatch.setattr(
        "core.content_engine.pipeline_v13.configure_openrouter",
        lambda: None,
    )
    # Stub tracing
    monkeypatch.setattr(
        "core.content_engine.pipeline_v13.create_pipeline_trace",
        lambda **kw: MagicMock(),
    )
    monkeypatch.setattr(
        "core.content_engine.pipeline_v13.update_trace_output",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        "core.content_engine.pipeline_v13.set_current_span",
        lambda *a: None,
    )
    monkeypatch.setattr(
        "core.content_engine.pipeline_v13.flush",
        lambda: None,
    )
    # Stub persistence helpers that aren't under test
    monkeypatch.setattr(
        "core.content_engine.pipeline_v13.persist_content_pieces",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "core.content_engine.pipeline_v13.persist_content_run_summary",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "core.content_engine.pipeline_v13.persist_v13_planner_output",
        AsyncMock(),
    )


# ===========================================================================
# Test class: TD HITL-2 Core Flows
# ===========================================================================


class TestTDHitl2Approve:
    """TD mode HITL-2: approve path."""

    @pytest.mark.asyncio
    async def test_approve_single_blueprint(self, tmp_path):
        """Single blueprint approved → appears in approved_blueprints, workers proceed."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, skip_stages=[3, 4, 5])

        bp = _make_blueprint()
        patches = _td_base_patches(tmp_path, hitl_return={"brief_decision": "approve"})

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"], patches["build_graph"], patches["hitl"] as mock_hitl, \
             patches["persist_early"], patches["persist_approval"] as mock_persist, \
             patches["get_sync_redis"], patches["cleanup_ga"], \
             patches["emit_company"], patches["write_state"]:
            result = await run_content_generation_v13(
                inp, session_factory=_mock_session_factory(), run_id=uuid.uuid4(), company_id=uuid.uuid4(),
            )

        mock_hitl.assert_called_once()
        assert result.total_briefs >= 1
        # Audit trail must record the approval
        mock_persist.assert_called_once()
        decisions = mock_persist.call_args.kwargs["approval_decisions"]
        assert len(decisions) == 1
        assert decisions[0]["decision"] == "approve"

    @pytest.mark.asyncio
    async def test_approve_with_feedback_text(self, tmp_path):
        """Approve with feedback text → user_feedback set on blueprint."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, skip_stages=[3, 4, 5])

        patches = _td_base_patches(
            tmp_path,
            hitl_return={"brief_decision": "approve", "brief_feedback": "Add more examples"},
        )

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"], patches["build_graph"], patches["hitl"], \
             patches["persist_early"], patches["persist_approval"] as mock_persist, \
             patches["get_sync_redis"], patches["cleanup_ga"], \
             patches["emit_company"], patches["write_state"]:
            result = await run_content_generation_v13(
                inp, session_factory=_mock_session_factory(), run_id=uuid.uuid4(), company_id=uuid.uuid4(),
            )

        assert result.total_briefs >= 1
        decisions = mock_persist.call_args.kwargs["approval_decisions"]
        assert decisions[0]["feedback"] == "Add more examples"


class TestTDHitl2Reject:
    """TD mode HITL-2: reject path."""

    @pytest.mark.asyncio
    async def test_reject_single_blueprint(self, tmp_path):
        """Single blueprint rejected → zero approved, pipeline fails gracefully."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, skip_stages=[3, 4, 5])

        patches = _td_base_patches(
            tmp_path,
            hitl_return={"brief_decision": "reject", "brief_feedback": "Not relevant"},
        )

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"], patches["build_graph"], patches["hitl"], \
             patches["persist_early"], patches["persist_approval"] as mock_persist, \
             patches["get_sync_redis"], patches["cleanup_ga"], \
             patches["emit_company"], patches["write_state"]:
            result = await run_content_generation_v13(
                inp, session_factory=_mock_session_factory(), run_id=uuid.uuid4(), company_id=uuid.uuid4(),
            )

        assert result.total_briefs == 0
        decisions = mock_persist.call_args.kwargs["approval_decisions"]
        assert decisions[0]["decision"] == "reject"

    @pytest.mark.asyncio
    async def test_reject_with_no_feedback(self, tmp_path):
        """Reject without feedback text → still records empty feedback."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, skip_stages=[3, 4, 5])

        patches = _td_base_patches(
            tmp_path,
            hitl_return={"brief_decision": "reject"},
        )

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"], patches["build_graph"], patches["hitl"], \
             patches["persist_early"], patches["persist_approval"] as mock_persist, \
             patches["get_sync_redis"], patches["cleanup_ga"], \
             patches["emit_company"], patches["write_state"]:
            result = await run_content_generation_v13(
                inp, session_factory=_mock_session_factory(), run_id=uuid.uuid4(), company_id=uuid.uuid4(),
            )

        assert result.total_briefs == 0
        decisions = mock_persist.call_args.kwargs["approval_decisions"]
        assert decisions[0]["feedback"] == ""


class TestTDHitl2Feedback:
    """TD mode HITL-2: feedback loop (re-brief)."""

    @pytest.mark.asyncio
    async def test_feedback_reruns_brief_builder(self, tmp_path):
        """Feedback → re-invokes build_briefs_parallel with user feedback in rationale."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, skip_stages=[3, 4, 5])

        gap_ctx = _make_gap_context()
        original = _make_blueprint(gap_context=gap_ctx)
        revised = _make_blueprint(title="GSAP Animation Guide (Revised)", gap_context=gap_ctx)

        patches = _td_base_patches(
            tmp_path,
            build_side_effect=[[original], [revised]],
            hitl_side_effect=[
                {"brief_decision": "feedback", "brief_feedback": "Focus on ScrollTrigger"},
                {"brief_decision": "approve"},
            ],
        )

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"] as mock_build, patches["build_graph"], patches["hitl"], \
             patches["persist_early"], patches["persist_approval"] as mock_persist, \
             patches["get_sync_redis"], patches["cleanup_ga"], \
             patches["emit_company"], patches["write_state"]:
            result = await run_content_generation_v13(
                inp, session_factory=_mock_session_factory(), run_id=uuid.uuid4(), company_id=uuid.uuid4(),
            )

        # build_briefs_parallel called twice: initial + feedback re-run
        assert mock_build.call_count == 2
        # Second call must embed feedback in TopicSelection.rationale
        second_call = mock_build.call_args_list[1]
        topics = second_call.kwargs.get("topics", second_call[1].get("topics", []))
        assert len(topics) == 1
        assert "Focus on ScrollTrigger" in topics[0].rationale
        assert result.total_briefs >= 1
        # Audit trail shows feedback attempt count
        decisions = mock_persist.call_args.kwargs["approval_decisions"]
        assert decisions[0]["feedback_attempts"] == 1

    @pytest.mark.asyncio
    async def test_feedback_then_reject(self, tmp_path):
        """Feedback once → reject on second pass → zero approved."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, skip_stages=[3, 4, 5])

        gap_ctx = _make_gap_context()
        original = _make_blueprint(gap_context=gap_ctx)
        revised = _make_blueprint(title="Revised", gap_context=gap_ctx)

        patches = _td_base_patches(
            tmp_path,
            build_side_effect=[[original], [revised]],
            hitl_side_effect=[
                {"brief_decision": "feedback", "brief_feedback": "Try again"},
                {"brief_decision": "reject"},
            ],
        )

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"], patches["build_graph"], patches["hitl"], \
             patches["persist_early"], patches["persist_approval"] as mock_persist, \
             patches["get_sync_redis"], patches["cleanup_ga"], \
             patches["emit_company"], patches["write_state"]:
            result = await run_content_generation_v13(
                inp, session_factory=_mock_session_factory(), run_id=uuid.uuid4(), company_id=uuid.uuid4(),
            )

        assert result.total_briefs == 0

    @pytest.mark.asyncio
    async def test_feedback_max_retries_exceeded(self, tmp_path):
        """Second feedback after max retries (1) → treated as reject."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, skip_stages=[3, 4, 5])

        gap_ctx = _make_gap_context()
        original = _make_blueprint(gap_context=gap_ctx)
        revised = _make_blueprint(title="Revised", gap_context=gap_ctx)

        patches = _td_base_patches(
            tmp_path,
            build_side_effect=[[original], [revised]],
            hitl_side_effect=[
                # First feedback → allowed (count goes to 1, which equals _MAX_BRIEF_FEEDBACK_RETRIES)
                {"brief_decision": "feedback", "brief_feedback": "Try v1"},
                # Second feedback → exceeds max (1), falls to else branch → treated as reject
                {"brief_decision": "feedback", "brief_feedback": "Try v2"},
            ],
        )

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"], patches["build_graph"], patches["hitl"], \
             patches["persist_early"], patches["persist_approval"] as mock_persist, \
             patches["get_sync_redis"], patches["cleanup_ga"], \
             patches["emit_company"], patches["write_state"]:
            result = await run_content_generation_v13(
                inp, session_factory=_mock_session_factory(), run_id=uuid.uuid4(), company_id=uuid.uuid4(),
            )

        assert result.total_briefs == 0
        decisions = mock_persist.call_args.kwargs["approval_decisions"]
        assert decisions[0]["decision"] == "reject"
        assert decisions[0]["feedback_attempts"] == 1

    @pytest.mark.asyncio
    async def test_feedback_without_gap_context_skips_rebrief(self, tmp_path):
        """Blueprint without gap_context: feedback doesn't re-run brief builder."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, skip_stages=[3, 4, 5])

        # Blueprint with NO gap_context
        bp_no_ctx = ContentBlueprint(
            brief_id="brief-001",
            title="Test",
            content_format="long_blog",
            gap_context=None,
        )

        patches = _td_base_patches(
            tmp_path,
            blueprints=[bp_no_ctx],
            hitl_side_effect=[
                {"brief_decision": "feedback", "brief_feedback": "Please revise"},
                {"brief_decision": "approve"},
            ],
        )

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"] as mock_build, patches["build_graph"], patches["hitl"], \
             patches["persist_early"], patches["persist_approval"], \
             patches["get_sync_redis"], patches["cleanup_ga"], \
             patches["emit_company"], patches["write_state"]:
            result = await run_content_generation_v13(
                inp, session_factory=_mock_session_factory(), run_id=uuid.uuid4(), company_id=uuid.uuid4(),
            )

        # build_briefs_parallel called once (initial), NOT re-invoked for feedback
        assert mock_build.call_count == 1
        assert result.total_briefs >= 1


class TestTDHitl2AutoApprove:
    """TD mode with auto_approve=True: HITL-2 should be completely bypassed."""

    @pytest.mark.asyncio
    async def test_auto_approve_skips_hitl2(self, tmp_path):
        """auto_approve=True → no HITL checkpoint, all blueprints approved."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, auto_approve=True, skip_stages=[3, 4, 5])

        patches = _td_base_patches(tmp_path)

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"], patches["build_graph"], patches["hitl"] as mock_hitl, \
             patches["persist_early"], patches["persist_approval"] as mock_persist, \
             patches["get_sync_redis"], patches["cleanup_ga"], \
             patches["emit_company"], patches["write_state"]:
            result = await run_content_generation_v13(
                inp, session_factory=_mock_session_factory(), run_id=uuid.uuid4(), company_id=uuid.uuid4(),
            )

        # HITL checkpoint never called
        mock_hitl.assert_not_called()
        # persist_v13_brief_approval never called (no decision log needed)
        mock_persist.assert_not_called()
        assert result.total_briefs >= 1


# ===========================================================================
# Test class: TD-fix — Early DB Persist + GA-phase Cleanup
# ===========================================================================


class TestTDEarlyPersistAndCleanup:
    """Verifies persist_blueprints_early and cleanup_ga_phase_state
    are called correctly BEFORE HITL-2."""

    @pytest.mark.asyncio
    async def test_persist_early_called_with_correct_args(self, tmp_path):
        """persist_blueprints_early called with session_factory, run_id, company_id, slug, blueprints."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, skip_stages=[3, 4, 5])
        _run_id = uuid.uuid4()
        _company_id = uuid.uuid4()
        _session_factory = AsyncMock()

        patches = _td_base_patches(tmp_path, hitl_return={"brief_decision": "approve"})

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"], patches["build_graph"], patches["hitl"], \
             patches["persist_early"] as mock_early, patches["persist_approval"], \
             patches["get_sync_redis"], patches["cleanup_ga"], \
             patches["emit_company"], patches["write_state"]:
            await run_content_generation_v13(
                inp, session_factory=_session_factory, run_id=_run_id, company_id=_company_id,
            )

        mock_early.assert_called_once()
        kw = mock_early.call_args.kwargs
        assert kw["session_factory"] is _session_factory
        assert kw["run_id"] == _run_id
        assert kw["company_id"] == _company_id
        assert kw["slug"] == "test-co"
        assert len(kw["blueprints"]) == 1

    @pytest.mark.asyncio
    async def test_cleanup_ga_phase_called(self, tmp_path):
        """cleanup_ga_phase_state called with Redis client, slug, and assignment IDs."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, skip_stages=[3, 4, 5])

        patches = _td_base_patches(tmp_path, hitl_return={"brief_decision": "approve"})

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"], patches["build_graph"], patches["hitl"], \
             patches["persist_early"], patches["persist_approval"], \
             patches["get_sync_redis"] as mock_redis, patches["cleanup_ga"] as mock_cleanup, \
             patches["emit_company"], patches["write_state"]:
            await run_content_generation_v13(
                inp, session_factory=_mock_session_factory(), run_id=uuid.uuid4(), company_id=uuid.uuid4(),
            )

        mock_cleanup.assert_called_once()
        args = mock_cleanup.call_args
        assert args[0][1] == "test-co"  # slug
        assert args[0][2] == [_ASSIGNMENT_ID_1]  # assignment_ids

    @pytest.mark.asyncio
    async def test_persist_early_before_hitl(self, tmp_path):
        """persist_blueprints_early is called BEFORE run_hitl_checkpoint."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, skip_stages=[3, 4, 5])

        call_order: list[str] = []

        async def track_persist(*a, **kw):
            call_order.append("persist_early")

        async def track_hitl(*a, **kw):
            call_order.append("hitl")
            return {"brief_decision": "approve"}

        patches = _td_base_patches(tmp_path)

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"], patches["build_graph"], \
             patch("core.content_engine.pipeline_v13.persist_blueprints_early",
                   new_callable=AsyncMock, side_effect=track_persist), \
             patch("core.content_engine.pipeline_v13.run_hitl_checkpoint",
                   new_callable=AsyncMock, side_effect=track_hitl), \
             patches["persist_approval"], patches["get_sync_redis"], patches["cleanup_ga"], \
             patches["emit_company"], patches["write_state"]:
            await run_content_generation_v13(
                inp, session_factory=_mock_session_factory(), run_id=uuid.uuid4(), company_id=uuid.uuid4(),
            )

        assert call_order.index("persist_early") < call_order.index("hitl")

    @pytest.mark.asyncio
    async def test_auto_approve_still_persists_early(self, tmp_path):
        """Even with auto_approve=True, blueprints are persisted early and GA cleaned up."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, auto_approve=True, skip_stages=[3, 4, 5])

        patches = _td_base_patches(tmp_path)

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"], patches["build_graph"], patches["hitl"], \
             patches["persist_early"] as mock_early, patches["persist_approval"], \
             patches["get_sync_redis"], patches["cleanup_ga"] as mock_cleanup, \
             patches["emit_company"], patches["write_state"]:
            await run_content_generation_v13(
                inp, session_factory=_mock_session_factory(), run_id=uuid.uuid4(), company_id=uuid.uuid4(),
            )

        mock_early.assert_called_once()
        mock_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_ga_failure_does_not_crash(self, tmp_path):
        """If cleanup_ga_phase_state raises, pipeline continues (best-effort)."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, skip_stages=[3, 4, 5])

        patches = _td_base_patches(tmp_path, hitl_return={"brief_decision": "approve"})

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"], patches["build_graph"], patches["hitl"], \
             patches["persist_early"], patches["persist_approval"], \
             patches["get_sync_redis"], \
             patch("core.content_engine.state_redis.cleanup_ga_phase_state",
                   side_effect=RuntimeError("Redis down")), \
             patches["emit_company"], patches["write_state"]:
            # Should not raise
            result = await run_content_generation_v13(
                inp, session_factory=_mock_session_factory(), run_id=uuid.uuid4(), company_id=uuid.uuid4(),
            )

        assert result.total_briefs >= 1


# ===========================================================================
# Test class: Pipeline State Writes
# ===========================================================================


class TestTDHitl2PipelineState:
    """Verifies pipeline state transitions: brief_review → pending_brief_approval → approved."""

    @pytest.mark.asyncio
    async def test_state_sequence_on_approve(self, tmp_path):
        """Pipeline state writes follow: brief_review → pending_brief_approval → approved."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, skip_stages=[3, 4, 5])

        patches = _td_base_patches(tmp_path, hitl_return={"brief_decision": "approve"})

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"], patches["build_graph"], patches["hitl"], \
             patches["persist_early"], patches["persist_approval"], \
             patches["get_sync_redis"], patches["cleanup_ga"], \
             patches["emit_company"], patches["write_state"] as mock_state:
            await run_content_generation_v13(
                inp, session_factory=_mock_session_factory(), run_id=uuid.uuid4(), company_id=uuid.uuid4(),
            )

        # Extract the phase argument from each _write_pipeline_state_async call
        phases = [c.args[2] for c in mock_state.call_args_list if len(c.args) >= 3]
        assert "brief_review" in phases
        assert "pending_brief_approval" in phases
        assert "approved" in phases
        # Order matters
        assert phases.index("brief_review") < phases.index("pending_brief_approval")
        assert phases.index("pending_brief_approval") < phases.index("approved")


# ===========================================================================
# Test class: Company SSE Events
# ===========================================================================


class TestTDHitl2CompanyEvents:
    """Verifies company-wide SSE events emitted during HITL-2."""

    @pytest.mark.asyncio
    async def test_emits_hitl_review_needed_notification(self, tmp_path):
        """pending_brief_approval emits hitl_review_needed notification."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, skip_stages=[3, 4, 5])

        patches = _td_base_patches(tmp_path, hitl_return={"brief_decision": "approve"})

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"], patches["build_graph"], patches["hitl"], \
             patches["persist_early"], patches["persist_approval"], \
             patches["get_sync_redis"], patches["cleanup_ga"], \
             patches["emit_company"] as mock_emit, patches["write_state"]:
            await run_content_generation_v13(
                inp, session_factory=_mock_session_factory(), run_id=uuid.uuid4(), company_id=uuid.uuid4(),
            )

        # Find hitl_review_needed notification calls
        notif_calls = [
            c for c in mock_emit.call_args_list
            if c.args[1] == "notification" and c.args[2].get("type") == "hitl_review_needed"
        ]
        assert len(notif_calls) >= 1
        assert notif_calls[0].args[2]["checkpoint"] == "brief_approval"

    @pytest.mark.asyncio
    async def test_emits_state_changed_on_pending(self, tmp_path):
        """pending_brief_approval emits state_changed event with brief ID."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, skip_stages=[3, 4, 5])

        patches = _td_base_patches(tmp_path, hitl_return={"brief_decision": "approve"})

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"], patches["build_graph"], patches["hitl"], \
             patches["persist_early"], patches["persist_approval"], \
             patches["get_sync_redis"], patches["cleanup_ga"], \
             patches["emit_company"] as mock_emit, patches["write_state"]:
            await run_content_generation_v13(
                inp, session_factory=_mock_session_factory(), run_id=uuid.uuid4(), company_id=uuid.uuid4(),
            )

        state_calls = [
            c for c in mock_emit.call_args_list
            if c.args[1] == "state_changed" and c.args[2].get("hint") == "pending_brief_approval"
        ]
        assert len(state_calls) >= 1
        assert "brief-001" in state_calls[0].args[2]["changed"]


# ===========================================================================
# Test class: Multiple Blueprints
# ===========================================================================


class TestTDHitl2MultipleBlueprints:
    """Multiple blueprints with independent per-brief decisions."""

    @pytest.mark.asyncio
    async def test_approve_first_reject_second(self, tmp_path):
        """Two blueprints: first approved, second rejected → 1 approved."""
        analysis = {
            "topic_query_map": {
                _ASSIGNMENT_ID_1: [_QUERY_ID_1],
                _ASSIGNMENT_ID_2: [_QUERY_ID_2],
            },
            "gaps": [
                {"query_id": _QUERY_ID_1, "query_text": "GSAP basics"},
                {"query_id": _QUERY_ID_2, "query_text": "GSAP advanced"},
            ],
        }
        _write_scoped_analysis(tmp_path, data=analysis)
        inp = _make_td_input(
            tmp_path,
            skip_stages=[3, 4, 5],
            assignment_ids=[_ASSIGNMENT_ID_1, _ASSIGNMENT_ID_2],
        )

        bp1 = _make_blueprint(brief_id="brief-001", title="GSAP Basics")
        bp2 = _make_blueprint(brief_id="brief-002", title="GSAP Advanced")

        patches = _td_base_patches(
            tmp_path,
            assignments=[_make_assignment(_ASSIGNMENT_ID_1, "Basics"), _make_assignment(_ASSIGNMENT_ID_2, "Advanced")],
            analysis_json=analysis,
            worker_contexts={_QUERY_ID_1: _make_gap_context(_QUERY_ID_1), _QUERY_ID_2: _make_gap_context(_QUERY_ID_2)},
            blueprints=[bp1, bp2],
            hitl_side_effect=[
                {"brief_decision": "approve"},   # bp1
                {"brief_decision": "reject"},    # bp2
            ],
        )

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"], patches["build_graph"], patches["hitl"], \
             patches["persist_early"], patches["persist_approval"] as mock_persist, \
             patches["get_sync_redis"], patches["cleanup_ga"], \
             patches["emit_company"], patches["write_state"]:
            result = await run_content_generation_v13(
                inp, session_factory=_mock_session_factory(), run_id=uuid.uuid4(), company_id=uuid.uuid4(),
            )

        assert result.total_briefs >= 1
        decisions = mock_persist.call_args.kwargs["approval_decisions"]
        assert len(decisions) == 2
        assert decisions[0]["decision"] == "approve"
        assert decisions[1]["decision"] == "reject"

    @pytest.mark.asyncio
    async def test_all_rejected_produces_error(self, tmp_path):
        """All blueprints rejected in TD mode → zero approved, pipeline reports failure."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, skip_stages=[3, 4, 5])

        patches = _td_base_patches(
            tmp_path,
            hitl_return={"brief_decision": "reject"},
        )

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"], patches["build_graph"], patches["hitl"], \
             patches["persist_early"], patches["persist_approval"], \
             patches["get_sync_redis"], patches["cleanup_ga"], \
             patches["emit_company"], patches["write_state"]:
            result = await run_content_generation_v13(
                inp, session_factory=_mock_session_factory(), run_id=uuid.uuid4(), company_id=uuid.uuid4(),
            )

        # Zero approved → C6 error path triggers
        assert result.total_briefs == 0
        assert result.total_briefs == 0


# ===========================================================================
# Test class: Decision Audit Trail
# ===========================================================================


class TestTDHitl2AuditTrail:
    """Verifies persist_v13_brief_approval captures full decision metadata."""

    @pytest.mark.asyncio
    async def test_audit_trail_records_feedback_attempts(self, tmp_path):
        """Feedback → approve records feedback_attempts=1 in audit trail."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, skip_stages=[3, 4, 5])

        gap_ctx = _make_gap_context()
        original = _make_blueprint(gap_context=gap_ctx)
        revised = _make_blueprint(title="Revised", gap_context=gap_ctx)

        patches = _td_base_patches(
            tmp_path,
            build_side_effect=[[original], [revised]],
            hitl_side_effect=[
                {"brief_decision": "feedback", "brief_feedback": "Add examples"},
                {"brief_decision": "approve"},
            ],
        )

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"], patches["build_graph"], patches["hitl"], \
             patches["persist_early"], patches["persist_approval"] as mock_persist, \
             patches["get_sync_redis"], patches["cleanup_ga"], \
             patches["emit_company"], patches["write_state"]:
            await run_content_generation_v13(
                inp, session_factory=_mock_session_factory(), run_id=uuid.uuid4(), company_id=uuid.uuid4(),
            )

        decisions = mock_persist.call_args.kwargs["approval_decisions"]
        assert len(decisions) == 1
        assert decisions[0]["brief_id"] == "brief-001"
        assert decisions[0]["decision"] == "approve"
        assert decisions[0]["feedback_attempts"] == 1

    @pytest.mark.asyncio
    async def test_audit_trail_includes_all_blueprints(self, tmp_path):
        """All blueprints (approved + rejected) are included in the persist call."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, skip_stages=[3, 4, 5])

        patches = _td_base_patches(
            tmp_path,
            hitl_return={"brief_decision": "approve"},
        )

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"], patches["build_graph"], patches["hitl"], \
             patches["persist_early"], patches["persist_approval"] as mock_persist, \
             patches["get_sync_redis"], patches["cleanup_ga"], \
             patches["emit_company"], patches["write_state"]:
            await run_content_generation_v13(
                inp, session_factory=_mock_session_factory(), run_id=uuid.uuid4(), company_id=uuid.uuid4(),
            )

        # The full blueprints list (not just approved) is passed for audit
        kw = mock_persist.call_args.kwargs
        assert len(kw["blueprints"]) == 1
        assert kw["slug"] == "test-co"


# ===========================================================================
# Test class: Edge Cases
# ===========================================================================


class TestTDHitl2EdgeCases:
    """Edge cases and error handling in TD HITL-2."""

    @pytest.mark.asyncio
    async def test_no_session_factory_raises(self, tmp_path):
        """TD mode without session_factory → RuntimeError."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, skip_stages=[3, 4, 5])

        patches = _td_base_patches(tmp_path)

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"], patches["build_graph"], patches["hitl"], \
             patches["persist_early"], patches["persist_approval"], \
             patches["get_sync_redis"], patches["cleanup_ga"], \
             patches["emit_company"], patches["write_state"]:
            with pytest.raises(RuntimeError, match="session_factory is required"):
                await run_content_generation_v13(
                    inp, session_factory=None, run_id=uuid.uuid4(), company_id=uuid.uuid4(),
                )

    @pytest.mark.asyncio
    async def test_empty_assignments_no_blueprints(self, tmp_path):
        """No matching assignments → no blueprints built → zero approved."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, skip_stages=[3, 4, 5])

        patches = _td_base_patches(tmp_path, assignments=[], worker_contexts={})

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"] as mock_build, patches["build_graph"], patches["hitl"], \
             patches["persist_early"], patches["persist_approval"], \
             patches["get_sync_redis"], patches["cleanup_ga"], \
             patches["emit_company"], patches["write_state"]:
            result = await run_content_generation_v13(
                inp, session_factory=_mock_session_factory(), run_id=uuid.uuid4(), company_id=uuid.uuid4(),
            )

        # Brief builder never called — no topics and no contexts
        mock_build.assert_not_called()

    @pytest.mark.asyncio
    async def test_default_decision_is_approve(self, tmp_path):
        """HITL checkpoint returning empty dict → defaults to 'approve'."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, skip_stages=[3, 4, 5])

        patches = _td_base_patches(tmp_path, hitl_return={})

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"], patches["build_graph"], patches["hitl"], \
             patches["persist_early"], patches["persist_approval"], \
             patches["get_sync_redis"], patches["cleanup_ga"], \
             patches["emit_company"], patches["write_state"]:
            result = await run_content_generation_v13(
                inp, session_factory=_mock_session_factory(), run_id=uuid.uuid4(), company_id=uuid.uuid4(),
            )

        # Default brief_decision is "approve"
        assert result.total_briefs >= 1

    @pytest.mark.asyncio
    async def test_no_redis_skips_ga_cleanup(self, tmp_path):
        """When Redis is unavailable, GA-phase cleanup is skipped gracefully."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, skip_stages=[3, 4, 5])

        patches = _td_base_patches(tmp_path, hitl_return={"brief_decision": "approve"})

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"], patches["build_graph"], patches["hitl"], \
             patches["persist_early"], patches["persist_approval"], \
             patch("core.redis.get_sync_redis_or_none", return_value=None), \
             patches["cleanup_ga"] as mock_cleanup, \
             patches["emit_company"], patches["write_state"]:
            result = await run_content_generation_v13(
                inp, session_factory=_mock_session_factory(), run_id=uuid.uuid4(), company_id=uuid.uuid4(),
            )

        mock_cleanup.assert_not_called()
        assert result.total_briefs >= 1

    @pytest.mark.asyncio
    async def test_feedback_with_empty_string(self, tmp_path):
        """Feedback with empty string → no crash, re-brief proceeds."""
        _write_scoped_analysis(tmp_path)
        inp = _make_td_input(tmp_path, skip_stages=[3, 4, 5])

        gap_ctx = _make_gap_context()
        bp = _make_blueprint(gap_context=gap_ctx)
        revised = _make_blueprint(title="Revised", gap_context=gap_ctx)

        patches = _td_base_patches(
            tmp_path,
            build_side_effect=[[bp], [revised]],
            hitl_side_effect=[
                {"brief_decision": "feedback", "brief_feedback": ""},
                {"brief_decision": "approve"},
            ],
        )

        with patches["db_read"], patches["extract_ctx"], patches["ta_to_sel"], \
             patches["build_briefs"], patches["build_graph"], patches["hitl"], \
             patches["persist_early"], patches["persist_approval"], \
             patches["get_sync_redis"], patches["cleanup_ga"], \
             patches["emit_company"], patches["write_state"]:
            result = await run_content_generation_v13(
                inp, session_factory=_mock_session_factory(), run_id=uuid.uuid4(), company_id=uuid.uuid4(),
            )

        assert result.total_briefs >= 1


# ===========================================================================
# Test class: persist_blueprints_early unit tests
# ===========================================================================


class TestPersistBlueprintsEarly:
    """Unit tests for the persist_blueprints_early function itself."""

    @pytest.mark.asyncio
    async def test_creates_pieces_in_db(self):
        """Creates ContentPiece records with correct fields."""
        from core.content_engine.persistence import persist_blueprints_early

        mock_session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.get_by_slug_and_brief_id = AsyncMock(return_value=None)
        mock_repo.create_piece = AsyncMock()

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session_ctx)
        run_id = uuid.uuid4()
        company_id = uuid.uuid4()
        bp = _make_blueprint()

        with patch("core.db.repositories.content_repo.ContentRepository", return_value=mock_repo):
            await persist_blueprints_early(
                session_factory=mock_factory,
                run_id=run_id,
                company_id=company_id,
                slug="test-co",
                blueprints=[bp],
            )

        mock_repo.create_piece.assert_called_once()
        kw = mock_repo.create_piece.call_args.kwargs
        assert kw["brief_id"] == "brief-001"
        assert kw["title"] == "GSAP Animation Guide"
        assert kw["effective_slug"] == "test-co"
        assert kw["company_id"] == company_id

    @pytest.mark.asyncio
    async def test_upserts_existing_piece(self):
        """If a piece already exists (slug + brief_id), updates it instead of creating."""
        from core.content_engine.persistence import persist_blueprints_early

        existing_piece = MagicMock()
        mock_repo = AsyncMock()
        mock_repo.get_by_slug_and_brief_id = AsyncMock(return_value=existing_piece)

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session_ctx)

        bp = _make_blueprint()

        with patch("core.db.repositories.content_repo.ContentRepository", return_value=mock_repo):
            await persist_blueprints_early(
                session_factory=mock_factory,
                run_id=uuid.uuid4(),
                company_id=uuid.uuid4(),
                slug="test-co",
                blueprints=[bp],
            )

        # create_piece NOT called (existing record updated)
        mock_repo.create_piece.assert_not_called()
        assert existing_piece.title == "GSAP Animation Guide"

    @pytest.mark.asyncio
    async def test_skips_when_no_session_factory(self):
        """No session_factory → no-op (graceful degradation)."""
        from core.content_engine.persistence import persist_blueprints_early

        # Should not raise
        await persist_blueprints_early(
            session_factory=None,
            run_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            slug="test-co",
            blueprints=[_make_blueprint()],
        )

    @pytest.mark.asyncio
    async def test_db_error_does_not_crash(self):
        """DB failure → logs warning, does not propagate exception."""
        from core.content_engine.persistence import persist_blueprints_early

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("DB down"))
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session_ctx)

        # Should not raise
        await persist_blueprints_early(
            session_factory=mock_factory,
            run_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            slug="test-co",
            blueprints=[_make_blueprint()],
        )
