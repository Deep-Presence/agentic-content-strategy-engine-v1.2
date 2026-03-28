"""Tests for Topic Discovery HITL graphs — Taxonomy Review + Matrix Review.

Covers:
- Graph builders (taxonomy + matrix)
- Auto-approve (skips interrupt)
- Interrupt payload structure
- Resume with approve / modify / retry
- Taxonomy edit operations (add/delete/rename/reparent)
- Matrix edit operations (adjust_priority/remove/add)
- run_td_hitl_checkpoint() helper
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.checkpoint.memory import MemorySaver

from langgraph.types import Command

from core.topic_discovery.graph import (
    _add_child_to_node,
    _count_nodes_and_max_depth,
    _extract_node,
    _get_interrupt_value,
    _has_interrupt,
    _normalize_tree_metadata,
    _process_matrix_edits,
    _process_taxonomy_edits,
    _remove_node,
    _rename_node,
    _set_depths,
    build_td_matrix_review_graph,
    build_td_taxonomy_review_graph,
    run_td_hitl_checkpoint,
)


@pytest.fixture(autouse=True)
def _use_memory_checkpointer(monkeypatch):
    """Use in-memory checkpointer so tests don't require Redis."""
    monkeypatch.setattr(
        "core.topic_discovery.graph.get_checkpointer",
        lambda override=None: override if override is not None else MemorySaver(),
    )


# ---------------------------------------------------------------------------
# Helpers — sample data factories
# ---------------------------------------------------------------------------


def _make_taxonomy(node_count: int = 3) -> dict:
    """Create a sample serialized taxonomy with root nodes."""
    return {
        "domain_name": "fintech",
        "version": 1,
        "root_nodes": [
            {
                "id": f"node-{i}",
                "name": f"Subdomain {i}",
                "description": f"Description for subdomain {i}",
                "depth": 0,
                "children": [],
                "source_provenance": {"source_a": True},
                "confidence": 0.8,
                "sort_order": i - 1,
            }
            for i in range(1, node_count + 1)
        ],
        "total_subdomains": node_count,
        "max_depth": 0,
    }


def _make_taxonomy_with_children() -> dict:
    """Taxonomy with nested structure for reparent/delete tests."""
    return {
        "domain_name": "fintech",
        "version": 1,
        "root_nodes": [
            {
                "id": "root-1",
                "name": "Expense Management",
                "description": "",
                "depth": 0,
                "children": [
                    {
                        "id": "child-1a",
                        "name": "Receipt Scanning",
                        "description": "",
                        "depth": 1,
                        "children": [],
                        "source_provenance": {},
                        "confidence": 0.7,
                    },
                    {
                        "id": "child-1b",
                        "name": "Policy Enforcement",
                        "description": "",
                        "depth": 1,
                        "children": [],
                        "source_provenance": {},
                        "confidence": 0.6,
                    },
                ],
                "source_provenance": {"source_a": True},
                "confidence": 0.9,
            },
            {
                "id": "root-2",
                "name": "Corporate Cards",
                "description": "",
                "depth": 0,
                "children": [],
                "source_provenance": {"source_b": True},
                "confidence": 0.8,
            },
        ],
    }


def _make_coverage() -> dict:
    """Sample coverage metrics."""
    return {
        "estimated_total": 25,
        "chao1_lower_bound": 22.5,
        "sample_coverage": 0.88,
        "observed_count": 20,
        "aggregate_sample_coverage": 0.88,
        "aggregate_chao1_ratio": 0.80,
        "per_source_coverage": {},
    }


def _make_matrix(assignment_count: int = 3) -> dict:
    """Create a sample serialized matrix with assignments."""
    return {
        "version": 1,
        "assignments": [
            {
                "id": f"assign-{i}",
                "subdomain_name": f"Subdomain {i}",
                "topic_text": f"Topic text {i}",
                "buyer_stage": "tofu",
                "intent_type": "informational",
                "audience_segment": f"Persona {i}",
                "audience_segment_type": "individual_persona",
                "relevance": "relevant",
                "priority_score": 0.5 + i * 0.1,
                "status": "not_started",
                "is_manually_added": False,
                "priority_factors": {},
                "metadata": {},
            }
            for i in range(1, assignment_count + 1)
        ],
        "total_assignments": assignment_count,
    }


# ═══════════════════════════════════════════════════════════════════════
# Helpers — _has_interrupt, _get_interrupt_value
# ═══════════════════════════════════════════════════════════════════════


class TestHelpers:
    """Unit tests for helper functions."""

    def test_has_interrupt_true(self):
        assert _has_interrupt({"__interrupt__": [{"value": {}}]}) is True

    def test_has_interrupt_false(self):
        assert _has_interrupt({}) is False
        assert _has_interrupt({"__interrupt__": []}) is False

    def test_get_interrupt_value_with_value_attr(self):
        mock_interrupt = MagicMock()
        mock_interrupt.value = {"status": "pending"}
        result = _get_interrupt_value({"__interrupt__": [mock_interrupt]})
        assert result == {"status": "pending"}

    def test_get_interrupt_value_without_value_attr(self):
        result = _get_interrupt_value({"__interrupt__": [{"status": "pending"}]})
        assert result == {"status": "pending"}

    def test_get_interrupt_value_empty(self):
        assert _get_interrupt_value({}) == {}
        assert _get_interrupt_value({"__interrupt__": []}) == {}


# ═══════════════════════════════════════════════════════════════════════
# Taxonomy: Graph Builder
# ═══════════════════════════════════════════════════════════════════════


class TestBuildTDTaxonomyReviewGraph:
    """Graph builder produces a compiled graph."""

    def test_build_returns_compiled_graph(self):
        graph = build_td_taxonomy_review_graph()
        assert graph is not None

    def test_custom_checkpointer(self):
        from langgraph.checkpoint.memory import MemorySaver

        graph = build_td_taxonomy_review_graph(checkpointer=MemorySaver())
        assert graph is not None


# ═══════════════════════════════════════════════════════════════════════
# Taxonomy: Auto-Approve
# ═══════════════════════════════════════════════════════════════════════


class TestTaxonomyAutoApprove:
    """Auto-approve skips interrupt entirely."""

    def test_auto_approve_returns_taxonomy(self):
        graph = build_td_taxonomy_review_graph()
        taxonomy = _make_taxonomy(3)
        result = graph.invoke(
            {"taxonomy": taxonomy, "checkpoint": 1, "auto_approve": True},
            {"configurable": {"thread_id": "td-tax-auto-1"}},
        )
        assert result["approved_taxonomy"] == taxonomy
        assert result["batch_decision"] == "approve"

    def test_auto_approve_no_interrupt(self):
        graph = build_td_taxonomy_review_graph()
        result = graph.invoke(
            {"taxonomy": _make_taxonomy(2), "checkpoint": 1, "auto_approve": True},
            {"configurable": {"thread_id": "td-tax-auto-2"}},
        )
        assert not result.get("__interrupt__")

    def test_auto_approve_sets_presented_at(self):
        graph = build_td_taxonomy_review_graph()
        result = graph.invoke(
            {"taxonomy": _make_taxonomy(2), "checkpoint": 1, "auto_approve": True},
            {"configurable": {"thread_id": "td-tax-auto-3"}},
        )
        assert result["presented_at"] > 0


# ═══════════════════════════════════════════════════════════════════════
# Taxonomy: Interrupt + Resume
# ═══════════════════════════════════════════════════════════════════════


class TestTaxonomyInterruptResume:
    """Manual mode triggers interrupt, resume resolves with decisions."""

    def test_interrupt_payload_has_required_fields(self):
        graph = build_td_taxonomy_review_graph()
        taxonomy = _make_taxonomy(3)
        coverage = _make_coverage()
        result = graph.invoke(
            {"taxonomy": taxonomy, "coverage_metrics": coverage, "checkpoint": 1},
            {"configurable": {"thread_id": "td-tax-int-1"}},
        )
        assert result.get("__interrupt__")
        interrupt_val = result["__interrupt__"][0].value
        assert interrupt_val["status"] == "pending_taxonomy_approval"
        assert interrupt_val["stage"] == "td_taxonomy_review"
        assert interrupt_val["checkpoint"] == 1
        assert interrupt_val["taxonomy"] == taxonomy
        assert interrupt_val["coverage_metrics"] == coverage

    def test_resume_approve(self):
        graph = build_td_taxonomy_review_graph()
        taxonomy = _make_taxonomy(3)
        config = {"configurable": {"thread_id": "td-tax-int-2"}}

        result = graph.invoke(
            {"taxonomy": taxonomy, "checkpoint": 1}, config
        )
        assert result.get("__interrupt__")

        result = graph.invoke(
            Command(resume={"batch_decision": "approve"}),
            config,
        )
        assert result["approved_taxonomy"] == taxonomy
        assert result["batch_decision"] == "approve"

    def test_resume_retry_clears_taxonomy(self):
        graph = build_td_taxonomy_review_graph()
        taxonomy = _make_taxonomy(3)
        config = {"configurable": {"thread_id": "td-tax-int-3"}}

        result = graph.invoke(
            {"taxonomy": taxonomy, "checkpoint": 1}, config
        )
        assert result.get("__interrupt__")

        result = graph.invoke(
            Command(resume={
                "batch_decision": "retry",
                "user_feedback": "Need more fintech subdomains",
            }),
            config,
        )
        assert result["batch_decision"] == "retry"
        assert result["approved_taxonomy"] == {}
        assert result["user_feedback"] == "Need more fintech subdomains"

    def test_resume_modify_with_edits(self):
        graph = build_td_taxonomy_review_graph()
        taxonomy = _make_taxonomy(3)
        config = {"configurable": {"thread_id": "td-tax-int-4"}}

        result = graph.invoke(
            {"taxonomy": taxonomy, "checkpoint": 1}, config
        )
        assert result.get("__interrupt__")

        result = graph.invoke(
            Command(resume={
                "batch_decision": "modify",
                "user_edits": [
                    {"op": "rename", "node_id": "node-1", "new_name": "Renamed Node"},
                ],
            }),
            config,
        )
        assert result["batch_decision"] == "modify"
        approved = result["approved_taxonomy"]
        renamed = [n for n in approved["root_nodes"] if n["id"] == "node-1"]
        assert renamed[0]["name"] == "Renamed Node"

    def test_resume_empty_dict_defaults_to_approve(self):
        graph = build_td_taxonomy_review_graph()
        taxonomy = _make_taxonomy(1)
        config = {"configurable": {"thread_id": "td-tax-int-5"}}

        graph.invoke(
            {"taxonomy": taxonomy, "checkpoint": 1}, config
        )
        result = graph.invoke(Command(resume={}), config)
        # Empty resume → decision defaults to "approve", taxonomy preserved
        assert result.get("batch_decision", "approve") == "approve"
        assert result.get("approved_taxonomy", taxonomy) == taxonomy


# ═══════════════════════════════════════════════════════════════════════
# Taxonomy: Edit Operations
# ═══════════════════════════════════════════════════════════════════════


class TestProcessTaxonomyEdits:
    """Unit tests for _process_taxonomy_edits()."""

    def test_no_edits_returns_unchanged(self):
        taxonomy = _make_taxonomy(2)
        result = _process_taxonomy_edits(taxonomy, [])
        assert result is taxonomy

    def test_add_root_node(self):
        taxonomy = _make_taxonomy(2)
        edits = [{"op": "add", "name": "New Node", "description": "New desc"}]
        result = _process_taxonomy_edits(taxonomy, edits)
        assert len(result["root_nodes"]) == 3
        added = result["root_nodes"][-1]
        assert added["name"] == "New Node"
        assert added["is_manually_added"] is True

    def test_add_child_node(self):
        taxonomy = _make_taxonomy(2)
        edits = [
            {"op": "add", "parent_id": "node-1", "name": "Child", "description": ""},
        ]
        result = _process_taxonomy_edits(taxonomy, edits)
        assert len(result["root_nodes"]) == 2  # still 2 roots
        children = result["root_nodes"][0]["children"]
        assert len(children) == 1
        assert children[0]["name"] == "Child"

    def test_delete_root_node(self):
        taxonomy = _make_taxonomy(3)
        edits = [{"op": "delete", "node_id": "node-2"}]
        result = _process_taxonomy_edits(taxonomy, edits)
        assert len(result["root_nodes"]) == 2
        ids = [n["id"] for n in result["root_nodes"]]
        assert "node-2" not in ids

    def test_delete_nested_node(self):
        taxonomy = _make_taxonomy_with_children()
        edits = [{"op": "delete", "node_id": "child-1a"}]
        result = _process_taxonomy_edits(taxonomy, edits)
        children = result["root_nodes"][0]["children"]
        assert len(children) == 1
        assert children[0]["id"] == "child-1b"

    def test_rename_node(self):
        taxonomy = _make_taxonomy(2)
        edits = [{"op": "rename", "node_id": "node-1", "new_name": "Renamed"}]
        result = _process_taxonomy_edits(taxonomy, edits)
        assert result["root_nodes"][0]["name"] == "Renamed"

    def test_rename_nested_node(self):
        taxonomy = _make_taxonomy_with_children()
        edits = [{"op": "rename", "node_id": "child-1b", "new_name": "Updated Policy"}]
        result = _process_taxonomy_edits(taxonomy, edits)
        child = result["root_nodes"][0]["children"][1]
        assert child["name"] == "Updated Policy"

    def test_reparent_to_root(self):
        taxonomy = _make_taxonomy_with_children()
        edits = [{"op": "reparent", "node_id": "child-1a", "new_parent_id": None}]
        result = _process_taxonomy_edits(taxonomy, edits)
        assert len(result["root_nodes"]) == 3  # 2 original roots + reparented
        root_ids = [n["id"] for n in result["root_nodes"]]
        assert "child-1a" in root_ids
        # removed from original parent
        assert len(result["root_nodes"][0]["children"]) == 1

    def test_reparent_to_different_parent(self):
        taxonomy = _make_taxonomy_with_children()
        edits = [{"op": "reparent", "node_id": "child-1a", "new_parent_id": "root-2"}]
        result = _process_taxonomy_edits(taxonomy, edits)
        # child-1a removed from root-1's children
        assert len(result["root_nodes"][0]["children"]) == 1
        # child-1a added to root-2's children
        assert len(result["root_nodes"][1]["children"]) == 1
        assert result["root_nodes"][1]["children"][0]["id"] == "child-1a"

    def test_multiple_edits_applied_sequentially(self):
        taxonomy = _make_taxonomy(3)
        edits = [
            {"op": "rename", "node_id": "node-1", "new_name": "First Renamed"},
            {"op": "delete", "node_id": "node-2"},
            {"op": "add", "name": "Brand New", "description": "fresh"},
        ]
        result = _process_taxonomy_edits(taxonomy, edits)
        assert len(result["root_nodes"]) == 3  # 3 - 1 deleted + 1 added
        names = [n["name"] for n in result["root_nodes"]]
        assert "First Renamed" in names
        assert "Brand New" in names
        assert "Subdomain 2" not in names


# ═══════════════════════════════════════════════════════════════════════
# Taxonomy: Tree Manipulation Helpers
# ═══════════════════════════════════════════════════════════════════════


class TestTreeHelpers:
    """Unit tests for _add_child_to_node, _remove_node, _rename_node, _extract_node."""

    def test_add_child_to_existing_parent(self):
        nodes = [{"id": "p1", "children": []}]
        child = {"id": "c1", "name": "Child"}
        assert _add_child_to_node(nodes, "p1", child) is True
        assert len(nodes[0]["children"]) == 1

    def test_add_child_parent_not_found(self):
        nodes = [{"id": "p1", "children": []}]
        child = {"id": "c1", "name": "Child"}
        assert _add_child_to_node(nodes, "nonexistent", child) is False

    def test_remove_node_returns_filtered(self):
        nodes = [
            {"id": "a", "children": []},
            {"id": "b", "children": []},
        ]
        result = _remove_node(nodes, "a")
        assert len(result) == 1
        assert result[0]["id"] == "b"

    def test_remove_node_not_found_unchanged(self):
        nodes = [{"id": "a", "children": []}]
        result = _remove_node(nodes, "nonexistent")
        assert len(result) == 1

    def test_rename_node_found(self):
        nodes = [{"id": "a", "name": "Old", "children": []}]
        _rename_node(nodes, "a", "New")
        assert nodes[0]["name"] == "New"

    def test_extract_node_found(self):
        nodes = [
            {"id": "a", "children": [{"id": "b", "children": []}]},
        ]
        result = _extract_node(nodes, "b")
        assert result is not None
        assert result["id"] == "b"

    def test_extract_node_not_found(self):
        nodes = [{"id": "a", "children": []}]
        assert _extract_node(nodes, "nonexistent") is None


# ═══════════════════════════════════════════════════════════════════════
# Matrix: Graph Builder
# ═══════════════════════════════════════════════════════════════════════


class TestBuildTDMatrixReviewGraph:
    """Graph builder produces a compiled graph."""

    def test_build_returns_compiled_graph(self):
        graph = build_td_matrix_review_graph()
        assert graph is not None

    def test_custom_checkpointer(self):
        from langgraph.checkpoint.memory import MemorySaver

        graph = build_td_matrix_review_graph(checkpointer=MemorySaver())
        assert graph is not None


# ═══════════════════════════════════════════════════════════════════════
# Matrix: Auto-Approve
# ═══════════════════════════════════════════════════════════════════════


class TestMatrixAutoApprove:
    """Auto-approve skips interrupt entirely."""

    def test_auto_approve_returns_matrix(self):
        graph = build_td_matrix_review_graph()
        matrix = _make_matrix(3)
        result = graph.invoke(
            {"matrix": matrix, "checkpoint": 2, "auto_approve": True},
            {"configurable": {"thread_id": "td-mat-auto-1"}},
        )
        assert result["approved_matrix"] == matrix
        assert result["batch_decision"] == "approve"

    def test_auto_approve_no_interrupt(self):
        graph = build_td_matrix_review_graph()
        result = graph.invoke(
            {"matrix": _make_matrix(2), "checkpoint": 2, "auto_approve": True},
            {"configurable": {"thread_id": "td-mat-auto-2"}},
        )
        assert not result.get("__interrupt__")

    def test_auto_approve_sets_presented_at(self):
        graph = build_td_matrix_review_graph()
        result = graph.invoke(
            {"matrix": _make_matrix(2), "checkpoint": 2, "auto_approve": True},
            {"configurable": {"thread_id": "td-mat-auto-3"}},
        )
        assert result["presented_at"] > 0


# ═══════════════════════════════════════════════════════════════════════
# Matrix: Interrupt + Resume
# ═══════════════════════════════════════════════════════════════════════


class TestMatrixInterruptResume:
    """Manual mode triggers interrupt, resume resolves with decisions."""

    def test_interrupt_payload_has_required_fields(self):
        graph = build_td_matrix_review_graph()
        matrix = _make_matrix(3)
        result = graph.invoke(
            {"matrix": matrix, "checkpoint": 2},
            {"configurable": {"thread_id": "td-mat-int-1"}},
        )
        assert result.get("__interrupt__")
        interrupt_val = result["__interrupt__"][0].value
        assert interrupt_val["status"] == "pending_matrix_approval"
        assert interrupt_val["stage"] == "td_matrix_review"
        assert interrupt_val["checkpoint"] == 2
        assert interrupt_val["matrix"] == matrix

    def test_resume_approve(self):
        graph = build_td_matrix_review_graph()
        matrix = _make_matrix(3)
        config = {"configurable": {"thread_id": "td-mat-int-2"}}

        result = graph.invoke({"matrix": matrix, "checkpoint": 2}, config)
        assert result.get("__interrupt__")

        result = graph.invoke(
            Command(resume={"batch_decision": "approve"}),
            config,
        )
        assert result["approved_matrix"] == matrix
        assert result["batch_decision"] == "approve"

    def test_resume_modify_with_edits(self):
        graph = build_td_matrix_review_graph()
        matrix = _make_matrix(3)
        config = {"configurable": {"thread_id": "td-mat-int-3"}}

        result = graph.invoke({"matrix": matrix, "checkpoint": 2}, config)
        assert result.get("__interrupt__")

        result = graph.invoke(
            Command(resume={
                "batch_decision": "modify",
                "user_edits": [
                    {"op": "adjust_priority", "assignment_id": "assign-1", "new_priority": 0.99},
                ],
            }),
            config,
        )
        assert result["batch_decision"] == "modify"
        approved = result["approved_matrix"]
        adjusted = [a for a in approved["assignments"] if a["id"] == "assign-1"]
        assert adjusted[0]["priority_score"] == 0.99

    def test_resume_empty_dict_defaults_to_approve(self):
        graph = build_td_matrix_review_graph()
        matrix = _make_matrix(1)
        config = {"configurable": {"thread_id": "td-mat-int-4"}}

        graph.invoke(
            {"matrix": matrix, "checkpoint": 2}, config
        )
        result = graph.invoke(Command(resume={}), config)
        # Empty resume → decision defaults to "approve", matrix preserved
        assert result.get("batch_decision", "approve") == "approve"
        assert result.get("approved_matrix", matrix) == matrix


# ═══════════════════════════════════════════════════════════════════════
# Matrix: Edit Operations
# ═══════════════════════════════════════════════════════════════════════


class TestProcessMatrixEdits:
    """Unit tests for _process_matrix_edits()."""

    def test_no_edits_returns_unchanged(self):
        matrix = _make_matrix(2)
        result = _process_matrix_edits(matrix, [])
        assert result is matrix

    def test_adjust_priority(self):
        matrix = _make_matrix(3)
        edits = [{"op": "adjust_priority", "assignment_id": "assign-2", "new_priority": 0.95}]
        result = _process_matrix_edits(matrix, edits)
        target = [a for a in result["assignments"] if a["id"] == "assign-2"]
        assert target[0]["priority_score"] == 0.95

    def test_adjust_priority_unknown_id_no_error(self):
        matrix = _make_matrix(2)
        edits = [{"op": "adjust_priority", "assignment_id": "nonexistent", "new_priority": 0.99}]
        result = _process_matrix_edits(matrix, edits)
        assert len(result["assignments"]) == 2  # unchanged

    def test_remove_assignment(self):
        matrix = _make_matrix(3)
        edits = [{"op": "remove", "assignment_id": "assign-2"}]
        result = _process_matrix_edits(matrix, edits)
        assert len(result["assignments"]) == 2
        assert result["total_assignments"] == 2
        ids = [a["id"] for a in result["assignments"]]
        assert "assign-2" not in ids

    def test_add_assignment(self):
        matrix = _make_matrix(2)
        edits = [
            {
                "op": "add",
                "topic_text": "New topic",
                "subdomain_name": "New Subdomain",
                "buyer_stage": "mofu",
                "intent_type": "commercial",
                "audience_segment": "VP Engineering",
                "priority_score": 0.75,
            }
        ]
        result = _process_matrix_edits(matrix, edits)
        assert len(result["assignments"]) == 3
        assert result["total_assignments"] == 3
        added = result["assignments"][-1]
        assert added["topic_text"] == "New topic"
        assert added["is_manually_added"] is True
        assert added["buyer_stage"] == "mofu"
        assert added["priority_score"] == 0.75

    def test_multiple_edits_applied_sequentially(self):
        matrix = _make_matrix(3)
        edits = [
            {"op": "remove", "assignment_id": "assign-1"},
            {"op": "adjust_priority", "assignment_id": "assign-2", "new_priority": 0.99},
            {"op": "add", "topic_text": "Fresh topic", "subdomain_name": "Fresh"},
        ]
        result = _process_matrix_edits(matrix, edits)
        assert len(result["assignments"]) == 3  # 3 - 1 + 1
        assert result["total_assignments"] == 3
        ids = [a["id"] for a in result["assignments"]]
        assert "assign-1" not in ids


# ═══════════════════════════════════════════════════════════════════════
# run_td_hitl_checkpoint() Helper
# ═══════════════════════════════════════════════════════════════════════


class TestRunTDHitlCheckpoint:
    """Tests for the async invocation helper."""

    @pytest.mark.asyncio
    async def test_auto_approve_taxonomy_no_interrupt(self):
        graph = build_td_taxonomy_review_graph()
        taxonomy = _make_taxonomy(3)
        result = await run_td_hitl_checkpoint(
            graph,
            {"taxonomy": taxonomy, "checkpoint": 1, "auto_approve": True},
            thread_id="td-helper-1",
        )
        assert result["approved_taxonomy"] == taxonomy

    @pytest.mark.asyncio
    async def test_auto_approve_matrix_no_interrupt(self):
        graph = build_td_matrix_review_graph()
        matrix = _make_matrix(2)
        result = await run_td_hitl_checkpoint(
            graph,
            {"matrix": matrix, "checkpoint": 2, "auto_approve": True},
            thread_id="td-helper-2",
        )
        assert result["approved_matrix"] == matrix

    @pytest.mark.asyncio
    async def test_no_task_store_auto_approves(self):
        """Without task_store, interrupt loop auto-approves."""
        graph = build_td_taxonomy_review_graph()
        taxonomy = _make_taxonomy(2)
        result = await run_td_hitl_checkpoint(
            graph,
            {"taxonomy": taxonomy, "checkpoint": 1},
            thread_id="td-helper-3",
            task_store=None,
            task_id=None,
        )
        # Without task_store: approval defaults to {"batch_decision": "approve"}
        assert result["batch_decision"] == "approve"
        assert result["approved_taxonomy"] == taxonomy

    @pytest.mark.asyncio
    async def test_with_task_store_auto_approve_skips_calls(self):
        """When auto_approve is True, task_store + event_bus are not called."""
        graph = build_td_taxonomy_review_graph()
        task_store = MagicMock()
        event_bus = MagicMock()

        result = await run_td_hitl_checkpoint(
            graph,
            {"taxonomy": _make_taxonomy(2), "checkpoint": 1, "auto_approve": True},
            thread_id="td-helper-4",
            task_store=task_store,
            event_bus=event_bus,
            task_id="task-123",
        )
        assert result["batch_decision"] == "approve"
        task_store.update_task.assert_not_called()
        event_bus.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_with_task_store_interrupt_flow(self):
        """task_store + event_bus get called when interrupt fires."""
        graph = build_td_taxonomy_review_graph()
        task_store = MagicMock()
        task_store.wait_for_approval = AsyncMock(
            return_value={"batch_decision": "approve"}
        )
        event_bus = MagicMock()

        result = await run_td_hitl_checkpoint(
            graph,
            {"taxonomy": _make_taxonomy(2), "checkpoint": 1},
            thread_id="td-helper-5",
            task_store=task_store,
            event_bus=event_bus,
            task_id="task-456",
            stage_name="td_taxonomy_review",
        )
        assert result["batch_decision"] == "approve"
        # update_task called twice: PENDING_APPROVAL + RUNNING reset
        assert task_store.update_task.call_count == 2
        # publish called twice: pending_approval + approval_received
        assert event_bus.publish.call_count == 2
        # Verify first publish (pending_approval)
        first_pub = event_bus.publish.call_args_list[0]
        assert first_pub[0][0] == "task-456"
        assert first_pub[0][1] == "pending_approval"
        assert first_pub[0][2]["stage"] == "td_taxonomy_review"
        assert "checkpoint_nonce" in first_pub[0][2]

    @pytest.mark.asyncio
    async def test_timeout_rejection_does_not_approve(self):
        """A rejected/timed-out approval must not produce an approved taxonomy."""
        graph = build_td_taxonomy_review_graph()
        task_store = MagicMock()
        task_store.wait_for_approval = AsyncMock(
            return_value={"batch_decision": "reject"}
        )
        event_bus = MagicMock()

        result = await run_td_hitl_checkpoint(
            graph,
            {"taxonomy": _make_taxonomy(2), "checkpoint": 1},
            thread_id="td-helper-timeout",
            task_store=task_store,
            event_bus=event_bus,
            task_id="task-timeout",
            stage_name="td_taxonomy_review",
        )
        assert result["batch_decision"] == "reject"
        assert result["approved_taxonomy"] == {}


# ═══════════════════════════════════════════════════════════════════════
# H8: Reparent to non-existent parent does not drop node
# ═══════════════════════════════════════════════════════════════════════


class TestReparentSafety:
    """H8: reparent to missing parent re-attaches at root instead of data loss."""

    def test_reparent_nonexistent_parent_preserves_node(self):
        taxonomy = _make_taxonomy_with_children()
        original_ids = {"root-1", "child-1a", "child-1b", "root-2"}
        edits = [{"op": "reparent", "node_id": "child-1a", "new_parent_id": "nonexistent"}]
        result = _process_taxonomy_edits(taxonomy, edits)
        # child-1a must still be in the tree — as a root node
        all_ids = _collect_all_ids(result["root_nodes"])
        assert original_ids == all_ids
        root_ids = {n["id"] for n in result["root_nodes"]}
        assert "child-1a" in root_ids  # re-attached at root

    def test_reparent_valid_parent_still_works(self):
        taxonomy = _make_taxonomy_with_children()
        edits = [{"op": "reparent", "node_id": "child-1a", "new_parent_id": "root-2"}]
        result = _process_taxonomy_edits(taxonomy, edits)
        # child-1a moved under root-2
        root2 = [n for n in result["root_nodes"] if n["id"] == "root-2"][0]
        assert len(root2["children"]) == 1
        assert root2["children"][0]["id"] == "child-1a"

    def test_reparent_to_root_null_parent(self):
        taxonomy = _make_taxonomy_with_children()
        edits = [{"op": "reparent", "node_id": "child-1b", "new_parent_id": None}]
        result = _process_taxonomy_edits(taxonomy, edits)
        root_ids = {n["id"] for n in result["root_nodes"]}
        assert "child-1b" in root_ids


# ═══════════════════════════════════════════════════════════════════════
# H9: Deep copy — edits do not mutate original state
# ═══════════════════════════════════════════════════════════════════════


class TestDeepCopyIsolation:
    """H9: taxonomy/matrix gate uses deep copy so edits don't mutate input."""

    def test_taxonomy_modify_does_not_mutate_original(self):
        graph = build_td_taxonomy_review_graph()
        taxonomy = _make_taxonomy(3)
        original_names = [n["name"] for n in taxonomy["root_nodes"]]
        config = {"configurable": {"thread_id": "td-h9-tax-1"}}

        result = graph.invoke(
            {"taxonomy": taxonomy, "checkpoint": 1}, config
        )
        assert result.get("__interrupt__")

        result = graph.invoke(
            Command(resume={
                "batch_decision": "modify",
                "user_edits": [
                    {"op": "rename", "node_id": "node-1", "new_name": "MUTATED"},
                    {"op": "add", "name": "Extra Node", "description": "should not leak"},
                ],
            }),
            config,
        )
        # The approved taxonomy has the edit
        approved = result["approved_taxonomy"]
        assert any(n["name"] == "MUTATED" for n in approved["root_nodes"])
        # The original taxonomy in the initial state was NOT mutated
        assert [n["name"] for n in taxonomy["root_nodes"]] == original_names
        assert len(taxonomy["root_nodes"]) == 3  # no extra node leaked

    def test_matrix_modify_does_not_mutate_original(self):
        graph = build_td_matrix_review_graph()
        matrix = _make_matrix(3)
        original_ids = [a["id"] for a in matrix["assignments"]]
        config = {"configurable": {"thread_id": "td-h9-mat-1"}}

        graph.invoke({"matrix": matrix, "checkpoint": 2}, config)
        result = graph.invoke(
            Command(resume={
                "batch_decision": "modify",
                "user_edits": [
                    {"op": "remove", "assignment_id": "assign-1"},
                ],
            }),
            config,
        )
        approved = result["approved_matrix"]
        assert len(approved["assignments"]) == 2
        # Original matrix was NOT mutated
        assert [a["id"] for a in matrix["assignments"]] == original_ids
        assert len(matrix["assignments"]) == 3


# ═══════════════════════════════════════════════════════════════════════
# H10: Tree metadata normalized after edits
# ═══════════════════════════════════════════════════════════════════════


class TestTreeMetadataNormalization:
    """H10: total_subdomains, max_depth, depth, sort_order correct after edits."""

    def test_add_updates_total_subdomains(self):
        taxonomy = _make_taxonomy(2)
        assert taxonomy.get("total_subdomains", 2) == 2
        edits = [
            {"op": "add", "name": "New Root", "description": ""},
            {"op": "add", "parent_id": "node-1", "name": "Child", "description": ""},
        ]
        result = _process_taxonomy_edits(taxonomy, edits)
        assert result["total_subdomains"] == 4  # 2 original + 2 added

    def test_delete_updates_total_subdomains(self):
        taxonomy = _make_taxonomy_with_children()
        edits = [{"op": "delete", "node_id": "child-1a"}]
        result = _process_taxonomy_edits(taxonomy, edits)
        # Original: root-1 (+ child-1a, child-1b), root-2 = 4 nodes; delete one = 3
        assert result["total_subdomains"] == 3

    def test_add_child_gets_correct_depth(self):
        taxonomy = _make_taxonomy(2)
        edits = [
            {"op": "add", "parent_id": "node-1", "name": "Child", "description": ""},
        ]
        result = _process_taxonomy_edits(taxonomy, edits)
        child = result["root_nodes"][0]["children"][0]
        assert child["depth"] == 1

    def test_reparent_updates_depth(self):
        taxonomy = _make_taxonomy_with_children()
        # child-1a starts at depth 1, reparent to root → depth 0
        edits = [{"op": "reparent", "node_id": "child-1a", "new_parent_id": None}]
        result = _process_taxonomy_edits(taxonomy, edits)
        reparented = [n for n in result["root_nodes"] if n["id"] == "child-1a"][0]
        assert reparented["depth"] == 0

    def test_max_depth_updated_after_nested_add(self):
        taxonomy = _make_taxonomy(1)
        # Add a child under node-1, then a grandchild under that child
        edits = [
            {"op": "add", "parent_id": "node-1", "name": "Child", "description": ""},
        ]
        result = _process_taxonomy_edits(taxonomy, edits)
        assert result["max_depth"] == 1

    def test_sort_order_recomputed(self):
        taxonomy = _make_taxonomy(3)
        # Delete node-2 (middle) — remaining roots should have sort_order 0, 1
        edits = [{"op": "delete", "node_id": "node-2"}]
        result = _process_taxonomy_edits(taxonomy, edits)
        orders = [n["sort_order"] for n in result["root_nodes"]]
        assert orders == [0, 1]

    def test_normalize_helper_standalone(self):
        """Direct test of _normalize_tree_metadata."""
        taxonomy = {
            "root_nodes": [
                {
                    "id": "a",
                    "depth": 99,
                    "sort_order": 99,
                    "children": [
                        {"id": "b", "depth": 99, "sort_order": 99, "children": []},
                    ],
                },
                {
                    "id": "c",
                    "depth": 99,
                    "sort_order": 99,
                    "children": [],
                },
            ],
            "total_subdomains": 0,
            "max_depth": 0,
        }
        _normalize_tree_metadata(taxonomy)
        assert taxonomy["total_subdomains"] == 3
        assert taxonomy["max_depth"] == 1
        assert taxonomy["root_nodes"][0]["depth"] == 0
        assert taxonomy["root_nodes"][0]["sort_order"] == 0
        assert taxonomy["root_nodes"][0]["children"][0]["depth"] == 1
        assert taxonomy["root_nodes"][0]["children"][0]["sort_order"] == 0
        assert taxonomy["root_nodes"][1]["depth"] == 0
        assert taxonomy["root_nodes"][1]["sort_order"] == 1

    def test_set_depths_recursive(self):
        """Direct test of _set_depths."""
        nodes = [
            {"id": "r", "depth": 99, "sort_order": 99, "children": [
                {"id": "c1", "depth": 99, "sort_order": 99, "children": [
                    {"id": "gc1", "depth": 99, "sort_order": 99, "children": []},
                ]},
                {"id": "c2", "depth": 99, "sort_order": 99, "children": []},
            ]},
        ]
        _set_depths(nodes, depth=0)
        assert nodes[0]["depth"] == 0
        assert nodes[0]["children"][0]["depth"] == 1
        assert nodes[0]["children"][0]["children"][0]["depth"] == 2
        assert nodes[0]["children"][1]["depth"] == 1

    def test_count_nodes_and_max_depth(self):
        nodes = [
            {"depth": 0, "children": [
                {"depth": 1, "children": [
                    {"depth": 2, "children": []},
                ]},
            ]},
            {"depth": 0, "children": []},
        ]
        total, max_d = _count_nodes_and_max_depth(nodes)
        assert total == 4
        assert max_d == 2

    def test_count_empty_tree(self):
        total, max_d = _count_nodes_and_max_depth([])
        assert total == 0
        assert max_d == 0


# ═══════════════════════════════════════════════════════════════════════
# Helper for collecting all IDs from a tree
# ═══════════════════════════════════════════════════════════════════════


def _collect_all_ids(nodes: list) -> set:
    """Recursively collect all node IDs."""
    ids = set()
    for n in nodes:
        ids.add(n["id"])
        ids.update(_collect_all_ids(n.get("children", [])))
    return ids
