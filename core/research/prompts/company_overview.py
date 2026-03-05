"""Company Overview specialist agent prompt.

Agent 1 — Deep research into company fundamentals using Perplexity sonar-deep-research.
Covers: founding story, funding, product evolution, business model, GTM, key metrics, target audience.
"""
from __future__ import annotations

from typing import Optional

from core.models.knowledge_base import KnowledgeBaseInput

COMPANY_OVERVIEW_SYSTEM_PROMPT = """\
You are a specialist research analyst focused on creating comprehensive company overviews \
for B2B SaaS companies. Your research will be used to help the company get cited in AI \
search results (Perplexity, ChatGPT, Claude, Gemini).

Your task is to produce a thorough, well-structured company overview covering:

## Required Sections

1. **Company Identity** — Full legal name, founding date, founders, headquarters, company size
2. **Founding Story & Mission** — Why the company was started, the problem it solves, mission statement
3. **Funding & Financial History** — Funding rounds, investors, valuation milestones, revenue signals
4. **Product & Platform** — Core products, key features, platform architecture, integrations
5. **Target Market** — Ideal customer profile, company size segments, industries served
6. **Business Model** — Pricing model, revenue streams, go-to-market strategy
7. **Growth & Traction** — Key metrics (users, customers, revenue growth), notable milestones
8. **Leadership & Culture** — Key executives, company culture signals, employer brand
9. **Partnerships & Ecosystem** — Strategic partnerships, technology integrations, channel partners
10. **Recent Developments** — Last 12 months of news, product launches, strategic moves

## Output Requirements

- Write in professional analytical tone
- Use markdown formatting with clear section headers
- Include inline citations [1], [2], etc. with source URLs
- Minimum 2000 words, maximum 5000 words
- Be factual — distinguish verified facts from market speculation
- Include specific numbers, dates, and names wherever available
"""

_HUB_NAME = "research-company-overview-system"


def get_company_overview_system_prompt() -> str:
    """Get company overview system prompt (Hub with local fallback)."""
    from core.content_engine.prompt_registry import get_prompt

    return get_prompt(_HUB_NAME, COMPANY_OVERVIEW_SYSTEM_PROMPT)


def build_company_overview_user_prompt(
    input_data: KnowledgeBaseInput,
    revision_note: Optional[str] = None,
) -> str:
    """Build user prompt for company overview research."""
    parts = [
        f"Research the following company and produce a comprehensive company overview.",
        f"\nCompany: {input_data.company_name}",
    ]
    if input_data.domain:
        parts.append(f"Domain: {input_data.domain}")
    if input_data.seed_urls:
        parts.append(f"Key URLs: {', '.join(str(u) for u in input_data.seed_urls)}")
    if input_data.internal_sources:
        parts.append(f"Additional sources to consult: {', '.join(input_data.internal_sources)}")
    if input_data.language and input_data.language != "en":
        parts.append(f"Language: {input_data.language}")
    if input_data.region:
        parts.append(f"Region focus: {input_data.region}")
    if input_data.additional_constraints:
        parts.append(f"\nAdditional instructions: {input_data.additional_constraints}")
    if revision_note:
        parts.append(
            f"\n## Reviewer Feedback\n\n"
            f"A previous version was reviewed and revisions were requested. "
            f"Address the following feedback:\n\n{revision_note}"
        )
    return "\n".join(parts)
