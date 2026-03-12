"""Topic Discovery HITL sub-graphs — Taxonomy Review + Matrix Review.

Two LangGraph graphs using interrupt/resume for human-in-the-loop:
- HITL-1: Taxonomy approval (approve/modify/retry)
- HITL-2: Matrix approval (approve/modify)

Mirrors build_vsg_author_review_graph() from voice_style_guide/graph.py.
"""
from __future__ import annotations

import asyncio
import copy
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from typing_extensions import TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from core.shared_tools.task_status import TaskStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Checkpointer helper
# ---------------------------------------------------------------------------


def _resolve_checkpointer(checkpointer: Any) -> BaseCheckpointSaver:
    """Return checkpointer if valid, otherwise default to MemorySaver."""
    if isinstance(checkpointer, BaseCheckpointSaver):
        return checkpointer
    return MemorySaver()


# ---------------------------------------------------------------------------
# Interrupt helpers (5th copy — defer shared refactor)
# ---------------------------------------------------------------------------


def _has_interrupt(result: Dict[str, Any]) -> bool:
    """Check if the graph result contains an interrupt."""
    return bool(result.get("__interrupt__"))


def _get_interrupt_value(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the interrupt payload from the graph result."""
    interrupts = result.get("__interrupt__", [])
    if interrupts and len(interrupts) > 0:
        first = interrupts[0]
        return first.value if hasattr(first, "value") else first
    return {}


# ═══════════════════════════════════════════════════════════════════════
# HITL-1: Taxonomy Review
# ═══════════════════════════════════════════════════════════════════════


class TDTaxonomyReviewState(TypedDict, total=False):
    """State for HITL-1: taxonomy approval."""

    taxonomy: dict  # Serialized TaxonomyTree
    coverage_metrics: dict  # Serialized CaptureRecaptureResult
    checkpoint: int  # Always 1
    auto_approve: bool
    presented_at: int  # Unix timestamp
    # Resume values:
    batch_decision: str  # "approve" | "modify" | "retry"
    user_edits: list  # List of edit operations
    user_feedback: str  # Natural language feedback for retry
    # Computed:
    approved_taxonomy: dict  # Final approved taxonomy


def _taxonomy_present(state: Dict[str, Any]) -> Dict[str, Any]:
    """Add presentation timestamp."""
    return {**state, "presented_at": int(time.time())}


def _process_taxonomy_edits(
    taxonomy: Dict[str, Any],
    edits: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Apply HITL edits to a serialized taxonomy.

    Supported edit operations:
    - {"op": "add", "parent_id": str|null, "name": str, "description": str}
    - {"op": "delete", "node_id": str}
    - {"op": "rename", "node_id": str, "new_name": str}
    - {"op": "reparent", "node_id": str, "new_parent_id": str|null}
    """
    if not edits:
        return taxonomy

    root_nodes = taxonomy.get("root_nodes", [])

    for edit in edits:
        op = edit.get("op", "")
        if op == "add":
            new_node = {
                "id": str(uuid.uuid4()),
                "name": edit.get("name", ""),
                "description": edit.get("description", ""),
                "is_manually_added": True,
                "depth": 0,
                "children": [],
                "source_provenance": {},
                "confidence": 1.0,
                "sort_order": len(root_nodes),
            }
            parent_id = edit.get("parent_id")
            if parent_id:
                _add_child_to_node(root_nodes, parent_id, new_node)
            else:
                root_nodes.append(new_node)
        elif op == "delete":
            node_id = edit.get("node_id", "")
            root_nodes = _remove_node(root_nodes, node_id)
        elif op == "rename":
            node_id = edit.get("node_id", "")
            new_name = edit.get("new_name", "")
            _rename_node(root_nodes, node_id, new_name)
        elif op == "reparent":
            node_id = edit.get("node_id", "")
            new_parent_id = edit.get("new_parent_id")
            node = _extract_node(root_nodes, node_id)
            if node:
                root_nodes = _remove_node(root_nodes, node_id)
                if new_parent_id:
                    added = _add_child_to_node(root_nodes, new_parent_id, node)
                    if not added:
                        # Target parent not found — re-attach at root to avoid data loss
                        logger.warning(
                            "Reparent: target parent %s not found, attaching %s at root",
                            new_parent_id, node_id,
                        )
                        root_nodes.append(node)
                else:
                    root_nodes.append(node)

    taxonomy["root_nodes"] = root_nodes
    _normalize_tree_metadata(taxonomy)
    return taxonomy


def _add_child_to_node(
    nodes: List[Dict[str, Any]], parent_id: str, child: Dict[str, Any]
) -> bool:
    """Recursively find parent and add child. Returns True if found."""
    for node in nodes:
        if node.get("id") == parent_id:
            node.setdefault("children", []).append(child)
            return True
        if _add_child_to_node(node.get("children", []), parent_id, child):
            return True
    return False


def _remove_node(
    nodes: List[Dict[str, Any]], node_id: str
) -> List[Dict[str, Any]]:
    """Remove a node by ID from the tree. Returns filtered list."""
    result = []
    for node in nodes:
        if node.get("id") == node_id:
            continue
        node["children"] = _remove_node(node.get("children", []), node_id)
        result.append(node)
    return result


def _rename_node(nodes: List[Dict[str, Any]], node_id: str, new_name: str) -> None:
    """Rename a node by ID in the tree."""
    for node in nodes:
        if node.get("id") == node_id:
            node["name"] = new_name
            return
        _rename_node(node.get("children", []), node_id, new_name)


def _extract_node(
    nodes: List[Dict[str, Any]], node_id: str
) -> Optional[Dict[str, Any]]:
    """Find and return a node by ID (without removing it)."""
    for node in nodes:
        if node.get("id") == node_id:
            return node
        found = _extract_node(node.get("children", []), node_id)
        if found:
            return found
    return None


def _set_depths(nodes: List[Dict[str, Any]], depth: int = 0) -> None:
    """Recursively set correct depth and sort_order on every node."""
    for i, node in enumerate(nodes):
        node["depth"] = depth
        node["sort_order"] = i
        _set_depths(node.get("children", []), depth + 1)


def _count_nodes_and_max_depth(
    nodes: List[Dict[str, Any]],
) -> tuple:
    """Count total nodes and max depth in a serialized tree."""
    if not nodes:
        return 0, 0
    total = 0
    max_d = 0
    for node in nodes:
        total += 1
        max_d = max(max_d, node.get("depth", 0))
        child_total, child_max = _count_nodes_and_max_depth(
            node.get("children", [])
        )
        total += child_total
        max_d = max(max_d, child_max)
    return total, max_d


def _normalize_tree_metadata(taxonomy: Dict[str, Any]) -> None:
    """Recompute depths, sort_order, total_subdomains, max_depth after edits."""
    root_nodes = taxonomy.get("root_nodes", [])
    _set_depths(root_nodes, depth=0)
    total, max_depth = _count_nodes_and_max_depth(root_nodes)
    taxonomy["total_subdomains"] = total
    taxonomy["max_depth"] = max_depth


def _taxonomy_gate(state: Dict[str, Any]) -> Dict[str, Any]:
    """Pause for human taxonomy review via interrupt().

    Auto-approve returns taxonomy as-is. Manual mode fires interrupt.
    """
    taxonomy = state.get("taxonomy", {})
    coverage = state.get("coverage_metrics", {})

    if state.get("auto_approve"):
        return {
            **state,
            "batch_decision": "approve",
            "approved_taxonomy": taxonomy,
        }

    resume = interrupt(
        {
            "status": "pending_taxonomy_approval",
            "stage": "td_taxonomy_review",
            "checkpoint": state.get("checkpoint", 1),
            "taxonomy": taxonomy,
            "coverage_metrics": coverage,
        }
    )

    if not isinstance(resume, dict):
        resume = {}

    decision = resume.get("batch_decision", "approve")
    user_edits = resume.get("user_edits", [])
    user_feedback = resume.get("user_feedback", "")

    if decision == "modify" and user_edits:
        taxonomy = _process_taxonomy_edits(copy.deepcopy(taxonomy), user_edits)

    approved_taxonomy = taxonomy if decision in ("approve", "modify") else {}

    return {
        **state,
        "batch_decision": decision,
        "user_edits": user_edits,
        "user_feedback": user_feedback,
        "approved_taxonomy": approved_taxonomy,
    }


def _taxonomy_route(state: Dict[str, Any]) -> str:
    """Route based on taxonomy decision."""
    decision = state.get("batch_decision", "approve")
    if decision == "retry":
        return "retry"
    return "done"


def build_td_taxonomy_review_graph(
    checkpointer: Optional[Any] = None,
) -> Any:
    """Build the Taxonomy Review sub-graph (HITL-1).

    Nodes: present → gate → route → END
    """
    graph = StateGraph(TDTaxonomyReviewState)

    graph.add_node("present", _taxonomy_present)
    graph.add_node("gate", _taxonomy_gate)

    graph.set_entry_point("present")
    graph.add_edge("present", "gate")
    graph.add_conditional_edges(
        "gate",
        _taxonomy_route,
        {
            "done": END,
            "retry": END,
        },
    )

    return graph.compile(checkpointer=_resolve_checkpointer(checkpointer))


# ═══════════════════════════════════════════════════════════════════════
# HITL-2: Matrix Review
# ═══════════════════════════════════════════════════════════════════════


class TDMatrixReviewState(TypedDict, total=False):
    """State for HITL-2: matrix approval."""

    matrix: dict  # Serialized TopicAssignmentMatrix
    checkpoint: int  # Always 2
    auto_approve: bool
    presented_at: int  # Unix timestamp
    # Resume values:
    batch_decision: str  # "approve" | "modify"
    user_edits: list  # List of edit operations
    # Computed:
    approved_matrix: dict  # Final approved matrix


def _matrix_present(state: Dict[str, Any]) -> Dict[str, Any]:
    """Add presentation timestamp."""
    return {**state, "presented_at": int(time.time())}


def _process_matrix_edits(
    matrix: Dict[str, Any],
    edits: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Apply HITL edits to a serialized matrix.

    Supported edit operations:
    - {"op": "adjust_priority", "assignment_id": str, "new_priority": float}
    - {"op": "remove", "assignment_id": str}
    - {"op": "add", "topic_text": str, "subdomain_name": str, ...}
    """
    if not edits:
        return matrix

    assignments = matrix.get("assignments", [])

    for edit in edits:
        op = edit.get("op", "")
        if op == "adjust_priority":
            aid = edit.get("assignment_id", "")
            new_priority = edit.get("new_priority", 0.5)
            for a in assignments:
                if a.get("id") == aid:
                    a["priority_score"] = new_priority
                    break
        elif op == "remove":
            aid = edit.get("assignment_id", "")
            assignments = [a for a in assignments if a.get("id") != aid]
        elif op == "add":
            new_assignment = {
                "id": str(uuid.uuid4()),
                "topic_text": edit.get("topic_text", ""),
                "subdomain_name": edit.get("subdomain_name", ""),
                "buyer_stage": edit.get("buyer_stage", "tofu"),
                "intent_type": edit.get("intent_type", "informational"),
                "audience_segment": edit.get("audience_segment", ""),
                "audience_segment_type": edit.get("audience_segment_type", "individual_persona"),
                "relevance": "relevant",
                "priority_score": edit.get("priority_score", 0.5),
                "status": "not_started",
                "is_manually_added": True,
                "priority_factors": {},
                "metadata": {},
            }
            assignments.append(new_assignment)

    matrix["assignments"] = assignments
    matrix["total_assignments"] = len(assignments)
    return matrix


def _matrix_gate(state: Dict[str, Any]) -> Dict[str, Any]:
    """Pause for human matrix review via interrupt()."""
    matrix = state.get("matrix", {})

    if state.get("auto_approve"):
        return {
            **state,
            "batch_decision": "approve",
            "approved_matrix": matrix,
        }

    resume = interrupt(
        {
            "status": "pending_matrix_approval",
            "stage": "td_matrix_review",
            "checkpoint": state.get("checkpoint", 2),
            "matrix": matrix,
        }
    )

    if not isinstance(resume, dict):
        resume = {}

    decision = resume.get("batch_decision", "approve")
    user_edits = resume.get("user_edits", [])

    if decision == "modify" and user_edits:
        matrix = _process_matrix_edits(copy.deepcopy(matrix), user_edits)

    approved_matrix = matrix if decision in ("approve", "modify") else {}

    return {
        **state,
        "batch_decision": decision,
        "user_edits": user_edits,
        "approved_matrix": approved_matrix,
    }


def _matrix_route(state: Dict[str, Any]) -> str:
    """Route — always ends (no retry for matrix)."""
    return "done"


def build_td_matrix_review_graph(
    checkpointer: Optional[Any] = None,
) -> Any:
    """Build the Matrix Review sub-graph (HITL-2).

    Nodes: present → gate → route → END
    """
    graph = StateGraph(TDMatrixReviewState)

    graph.add_node("present", _matrix_present)
    graph.add_node("gate", _matrix_gate)

    graph.set_entry_point("present")
    graph.add_edge("present", "gate")
    graph.add_conditional_edges(
        "gate",
        _matrix_route,
        {
            "done": END,
        },
    )

    return graph.compile(checkpointer=_resolve_checkpointer(checkpointer))


# ═══════════════════════════════════════════════════════════════════════
# HITL-1.5: Subdomain Selection (between scoring and expansion)
# ═══════════════════════════════════════════════════════════════════════


class TDSubdomainSelectionState(TypedDict, total=False):
    """State for HITL-1.5: subdomain selection after scoring."""

    scored_subdomains: dict  # Serialized ScoredSubdomainList
    persona_affinity: dict  # Serialized PersonaAffinityIndex
    checkpoint: int  # Always 3
    auto_approve: bool
    top_n: int  # Default top-N for auto-approve
    presented_at: int  # Unix timestamp
    # Resume values:
    selection_mode: str  # "manual" | "top_n"
    selected_subdomain_ids: list  # List of subdomain IDs
    persona_filter: str  # Optional persona_id filter
    # Computed:
    final_subdomain_ids: list  # IDs to expand


def _subdomain_selection_present(state: Dict[str, Any]) -> Dict[str, Any]:
    """Add presentation timestamp."""
    return {**state, "presented_at": int(time.time())}


def _subdomain_selection_gate(state: Dict[str, Any]) -> Dict[str, Any]:
    """Pause for human subdomain selection via interrupt().

    Auto-approve selects top-N by composite score.
    Manual mode fires interrupt for user selection.
    """
    scored = state.get("scored_subdomains", {})
    top_n = state.get("top_n", 10)
    persona_affinity = state.get("persona_affinity", {})

    if state.get("auto_approve"):
        # Select top-N subdomain IDs by score
        scores = scored.get("scores", [])
        sorted_scores = sorted(
            scores, key=lambda s: s.get("composite_score", 0.0), reverse=True
        )
        selected_ids = [s.get("subdomain_id", "") for s in sorted_scores[:top_n]]
        return {
            **state,
            "selection_mode": "top_n",
            "selected_subdomain_ids": selected_ids,
            "final_subdomain_ids": selected_ids,
        }

    resume = interrupt(
        {
            "status": "pending_subdomain_selection",
            "stage": "td_subdomain_selection",
            "checkpoint": state.get("checkpoint", 3),
            "scored_subdomains": scored,
            "persona_affinity": persona_affinity,
            "top_n_default": top_n,
        }
    )

    if not isinstance(resume, dict):
        resume = {}

    selection_mode = resume.get("selection_mode", "top_n")
    selected_ids = resume.get("selected_subdomain_ids", [])
    persona_filter = resume.get("persona_filter", "")

    if selection_mode == "top_n":
        # User chose top-N but may have changed N
        user_n = resume.get("top_n", top_n)
        scores = scored.get("scores", [])

        # Apply persona filter if set
        if persona_filter:
            entries = persona_affinity.get("persona_entries", {})
            persona_subs = entries.get(persona_filter, [])
            persona_sub_ids = {
                e.get("subdomain_id", "")
                for e in persona_subs
                if e.get("affinity_score", 0.0) > 0.3
            }
            scores = [
                s for s in scores
                if s.get("subdomain_id", "") in persona_sub_ids
            ]

        sorted_scores = sorted(
            scores, key=lambda s: s.get("composite_score", 0.0), reverse=True
        )
        selected_ids = [s.get("subdomain_id", "") for s in sorted_scores[:user_n]]

    # Manual selection — use IDs as provided
    final_ids = selected_ids if selected_ids else []

    return {
        **state,
        "selection_mode": selection_mode,
        "selected_subdomain_ids": selected_ids,
        "persona_filter": persona_filter,
        "final_subdomain_ids": final_ids,
    }


def _subdomain_selection_route(state: Dict[str, Any]) -> str:
    """Route — always ends (no retry for subdomain selection)."""
    return "done"


def build_td_subdomain_selection_graph(
    checkpointer: Optional[Any] = None,
) -> Any:
    """Build the Subdomain Selection sub-graph (HITL-1.5).

    Nodes: present → gate → route → END
    """
    graph = StateGraph(TDSubdomainSelectionState)

    graph.add_node("present", _subdomain_selection_present)
    graph.add_node("gate", _subdomain_selection_gate)

    graph.set_entry_point("present")
    graph.add_edge("present", "gate")
    graph.add_conditional_edges(
        "gate",
        _subdomain_selection_route,
        {
            "done": END,
        },
    )

    return graph.compile(checkpointer=_resolve_checkpointer(checkpointer))


# ═══════════════════════════════════════════════════════════════════════
# Graph Invocation Helper
# ═══════════════════════════════════════════════════════════════════════


async def run_td_hitl_checkpoint(
    graph: Any,
    initial_state: Dict[str, Any],
    thread_id: str,
    task_store: Optional[Any] = None,
    event_bus: Optional[Any] = None,
    task_id: Optional[str] = None,
    stage_name: str = "td_hitl",
) -> Dict[str, Any]:
    """Run a TD HITL checkpoint graph, handling interrupt/resume.

    Mirrors run_kb_hitl_checkpoint() from knowledge_base/graph.py.
    """
    config = {"configurable": {"thread_id": thread_id}}

    result = await asyncio.to_thread(graph.invoke, initial_state, config)

    while _has_interrupt(result):
        interrupt_val = _get_interrupt_value(result)

        checkpoint_nonce = str(uuid.uuid4())

        logger.info(
            "TD HITL %s: interrupt at stage=%s, status=%s",
            stage_name,
            interrupt_val.get("stage", "unknown"),
            interrupt_val.get("status", "unknown"),
        )

        # Publish SSE event (sync)
        if event_bus and task_id:
            event_bus.publish(
                task_id,
                "pending_approval",
                {
                    "stage": stage_name,
                    "checkpoint_nonce": checkpoint_nonce,
                    **interrupt_val,
                },
            )

        # Update task store with pending status (sync)
        if task_store and task_id:
            task_store.update_task(
                task_id,
                status=TaskStatus.PENDING_APPROVAL.value,
                approval_payload={
                    "stage": stage_name,
                    "checkpoint_nonce": checkpoint_nonce,
                    **interrupt_val,
                },
            )

        # Wait for human decision (async)
        if task_store and task_id:
            approval = await task_store.wait_for_approval(task_id)

            # Reset status to RUNNING and clear approval_payload
            task_store.update_task(
                task_id,
                status=TaskStatus.RUNNING.value,
                current_step=stage_name,
                approval_payload=None,
            )
        else:
            # CLI/auto mode fallback
            logger.warning("No task_store for TD HITL %s — auto-approving", stage_name)
            approval = {"batch_decision": "approve"}

        # Publish approval received event (sync)
        if event_bus and task_id:
            event_bus.publish(
                task_id,
                "approval_received",
                {
                    "stage": stage_name,
                    "decision": approval.get("batch_decision", "unknown"),
                },
            )

        result = await asyncio.to_thread(
            graph.invoke, Command(resume=approval), config
        )

    return result
