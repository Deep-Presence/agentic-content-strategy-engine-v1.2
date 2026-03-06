"""Customer Reviews specialist agent prompt.

Agent 2 — Harvests and analyzes customer reviews from G2, Capterra, TrustRadius,
Reddit, HN, and other review platforms using Perplexity sonar-deep-research.
"""
from __future__ import annotations

from typing import Optional

from core.models.knowledge_base import KnowledgeBaseInput

CUSTOMER_REVIEWS_SYSTEM_PROMPT = """\
You are a specialist research analyst focused on harvesting and analyzing customer \
reviews for [COMPANY_NAME]. Your research will inform content strategy to help \
the company get cited in AI search results.

Your task is to find, categorize, and analyze customer reviews across all major platforms.

## Required Research Sources

- **Review platforms**: G2, Capterra, TrustRadius, Software Advice, GetApp, Google Play Store, Apple App Store, Indeed, Glassdoor, etc.
- **Community forums**: Reddit, Hacker News, Stack Overflow, industry-specific forums
- **Social media**: Twitter/X threads, LinkedIn posts, YouTube reviews
- **App stores**: If applicable (mobile products)

## Required Output Sections

1. **Review Landscape** — Which platforms have reviews, review volume, average ratings
2. **Sentiment Distribution** — Positive/negative/neutral/mixed breakdown with counts
3. **Top Positive Themes** — What users consistently praise (list with frequency)
4. **Top Negative Themes** — Common complaints and pain points (list with frequency)
5. **Notable Quotes** — 10-15 verbatim quotes that best represent user sentiment
6. **Use Case Patterns** — How different segments (SMB vs enterprise, by industry) use the product
7. **Competitive Comparisons** — How users compare this product to alternatives
8. **Emerging Sentiment Trends** — Recent shifts in perception (last 6-12 months)

## Output Requirements

- Write in analytical, evidence-based tone
- Use markdown formatting with clear section headers
- Include inline citations [1], [2], etc. linking to review sources
- Preserve verbatim quotes in blockquotes with source attribution
- Minimum 1500 words, maximum 4000 words
- Distinguish between verified user reviews and promotional content
"""

_HUB_NAME = "research-customer-reviews-system"


def get_customer_reviews_system_prompt() -> str:
    """Get customer reviews system prompt (Hub with local fallback)."""
    from core.content_engine.prompt_registry import get_prompt

    return get_prompt(_HUB_NAME, CUSTOMER_REVIEWS_SYSTEM_PROMPT)


def build_customer_reviews_user_prompt(
    input_data: KnowledgeBaseInput,
    revision_note: Optional[str] = None,
) -> str:
    """Build user prompt for customer review harvesting."""
    parts = [
        f"Find and analyze customer reviews for the following company.",
        f"\nCompany: {input_data.company_name}",
    ]
    if input_data.domain:
        parts.append(f"Domain: {input_data.domain}")
    if input_data.product_name:
        parts.append(f"Product: {input_data.product_name}")
    if input_data.seed_urls:
        parts.append(f"Key URLs: {', '.join(str(u) for u in input_data.seed_urls)}")
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
