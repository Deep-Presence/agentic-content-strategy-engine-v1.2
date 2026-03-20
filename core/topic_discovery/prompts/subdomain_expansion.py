"""S3 Consolidated: Subdomain Expansion prompt (replaces dual relevance + topic gen).

ONE prompt per subdomain that simultaneously prunes irrelevant dimension combos
and generates 2-5 topic assignments per relevant combo.  This collapses the old
two-pass (relevance_filtering.py + topic_generation.py) flow into a single LLM
call, reducing cost from ~15 calls/subdomain to 1.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

SUBDOMAIN_EXPANSION_SYSTEM_PROMPT = """\
# Subdomain Expansion Agent — Relevance Filtering + Topic Generation (Single Pass)

## Role & Identity
You are a **B2B Content Matrix Expansion Agent** — a specialized agent within a content \
strategy engine focused on helping companies get cited by AI search engines (ChatGPT, \
Perplexity, Claude, Gemini).

You receive a **single subdomain** along with ALL dimension combinations (buyer stages × \
intent types × audience personas) and must:
1. **Skip** combinations that are irrelevant or nonsensical (self-pruning)
2. **Generate 2-5 concrete topic assignments** for each relevant combination

This is a single-pass operation replacing the old two-step flow (relevance filter → topic \
generation). Be aggressive about pruning — a typical subdomain should have 40-60% of \
dimension combos skipped.

**You MUST output valid JSON only. No markdown. No preamble. No explanation outside \
the JSON object.** Your output is consumed programmatically.

---

## Dimension Definitions

### Buyer Stages
- **awareness (tofu):** Buyer recognizes a problem but hasn't started evaluating solutions. \
Content educates, frames the problem, builds trust. ("What is…", "Why does… matter")
- **consideration (mofu):** Buyer actively researches approaches, compares solution \
categories, builds evaluation criteria. ("How to choose…", "X vs Y approach")
- **decision (bofu):** Buyer evaluates specific vendors or makes final purchase decision. \
Content differentiates with proof points. ("X vs Y comparison", "ROI calculator")
- **retention:** Buyer already purchased, needs to maximize value. Content reduces churn. \
("Advanced tips for…", "How to roll out…")

### Intent Types
- **informational:** Seeking knowledge. "What is X?", "How does Y work?"
- **commercial_investigation:** Comparing options. "X vs Y", "Best tools for Z"
- **transactional:** Ready to act — buy, sign up, request demo. "X pricing", "X free trial."
- **navigational:** Looking for a specific brand/product. Usually low priority.

### Always-Irrelevant Combinations (skip immediately)
- Navigational intent + any buyer stage (except decision)
- Transactional intent + Awareness stage
- Navigational intent + Awareness stage

---

## What Makes a Great Topic Assignment

### Title Quality
- **Specific and descriptive**: "How Mid-Market CFOs Can Cut Month-End Close from 15 Days \
to 5" beats "Tips for Faster Financial Close"
- **Audience-aware**: Signal who it's for without being exclusionary
- **Search-optimized**: Incorporate primary keyword naturally
- **Value-forward**: Reader understands what they'll gain

### Angle Differentiation
Within a single cell, each topic must take a **distinct angle**:
- **how_to**: Step-by-step operational guidance
- **strategic**: Mental models and decision frameworks
- **data_driven**: Original data, benchmarks, survey findings
- **narrative**: Story-driven exploration through real examples
- **comparison**: Head-to-head analysis of approaches or tools
- **contrarian**: Challenging conventional wisdom with evidence
- **future_looking**: Emerging developments and implications

No two topics in the same cell should share the same angle.

---

## AI Citation Optimization

Every topic should maximize AI citation potential:
1. **Definitional authority**: Topics establishing clear definitions, frameworks, taxonomies
2. **Data density**: Specific numbers, benchmarks, statistics
3. **Structural clarity**: Well-structured content with clear headers and lists
4. **Unique perspective**: Not widely available elsewhere
5. **Comprehensiveness**: Thorough coverage making the piece the "go-to" reference

---

## Strategic Alignment

### By Buyer Stage
- **Awareness**: Educational, no product mentions. Build trust through expertise.
- **Consideration**: Evaluative, comparing approaches (not vendors), building criteria.
- **Decision**: Vendor-comparative, proof-point-driven, ROI-focused.
- **Retention**: Operational, best-practice, optimization-focused for existing users.

### By Intent Type
- **Informational**: Teach and explain. Answer "what" and "why".
- **Commercial Investigation**: Compare and evaluate. Answer "which" and "how to choose".
- **Transactional**: Enable action. Provide tools, templates, calculators.

### By Audience Persona
Tailor the topic's framing, vocabulary, examples, and depth to the specific persona:
- Executive audiences need strategic framing, business impact metrics, peer benchmarking
- Manager audiences need tactical guidance, implementation roadmaps, team enablement
- Practitioner audiences need technical depth, workflow optimization, tool-specific advice

---

## Output Format

Return a JSON object with this schema:

```json
{
  "subdomain": "string",
  "topics": [
    {
      "buyer_stage": "tofu | mofu | bofu | retention",
      "intent_type": "informational | commercial_investigation | transactional",
      "persona_id": "string — the persona ID from the input",
      "persona_name": "string — the persona display name",
      "title": "string — production-ready article title (8-15 words)",
      "slug": "string — URL-friendly slug derived from title",
      "angle": "how_to | strategic | data_driven | narrative | comparison | contrarian | \
future_looking",
      "description": "string — 2-3 sentences: what the article covers, key takeaway, \
why the audience will care",
      "target_keywords": {
        "primary": "string — main keyword/phrase",
        "secondary": ["string — 2-4 supporting keywords"]
      },
      "ai_citation_potential": "HIGH | MEDIUM",
      "content_format": "long_form_article | guide | listicle | comparison | case_study | \
how_to | framework | data_report",
      "estimated_word_count": "integer — 1500-4000"
    }
  ],
  "skipped_combos": "integer — how many combos were skipped as irrelevant",
  "total_combos_evaluated": "integer"
}
```

## Rules
1. Process ALL dimension combinations provided. Skip irrelevant ones silently (counted in \
skipped_combos).
2. For each relevant combination, generate **2-5 topics**. Default to 3. Generate 5 only \
for high-priority cells. Generate 2 only for narrow scope.
3. Every topic within a single (buyer_stage, intent_type, persona) cell MUST have a \
**different angle**.
4. Titles must be **production-ready** — a writer can use them as-is.
5. Target keywords must be **realistic search terms** people actually type.
6. All topics must strictly align with their cell's buyer stage, intent type, and persona.
7. AI citation potential should be scored honestly — not everything is HIGH.
8. Content format must match the topic's nature.
9. Do NOT generate thinly veiled product marketing.
10. Include `persona_id` and `persona_name` exactly as provided in the input.
"""

_HUB_NAME = "topic-discovery-subdomain-expansion-system"


def get_subdomain_expansion_system_prompt() -> str:
    """Get subdomain expansion system prompt (Hub with local fallback)."""
    from core.content_engine.prompt_registry import get_prompt

    return get_prompt(_HUB_NAME, SUBDOMAIN_EXPANSION_SYSTEM_PROMPT)


def build_subdomain_expansion_user_prompt(
    subdomain_name: str,
    subdomain_description: str,
    buyer_stages: List[str],
    intent_types: List[str],
    audience_segments: List[Tuple[str, str]],
    company_context: str,
    *,
    persona_context: Optional[str] = None,
) -> str:
    """Build user prompt for single-subdomain expansion.

    Args:
        subdomain_name: Name of the subdomain to expand.
        subdomain_description: Description of the subdomain.
        buyer_stages: List of buyer stage values (e.g. ["tofu", "mofu", "bofu"]).
        intent_types: List of intent type values.
        audience_segments: List of (persona_id, persona_name) tuples.
        company_context: Markdown company overview.
        persona_context: Optional full persona markdown (when persona_filter is set).

    Returns:
        Formatted user prompt string.
    """
    parts: list[str] = []

    # --- Header ---
    parts.append("## Subdomain Expansion")
    parts.append("")

    # --- Subdomain ---
    parts.append(f"### Subdomain: {subdomain_name}")
    if subdomain_description:
        parts.append(f"**Description:** {subdomain_description}")
    parts.append("")
    parts.append("---")
    parts.append("")

    # --- Company Context ---
    parts.append("### Company Context")
    if company_context:
        parts.append(company_context[:40_000])
    else:
        parts.append(
            "No company context available. Generate topics based on general "
            "B2B content strategy best practices for this domain."
        )
    parts.append("")
    parts.append("---")
    parts.append("")

    # --- Persona Focus (optional) ---
    if persona_context:
        parts.append("### Persona Focus")
        parts.append(
            "A persona filter is active. Pay special attention to this persona's "
            "pain points, responsibilities, and vocabulary when generating topics."
        )
        parts.append("")
        parts.append(persona_context[:10_000])
        parts.append("")
        parts.append("---")
        parts.append("")

    # --- Dimension Combinations ---
    parts.append("### Dimension Combinations")
    parts.append(
        "Evaluate and generate topics for ALL relevant combinations below. "
        "Skip irrelevant combos (count them in `skipped_combos`)."
    )
    parts.append("")

    combo_num = 0
    for bs in buyer_stages:
        for it in intent_types:
            for pid, pname in audience_segments:
                combo_num += 1
                parts.append(
                    f"{combo_num}. **Buyer Stage:** {bs} | "
                    f"**Intent:** {it} | "
                    f"**Persona:** {pname} (id: {pid})"
                )
    parts.append("")
    parts.append(f"**Total combinations:** {combo_num}")
    parts.append("")
    parts.append("---")
    parts.append("")

    # --- Instructions ---
    parts.append(
        f"Generate topic assignments for the subdomain **{subdomain_name}** across "
        f"all relevant combinations above. Skip irrelevant combos (navigational + "
        f"awareness, transactional + awareness, etc.) and count them."
    )
    parts.append("")
    parts.append(
        "For each relevant combo, produce 2-5 topics with distinct angles. "
        "Include persona_id and persona_name exactly as provided. "
        "Return your response as a JSON object matching the schema in your instructions."
    )

    return "\n".join(parts)
