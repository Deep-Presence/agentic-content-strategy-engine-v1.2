import json
import logging
import time
from typing import Any, Dict, List, Optional

from langgraph.checkpoint.memory import MemorySaver

from core.research.graphs.company_research import build_graph as build_company_graph
from core.research.graphs.persona_research import build_graph as build_persona_graph
from core.research.graphs.style_guide import build_graph as build_style_graph
from core.reddit_hil.graph import build_graph as build_reddit_hil_graph
from core.models.artifacts import CompanyResearchInput
from core.models.personas import PersonaResearchInput
from core.models.reddit_hil import RedditMonitorInput
from core.models.style_guide import StyleGuideResearchInput


_LOG = logging.getLogger("content_engine.pipeline")
if not _LOG.handlers:
    logging.basicConfig(level=logging.INFO)


def _log_event(stage: str, event: str, data: Dict[str, Any]) -> None:
    payload = {
        "stage": stage,
        "event": event,
        "timestamp_ms": int(time.time() * 1000),
        "data": data,
    }
    _LOG.info(json.dumps(payload))


def _has_interrupt(result: Dict[str, Any]) -> bool:
    """Check if a LangGraph >=1.0 invoke result contains an interrupt.

    LangGraph >=1.0 returns __interrupt__ in the result dict — it does NOT
    raise GraphInterrupt.
    """
    return bool(result.get("__interrupt__"))


def _get_interrupt_value(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the first interrupt payload from a LangGraph invoke result."""
    interrupts = result.get("__interrupt__", [])
    if interrupts and hasattr(interrupts[0], "value"):
        return interrupts[0].value
    return {}


def _invoke_graph(build_fn, state: Dict[str, Any], stage_name: str = "unknown") -> Dict[str, Any]:
    """Invoke a research graph with checkpointer support.

    Uses MemorySaver so interrupt() + Command(resume=...) works.
    When auto_approve=True in state, the approval gate skips the interrupt
    and graphs complete without pausing.
    """
    checkpointer = MemorySaver()
    app = build_fn(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": f"pipeline-{stage_name}"}}
    try:
        result = app.invoke(state, config)
        if _has_interrupt(result):
            interrupt_values = _get_interrupt_value(result)
            return {"status": "interrupt", "values": interrupt_values}
        return result
    except Exception as exc:
        _log_event("pipeline", "graph_error", {"error": str(exc)})
        raise


def run_company_stage(
    company_input: CompanyResearchInput,
    *,
    auto_approve: bool = False,
) -> Dict[str, Any]:
    return _invoke_graph(
        build_company_graph,
        {"input": company_input, "auto_approve": auto_approve},
        stage_name="company",
    )


def run_persona_stage(
    persona_input: PersonaResearchInput,
    *,
    auto_approve: bool = False,
) -> Dict[str, Any]:
    return _invoke_graph(
        build_persona_graph,
        {"input": persona_input, "auto_approve": auto_approve},
        stage_name="persona",
    )


def run_style_stage(
    style_input: StyleGuideResearchInput,
    *,
    auto_approve: bool = False,
) -> Dict[str, Any]:
    return _invoke_graph(
        build_style_graph,
        {"input": style_input, "auto_approve": auto_approve},
        stage_name="style",
    )


def run_reddit_hil_stage(reddit_input: RedditMonitorInput) -> Dict[str, Any]:
    return _invoke_graph(
        build_reddit_hil_graph,
        {"input": reddit_input},
        stage_name="reddit_hil",
    )


def run_pipeline(
    *,
    company_input: CompanyResearchInput,
    persona_input: Optional[PersonaResearchInput] = None,
    style_input: Optional[StyleGuideResearchInput] = None,
    auto_approve: bool = False,
) -> Dict[str, Any]:
    """
    Pipeline flow: company_research -> persona_research -> style_guide.

    Each stage follows: agent -> temporary draft written -> approval_gate -> route ->
      (write_and_mirror | agent | END).

    On approve at company stage: write artifact, mirror, then run persona_research.
    On approve at persona stage: write artifacts, mirror, then run style_guide.
    On approve at style stage: write artifact, mirror, then complete.

    If any stage interrupts for approval, returns immediately with status=interrupt,
    stage=<name>, values=<payload>. Caller should resume that stage with
    approval_decision (approve|revise|reject) and optional revision_note.
    """
    # Company stage
    _log_event("company", "start", {"auto_approve": auto_approve})
    company_res = run_company_stage(company_input, auto_approve=auto_approve)
    if company_res.get("status") == "interrupt":
        _log_event("company", "interrupt", {"values": company_res.get("values", {})})
        return {"stage": "company", **company_res}
    company_output_path = company_res.get("output_path")
    _log_event("company", "complete", {"output_path": company_output_path})

    # Persona stage (runs after company approves)
    if persona_input:
        persona_input = persona_input.model_copy(update={"company_context_path": company_output_path})
        _log_event("persona", "start", {"auto_approve": auto_approve})
        persona_res = run_persona_stage(persona_input, auto_approve=auto_approve)
        if persona_res.get("status") == "interrupt":
            _log_event("persona", "interrupt", {"values": persona_res.get("values", {})})
            return {"stage": "persona", **persona_res}
        # After write_and_mirror, written_paths are permanent paths (not drafts)
        persona_paths = persona_res.get("written_paths") or []
        _log_event("persona", "complete", {"written_paths": persona_paths})
    else:
        persona_paths = []

    # Style stage
    if style_input:
        style_input = style_input.model_copy(
            update={
                "company_context_path": company_output_path,
                "persona_paths": style_input.persona_paths or persona_paths,
            }
        )
        _log_event("style", "start", {"auto_approve": auto_approve})
        style_res = run_style_stage(style_input, auto_approve=auto_approve)
        if style_res.get("status") == "interrupt":
            _log_event("style", "interrupt", {"values": style_res.get("values", {})})
            return {"stage": "style", **style_res}
        _log_event("style", "complete", {"status": style_res.get("status")})
    else:
        style_res = {}

    return {
        "stage": "complete",
        "company": company_res,
        "personas": persona_res if persona_input else None,
        "style": style_res if style_input else None,
    }
