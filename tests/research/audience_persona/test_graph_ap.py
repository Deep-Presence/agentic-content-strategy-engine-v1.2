"""Tests for Audience Persona HITL graphs — brief review + profile review.

Tests the two sub-graphs (brief review, profile review) and the
run_ap_hitl_checkpoint() invocation helper.

Phase C of the Audience Persona Research Pipeline.
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.research.audience_persona.graph import (
    build_ap_brief_review_graph,
    build_ap_profile_review_graph,
    run_ap_hitl_checkpoint,
)


# ---------------------------------------------------------------------------
# Helpers — sample data factories
# ---------------------------------------------------------------------------

def _make_briefs(count: int = 3) -> list:
    """Create sample brief dicts (serialized PersonaBrief)."""
    return [
        {
            "brief_id": f"pb-{i:03d}",
            "persona_name": f"Persona{i}",
            "tagline": f"Tagline for persona {i}",
            "description": f"Description for persona {i}",
            "rationale": [f"Reason A{i}", f"Reason B{i}"],
            "source": "agent",
        }
        for i in range(1, count + 1)
    ]


def _make_profile_summaries(persona_ids: list[str] | None = None) -> dict:
    """Create sample profile summaries dict."""
    ids = persona_ids or ["vp-finance", "head-ops", "cto-startup"]
    return {
        pid: {
            "content_preview": f"# Persona: {pid}\n\nProfile content...",
            "word_count": 2500 + i * 200,
            "has_error": False,
            "storage_path": f"{pid}/v1.md",
        }
        for i, pid in enumerate(ids)
    }


# ═══════════════════════════════════════════════════════════════════════
# Brief Review Graph — build
# ═══════════════════════════════════════════════════════════════════════


class TestBuildAPBriefReviewGraph:
    """Graph builder produces a compiled graph."""

    def test_build_returns_compiled_graph(self):
        graph = build_ap_brief_review_graph()
        assert graph is not None

    def test_custom_checkpointer(self):
        from langgraph.checkpoint.memory import MemorySaver

        graph = build_ap_brief_review_graph(checkpointer=MemorySaver())
        assert graph is not None


# ═══════════════════════════════════════════════════════════════════════
# Brief Review Graph — auto-approve
# ═══════════════════════════════════════════════════════════════════════


class TestAPBriefReviewAutoApprove:
    """Auto-approve skips interrupt entirely."""

    def test_auto_approve_returns_all_briefs(self):
        graph = build_ap_brief_review_graph()
        briefs = _make_briefs(4)
        result = graph.invoke(
            {"briefs": briefs, "checkpoint": 1, "auto_approve": True},
            {"configurable": {"thread_id": "test-br-auto-1"}},
        )
        assert result["approved_briefs"] == briefs

    def test_auto_approve_sets_batch_decision(self):
        graph = build_ap_brief_review_graph()
        result = graph.invoke(
            {"briefs": _make_briefs(3), "checkpoint": 1, "auto_approve": True},
            {"configurable": {"thread_id": "test-br-auto-2"}},
        )
        assert result["batch_decision"] == "approve_all"

    def test_auto_approve_no_interrupt(self):
        graph = build_ap_brief_review_graph()
        result = graph.invoke(
            {"briefs": _make_briefs(3), "checkpoint": 1, "auto_approve": True},
            {"configurable": {"thread_id": "test-br-auto-3"}},
        )
        assert not result.get("__interrupt__")


# ═══════════════════════════════════════════════════════════════════════
# Brief Review Graph — interrupt + resume
# ═══════════════════════════════════════════════════════════════════════


class TestAPBriefReviewInterrupt:
    """Manual mode triggers interrupt, resume resolves with per-brief decisions."""

    def test_interrupt_payload_has_required_fields(self):
        graph = build_ap_brief_review_graph()
        briefs = _make_briefs(3)
        result = graph.invoke(
            {"briefs": briefs, "checkpoint": 1},
            {"configurable": {"thread_id": "test-br-int-1"}},
        )
        assert result.get("__interrupt__")
        interrupt_val = result["__interrupt__"][0]
        payload = interrupt_val.value if hasattr(interrupt_val, "value") else interrupt_val
        assert payload["status"] == "pending_persona_brief_approval"
        assert payload["stage"] == "persona_brief_review"
        assert payload["checkpoint"] == 1
        assert payload["briefs"] == briefs

    def test_resume_approve_all(self):
        from langgraph.types import Command

        graph = build_ap_brief_review_graph()
        briefs = _make_briefs(3)
        config = {"configurable": {"thread_id": "test-br-resume-aa"}}

        graph.invoke({"briefs": briefs, "checkpoint": 1}, config)
        result = graph.invoke(
            Command(resume={"batch_decision": "approve_all"}),
            config,
        )
        assert not result.get("__interrupt__")
        assert result["approved_briefs"] == briefs

    def test_resume_reject_all(self):
        from langgraph.types import Command

        graph = build_ap_brief_review_graph()
        config = {"configurable": {"thread_id": "test-br-resume-ra"}}

        graph.invoke({"briefs": _make_briefs(3), "checkpoint": 1}, config)
        result = graph.invoke(
            Command(resume={"batch_decision": "reject_all"}),
            config,
        )
        assert not result.get("__interrupt__")
        assert result["approved_briefs"] == []

    def test_resume_partial_approve(self):
        from langgraph.types import Command

        graph = build_ap_brief_review_graph()
        briefs = _make_briefs(3)
        config = {"configurable": {"thread_id": "test-br-resume-pa"}}

        graph.invoke({"briefs": briefs, "checkpoint": 1}, config)
        result = graph.invoke(
            Command(resume={
                "batch_decision": "partial",
                "brief_reviews": [
                    {"brief_id": "pb-001", "decision": "approve"},
                    {"brief_id": "pb-003", "decision": "approve"},
                ],
            }),
            config,
        )
        assert not result.get("__interrupt__")
        approved_ids = [b["brief_id"] for b in result["approved_briefs"]]
        assert "pb-001" in approved_ids
        assert "pb-003" in approved_ids
        # pb-002 was not reviewed → rejected (fail-closed)
        assert "pb-002" not in approved_ids

    def test_resume_partial_modify(self):
        from langgraph.types import Command

        graph = build_ap_brief_review_graph()
        briefs = _make_briefs(3)
        config = {"configurable": {"thread_id": "test-br-resume-pm"}}

        modified = {
            "brief_id": "pb-001",
            "persona_name": "ModifiedSarah",
            "tagline": "Changed tagline",
            "description": "Changed desc",
            "rationale": ["New rationale"],
        }
        graph.invoke({"briefs": briefs, "checkpoint": 1}, config)
        result = graph.invoke(
            Command(resume={
                "batch_decision": "partial",
                "brief_reviews": [
                    {"brief_id": "pb-001", "decision": "modify", "modified_brief": modified},
                    {"brief_id": "pb-002", "decision": "approve"},
                    {"brief_id": "pb-003", "decision": "reject"},
                ],
            }),
            config,
        )
        assert not result.get("__interrupt__")
        approved_ids = [b["brief_id"] for b in result["approved_briefs"]]
        assert "pb-001" in approved_ids
        assert "pb-002" in approved_ids
        assert "pb-003" not in approved_ids

        # Check the modified brief has source="hybrid"
        modified_result = next(b for b in result["approved_briefs"] if b["brief_id"] == "pb-001")
        assert modified_result["source"] == "hybrid"
        assert modified_result["persona_name"] == "ModifiedSarah"

    def test_resume_partial_reject(self):
        from langgraph.types import Command

        graph = build_ap_brief_review_graph()
        briefs = _make_briefs(3)
        config = {"configurable": {"thread_id": "test-br-resume-pr"}}

        graph.invoke({"briefs": briefs, "checkpoint": 1}, config)
        result = graph.invoke(
            Command(resume={
                "batch_decision": "partial",
                "brief_reviews": [
                    {"brief_id": "pb-001", "decision": "reject"},
                    {"brief_id": "pb-002", "decision": "reject"},
                    {"brief_id": "pb-003", "decision": "reject"},
                ],
            }),
            config,
        )
        assert result["approved_briefs"] == []

    def test_resume_with_added_briefs(self):
        from langgraph.types import Command

        graph = build_ap_brief_review_graph()
        config = {"configurable": {"thread_id": "test-br-resume-add"}}

        graph.invoke({"briefs": _make_briefs(2), "checkpoint": 1}, config)
        result = graph.invoke(
            Command(resume={
                "batch_decision": "partial",
                "brief_reviews": [
                    {"brief_id": "pb-001", "decision": "approve"},
                    {"brief_id": "pb-002", "decision": "approve"},
                ],
                "added_briefs": [
                    {
                        "persona_name": "ManualPersona",
                        "tagline": "Manual tagline",
                        "description": "Manual desc",
                        "rationale": ["Manual reason"],
                    },
                ],
            }),
            config,
        )
        approved = result["approved_briefs"]
        assert len(approved) == 3
        manual = [b for b in approved if b.get("source") == "manual"]
        assert len(manual) == 1
        assert manual[0]["persona_name"] == "ManualPersona"
        # Manual briefs get generated IDs
        assert manual[0]["brief_id"].startswith("pb-manual-")

    def test_resume_reject_all_with_added_briefs(self):
        from langgraph.types import Command

        graph = build_ap_brief_review_graph()
        config = {"configurable": {"thread_id": "test-br-resume-ra-add"}}

        graph.invoke({"briefs": _make_briefs(2), "checkpoint": 1}, config)
        result = graph.invoke(
            Command(resume={
                "batch_decision": "reject_all",
                "added_briefs": [
                    {"persona_name": "AddedOne", "tagline": "t", "description": "d", "rationale": ["r"]},
                ],
            }),
            config,
        )
        # All originals rejected, but added briefs still included
        approved = result["approved_briefs"]
        assert len(approved) == 1
        assert approved[0]["persona_name"] == "AddedOne"
        assert approved[0]["source"] == "manual"

    def test_unknown_brief_id_skipped(self):
        """Unknown brief_id in reviews should be silently skipped, not crash."""
        from langgraph.types import Command

        graph = build_ap_brief_review_graph()
        briefs = _make_briefs(2)
        config = {"configurable": {"thread_id": "test-br-unknown-id"}}

        graph.invoke({"briefs": briefs, "checkpoint": 1}, config)
        result = graph.invoke(
            Command(resume={
                "batch_decision": "partial",
                "brief_reviews": [
                    {"brief_id": "pb-001", "decision": "approve"},
                    {"brief_id": "pb-NONEXISTENT", "decision": "approve"},
                ],
            }),
            config,
        )
        approved_ids = [b["brief_id"] for b in result["approved_briefs"]]
        assert "pb-001" in approved_ids
        assert "pb-NONEXISTENT" not in approved_ids

    def test_duplicate_brief_id_first_wins(self):
        """Duplicate brief_id in reviews — first decision wins."""
        from langgraph.types import Command

        graph = build_ap_brief_review_graph()
        briefs = _make_briefs(2)
        config = {"configurable": {"thread_id": "test-br-dup-id"}}

        graph.invoke({"briefs": briefs, "checkpoint": 1}, config)
        result = graph.invoke(
            Command(resume={
                "batch_decision": "partial",
                "brief_reviews": [
                    {"brief_id": "pb-001", "decision": "approve"},
                    {"brief_id": "pb-001", "decision": "reject"},  # duplicate — ignored
                    {"brief_id": "pb-002", "decision": "approve"},
                ],
            }),
            config,
        )
        approved_ids = [b["brief_id"] for b in result["approved_briefs"]]
        assert "pb-001" in approved_ids  # First decision wins (approve)

    def test_unreviewed_briefs_rejected(self):
        """Briefs in originals but not in reviews are rejected (fail-closed)."""
        from langgraph.types import Command

        graph = build_ap_brief_review_graph()
        briefs = _make_briefs(3)
        config = {"configurable": {"thread_id": "test-br-unreviewed"}}

        graph.invoke({"briefs": briefs, "checkpoint": 1}, config)
        result = graph.invoke(
            Command(resume={
                "batch_decision": "partial",
                "brief_reviews": [
                    {"brief_id": "pb-001", "decision": "approve"},
                    # pb-002 and pb-003 not reviewed → rejected
                ],
            }),
            config,
        )
        approved_ids = [b["brief_id"] for b in result["approved_briefs"]]
        assert approved_ids == ["pb-001"]

    def test_modified_brief_requires_persona_name(self):
        """Modified brief with empty persona_name is skipped (treated as reject)."""
        from langgraph.types import Command

        graph = build_ap_brief_review_graph()
        briefs = _make_briefs(2)
        config = {"configurable": {"thread_id": "test-br-mod-invalid"}}

        graph.invoke({"briefs": briefs, "checkpoint": 1}, config)
        result = graph.invoke(
            Command(resume={
                "batch_decision": "partial",
                "brief_reviews": [
                    {
                        "brief_id": "pb-001",
                        "decision": "modify",
                        "modified_brief": {
                            "persona_name": "",  # Invalid — empty
                            "tagline": "ok",
                            "description": "ok",
                        },
                    },
                    {"brief_id": "pb-002", "decision": "approve"},
                ],
            }),
            config,
        )
        approved_ids = [b["brief_id"] for b in result["approved_briefs"]]
        assert "pb-001" not in approved_ids  # Invalid modify → skipped
        assert "pb-002" in approved_ids

    def test_empty_resume_payload_rejects_all(self):
        """Malformed resume with empty batch_decision → no briefs approved (fail-closed)."""
        from langgraph.types import Command

        graph = build_ap_brief_review_graph()
        config = {"configurable": {"thread_id": "test-br-empty-resume"}}

        graph.invoke({"briefs": _make_briefs(3), "checkpoint": 1}, config)
        # Send a resume with an unrecognized batch_decision — should fail-closed
        result = graph.invoke(
            Command(resume={"batch_decision": ""}),
            config,
        )
        assert not result.get("__interrupt__")
        assert result["approved_briefs"] == []


# ═══════════════════════════════════════════════════════════════════════
# Profile Review Graph — build
# ═══════════════════════════════════════════════════════════════════════


class TestBuildAPProfileReviewGraph:
    """Graph builder produces a compiled graph."""

    def test_build_returns_compiled_graph(self):
        graph = build_ap_profile_review_graph()
        assert graph is not None


# ═══════════════════════════════════════════════════════════════════════
# Profile Review Graph — auto-approve
# ═══════════════════════════════════════════════════════════════════════


class TestAPProfileReviewAutoApprove:
    """Auto-approve skips interrupt for profile review."""

    def test_auto_approve_returns_all_profiles(self):
        graph = build_ap_profile_review_graph()
        summaries = _make_profile_summaries()
        result = graph.invoke(
            {"profile_summaries": summaries, "checkpoint": 2, "auto_approve": True},
            {"configurable": {"thread_id": "test-pr-auto-1"}},
        )
        assert sorted(result["approved_profiles"]) == sorted(list(summaries.keys()))
        assert result["revision_requests"] == {}
        assert result["rejected_profiles"] == []

    def test_auto_approve_no_interrupt(self):
        graph = build_ap_profile_review_graph()
        result = graph.invoke(
            {
                "profile_summaries": _make_profile_summaries(),
                "checkpoint": 2,
                "auto_approve": True,
            },
            {"configurable": {"thread_id": "test-pr-auto-2"}},
        )
        assert not result.get("__interrupt__")


# ═══════════════════════════════════════════════════════════════════════
# Profile Review Graph — interrupt + resume
# ═══════════════════════════════════════════════════════════════════════


class TestAPProfileReviewInterrupt:
    """Manual mode triggers interrupt, resume resolves with per-profile decisions."""

    def test_interrupt_payload_has_required_fields(self):
        graph = build_ap_profile_review_graph()
        summaries = _make_profile_summaries()
        result = graph.invoke(
            {"profile_summaries": summaries, "checkpoint": 2},
            {"configurable": {"thread_id": "test-pr-int-1"}},
        )
        assert result.get("__interrupt__")
        interrupt_val = result["__interrupt__"][0]
        payload = interrupt_val.value if hasattr(interrupt_val, "value") else interrupt_val
        assert payload["status"] == "pending_persona_profile_approval"
        assert payload["stage"] == "persona_profile_review"
        assert payload["checkpoint"] == 2
        assert "profiles" in payload

    def test_resume_all_approved(self):
        from langgraph.types import Command

        graph = build_ap_profile_review_graph()
        summaries = _make_profile_summaries(["vp-finance", "head-ops"])
        config = {"configurable": {"thread_id": "test-pr-resume-aa"}}

        graph.invoke({"profile_summaries": summaries, "checkpoint": 2}, config)
        result = graph.invoke(
            Command(resume={
                "profile_reviews": [
                    {"persona_id": "vp-finance", "decision": "approve"},
                    {"persona_id": "head-ops", "decision": "approve"},
                ],
            }),
            config,
        )
        assert not result.get("__interrupt__")
        assert sorted(result["approved_profiles"]) == ["head-ops", "vp-finance"]
        assert result["revision_requests"] == {}
        assert result["rejected_profiles"] == []

    def test_resume_revise_with_note(self):
        from langgraph.types import Command

        graph = build_ap_profile_review_graph()
        summaries = _make_profile_summaries(["vp-finance"])
        config = {"configurable": {"thread_id": "test-pr-resume-rev"}}

        graph.invoke({"profile_summaries": summaries, "checkpoint": 2}, config)
        result = graph.invoke(
            Command(resume={
                "profile_reviews": [
                    {
                        "persona_id": "vp-finance",
                        "decision": "revise",
                        "revision_note": "Add more procurement triggers",
                    },
                ],
            }),
            config,
        )
        assert result["revision_requests"] == {"vp-finance": "Add more procurement triggers"}
        assert result["approved_profiles"] == []
        assert result["rejected_profiles"] == []

    def test_resume_reject_profiles(self):
        from langgraph.types import Command

        graph = build_ap_profile_review_graph()
        summaries = _make_profile_summaries(["vp-finance", "head-ops"])
        config = {"configurable": {"thread_id": "test-pr-resume-rej"}}

        graph.invoke({"profile_summaries": summaries, "checkpoint": 2}, config)
        result = graph.invoke(
            Command(resume={
                "profile_reviews": [
                    {"persona_id": "vp-finance", "decision": "reject"},
                    {"persona_id": "head-ops", "decision": "reject"},
                ],
            }),
            config,
        )
        assert result["approved_profiles"] == []
        assert sorted(result["rejected_profiles"]) == ["head-ops", "vp-finance"]

    def test_resume_mixed_decisions(self):
        from langgraph.types import Command

        graph = build_ap_profile_review_graph()
        summaries = _make_profile_summaries(["vp-finance", "head-ops", "cto-startup"])
        config = {"configurable": {"thread_id": "test-pr-resume-mix"}}

        graph.invoke({"profile_summaries": summaries, "checkpoint": 2}, config)
        result = graph.invoke(
            Command(resume={
                "profile_reviews": [
                    {"persona_id": "vp-finance", "decision": "approve"},
                    {"persona_id": "head-ops", "decision": "revise", "revision_note": "Expand pain points"},
                    {"persona_id": "cto-startup", "decision": "reject"},
                ],
            }),
            config,
        )
        assert result["approved_profiles"] == ["vp-finance"]
        assert result["revision_requests"] == {"head-ops": "Expand pain points"}
        assert result["rejected_profiles"] == ["cto-startup"]

    def test_unknown_persona_id_skipped(self):
        """Unknown persona_id in reviews should be silently skipped."""
        from langgraph.types import Command

        graph = build_ap_profile_review_graph()
        summaries = _make_profile_summaries(["vp-finance"])
        config = {"configurable": {"thread_id": "test-pr-unknown-id"}}

        graph.invoke({"profile_summaries": summaries, "checkpoint": 2}, config)
        result = graph.invoke(
            Command(resume={
                "profile_reviews": [
                    {"persona_id": "vp-finance", "decision": "approve"},
                    {"persona_id": "NONEXISTENT", "decision": "approve"},
                ],
            }),
            config,
        )
        assert result["approved_profiles"] == ["vp-finance"]

    def test_duplicate_persona_id_first_wins(self):
        """Duplicate persona_id in reviews — first decision wins."""
        from langgraph.types import Command

        graph = build_ap_profile_review_graph()
        summaries = _make_profile_summaries(["vp-finance"])
        config = {"configurable": {"thread_id": "test-pr-dup-id"}}

        graph.invoke({"profile_summaries": summaries, "checkpoint": 2}, config)
        result = graph.invoke(
            Command(resume={
                "profile_reviews": [
                    {"persona_id": "vp-finance", "decision": "approve"},
                    {"persona_id": "vp-finance", "decision": "reject"},  # dup → ignored
                ],
            }),
            config,
        )
        assert "vp-finance" in result["approved_profiles"]
        assert "vp-finance" not in result["rejected_profiles"]

    def test_empty_profile_summaries_skips_interrupt(self):
        """Empty profile_summaries → skip interrupt, return empty lists."""
        graph = build_ap_profile_review_graph()
        result = graph.invoke(
            {"profile_summaries": {}, "checkpoint": 2},
            {"configurable": {"thread_id": "test-pr-empty-summaries"}},
        )
        # Should NOT interrupt — no profiles to review
        assert not result.get("__interrupt__")
        assert result["approved_profiles"] == []
        assert result["revision_requests"] == {}
        assert result["rejected_profiles"] == []


# ═══════════════════════════════════════════════════════════════════════
# run_ap_hitl_checkpoint — invocation helper
# ═══════════════════════════════════════════════════════════════════════


class TestRunAPHITLCheckpoint:
    """Tests for run_ap_hitl_checkpoint() async helper."""

    @pytest.mark.asyncio
    async def test_auto_approve_returns_without_interrupt(self):
        """Auto-approve state completes without interrupt loop."""
        graph = build_ap_brief_review_graph()
        result = await run_ap_hitl_checkpoint(
            graph=graph,
            initial_state={
                "briefs": _make_briefs(3),
                "checkpoint": 1,
                "auto_approve": True,
            },
            thread_id="test-helper-auto",
            stage_name="persona_brief_review",
        )
        assert result["batch_decision"] == "approve_all"
        assert len(result["approved_briefs"]) == 3

    @pytest.mark.asyncio
    async def test_interrupt_publishes_sse_event(self):
        """When graph interrupts, event_bus.publish is called."""
        mock_graph = MagicMock()
        interrupt_obj = MagicMock()
        interrupt_obj.value = {
            "status": "pending_persona_brief_approval",
            "stage": "persona_brief_review",
            "checkpoint": 1,
            "briefs": [],
        }

        mock_graph.invoke.side_effect = [
            {"__interrupt__": [interrupt_obj]},
            {"batch_decision": "approve_all", "approved_briefs": []},
        ]

        event_bus = MagicMock()
        task_store = MagicMock()
        task_store.wait_for_approval = AsyncMock(
            return_value={"batch_decision": "approve_all"},
        )

        await run_ap_hitl_checkpoint(
            graph=mock_graph,
            initial_state={},
            thread_id="test-sse-ap",
            task_store=task_store,
            event_bus=event_bus,
            task_id="ap-task-001",
            stage_name="persona_brief_review",
        )

        pending_calls = [
            c for c in event_bus.publish.call_args_list
            if c[0][1] == "pending_approval"
        ]
        assert len(pending_calls) == 1
        call_data = pending_calls[0][0][2]
        assert call_data["stage"] == "persona_brief_review"
        assert "checkpoint_nonce" in call_data

    @pytest.mark.asyncio
    async def test_interrupt_updates_task_store_pending(self):
        """When interrupted, task_store gets PENDING_APPROVAL then RUNNING."""
        mock_graph = MagicMock()
        interrupt_obj = MagicMock()
        interrupt_obj.value = {"status": "pending", "stage": "persona_brief_review"}

        mock_graph.invoke.side_effect = [
            {"__interrupt__": [interrupt_obj]},
            {"batch_decision": "approve_all", "approved_briefs": []},
        ]

        task_store = MagicMock()
        task_store.wait_for_approval = AsyncMock(
            return_value={"batch_decision": "approve_all"},
        )

        await run_ap_hitl_checkpoint(
            graph=mock_graph,
            initial_state={},
            thread_id="test-ts-ap",
            task_store=task_store,
            task_id="ap-task-002",
            stage_name="persona_brief_review",
        )

        assert task_store.update_task.call_count == 2
        first_call = task_store.update_task.call_args_list[0]
        assert first_call[1]["status"] == "pending_approval"
        second_call = task_store.update_task.call_args_list[1]
        assert second_call[1]["status"] == "running"
        assert second_call[1]["approval_payload"] is None

    @pytest.mark.asyncio
    async def test_resume_resets_status_to_running(self):
        """After approval, task status resets to running."""
        mock_graph = MagicMock()
        interrupt_obj = MagicMock()
        interrupt_obj.value = {"status": "pending"}

        mock_graph.invoke.side_effect = [
            {"__interrupt__": [interrupt_obj]},
            {"approved_profiles": ["vp-finance"]},
        ]

        task_store = MagicMock()
        task_store.wait_for_approval = AsyncMock(
            return_value={"profile_reviews": [{"persona_id": "vp-finance", "decision": "approve"}]},
        )

        await run_ap_hitl_checkpoint(
            graph=mock_graph,
            initial_state={},
            thread_id="test-reset-ap",
            task_store=task_store,
            task_id="ap-task-003",
            stage_name="persona_profile_review",
        )

        running_calls = [
            c for c in task_store.update_task.call_args_list
            if c[1].get("status") == "running"
        ]
        assert len(running_calls) == 1

    @pytest.mark.asyncio
    async def test_publishes_approval_received_event(self):
        """After resume, approval_received event is published."""
        mock_graph = MagicMock()
        interrupt_obj = MagicMock()
        interrupt_obj.value = {"status": "pending"}

        mock_graph.invoke.side_effect = [
            {"__interrupt__": [interrupt_obj]},
            {"approved_briefs": []},
        ]

        event_bus = MagicMock()
        task_store = MagicMock()
        approval = {"batch_decision": "approve_all"}
        task_store.wait_for_approval = AsyncMock(return_value=approval)

        await run_ap_hitl_checkpoint(
            graph=mock_graph,
            initial_state={},
            thread_id="test-ack-ap",
            task_store=task_store,
            event_bus=event_bus,
            task_id="ap-task-004",
            stage_name="persona_brief_review",
        )

        event_bus.publish.assert_any_call(
            "ap-task-004",
            "approval_received",
            {"stage": "persona_brief_review", "decision": "approve_all"},
        )

    @pytest.mark.asyncio
    async def test_no_task_store_uses_auto_approve_fallback(self):
        """Without task_store, fallback auto-approval is used."""
        mock_graph = MagicMock()
        interrupt_obj = MagicMock()
        interrupt_obj.value = {"status": "pending"}

        mock_graph.invoke.side_effect = [
            {"__interrupt__": [interrupt_obj]},
            {"approved_briefs": []},
        ]

        result = await run_ap_hitl_checkpoint(
            graph=mock_graph,
            initial_state={},
            thread_id="test-no-ts-ap",
            stage_name="persona_brief_review",
        )
        assert result == {"approved_briefs": []}

    @pytest.mark.asyncio
    async def test_checkpoint_nonce_unique_per_interrupt(self):
        """Each interrupt generates a unique checkpoint_nonce."""
        mock_graph = MagicMock()
        int1 = MagicMock()
        int1.value = {"status": "pending_1"}
        int2 = MagicMock()
        int2.value = {"status": "pending_2"}

        mock_graph.invoke.side_effect = [
            {"__interrupt__": [int1]},
            {"__interrupt__": [int2]},
            {"approved_briefs": []},
        ]

        task_store = MagicMock()
        task_store.wait_for_approval = AsyncMock(side_effect=[
            {"batch_decision": "reject_all"},  # Triggers another interrupt cycle
            {"batch_decision": "approve_all"},
        ])

        await run_ap_hitl_checkpoint(
            graph=mock_graph,
            initial_state={},
            thread_id="test-nonce-ap",
            task_store=task_store,
            task_id="ap-task-005",
            stage_name="persona_brief_review",
        )

        pending_calls = [
            c for c in task_store.update_task.call_args_list
            if c[1].get("status") == "pending_approval"
        ]
        assert len(pending_calls) == 2
        nonce1 = pending_calls[0][1]["approval_payload"]["checkpoint_nonce"]
        nonce2 = pending_calls[1][1]["approval_payload"]["checkpoint_nonce"]
        assert nonce1 != nonce2

    @pytest.mark.asyncio
    async def test_resume_passes_approval_to_command(self):
        """Verify that Command(resume=approval) is used for graph resumption."""
        from langgraph.types import Command

        mock_graph = MagicMock()
        interrupt_obj = MagicMock()
        interrupt_obj.value = {"status": "pending"}

        mock_graph.invoke.side_effect = [
            {"__interrupt__": [interrupt_obj]},
            {"approved_briefs": []},
        ]

        task_store = MagicMock()
        approval_data = {"batch_decision": "approve_all", "brief_reviews": []}
        task_store.wait_for_approval = AsyncMock(return_value=approval_data)

        await run_ap_hitl_checkpoint(
            graph=mock_graph,
            initial_state={},
            thread_id="test-cmd-ap",
            task_store=task_store,
            task_id="ap-task-006",
            stage_name="persona_brief_review",
        )

        # Second invoke call should use Command(resume=approval_data)
        second_call = mock_graph.invoke.call_args_list[1]
        cmd = second_call[0][0]
        assert isinstance(cmd, Command)
        assert cmd.resume == approval_data

    @pytest.mark.asyncio
    async def test_multiple_interrupt_resume_cycles(self):
        """Helper handles multiple interrupt/resume cycles correctly."""
        mock_graph = MagicMock()
        int1 = MagicMock()
        int1.value = {"status": "pending_1"}
        int2 = MagicMock()
        int2.value = {"status": "pending_2"}
        int3 = MagicMock()
        int3.value = {"status": "pending_3"}

        mock_graph.invoke.side_effect = [
            {"__interrupt__": [int1]},
            {"__interrupt__": [int2]},
            {"__interrupt__": [int3]},
            {"final": "result"},
        ]

        task_store = MagicMock()
        task_store.wait_for_approval = AsyncMock(side_effect=[
            {"decision": "d1"},
            {"decision": "d2"},
            {"decision": "d3"},
        ])
        event_bus = MagicMock()

        result = await run_ap_hitl_checkpoint(
            graph=mock_graph,
            initial_state={},
            thread_id="test-multi-cycle",
            task_store=task_store,
            event_bus=event_bus,
            task_id="ap-task-007",
            stage_name="test_stage",
        )

        assert result == {"final": "result"}
        assert mock_graph.invoke.call_count == 4
        # 3 pending_approval + 3 running resets = 6 task_store updates
        assert task_store.update_task.call_count == 6
        assert task_store.wait_for_approval.call_count == 3
