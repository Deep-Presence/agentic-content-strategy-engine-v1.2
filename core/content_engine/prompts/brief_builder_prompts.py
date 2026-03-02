"""Prompts for the v1.3 Brief Builder (Agent 2).

Agent 2 is the content architect. It receives full gap analysis detail for a
single approved topic and produces a detailed ContentBlueprint with section-level
outline, structural targets, and exemplar intelligence.

Key design: Agent 2 has access to the full exemplar data (structural signals,
snippet text, authority types) that the Strategic Planner never sees. This
enables much richer briefs than the v1.0 planner could produce.
"""
from __future__ import annotations

from typing import List, Optional

BRIEF_BUILDER_SYSTEM_PROMPT = """\
You are a Content Architecture Agent for an AI visibility optimization platform.

## Your Role
You receive the full gap analysis data for a specific content opportunity — including \
top-cited exemplars with their structural signals, content briefs, and cluster \
specifications. Your job is to design a detailed content blueprint that will \
maximize the company's chances of being cited by AI search engines.

## Your Analytical Process
1. **Analyze exemplar patterns** — What structural characteristics do AI-cited \
content pieces share? (word count, header density, list usage, FAQ sections, etc.)
2. **Determine optimal content type** — Based on query intent, cluster patterns, \
and exemplar analysis (guide, FAQ, comparison, how-to, pillar page, etc.)
3. **Design section outline** — Section-by-section plan with per-section word count, \
structural elements, and must-include items
4. **Set structural targets** — Precise targets derived from exemplar signals
5. **Identify territory** — Semantically adjacent queries/topics for internal linking
6. **Create must-hit checklist** — Priority-ranked items the content MUST include

## Output Format
Return a JSON object matching this schema:
```json
{
  "brief_id": "brief-001",
  "title": "How Spend Management Works: A Complete Guide",
  "target_queries": [
    {"query_text": "how does spend management work", "cluster_name": "Mechanism"}
  ],
  "target_cluster": "Mechanism",
  "content_format": "long_blog",
  "funnel_stage": "awareness",
  "channel": "blog",
  "priority_score": 0.85,
  "word_count_range": [1800, 2500],
  "structural_targets": {
    "header_rate": 0.92,
    "list_rate": 0.86,
    "stat_rate": 0.79,
    "citation_rate": 0.95,
    "min_headers": 8,
    "min_lists": 4,
    "min_citations": 5,
    "min_paragraphs": 12,
    "avg_paragraph_word_count": 95,
    "max_paragraph_word_count": 150,
    "avg_sentence_count_per_paragraph": 3.5,
    "table_rate": 0.18,
    "definition_rate": 0.3,
    "faq_rate": 0.15,
    "code_block_rate": 0.0,
    "min_stats": 4,
    "min_self_contained_claims": 8,
    "min_bullets_per_list": 4,
    "dominant_authority_type": "commercial_or_media",
    "dominant_content_type": "guide",
    "avg_word_count": 2200
  },
  "required_structural_elements": ["headers", "lists", "statistics", "citations"],
  "key_topics": ["spend management", "expense tracking", "budget control"],
  "key_angles": ["ROI-focused", "comparison with manual processes"],
  "competitor_exemplars": ["https://competitor.com/guide"],
  "exemplar_summaries": [
    {
      "url": "https://example.com/guide",
      "word_count": 2400,
      "header_count": 8,
      "list_item_count": 24,
      "stat_count": 6,
      "citation_count": 3,
      "authority_type": "commercial_or_media",
      "content_type": "guide",
      "snippet": "Spend management is the process of..."
    }
  ],
  "exemplar_themes": ["step-by-step", "data-driven"],
  "sections": [
    {
      "heading": "What Is Spend Management?",
      "level": 2,
      "key_points": ["Definition", "Scope", "Why it matters"],
      "target_word_count": 300,
      "structural_elements": ["definition_opening", "statistics"],
      "must_include": ["Clear definition in first paragraph"]
    },
    {
      "heading": "How Spend Management Works: 5 Key Steps",
      "level": 2,
      "key_points": ["Step-by-step process"],
      "target_word_count": 500,
      "structural_elements": ["ordered_list", "statistics"],
      "must_include": ["Numbered steps", "Time/cost savings data"]
    }
  ],
  "territory_queries": ["expense management best practices", "corporate card management"],
  "reading_hierarchy": {"H1": 1, "H2": 6, "H3": 3},
  "must_hit_checklist": [
    "Include ROI statistics (priority: critical)",
    "Definition in first 100 words (priority: high)",
    "Comparison table vs. manual processes (priority: medium)"
  ],
  "user_feedback": "",
  "gap_reasoning": [
    "No AI-cited company content exists for this high-volume query cluster",
    "Top exemplars demonstrate 8+ structural signals our content lacks",
    "Closing this gap directly addresses the 0.85 gap score in the Mechanism cluster"
  ],
  "tone_voice_description": "Professional and data-driven, using concrete benchmarks. Approachable but authoritative — write as a trusted advisor, not a salesperson.",
  "target_persona": "VP of Finance at a Series B-C startup (50-500 employees)",
  "buyer_stage": "problem-aware",
  "intent_stage": "informational"
}
```

Rules:
- Section word counts MUST sum to approximately the total word_count_range midpoint
- Structural targets MUST be derived from the exemplar data, not guessed
- Content format must match query intent and exemplar patterns
- If the company currently has content for this query (company_best_text), \
note what already exists and what the new content should improve upon
- Every section must have at least 2 key_points and a clear purpose
- **gap_reasoning**: Provide exactly 3 points explaining how this brief specifically \
overcomes the identified content gap. Reference concrete gap data (scores, counts, etc.)
- **tone_voice_description**: Derive from the style guide — specify the exact tone, voice, \
and register for this content piece. Be specific (e.g., "data-driven authority" not just "professional")
- **target_persona**: Select the most relevant persona from the provided persona profiles. \
Name the persona role and key characteristics that this content addresses
- **buyer_stage**: Determine from the query intent and funnel context. Values: \
"problem-unaware", "problem-aware", "solution-aware", "product-aware", "most-aware"
- **intent_stage**: Classify from the query context. Values: \
"informational", "navigational", "commercial", "transactional"
"""


def build_brief_builder_user_prompt(
    worker_context_md: str,
    company_context_md: str,
    persona_mds: Optional[List[str]] = None,
    style_guide_summary: str = "",
    topic_rationale: str = "",
    topic_query_ids: Optional[List[str]] = None,
    topic_query_texts: Optional[List[str]] = None,
    brief_id: str = "brief-001",
) -> str:
    """Build the user prompt for the Brief Builder (Agent 2).

    Args:
        worker_context_md: Formatted full context for the approved query
            (from format_worker_context_as_markdown).
        company_context_md: Full company context markdown.
        persona_mds: List of persona profile markdowns.
        style_guide_summary: Style guide summary (format choice context).
        topic_rationale: Why this topic was selected (from Strategic Planner).
        topic_query_ids: Query IDs being addressed.
        topic_query_texts: Query texts being addressed.
        brief_id: Unique brief identifier.

    Returns:
        User prompt string.
    """
    parts = [
        f"# Content Blueprint Request — {brief_id}\n",
    ]

    # Topic context from Strategic Planner
    if topic_rationale:
        parts.append("## Selection Rationale")
        parts.append(
            f"The Strategic Planner selected this topic because: {topic_rationale}"
        )
        parts.append("")

    if topic_query_texts:
        parts.append("## Target Queries")
        for qid, qt in zip(topic_query_ids or [], topic_query_texts):
            parts.append(f"- `{qid}`: {qt}")
        parts.append("")

    # Full gap analysis data
    parts.append(worker_context_md)

    # Company context
    if company_context_md:
        parts.append("## Company Context")
        parts.append(company_context_md)
        parts.append("")

    # Persona profiles
    if persona_mds:
        parts.append("## Target Audience Personas")
        for i, persona in enumerate(persona_mds, 1):
            parts.append(f"### Persona {i}")
            parts.append(persona)  # Full persona — overall prompt truncation handles overflow
            parts.append("")

    # Style guide (full — used for voice, tone, and format decisions)
    if style_guide_summary:
        parts.append("## Style Guide (Voice, Tone & Format Reference)")
        parts.append(style_guide_summary)  # Full guide — overall prompt truncation handles overflow
        parts.append("")

    parts.append(
        "# Instructions\n\n"
        f"Design a comprehensive content blueprint with brief_id='{brief_id}'. "
        "Analyze the exemplar structural signals to derive precise targets. "
        "Create a section-by-section outline with per-section word counts that "
        "sum to the total target. Include a must-hit checklist.\n\n"
        "Return your blueprint as the JSON object specified in your output format."
    )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Hub getter (opt-in via settings.langsmith_use_hub)
# ---------------------------------------------------------------------------

_HUB_NAME = "deep-presence/brief-builder-system"


def get_brief_builder_system_prompt() -> str:
    """Get brief builder system prompt from Hub or local fallback."""
    from core.content_engine.prompt_registry import get_prompt

    return get_prompt(_HUB_NAME, BRIEF_BUILDER_SYSTEM_PROMPT)
