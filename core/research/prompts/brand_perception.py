"""Brand Perception specialist agent prompt.

Agent 5 — Synthesizes brand perception from upstream L2 docs + selective web search.
Uses Claude with Anthropic native web_search_20250305 tool (NOT Perplexity).
"""
from __future__ import annotations

from typing import Dict, Optional

from core.models.knowledge_base import KnowledgeBaseInput

BRAND_PERCEPTION_SYSTEM_PROMPT = """\
You are a specialist brand perception analyst focused on assessing how B2B SaaS \
companies are perceived in the market. Your analysis will inform content strategy \
to help the company get cited in AI search results.

You have access to four upstream research documents:
- Company Overview (comprehensive company profile)
- Customer Reviews (sentiment analysis and user feedback)
- Competitor Registry (competitive landscape mapping)
- Weakness Analysis (competitor gaps and opportunities)

Your primary task is to **synthesize** these documents into a brand perception \
assessment. Use the web search tool selectively for:
- Recent brand mentions not covered in the upstream docs
- Social media sentiment signals
- Industry analyst opinions
- Brand ranking data

## Required Output Sections

1. **Market Position** — Where the company sits in its market category
2. **Brand Positioning** — How the company positions itself vs. how the market perceives it
3. **Key Differentiators** — What makes this brand unique (perceived, not claimed)
4. **Strengths Liked by Users** — Top strengths based on real user feedback
5. **Challenges & Pain Points** — Perception gaps and areas of concern
6. **AI Search Presence** — How well the brand appears in AI search results today
7. **Strategic Recommendations** — Actionable steps to improve brand perception for AI search

## Output Requirements

- Write in analytical, evidence-based tone
- Use markdown formatting with clear section headers
- Cite sources for any claims (both upstream docs and web search results)
- Distinguish between verified perception data and inference
- Minimum 1500 words, maximum 3500 words
- Focus specifically on how brand perception affects AI search citation potential
"""

_HUB_NAME = "research-brand-perception-system"


def get_brand_perception_system_prompt() -> str:
    """Get brand perception system prompt (Hub with local fallback)."""
    from core.content_engine.prompt_registry import get_prompt

    return get_prompt(_HUB_NAME, BRAND_PERCEPTION_SYSTEM_PROMPT)


def build_brand_perception_user_prompt(
    input_data: KnowledgeBaseInput,
    upstream_docs: Dict[str, str],
    revision_note: Optional[str] = None,
) -> str:
    """Build user prompt for brand perception assessment.

    Args:
        input_data: Pipeline input with company details.
        upstream_docs: Dict mapping doc_type.value to markdown content
            (e.g., {"company_overview": "...", "customer_reviews": "..."}).
        revision_note: Optional reviewer feedback from a previous version.
    """
    parts = [
        f"Assess the brand perception for the following company by synthesizing "
        f"the upstream research documents below. Use web search selectively for "
        f"supplementary data not covered in the documents.",
        f"\nCompany: {input_data.company_name}",
    ]
    if input_data.domain:
        parts.append(f"Domain: {input_data.domain}")
    if input_data.additional_constraints:
        parts.append(f"\nAdditional instructions: {input_data.additional_constraints}")

    # Include upstream docs with clear headers
    doc_labels = {
        "company_overview": "Company Overview",
        "customer_reviews": "Customer Reviews",
        "competitor_registry": "Competitor Registry",
        "weakness_analysis": "Weakness Analysis",
    }
    for doc_type, label in doc_labels.items():
        content = upstream_docs.get(doc_type, "")
        if content:
            # Truncate each doc to keep total prompt manageable
            truncated = content[:40_000]  # ~10k tokens
            if len(content) > 40_000:
                truncated += "\n\n[... truncated for brevity ...]"
            parts.append(f"\n## {label}\n\n{truncated}")
        else:
            parts.append(f"\n## {label}\n\n*Not available — use web search to fill gaps.*")

    if revision_note:
        parts.append(
            f"\n## Reviewer Feedback\n\n"
            f"A previous version was reviewed and revisions were requested. "
            f"Address the following feedback:\n\n{revision_note}"
        )

    return "\n".join(parts)
