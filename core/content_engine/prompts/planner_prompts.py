"""Prompts for the Strategic Planner (Stage 1).

The planner reads gap analysis outputs and produces content briefs
that specify exactly what content to create to fill citation gaps.
"""

PLANNER_SYSTEM_PROMPT = """\
You are a strategic content planner for B2B SaaS companies optimizing for AI search citation.

Your task: Analyze the gap analysis data and produce a set of content briefs that will
fill the identified gaps in AI search coverage. Each brief specifies a single content
piece with enough detail for a writer to execute.

## Output Format

Respond with ONLY valid JSON matching this schema:

```json
{
  "briefs": [
    {
      "brief_id": "brief-001",
      "title": "Clear, specific article title",
      "target_queries": [
        {"query_text": "the search query to optimize for", "cluster_name": "cluster-name"}
      ],
      "target_cluster": "cluster-name",
      "content_format": "long_blog|short_faq|pillar_page|comparison|how_to",
      "funnel_stage": "awareness|consideration|decision|retention",
      "channel": "blog|help_center|landing_page|resource_hub",
      "priority_score": 0.0-1.0,
      "word_count_range": [min_words, max_words],
      "structural_targets": {
        "header_rate": 0.0,
        "list_rate": 0.0,
        "stat_rate": 0.0,
        "citation_rate": 0.0,
        "min_headers": 3,
        "min_lists": 1,
        "min_citations": 2
      },
      "required_structural_elements": ["headers", "lists", "statistics", "citations"],
      "key_topics": ["topic1", "topic2"],
      "key_angles": ["unique angle or hook"],
      "competitor_exemplars": ["urls of competitor content that ranks well"]
    }
  ],
  "planning_metadata": {
    "total_gaps_analyzed": 0,
    "clusters_covered": [],
    "model_used": "model-name"
  }
}
```

## Guidelines

1. **Priority scoring**: Higher scores for queries with larger gaps (high avg_citation_similarity
   but low company_similarity). A query gap > 0.3 is critical.

2. **Content format selection**:
   - Queries with "how to", "guide", "steps" → how_to
   - Queries comparing solutions → comparison
   - Short definitional queries → short_faq
   - Broad topic queries → pillar_page
   - Everything else → long_blog

3. **Word count ranges**: Derive from cluster_specs.word_count_range when available.
   Default to [1200, 2000] for long_blog, [500, 800] for short_faq, [2500, 4000] for pillar_page.

4. **Structural targets**: Derive from cluster_specs.structural_rates when available.
   These define what successful content looks like in each cluster based on
   analysis of top-cited competitor content.

5. **Deduplication**: Don't create overlapping briefs. If multiple queries in the same
   cluster have similar gaps, consolidate into one brief with multiple target_queries.

6. **Competitor exemplars**: Pull top_cited_exemplars URLs from the gap data.

7. **Target exactly the requested number of briefs** (max_briefs parameter).
"""


def build_planner_user_prompt(
    *,
    company_name: str,
    domain: str,
    company_context_md: str,
    gap_report_json: dict,
    generation_spec_json: dict,
    analysis_json: dict,
    persona_mds: list[str],
    max_briefs: int,
) -> str:
    """Build the user prompt for the planner with all context artifacts."""

    persona_section = ""
    if persona_mds:
        persona_section = "\n\n## Persona Profiles\n\n"
        for i, pmd in enumerate(persona_mds, 1):
            if pmd.strip():
                persona_section += f"### Persona {i}\n{pmd}\n\n"

    # Extract key data from analysis JSON
    gaps_summary = ""
    if analysis_json:
        gaps = analysis_json.get("gaps", [])
        if gaps:
            # Sort by gap size (descending)
            sorted_gaps = sorted(gaps, key=lambda g: g.get("gap", 0) or 0, reverse=True)
            gaps_summary = "\n## Top Query Gaps (sorted by gap size)\n\n"
            for g in sorted_gaps[:30]:  # Top 30 gaps
                gaps_summary += (
                    f"- **{g.get('query_text', 'N/A')}** "
                    f"(cluster: {g.get('cluster_name', 'N/A')}, "
                    f"gap: {g.get('gap', 0):.2f}, "
                    f"company_sim: {g.get('best_company_similarity', 0):.2f}, "
                    f"citation_sim: {g.get('avg_citation_similarity', 0):.2f})\n"
                )

        cluster_specs = analysis_json.get("cluster_specs", [])
        if cluster_specs:
            gaps_summary += "\n## Cluster Content Specs\n\n"
            for cs in cluster_specs:
                gaps_summary += (
                    f"- **{cs.get('cluster_name', 'N/A')}**: "
                    f"word_count_range={cs.get('word_count_range', [0, 0])}, "
                    f"required_elements={cs.get('required_elements', [])}, "
                    f"structural_rates={cs.get('structural_rates', {})}\n"
                )

    return f"""\
## Company
Name: {company_name}
Domain: {domain}

## Company Context
{company_context_md[:8000] if company_context_md else "Not provided."}
{persona_section}
{gaps_summary}

## Generation Spec (from gap analysis)
```json
{_safe_json_str(generation_spec_json)}
```

## Gap Report Summary
```json
{_safe_json_str(gap_report_json, max_len=6000)}
```

## Instructions
Produce exactly {max_briefs} content briefs as JSON. Prioritize the largest gaps first.
Ensure briefs cover different clusters for maximum coverage breadth.
"""


def _safe_json_str(data: dict, max_len: int = 10000) -> str:
    """Safely serialize dict to JSON string, truncating if needed."""
    import json

    try:
        s = json.dumps(data, indent=2, default=str)
        if len(s) > max_len:
            return s[:max_len] + "\n... [truncated]"
        return s
    except Exception:
        return "{}"
