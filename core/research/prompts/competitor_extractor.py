"""Competitor Registry Extractor — structured JSON extraction from markdown.

Pass 2 of the two-pass competitor analysis pipeline.  Pass 1 (Perplexity
sonar-deep-research) produces a rich markdown report.  This prompt drives
Claude Haiku to extract structured ``CompetitorRegistryStructured`` JSON
from that markdown.

The extraction is deterministic (temperature=0) and costs ~$0.001/call.
"""
from __future__ import annotations

from core.models.knowledge_base import CompetitorRegistryStructured

COMPETITOR_EXTRACTOR_SYSTEM_PROMPT = """\
You are a structured data extraction specialist.  Your ONLY job is to read \
a competitive landscape analysis document (markdown) and output a single \
JSON object that captures ALL competitors, their details, and the market \
context described in the document.

## Rules

1. Output ONLY valid JSON — no markdown fences, no commentary, no preamble.
2. Follow the JSON schema EXACTLY as provided in the user message.
3. Map each competitor to the correct category based on the section headers:
   - "Direct Competitors" → direct_competitors
   - "Mindshare Competitors" → mindshare_competitors
   - "Niche" or "Specialized Competitors" → niche_competitors
   - "Emerging Competitors" → emerging_competitors
   - If unclear, default to "mindshare"
4. Extract relevance_score from textual cues:
   - "Direct (Very High)" or "Direct (High)" → 0.9
   - "Direct (Medium-High)" → 0.75
   - "Mindshare (Very High)" → 0.85
   - "Mindshare (High)" → 0.8
   - "Mindshare (Medium)" → 0.6
   - "Niche (Low)" → 0.3
   - If no score mentioned, estimate based on analysis depth (more text = higher)
5. Extract strengths from subsections like "Competitive Strengths", \
"Advantages", or "Key Strengths" — keep each as a concise bullet point.
6. Extract weaknesses from subsections like "Where X Falls Short", \
"Limitations", or "Weaknesses" — keep each as a concise bullet point.
7. Extract domain from mentioned URLs, or derive from company name \
(e.g., "Wix" → "wix.com", "Shopify" → "shopify.com").
8. Capture the "Market Map" section text in market_map.
9. Capture "Competitive Positioning" or similar in competitive_positioning.
10. Capture "Feature Comparison" summary in feature_comparison_summary \
(prose summary, not a table).
11. Set total_competitor_count to the total number of unique competitors.
12. Preserve ALL competitor details from the source — do not drop any.
"""

_HUB_NAME = "research-competitor-extractor-system"


def get_competitor_extractor_system_prompt() -> str:
    """Get competitor extractor system prompt (Hub with local fallback)."""
    from core.content_engine.prompt_registry import get_prompt

    return get_prompt(_HUB_NAME, COMPETITOR_EXTRACTOR_SYSTEM_PROMPT)


def build_competitor_extractor_user_prompt(
    competitor_registry_md: str,
    company_name: str = "",
) -> str:
    """Build user prompt for structured extraction from competitor markdown.

    Args:
        competitor_registry_md: Full markdown output from the competitor
            scanner agent (Pass 1).
        company_name: Target company name for context.
    """
    schema = CompetitorRegistryStructured.model_json_schema()

    parts = [
        "Extract ALL competitor data from the following competitive landscape "
        "analysis into the JSON schema below.",
    ]
    if company_name:
        parts.append(f"\nTarget company (NOT a competitor): {company_name}")
    parts.append(f"\n## JSON Schema\n\n```json\n{_compact_schema(schema)}\n```")
    parts.append(f"\n## Source Document\n\n{competitor_registry_md}")
    return "\n".join(parts)


def _compact_schema(schema: dict) -> str:
    """Produce a compact but readable JSON schema string."""
    import json

    # Remove verbose $defs expansion — the model names are self-explanatory
    cleaned = {k: v for k, v in schema.items() if k != "$defs"}
    return json.dumps(cleaned, indent=2)
