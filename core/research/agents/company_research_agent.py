import json
import time
from pathlib import Path
from typing import Any, Dict, List

from deepagents import create_deep_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.store.memory import InMemoryStore

from core.config.settings import settings
from core.research.agents.base import (
    _dbg,
    _dotenv_presence,
    _env_flag,
    get_backend,
    get_store,
)
from core.research.tools import perplexity_client


def internet_search(query: str, max_results: int = 6, include_raw_content: bool = True) -> str:
    """Web research via Perplexity Deep Research (sonar-deep-research)."""
    return perplexity_client.research(query=query)

def read_local_text(path: str, max_chars: int = 8000) -> str:
    """Read internal transcript/notes to ground the agent."""
    p = Path(path)
    if not p.exists():
        return f"ERROR: path not found: {path}"
    return p.read_text(encoding="utf-8")[:max_chars]


SYSTEM_PROMPT = """
You are the Company Research Agent. Produce a Company Context artifact in Markdown as the single source of truth.
- Use tools to research (web search) and to read provided internal transcripts/notes.
- You MUST call the `internet_search` tool at least once before finalizing the artifact. If it fails, say so explicitly.
- Be concise but complete; prefer bullets.
- Cite provenance inline with [source_id] references. Unknowns => write "TBD".
- Start with **deep research** about the company, including:
    - **Origin story**: Founders' background, early funding, initial customers, and evolution.
    - **Business reality**: What does the company do? Products, features, major pivots, market positioning.
    - **Competitive landscape**: Direct competitors, mind share competitors, and perceptions around these players.
    - **Target customers and use cases**: Who they serve and how.
    - **Brand perception**: What customers and the market say about the brand and competitors (quotes, reviews, testimonials).
    - **Internal insights**: Collect existing company resources such as personas, sales call transcripts, pitch decks, recorded meetings, and product documentation.
- Use tools like **internet_search** for automated, broad, and deep research.

** Structuring the Company Context Artifact**

Organize the artifact into sections that cover:

- **Company origin and story**: Narrative about the founders and evolution.
- **Core products and services**: Features, benefits, and what problems the company solves.
- **Market position and competitive advantages**: How the company compares and stands out.
- **Target audience overview**: High-level description of personas.
- **Customer insights**: Pain points, motivations, daily challenges, and decision-making criteria.
- **Brand reputation and perception**: External and internal viewpoints.
- **Growth drivers and bottlenecks**: What limits or accelerates company growth.
- **Urgency and business goals**: What is driving the current strategy, including short and long-term objectives.
Export findings preferably in **Markdown format** for easier processing by AI tools and teams.
Return only the final Markdown artifact.
"""


_agent = None


def build_agent():
    google_key = settings.google_api_key_company_deepagent
    if not google_key:
        raise RuntimeError("GOOGLE_API_KEY_COMPANY_DEEPAGENT is not set")
    gemini_model = settings.google_gemini_model_company_deepagent
    model = ChatGoogleGenerativeAI(
        model=gemini_model,
        api_key=google_key,
    )

    backend = get_backend()

    try:
        agent = create_deep_agent(
            model=model,
            tools=[internet_search, read_local_text],
            system_prompt=SYSTEM_PROMPT.strip(),
            backend=backend,
            store=get_store(),
        )
    except Exception as e:
        raise
    return agent


def get_agent():
    global _agent
    if _agent is None:
        try:
            _agent = build_agent()
        except Exception as e:
            raise
    return _agent
