from pathlib import Path
import json
import logging
import time
from typing import Any, Dict, List

from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from core.research.agents.persona_agent import run_persona_agent
from core.models.personas import PersonaResearchInput
from core.storage.supabase_mirror import mirror_persona_if_configured

_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # content-strategy-engine/


def _overwrite_virtual_path(vpath: str, content: str) -> None:
    target = (_PROJECT_ROOT / vpath.lstrip("/")).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


_LOG = logging.getLogger("content_engine.persona_graph")
if not _LOG.handlers:
    logging.basicConfig(level=logging.INFO)


def _log_event(event: str, data: Dict[str, Any]) -> None:
    payload = {
        "stage": "persona",
        "event": event,
        "timestamp_ms": int(time.time() * 1000),
        "data": data,
    }
    _LOG.info(json.dumps(payload))


def _agent(state: Dict[str, Any]) -> Dict[str, Any]:
    input_data: PersonaResearchInput = state["input"]
    revision_note = state.get("revision_note")
    _log_event("agent_start", {"company_name": input_data.company_name})
    result = run_persona_agent(input_data, revision_note=revision_note, use_draft_paths=True)
    return {**state, "agent_result": result, "revision_note": None}


def _approval_gate(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pause for human approval. Resume with {"approval_decision": "approve" | "revise" | "reject", "revision_note": "..."}.
    If state.auto_approve is True, skip interrupt (for testing).
    """
    if state.get("auto_approve"):
        return {**state, "approval_decision": "approve"}
    agent_result: Dict[str, Any] = state.get("agent_result", {})
    written_paths: List[str] = agent_result.get("written_paths") or []  # draft paths
    notes = agent_result.get("notes", "")
    return interrupt(
        {
            "status": "pending_approval",
            "draft_paths": written_paths,
            "notes": notes,
        }
    )


def _route(state: Dict[str, Any]) -> Dict[str, Any]:
    # decision handled via conditional edges
    return state


def _write_and_mirror(state: Dict[str, Any]) -> Dict[str, Any]:
    """On approval: promote draft artifacts to permanent paths and mirror to Supabase."""
    input_data: PersonaResearchInput = state["input"]
    agent_result: Dict[str, Any] = state.get("agent_result", {})
    draft_paths: List[str] = agent_result.get("written_paths") or []

    mirrored: List[Dict[str, Any]] = []
    written_paths: List[str] = []

    for draft_path in draft_paths:
        # Read draft from disk (already relocated to artifacts/)
        draft_disk = (_PROJECT_ROOT / draft_path.lstrip("/")).resolve()
        if not draft_disk.exists():
            continue
        md = draft_disk.read_text(encoding="utf-8")
        if not md.strip():
            continue
        # Promote to permanent path (strip .draft from path)
        permanent_path = draft_path.replace(".draft.md", ".md")
        _overwrite_virtual_path(permanent_path, md)
        written_paths.append(permanent_path)
        _log_event("promote", {"from": draft_path, "to": permanent_path})

        mirror_res = mirror_persona_if_configured(
            company_id=input_data.company_id,
            company_name=input_data.company_name,
            domain=input_data.domain,
            artifact_path=permanent_path,
            markdown=md,
        )
        if mirror_res:
            mirrored.append(mirror_res)

    return {**state, "written_paths": written_paths, "mirrored": mirrored}


def build_graph():
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
    return graph.compile()
