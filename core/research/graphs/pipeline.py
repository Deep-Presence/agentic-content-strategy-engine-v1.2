import json
import logging
import time
from typing import Any, Dict, List, Optional

from langgraph.errors import GraphInterrupt

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


def _invoke_graph(app, state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return app.invoke(state)
    except GraphInterrupt as gi:
        # Surface interrupt payload so caller/front-end can resume
        return {"status": "interrupt", "values": gi.values}
    except Exception as exc:
        _log_event("pipeline", "graph_error", {"error": str(exc)})
        raise


def run_company_stage(
    company_input: CompanyResearchInput,
    *,
    auto_approve: bool = False,
) -> Dict[str, Any]:
    app = build_company_graph()
    return _invoke_graph(app, {"input": company_input, "auto_approve": auto_approve})


def run_persona_stage(
    persona_input: PersonaResearchInput,
    *,
    auto_approve: bool = False,
) -> Dict[str, Any]:
    app = build_persona_graph()
    return _invoke_graph(app, {"input": persona_input, "auto_approve": auto_approve})


def run_style_stage(
    style_input: StyleGuideResearchInput,
    *,
    auto_approve: bool = False,
) -> Dict[str, Any]:
    app = build_style_graph()
    return _invoke_graph(app, {"input": style_input, "auto_approve": auto_approve})


def run_reddit_hil_stage(reddit_input: RedditMonitorInput) -> Dict[str, Any]:
    app = build_reddit_hil_graph()
    return _invoke_graph(app, {"input": reddit_input})


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
