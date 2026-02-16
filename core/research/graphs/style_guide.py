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
    input_data: StyleGuideResearchInput = state["input"]
    revision_note = state.get("revision_note")
    _log_event("agent_start", {"company_name": input_data.company_name})
    result = run_style_guide_agent(input_data, revision_note=revision_note, use_draft_paths=True)
    return {**state, "agent_result": result}


def _approval_gate(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Human-in-the-loop gate. Pause the graph and surface the draft path and notes.
    Resume with {"approval_decision": "approve" | "revise" | "reject", "revision_note": "..."}.
    If state.auto_approve is True, skip interrupt (for testing).
    """
    if state.get("auto_approve"):
        return {**state, "approval_decision": "approve"}
    agent_result: Dict[str, Any] = state.get("agent_result", {})
    draft_paths: List[str] = agent_result.get("written_paths") or []
    notes = agent_result.get("notes", "")
    return interrupt(
        {
            "status": "pending_approval",
            "draft_paths": draft_paths,
            "notes": notes,
        }
    )


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
    input_data: StyleGuideResearchInput = state["input"]
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

    return {**state, "written_paths": written_paths, "mirrored": mirrored}


def build_graph(checkpointer=None):
    graph = StateGraph(dict)
    graph.add_node("agent", _agent)
    graph.add_node("approval_gate", _approval_gate)
    graph.add_node("route", _route)
    graph.add_node("write_and_mirror", _write_and_mirror)
    graph.set_entry_point("agent")
    graph.add_edge("agent", "approval_gate")
    graph.add_edge("approval_gate", "route")
    graph.add_conditional_edges(
        "route",
        lambda state: (state.get("approval_decision") or "").lower(),
        {
            "approve": "write_and_mirror",
            "revise": "agent",
            "reject": END,
        },
    )
    graph.add_edge("write_and_mirror", END)
    return graph.compile(checkpointer=checkpointer)
