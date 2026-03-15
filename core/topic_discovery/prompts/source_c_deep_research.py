"""Source C: Deep Research competitive content landscape analysis (S1 of Topic Discovery).

Uses Perplexity deep research to analyze the competitive content landscape,
identify content subdomains (established, emerging, whitespace), and surface
gaps that represent high-opportunity content territories.
"""
from __future__ import annotations

SOURCE_C_SYSTEM_PROMPT = """\
You are a competitive content landscape analyst for B2B companies. You will \
receive a company context, its competitive landscape, and its industry domain. \
Your job is to research the current content landscape in this industry and \
identify content subdomains — knowledge territories that represent distinct \
content opportunities.

You MUST output valid JSON only. No markdown. No preamble. No explanation \
outside the JSON object.

RESEARCH FOCUS:

1. What content themes are the major publishers in this industry actively \
covering? Identify the distinct topic clusters they've built content hubs around.

2. Where are the GAPS — topics that matter to this industry but have no \
definitive, comprehensive source? Look for topics where search results return \
shallow, outdated, or generic content.

3. What's EMERGING — new regulations, technology shifts, or market changes \
in the last 6-12 months that are creating fresh content demand?

4. What NICHE topics have almost zero quality content? These are narrow but \
valuable — a single authoritative guide can own the space. Do NOT deprioritize \
topics for being niche. Niche + no competition = high opportunity.

OUTPUT FORMAT:
{
  "subdomains": [
    {
      "name": "string — 2-6 word subdomain label using industry terminology",
      "description": "string — 1-2 sentences: what this covers and what the \
current content landscape looks like for it",
      "competitive_density": "high | medium | low",
      "source_type": "established | emerging | whitespace",
      "confidence": 0.0-1.0
    }
  ],
  "metadata": {
    "publishers_identified": ["string — major content publishers found"],
    "top_gaps": ["string — biggest content gaps identified"],
    "emerging_trends": ["string — key trends creating new demand"]
  }
}

RULES:
- Generate 15-25 subdomains
- Every subdomain must be grounded in what you actually found during research — \
do not invent topics without evidence
- competitive_density: "high" = 3+ strong publishers, "medium" = 1-2 or shallow, \
"low" = little to no quality content
- source_type: "established" = well-known topic, "emerging" = recent trend, \
"whitespace" = gap no one covers well
- confidence: 0.8+ = strongly evidenced, 0.6-0.79 = moderately evidenced, \
0.4-0.59 = inferred. Do not include anything below 0.4
- Balance output across established, emerging, and whitespace — do not \
over-index on mainstream topics
"""

_HUB_NAME = "topic-discovery-source-c-deep-research-system"


def get_source_c_system_prompt() -> str:
    """Get Source C system prompt (Hub with local fallback)."""
    from core.content_engine.prompt_registry import get_prompt

    return get_prompt(_HUB_NAME, SOURCE_C_SYSTEM_PROMPT)


def build_source_c_user_prompt(
    company_context: str,
    competitor_landscape: str,
    domain: str,
    *,
    revision_note: str | None = None,
) -> str:
    """Build user prompt for Source C deep research.

    Args:
        company_context: Company context markdown (truncated).
        competitor_landscape: Competitive landscape artifact from KB.
        domain: Company domain/industry.
        revision_note: Optional HITL retry feedback.
    """
    parts: list[str] = []

    parts.append(f"## Industry Domain: {domain}")
    parts.append("")

    # Company context — truncated to keep Perplexity focused
    parts.append("## Company Context (summary)")
    ctx_words = company_context.split()[:1500]
    parts.append(" ".join(ctx_words))
    parts.append("")

    # Competitive landscape from KB artifact
    parts.append("## Competitive Landscape")
    if competitor_landscape:
        cl_words = competitor_landscape.split()[:3000]
        parts.append(" ".join(cl_words))
    else:
        parts.append(
            "No competitor data provided. Identify the major content "
            "publishers in this space as part of your research."
        )
    parts.append("")

    parts.append(
        "Research the current B2B content landscape for this industry. "
        "Identify what's well-covered, what's missing, and what's emerging. "
        "Return your findings as a JSON object matching the schema in "
        "your instructions."
    )

    if revision_note:
        parts.append("")
        parts.append(f"## Reviewer Feedback\n{revision_note}")

    return "\n".join(parts)
