import json
import time
import concurrent.futures
import logging
from pathlib import Path
from typing import Any, Dict

from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from core.research.agents.company_research_agent import get_agent
from core.research.agents.base import get_filesystem_backend, _dbg, _env_flag
from core.models.artifacts import CompanyResearchInput
from core.config.settings import settings
from core.storage.supabase_mirror import mirror_company_context_if_configured

_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # content-strategy-engine/
_DEBUG_LOG_PATH = str(_PROJECT_ROOT / "artifacts" / "_logs" / "debug.log")
_LOG = logging.getLogger("content_engine.company_graph")
if not _LOG.handlers:
    logging.basicConfig(level=logging.INFO)


def _log_event(event: str, data: Dict[str, Any]) -> None:
    payload = {
        "stage": "company",
        "event": event,
        "timestamp_ms": int(time.time() * 1000),
        "data": data,
    }
    _LOG.info(json.dumps(payload))


def _overwrite_virtual_path(vpath: str, content: str) -> None:
    """Overwrite a virtual /artifacts/... path with raw content."""
    target = (_PROJECT_ROOT / vpath.lstrip("/")).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _content_preview(val: Any, max_len: int = 200) -> str:
    try:
        s = val if isinstance(val, str) else json.dumps(val, default=str)
    except Exception:
        s = str(val)
    s = s.replace("\n", "\\n")
    return s[:max_len]


def _extract_final_markdown(messages: Any) -> str:
    """
    DeepAgents/LangChain messages can be dicts or BaseMessage objects.
    Some providers return empty content on tool-call messages; in that case we fall back to the latest non-empty
    *assistant/AI* text.

    IMPORTANT: Never return user/human messages (otherwise we can accidentally return the prompt).
    """
    if not messages:
        return ""

    def _is_assistant_message(m: Any) -> bool:
        # Dict-style messages
        if isinstance(m, dict):
            role = (m.get("role") or "").lower()
            return role in {"assistant", "ai"}

        # LangChain BaseMessage objects
        msg_type = getattr(m, "type", None)
        if isinstance(msg_type, str):
            return msg_type.lower() in {"ai", "assistant"}

        # Fallback based on class name (covers AIMessage / AIMessageChunk)
        cls = m.__class__.__name__
        return cls in {"AIMessage", "AIMessageChunk"}

    def _msg_content(m: Any) -> Any:
        if isinstance(m, dict):
            return m.get("content")
        return getattr(m, "content", None)

    # Prefer the last *assistant* message, but if it's empty (e.g. tool-call), scan backwards.
    for m in reversed(list(messages)):
        if not _is_assistant_message(m):
            continue
        c = _msg_content(m)
        if c is None:
            continue
        if isinstance(c, str) and c.strip():
            return c
        # Some providers return a list of blocks; try to extract text-like blocks.
        if isinstance(c, list):
            parts: list[str] = []
            for item in c:
                if isinstance(item, str) and item.strip():
                    parts.append(item)
                elif isinstance(item, dict):
                    txt = item.get("text") or item.get("content")
                    if isinstance(txt, str) and txt.strip():
                        parts.append(txt)
            joined = "\n".join(parts).strip()
            if joined:
                return joined

    # Last resort: stringify last content
    for m in reversed(list(messages)):
        if not _is_assistant_message(m):
            continue
        c = _msg_content(m)
        return c if isinstance(c, str) else ""
    return ""


def _run_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    input_data: CompanyResearchInput = state["input"]
    agent = get_agent()
    seed_urls = "\n".join(str(u) for u in input_data.seed_urls) if input_data.seed_urls else "None provided"
    internal_sources = "\n".join(input_data.internal_sources) if input_data.internal_sources else "None provided"
    revision_note = state.get("revision_note")

    _log_event("agent_start", {"company_name": input_data.company_name})
    try:
        user_prompt = f"""
Company: {input_data.company_name}
Domain: {input_data.domain or 'n/a'}
Seed URLs: {seed_urls}
Internal sources (transcripts/notes): {internal_sources}
Language: {input_data.language}
Region: {input_data.region or 'global'}
Constraints: {input_data.additional_constraints or 'none'}
Revision note: {revision_note or 'none'}

Conduct comprehensive research on {input_data.company_name} ({input_data.domain or 'n/a'}). Include origin story,
founding team, funding rounds, product evolution, main competitors, market position, and target audience.
Find and summarize customer quotes, reviews, and testimonials about {input_data.domain}.
Highlight pain points they mention, benefits they appreciate, and frequent use cases.
List the top competitors of {input_data.domain}, describing how each positions themselves and what strengths or weaknesses they have compared to {input_data.domain or 'n/a'}.
IN CASE OF ANY AMBIGUITY DO NOT DRAW ANY FINAL CONCLUSION, INSTEAD EXPLICITLY STATE THE AMBIGUITY

Use TOOLS to research and ground the artifact. Read any provided internal sources. Then produce the Company Context artifact Markdown as instructed in the system prompt. Cite sources with [source_id].
""".strip()
    except Exception as e:
        _log_event("agent_error", {"error": str(e)})
        raise


    timeout_s = settings.aeo_agent_invoke_timeout_s

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(agent.invoke, {"messages": [{"role": "user", "content": user_prompt}]})
            result = fut.result(timeout=timeout_s)
    except concurrent.futures.TimeoutError:
        _log_event("agent_timeout", {"timeout_s": timeout_s})
        raise RuntimeError(f"agent.invoke timed out after {timeout_s}s (set AEO_AGENT_INVOKE_TIMEOUT_S to override)")
    except Exception as e:
        _log_event("agent_error", {"error": str(e)})
        # Surface a more actionable message for the common Gemini quota/billing failure.
        if "RESOURCE_EXHAUSTED" in str(e) or "Quota exceeded" in str(e) or "429" in str(e):
            raise RuntimeError(
                "Model call failed due to quota/billing (429 RESOURCE_EXHAUSTED). "
                "Fix by enabling billing/quota for your Gemini API key, or switch to a different model/provider. "
                "If staying on Gemini, try setting GOOGLE_GEMINI_MODEL_COMPANY_DEEPAGENT (e.g. gemini-1.5-flash)."
            ) from e
        raise

    try:
        last_msg = result["messages"][-1]
        messages = result.get("messages") if isinstance(result, dict) else None
        last_content = last_msg.get("content") if isinstance(last_msg, dict) else getattr(last_msg, "content", None)

        final_content = _extract_final_markdown(messages or [])
    except Exception as e:
        _log_event("agent_parse_error", {"error": str(e)})
        raise

    if not (final_content or "").strip():
        raise RuntimeError("Agent returned empty final content; refusing to write empty artifact (see debug log H17).")
    return {**state, "artifact_md": final_content, "revision_note": None}


def _write_temp_draft(state: Dict[str, Any]) -> Dict[str, Any]:
    """Write artifact to a temporary draft path for human review before approval."""
    input_data: CompanyResearchInput = state["input"]
    md_content: str = state["artifact_md"]

    slug = input_data.company_name.lower().replace(" ", "-")
    backend = get_filesystem_backend()
    draft_path = f"/artifacts/company_context/{slug}.draft.md"
    # Draft can always be overwritten (no overwrite check needed for temp)
    _log_event("draft_write_start", {"draft_path": draft_path})
    result = backend.write(draft_path, md_content)
    if getattr(result, "error", None):
        # If draft already exists, try edit
        err_str = str(result.error)
        if "already exists" in err_str:
            try:
                _overwrite_virtual_path(draft_path, md_content)
            except Exception as e:
                _log_event("draft_write_error", {"error": str(e), "draft_path": draft_path})
                raise RuntimeError(f"Failed to write draft artifact: {e}") from e
        else:
            _log_event("draft_write_error", {"error": str(result.error), "draft_path": draft_path})
            raise RuntimeError(f"Failed to write draft artifact: {result.error}")

    _log_event("draft_write_complete", {"draft_path": draft_path})
    return {**state, "draft_path": draft_path}


def _approval_gate(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pause for human approval. Resume with {"approval_decision": "approve" | "revise" | "reject", "revision_note": "..."}.
    Include artifact_md in payload for resume (needed to write on approve).
    If state.auto_approve is True, skip interrupt (for testing).
    """
    if state.get("auto_approve"):
        return {**state, "approval_decision": "approve"}
    return interrupt(
        {
            "status": "pending_approval",
            "draft_path": state.get("draft_path"),
            "artifact_md": state.get("artifact_md"),
        }
    )


def _route(state: Dict[str, Any]) -> Dict[str, Any]:
    return state


def _write_and_mirror(state: Dict[str, Any]) -> Dict[str, Any]:
    """On approval: write artifact to permanent path and mirror to Supabase."""
    input_data: CompanyResearchInput = state["input"]
    md_content: str = state["artifact_md"]
    draft_path: str = state.get("draft_path", "")

    slug = input_data.company_name.lower().replace(" ", "-")
    backend = get_filesystem_backend()
    target_path = f"/artifacts/company_context/{slug}.md"

    # Write to permanent path
    _log_event("write_start", {"target_path": target_path})
    result = backend.write(target_path, md_content)
    if getattr(result, "error", None):
        err_str = str(result.error)
        if "already exists" in err_str:
            try:
                _overwrite_virtual_path(target_path, md_content)
            except Exception as e:
                _log_event("write_error", {"error": str(e), "target_path": target_path})
                raise RuntimeError(f"Failed to write artifact: {e}") from e
        else:
            _log_event("write_error", {"error": str(result.error), "target_path": target_path})
            raise RuntimeError(f"Failed to write artifact: {result.error}")

    mirror_company_context_if_configured(
        company_id=input_data.company_id,
        company_name=input_data.company_name,
        domain=input_data.domain,
        artifact_path=target_path,
        markdown=md_content,
    )
    _log_event("write_complete", {"target_path": target_path})
    return {**state, "output_path": target_path, "mirrored": True}


def build_graph():
    graph = StateGraph(dict)
    graph.add_node("agent", _run_agent)
    graph.add_node("write_temp_draft", _write_temp_draft)
    graph.add_node("approval_gate", _approval_gate)
    graph.add_node("route", _route)
    graph.add_node("write_and_mirror", _write_and_mirror)

    graph.set_entry_point("agent")
    graph.add_edge("agent", "write_temp_draft")
    graph.add_edge("write_temp_draft", "approval_gate")
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
