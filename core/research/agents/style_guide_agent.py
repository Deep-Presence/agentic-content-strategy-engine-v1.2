import json
import concurrent.futures
from typing import Any, Dict, List, Optional

from deepagents import create_deep_agent
from langchain_google_genai import ChatGoogleGenerativeAI

from core.research.agents.base import get_backend, get_store
from core.config.settings import settings
from core.models.style_guide import StyleGuideResearchInput
from core.research.tools import perplexity_client


def internet_search(query: str, max_results: int = 6, include_raw_content: bool = True) -> str:
    """Web research via Perplexity Deep Research (sonar-deep-research)."""
    return perplexity_client.search(query=query)


SYSTEM_PROMPT = """
You are the Writing Style-Guide Agent.

Goal: Create and maintain a Writing Style-Guide artifact in Markdown as the canonical reference for voice/tone/style. Write in concise, directive language. Use numbered citations [source_id] where applicable.

Inputs:
- Company info (name/domain)
- Path to Company Context artifact (Markdown)
- Paths to Persona artifacts (one or more)
- Optional internal transcripts/notes

Output file (canonical):
- /artifacts/style_guides/<company_slug>.md

Stable section headers (must stay exactly as written):
- Voice & Tone
- Channel Variations
- Show vs Tell (Good/Bad Examples)
- Sentence & Language Choices
- Jargon / Terminology Rules
- Audience Resonance (from Personas)
- Product Positioning & Messaging Pillars
- Do / Don't
- Formatting & Structure
- Sample Snippets
- Sources

Update behavior:
- If the style guide file already exists, DO NOT rewrite from scratch. Use patch-style edits targeting sections; keep headings unchanged.
- If missing, create from scratch with all required sections.

Use tools:
- read_file existing style guide (if present), company context, persona files, internal sources
- internet_search for supporting examples/archetypes/benchmarks
- write_file / edit_file to update the style guide

Return ONLY JSON with:
  { "written_paths": [ ... ], "notes": "short string" }
No extra text.
"""


def build_agent():
    google_key = settings.google_api_key_style_guide_research_deepagent
    if not google_key:
        raise RuntimeError("GOOGLE_API_KEY_STYLE_GUIDE_RESEARCH_DEEPAGENT is not set")

    gemini_model = settings.google_style_guide_deepagents_model
    model = ChatGoogleGenerativeAI(
        model=gemini_model,
        api_key=google_key,
    )
    return create_deep_agent(
        model=model,
        tools=[internet_search],
        system_prompt=SYSTEM_PROMPT.strip(),  # BUG FIX: was system_message=
        backend=get_backend(),
        store=get_store(),
    )


_agent = None


def get_style_guide_agent():
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


def run_style_guide_agent(
    input_data: StyleGuideResearchInput,
    revision_note: Optional[str] = None,
    use_draft_paths: bool = False,
) -> Dict[str, Any]:
    company_slug = input_data.company_slug or input_data.company_name.lower().replace(" ", "-")
    context_path = input_data.company_context_path or f"/artifacts/company_context/{company_slug}.md"
    suffix = ".draft.md" if use_draft_paths else ".md"
    target_path = f"/artifacts/style_guides/{company_slug}{suffix}"

    persona_list = input_data.persona_paths or [
        f"/artifacts/personas/{company_slug}__persona-icp.md",
        f"/artifacts/personas/{company_slug}__persona-2.md",
        f"/artifacts/personas/{company_slug}__persona-3.md",
    ]

    prompt = f"""
Company: {input_data.company_name}
Domain: {input_data.domain or 'n/a'}
Company slug: {company_slug}
Company context path: {context_path}
Persona paths: {persona_list}
Internal sources: {input_data.internal_sources or []}
Language: {input_data.language}
Region: {input_data.region or 'global'}
Constraints: {input_data.additional_constraints or 'none'}
Target style guide file: {target_path}
Revision note: {revision_note or 'none'}

Instructions:
1) Read company context and persona files (if missing, note in output).
2) Use internet_search as needed for archetypes/examples tied to the audience.
3) If target file exists, patch sections (keep headings). If not, create it with all required sections.
4) Include citations [source_id] where relevant.
5) Return JSON with written_paths and notes.
""".strip()

    agent = get_style_guide_agent()
    # BUG FIX: Added ThreadPoolExecutor isolation (was missing, matching persona_agent pattern)
    timeout_s = settings.aeo_agent_invoke_timeout_s
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(agent.invoke, {"messages": [{"role": "user", "content": prompt}]})
        result = fut.result(timeout=timeout_s)
    last_msg = result["messages"][-1]
    raw = last_msg.get("content") if isinstance(last_msg, dict) else getattr(last_msg, "content", "")
    try:
        return json.loads(raw)
    except Exception:
        return {"written_paths": [], "notes": "Non-JSON agent output", "raw": raw}
