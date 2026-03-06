import json
import concurrent.futures
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from deepagents import create_deep_agent
from langchain_google_genai import ChatGoogleGenerativeAI

from core.research.agents.base import get_backend, get_store
from core.models.personas import PersonaResearchInput
from core.config.settings import settings
from core.research.tools import perplexity_client

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # content-strategy-engine/


def internet_search(query: str, max_results: int = 6, include_raw_content: bool = True) -> str:
    """Web research via Perplexity Deep Research (sonar-deep-research)."""
    return perplexity_client.research(query=query)


SYSTEM_PROMPT = """
You are the Audience Persona Agent.

Goal: Create and maintain persona artifacts as canonical Markdown files, written in 3rd person as if each persona is a real person.

Inputs you will receive:
- Company info + domain
- Path to the canonical Company Context artifact (Markdown)
- Optional internal transcript/note file paths
- A max_personas cap (1–3)

Hard requirements:
- Always create/update the ICP persona first.
- Create up to 2 additional secondary personas only if you have high confidence there are distinct buyer types.
- Each persona must be its own Markdown artifact under:
  - /artifacts/personas/<company_slug>__persona-icp.md
  - /artifacts/personas/<company_slug>__persona-2.md
  - /artifacts/personas/<company_slug>__persona-3.md
- Use stable section headers EXACTLY as below to enable future patch updates:
  - Persona Summary
  - Role & Context
  - Day-in-the-Life Mechanics
  - KPIs / What Success Means
  - Pain Points & Blockers
  - Buying Triggers
  - Trust Builders & Objections
  - Annoyances
  - Messaging Angles
  - Quotes
  - Sources
- Cite sources in the persona content, using [source_id] markers.

Update behavior (important):
- If a target persona file already exists, DO NOT rewrite it from scratch.
- Instead, read it and use edit/patch updates by replacing only the relevant sections.
- Keep headings unchanged.

Tools available:
- Use filesystem tools (ls/read_file/write_file/edit_file/grep/glob) through the backend.
- Use internet_search for web research.

Output:
- After writing/updating files, return a JSON object with:
  - written_paths: string[]
  - notes: short string
Return ONLY valid JSON, no extra text.
"""


def build_agent():
    google_key = settings.google_api_key_persona_research_deepagent
    if not google_key:
        raise RuntimeError("GOOGLE_API_KEY_PERSONA_RESEARCH_DEEPAGENT is not set")

    gemini_model = settings.google_persona_deepagents_model
    model = ChatGoogleGenerativeAI(
        model=gemini_model,
        api_key=google_key,
    )
    return create_deep_agent(
        model=model,
        tools=[internet_search],
        system_prompt=SYSTEM_PROMPT.strip(),
        backend=get_backend(),
        store=get_store(),
    )


_agent = None


def get_persona_agent():
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


def run_persona_agent(
    input_data: PersonaResearchInput,
    revision_note: Optional[str] = None,
    use_draft_paths: bool = False,
) -> Dict[str, Any]:
    company_slug = input_data.company_slug or input_data.company_name.lower().replace(" ", "-")
    company_context_path = (
        input_data.company_context_path
        or f"/artifacts/company_context/{company_slug}.md"
    )

    suffix = ".draft.md" if use_draft_paths else ".md"
    target_paths = [
        f"/artifacts/personas/{company_slug}__persona-icp{suffix}",
        f"/artifacts/personas/{company_slug}__persona-2{suffix}",
        f"/artifacts/personas/{company_slug}__persona-3{suffix}",
    ][: input_data.max_personas]

    prompt = f"""
Company: {input_data.company_name}
Domain: {input_data.domain or 'n/a'}
Company slug: {company_slug}
Company context path: {company_context_path}
Internal sources: {input_data.internal_sources or []}
Language: {input_data.language}
Region: {input_data.region or 'global'}
Constraints: {input_data.additional_constraints or 'none'}
Max personas: {input_data.max_personas}
Target persona files: {target_paths}
Revision note: {revision_note or 'none'}

Instructions:
1) Read the company context file. If missing, explain in notes and create only ICP with best effort.
2) Read any internal sources if available.
3) Use internet_search as needed to fill in realistic KPIs/pains/objections as well as direct competitor's customer persona reviews for the buyer types.
4) Create/update the persona files at the target paths. Use patch updates if file exists.
5) Return JSON with written_paths and notes.
""".strip()

    agent = get_persona_agent()
    timeout_s = settings.aeo_agent_invoke_timeout_s
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(agent.invoke, {"messages": [{"role": "user", "content": prompt}]})
        result = fut.result(timeout=timeout_s)
    last_msg = result["messages"][-1]
    raw = last_msg.get("content") if isinstance(last_msg, dict) else getattr(last_msg, "content", "")

    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = {"written_paths": [], "notes": "Non-JSON agent output", "raw": raw}

    # Fallback: if agent didn't return written_paths (common with LLM outputs),
    # scan disk for the expected draft files that the agent was told to write.
    if not parsed.get("written_paths"):
        found_on_disk = []
        for tp in target_paths:
            disk_path = _PROJECT_ROOT / tp.lstrip("/")
            if disk_path.exists() and disk_path.stat().st_size > 0:
                found_on_disk.append(tp)
        if found_on_disk:
            logger.info(
                "Agent didn't return written_paths but files found on disk: %s",
                found_on_disk,
            )
            parsed["written_paths"] = found_on_disk

    return parsed
