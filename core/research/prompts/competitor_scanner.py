"""Competitor Scanner specialist agent prompt.

Agent 3 — Maps the competitive landscape using Perplexity sonar-deep-research.
Receives company overview as upstream context.
"""
from __future__ import annotations

from typing import Optional

from core.models.knowledge_base import KnowledgeBaseInput

COMPETITOR_SCANNER_SYSTEM_PROMPT = """\
You are a specialist competitive intelligence analyst focused on mapping the \
competitive landscape for B2B SaaS companies. Your research will inform content \
strategy to help the company get cited in AI search results.

You will receive the company overview as context. Use it to understand the \
company's positioning before researching competitors.

## Required Output Sections

1. **Direct Competitors** — Companies offering the same core product to the same market
   - For each: name, domain, founding year, funding, market position, key differentiators
2. **Mindshare Competitors** — Companies that compete for the same buyer's attention
   - May solve different problems but appear in the same consideration set
3. **Niche/Emerging Competitors** — Smaller or newer entrants worth monitoring
4. **Market Map** — How the competitive landscape is segmented (by feature, by segment, by price)
5. **Competitive Positioning** — Where the target company fits relative to competitors
6. **Feature Comparison Matrix** — Key features across top 5-7 competitors
7. **Funding & Growth Comparison** — Relative funding, team size, growth signals

## Output Requirements

- Write in analytical, evidence-based tone
- Use markdown formatting with clear section headers
- Include inline citations [1], [2], etc.
- Score competitor relevance: direct, indirect, mindshare, niche
- Minimum 2000 words, maximum 5000 words
- Be objective — acknowledge where competitors are stronger
"""

_HUB_NAME = "research-competitor-scanner-system"


def get_competitor_scanner_system_prompt() -> str:
    """Get competitor scanner system prompt (Hub with local fallback)."""
    from core.content_engine.prompt_registry import get_prompt

    return get_prompt(_HUB_NAME, COMPETITOR_SCANNER_SYSTEM_PROMPT)


def build_competitor_scanner_user_prompt(
    input_data: KnowledgeBaseInput,
    company_overview_md: str,
    revision_note: Optional[str] = None,
) -> str:
    """Build user prompt for competitive landscape research.

    Args:
        input_data: Pipeline input with company details.
        company_overview_md: Upstream company overview markdown (Agent 1 output).
        revision_note: Optional reviewer feedback from a previous version.
    """
    # Truncate upstream doc to avoid excessive prompt length
    overview_truncated = company_overview_md[:12000]
    if len(company_overview_md) > 12000:
        overview_truncated += "\n\n[... truncated for brevity ...]"

    parts = [
        f"Map the competitive landscape for the following company.",
        f"\nCompany: {input_data.company_name}",
    ]
    if input_data.domain:
        parts.append(f"Domain: {input_data.domain}")
    if input_data.additional_constraints:
        parts.append(f"\nAdditional instructions: {input_data.additional_constraints}")
    parts.append(f"\n## Company Overview (for context)\n\n{overview_truncated}")
    if revision_note:
        parts.append(
            f"\n## Reviewer Feedback\n\n"
            f"A previous version was reviewed and revisions were requested. "
            f"Address the following feedback:\n\n{revision_note}"
        )
    return "\n".join(parts)
