from pathlib import Path
import json
import logging
import time
from typing import Any, Dict, List

from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from core.research.agents.base import get_filesystem_backend
from core.research.agents.style_guide_agent import run_style_guide_agent
from core.models.style_guide import StyleGuideResearchInput
from core.storage.supabase_mirror import mirror_styleguide_if_configured

_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # content-strategy-engine/


def _overwrite_virtual_path(vpath: str, content: str) -> None:
    target = (_PROJECT_ROOT / vpath.lstrip("/")).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


_LOG = logging.getLogger("content_engine.style_graph")
if not _LOG.handlers:
    logging.basicConfig(level=logging.INFO)


def _log_event(event: str, data: Dict[str, Any]) -> None:
    payload = {
        "stage": "style",
        "event": event,
        "timestamp_ms": int(time.time() * 1000),
        "data": data,
    }
    _LOG.info(json.dumps(payload))


def _agent(state: Dict[str, Any]) -> Dict[str, Any]:
    raw = state["input"]
    input_data = StyleGuideResearchInput(**raw) if isinstance(raw, dict) else raw
    revision_note = state.get("revision_note")
    _log_event("agent_start", {"company_name": input_data.company_name})
    result = run_style_guide_agent(input_data, revision_note=revision_note, use_draft_paths=True)
    return {**state, "agent_result": result}


def _approval_gate(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Human-in-the-loop gate. Pause the graph and surface the draft path and notes.
    Resume with {"approval_decision": "approve" | "revise" | "reject", "revision_note": "..."}.
    If state.auto_approve is True, skip interrupt (for testing).

    LangGraph >=1.0: interrupt() returns the resume value on the second execution
    of this node. We must merge it into state because StateGraph(dict) replaces
    state with the node's return value.
    """
    if state.get("auto_approve"):
        return {**state, "approval_decision": "approve"}
    agent_result: Dict[str, Any] = state.get("agent_result", {})
    draft_paths: List[str] = agent_result.get("written_paths") or []
    notes = agent_result.get("notes", "")
    resume_value = interrupt(
        {
            "status": "pending_approval",
            "draft_paths": draft_paths,
            "notes": notes,
        }
    )
    # Merge resume value into full state to preserve input, agent_result, etc.
    if isinstance(resume_value, dict):
        return {**state, **resume_value}
    return {**state, "approval_decision": str(resume_value)}


def _route(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decide next step based on human decision.
    approval_decision: "approve" -> mirror
                       "revise"  -> re-run agent with revision_note
                       "reject"  -> end without mirroring
    """
    return state


def _write_and_mirror(state: Dict[str, Any]) -> Dict[str, Any]:
    """On approval: promote draft artifacts to permanent path and mirror to Supabase."""
    raw = state["input"]
    input_data = StyleGuideResearchInput(**raw) if isinstance(raw, dict) else raw
    agent_result: Dict[str, Any] = state.get("agent_result", {})
    draft_paths: List[str] = agent_result.get("written_paths") or []

    backend = get_filesystem_backend()
    mirrored: List[Dict[str, Any]] = []
    written_paths: List[str] = []

    for draft_path in draft_paths:
        md = backend.read(draft_path, offset=0, limit=200000)
        if not md or not md.strip():
            continue
        permanent_path = draft_path.replace(".draft.md", ".md")
        result = backend.write(permanent_path, md)
        if getattr(result, "error", None):
            err_str = str(result.error)
            if "already exists" in err_str:
                try:
                    _overwrite_virtual_path(permanent_path, md)
                except Exception as exc:
                    _log_event("write_error", {"error": str(exc), "path": permanent_path})
                    raise RuntimeError(f"Failed to write style guide artifact: {exc}") from exc
            else:
                _log_event("write_error", {"error": str(result.error), "path": permanent_path})
                raise RuntimeError(f"Failed to write style guide artifact: {result.error}")
        written_paths.append(permanent_path)
        mirror_res = mirror_styleguide_if_configured(
            company_id=input_data.company_id,
            company_name=input_data.company_name,
            domain=input_data.domain,
            artifact_path=permanent_path,
            markdown=md,
        )
        if mirror_res:
            mirrored.append(mirror_res)

        # Clean up draft file after promotion
        draft_disk = (_PROJECT_ROOT / draft_path.lstrip("/")).resolve()
        if draft_disk.exists():
            try:
                draft_disk.unlink()
                _log_event("draft_cleanup", {"draft_path": draft_path})
            except Exception as e:
                _log_event("draft_cleanup_warning", {"error": str(e), "draft_path": draft_path})

    if not written_paths:
        _log_event("promotion_warning", {
            "message": "No draft files found on disk to promote",
            "draft_paths": draft_paths,
        })

    return {**state, "written_paths": written_paths, "mirrored": mirrored}


def _cleanup_drafts(state: Dict[str, Any]) -> Dict[str, Any]:
    """On reject: delete orphaned .draft.md files from disk."""
    agent_result: Dict[str, Any] = state.get("agent_result", {})
    draft_paths: List[str] = agent_result.get("written_paths") or []

    for draft_path in draft_paths:
        draft_disk = (_PROJECT_ROOT / draft_path.lstrip("/")).resolve()
        if draft_disk.exists():
            try:
                draft_disk.unlink()
                _log_event("reject_cleanup", {"draft_path": draft_path})
            except Exception as e:
                _log_event("reject_cleanup_warning", {"error": str(e), "draft_path": draft_path})

    return {**state, "approval_decision": "reject"}


def build_graph(checkpointer=None):
    graph = StateGraph(dict)
    graph.add_node("agent", _agent)
    graph.add_node("approval_gate", _approval_gate)
    graph.add_node("route", _route)
    graph.add_node("write_and_mirror", _write_and_mirror)
    graph.add_node("cleanup_drafts", _cleanup_drafts)
    graph.set_entry_point("agent")
    graph.add_edge("agent", "approval_gate")
    graph.add_edge("approval_gate", "route")
    graph.add_conditional_edges(
        "route",
        lambda state: (state.get("approval_decision") or "").lower(),
        {
            "approve": "write_and_mirror",
            "revise": "agent",
            "reject": "cleanup_drafts",
        },
    )
    graph.add_edge("write_and_mirror", END)
    graph.add_edge("cleanup_drafts", END)
    return graph.compile(checkpointer=checkpointer)
