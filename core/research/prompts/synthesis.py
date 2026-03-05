"""Synthesis agent prompt.

Produces the L3 Company Profile by cross-referencing all L2 knowledge base documents.
Uses Claude Opus with read_file tool via langgraph.prebuilt.create_react_agent.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from core.models.knowledge_base import KnowledgeBaseInput

SYNTHESIS_SYSTEM_PROMPT = """\
You are a senior research analyst producing a comprehensive Company Profile document. \
This document will serve as the authoritative reference for all downstream content \
strategy — including gap analysis, content generation, and AI search optimization.

You have access to a `read_file` tool to read research documents from the knowledge base. \
Use it to read the available L2 research documents listed in the user prompt.

## Your Task

Synthesize all available research documents into a single, cohesive Company Profile \
that covers:

1. **Company Overview** — Identity, founding, mission, key metrics
2. **Product & Platform** — What they build, key features, value proposition
3. **Market Position** — Where they sit in the market, brand perception
4. **Target Audience** — Who they serve, ICP, segments
5. **Competitive Landscape** — Key competitors, differentiation, market map
6. **Strengths & Advantages** — What users love, competitive moats
7. **Weaknesses & Opportunities** — Where competitors are vulnerable, content gaps
8. **Brand Voice & Messaging** — How the company communicates, tone patterns
9. **Strategic Recommendations** — Top opportunities for AI search citation content

## Synthesis Guidelines

- **Cross-reference** information across documents — resolve conflicts by favoring \
  more specific or evidence-backed claims
- **De-duplicate** — don't repeat the same information in multiple sections
- **Maintain citations** — preserve source citations from the original documents
- **Flag gaps** — if a research document is missing, note what data is unavailable
- **Be comprehensive** — this is the single source of truth for content strategy
- **Output format** — well-structured markdown with clear section headers

## Output Length

Target 3000-6000 words. This is a reference document, so thoroughness matters more \
than brevity.
"""

_HUB_NAME = "research-synthesis-system"


def get_synthesis_system_prompt() -> str:
    """Get synthesis system prompt (Hub with local fallback)."""
    from core.content_engine.prompt_registry import get_prompt

    return get_prompt(_HUB_NAME, SYNTHESIS_SYSTEM_PROMPT)


def build_synthesis_user_prompt(
    input_data: KnowledgeBaseInput,
    available_docs: Dict[str, str],
    missing_docs: List[str],
    revision_note: Optional[str] = None,
) -> str:
    """Build user prompt for L2 → L3 synthesis.

    Args:
        input_data: Pipeline input with company details.
        available_docs: Dict mapping doc_type.value to file path
            (e.g., {"company_overview": "company_overview/v1.md"}).
        missing_docs: List of doc_type.value strings that are missing.
        revision_note: Optional reviewer feedback from a previous version.
    """
    parts = [
        f"Synthesize the following research documents into a comprehensive Company Profile.",
        f"\nCompany: {input_data.company_name}",
    ]
    if input_data.domain:
        parts.append(f"Domain: {input_data.domain}")

    parts.append("\n## Available Documents")
    parts.append("Read each of these files using the read_file tool:\n")
    for doc_type, file_path in available_docs.items():
        label = doc_type.replace("_", " ").title()
        parts.append(f"- **{label}**: `{file_path}`")

    if missing_docs:
        parts.append("\n## Missing Documents")
        parts.append("The following research documents are NOT available. "
                      "Note these gaps in your synthesis:\n")
        for doc_type in missing_docs:
            label = doc_type.replace("_", " ").title()
            parts.append(f"- {label}")

    if input_data.additional_constraints:
        parts.append(f"\nAdditional instructions: {input_data.additional_constraints}")

    if revision_note:
        parts.append(
            f"\n## Reviewer Feedback\n\n"
            f"A previous version was reviewed and revisions were requested. "
            f"Address the following feedback:\n\n{revision_note}"
        )

    return "\n".join(parts)
