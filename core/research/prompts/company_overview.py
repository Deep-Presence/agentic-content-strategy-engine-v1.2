"""Company Overview specialist agent prompt.

Agent 1 — Deep research into company fundamentals using Perplexity sonar-deep-research.
Covers: founding story, funding, product evolution, business model, GTM, key metrics, target audience.
"""
from __future__ import annotations

from typing import Optional

from core.models.knowledge_base import KnowledgeBaseInput

COMPANY_OVERVIEW_SYSTEM_PROMPT = """\
Research [COMPANY NAME] and create a comprehensive report covering these areas:
==The Origin Story==
•	How did this company start? What problem were they solving?
•	Who are the founders? What's their background and previous experience?
•	Early funding, initial customers, and first product iterations
==The Business Reality==
•	How does this company make money? What's their revenue model?
•	Are they profitable? What's their financial trajectory?
•	Who funds them? Latest valuation and investor expectations
==What They Actually Do==
•	Current products and services – skip the marketing fluff
•	How their technology works under the hood
•	Key features that matter to users
•	Product evolution and major pivots
==The Market Position==
•	Who are their main competitors? How do they stack up?
•	What's their competitive advantage? Is it defensible?
•	Market size, share, and growth potential
•	Target customers and use cases
==The Customer Reality==
•	Who actually uses this? Customer segments and personas
•	Positive reviews and success stories
•	Complaints, negative feedback, and common problems
•	Customer retention and satisfaction data
==The People==
•	Current leadership team and key employees
•	Company culture and employee reviews
•	Team size, hiring patterns, and organizational structure
==The Problems==
•	What criticism do they face? Industry controversies
•	Failed products or initiatives
•	Operational challenges and technical debt
==The Future==
•	Product roadmap and strategic direction
•	Market trends that help or hurt them
•	Partnerships, acquisitions, and expansion plans
•	Regulatory risks and opportunities
==Recent Context==
•	Latest news, announcements, and developments
•	Industry changes affecting the company
•	Geopolitical pressures and international strategy
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
