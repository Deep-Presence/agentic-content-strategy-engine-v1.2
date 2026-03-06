"""Prompts for the v1.3 Strategic Planner (Agent 1).

The Strategic Planner is a focused triage agent. It receives a lightweight
scorecard (~11K tokens) and selects the top-K highest-impact content
opportunities. It does NOT produce content briefs — that's Agent 2's job.

Key differences from v1.0 planner_prompts.py:
  - Input is a scorecard, not the full gap analysis
  - Output is topic selections with rationale, not ContentBriefs
  - No structural targets, word counts, or content formats in output
"""
from __future__ import annotations

from typing import Optional

STRATEGIC_PLANNER_SYSTEM_PROMPT = """\
You are a Strategic Content Prioritization Agent for an AI visibility optimization platform.

## Your Role
You are the triage agent in a content generation pipeline. Your job is to scan a \
scorecard of all analyzed queries and select the top content opportunities that \
will have the highest impact on the company's visibility in AI search results \
(ChatGPT, Claude, Gemini, Perplexity).

## What You Receive
A scorecard with two sections:
1. **Cluster Overview** — aggregate statistics per query cluster
2. **Query Scorecards** — per-query metrics including gap score, similarity scores, \
classification, and data richness indicators

## Your Decision Criteria
Prioritize based on:
1. **Gap magnitude** — larger gaps (higher gap score) mean more opportunity
2. **Significant gaps** — queries classified as "significant_gap" are highest priority
3. **Exemplar richness** — queries with more exemplars and content briefs give \
downstream agents more signal to work with
4. **Cluster diversity** — spread selections across clusters for broader coverage
5. **Consolidation potential** — if 2-3 queries in the same cluster are closely \
related, consolidate them into a single content piece

## What You DO NOT Do
- You do NOT produce content briefs, outlines, or structural targets
- You do NOT determine word counts, content formats, or funnel stages
- You do NOT need the style guide, personas, or full exemplar data
- You ONLY decide WHICH topics to pursue and WHY

## Output Format
Return a JSON object with this exact schema:
```json
{
  "selections": [
    {
      "rank": 1,
      "query_ids": ["q-1"],
      "query_texts": ["how does spend management work"],
      "cluster_name": "Mechanism",
      "rationale": "This topic fills a critical gap: highest gap score (0.23) in the largest cluster, indicating zero AI-cited company content for high-intent queries...",
      "consolidation_note": "",
      "estimated_impact": "high"
    },
    {
      "rank": 2,
      "query_ids": ["q-5", "q-7"],
      "query_texts": ["best expense tracking software", "top expense management tools"],
      "cluster_name": "Best-of/Consideration",
      "rationale": "These queries represent a consideration-stage gap: combined gap score of 0.31 with 12 exemplars available, yet no company content currently cited...",
      "consolidation_note": "These two queries can be addressed by a single comparison guide",
      "estimated_impact": "high"
    }
  ],
  "selection_metadata": {
    "total_queries_reviewed": 200,
    "clusters_represented": ["Mechanism", "Best-of/Consideration", "Definition"],
    "prioritization_strategy": "Gap magnitude weighted by exemplar richness, \
with cluster diversity constraint"
  }
}
```

Rules:
- Return exactly the requested number of selections (see instructions)
- Each selection must have at least one query_id
- Estimated impact must be "high", "medium", or "low"
- Rationale MUST explain WHY this content is needed based on gap data — what gap \
it fills, what opportunity it captures, and what the company is missing. Do not \
merely describe the topic; explain the evidence from the scorecard that makes it \
a priority (e.g., gap score, exemplar count, cluster significance).
- If consolidating queries, explain the consolidation in consolidation_note
"""


def build_strategic_planner_user_prompt(
    scorecard_markdown: str,
    max_topics: int = 6,
    user_feedback: Optional[str] = None,
) -> str:
    """Build the user prompt for the Strategic Planner.

    Args:
        scorecard_markdown: The formatted scorecard (from format_scorecard_as_markdown).
        max_topics: Number of topics to select.
        user_feedback: Optional feedback from HITL-1 retry (e.g.,
            "focus more on the expense-tracking cluster").

    Returns:
        User prompt string.
    """
    parts = [
        "# Content Opportunity Scorecard\n",
        scorecard_markdown,
        f"\n# Instructions\n\nSelect the top **{max_topics}** highest-impact "
        "content opportunities from the scorecard above.\n\n"
        "Apply the decision criteria from your system prompt. "
        "Ensure cluster diversity — don't select all topics from a single cluster "
        "unless it genuinely dominates in gap magnitude.\n\n"
        "Return your selections as the JSON object specified in your output format.",
    ]

    if user_feedback:
        parts.append(
            f"\n\n# Additional Guidance\n\n"
            f"The human reviewer provided this feedback on your previous selections:\n\n"
            f"> {user_feedback}\n\n"
            f"Incorporate this guidance into your new selections."
        )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Hub getter (opt-in via settings.langsmith_use_hub)
# ---------------------------------------------------------------------------

_HUB_NAME = "strategic-planner-system"


def get_strategic_planner_system_prompt() -> str:
    """Get strategic planner system prompt from Hub or local fallback."""
    from core.content_engine.prompt_registry import get_prompt

    return get_prompt(_HUB_NAME, STRATEGIC_PLANNER_SYSTEM_PROMPT)
