"""Prompts for the Strategic Planner (Stage 1).

The planner reads gap analysis outputs and produces content briefs
that specify exactly what content to create to fill citation gaps.

v2.0: Full structural intelligence — expanded structural_targets (22 fields),
exemplar_summaries, exemplar_themes, style guide awareness.
"""

PLANNER_SYSTEM_PROMPT = """\
You are a strategic content planner for B2B SaaS companies optimizing for AI search citation.

Your task: Analyze the gap analysis data — including structural intelligence about what \
top-cited content looks like — and produce content briefs that will fill citation gaps. \
Each brief must carry enough structural detail for a writer to produce content that \
matches or exceeds the structural fingerprint of content AI search engines actually cite.

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
        "min_citations": 2,
        "min_paragraphs": 8,
        "avg_paragraph_word_count": 80,
        "max_paragraph_word_count": 150,
        "avg_sentence_count_per_paragraph": 3.5,
        "table_rate": 0.0,
        "definition_rate": 0.0,
        "faq_rate": 0.0,
        "code_block_rate": 0.0,
        "min_stats": 2,
        "min_self_contained_claims": 5,
        "min_bullets_per_list": 3,
        "dominant_authority_type": null,
        "dominant_content_type": null,
        "avg_word_count": 0
      },
      "required_structural_elements": ["headers", "lists", "statistics", "citations"],
      "key_topics": ["topic1", "topic2"],
      "key_angles": ["unique angle or hook"],
      "competitor_exemplars": ["urls of competitor content that ranks well"],
      "exemplar_summaries": [
        {
          "url": "https://...",
          "word_count": 0,
          "header_count": 0,
          "list_item_count": 0,
          "stat_count": 0,
          "citation_count": 0,
          "authority_type": "",
          "content_type": "",
          "snippet": "first 200 chars of cited content"
        }
      ],
      "exemplar_themes": ["theme1", "theme2"]
    }
  ],
  "planning_metadata": {
    "total_gaps_analyzed": 0,
    "clusters_covered": [],
    "model_used": "model-name"
  }
}
```

## Structural Intelligence Guidelines

1. **Structural targets** are derived from analyzing what content AI search engines \
actually cite. The gap analysis provides:
   - Per-cluster structural rates (header_rate, list_rate, stat_rate, etc.)
   - Per-cluster authority and content type distributions
   - Per-exemplar structural counts (headers, lists, stats, word counts)
   Use this data to set structural_targets that match or slightly exceed the median \
of what gets cited in each cluster.

2. **Paragraph targets**: Compute from exemplar analysis. AI search engines cite \
self-contained paragraphs of 50-150 words. Set avg_paragraph_word_count to match \
the cluster median. Set min_paragraphs = ceil(target_word_count / avg_paragraph_word_count).

3. **Authority type**: Set dominant_authority_type from the cluster's authority_signals \
distribution (e.g., "industry_report", "company_blog", "academic", "government").

4. **FAQ/table/definition rates**: If >30% of cited content in the cluster has FAQ sections, \
tables, or definitions, set the corresponding rate and add to required_structural_elements.

5. **Self-contained claims**: Target min_self_contained_claims = max(5, ceil(word_count_range[0] / 200)). \
Each claim should be a standalone factual statement that AI search can extract and cite.

6. **Exemplar summaries**: For each brief, include the top 3-5 exemplars from the gap data \
with their structural fingerprints. Include a short snippet for writer reference.

7. **Exemplar themes**: Identify 2-4 common themes or patterns across the exemplars \
(e.g., "step-by-step format", "data-heavy", "comparison tables", "FAQ-driven").

## Content Strategy Guidelines

1. **Priority scoring**: Higher scores for queries with larger gaps (high avg_citation_similarity \
but low company_similarity). A query gap > 0.3 is critical.

2. **Content format selection**:
   - Queries with "how to", "guide", "steps" → how_to
   - Queries comparing solutions → comparison
   - Short definitional queries → short_faq
   - Broad topic queries with many sub-queries → pillar_page
   - Everything else → long_blog

3. **Word count ranges**: Derive from cluster exemplar analysis. Use the median word count \
of top-cited exemplars ±20%. Defaults: long_blog [1200, 2000], short_faq [500, 800], \
pillar_page [2500, 4000], comparison [1500, 2500], how_to [1000, 1800].

4. **Deduplication**: Don't create overlapping briefs. If multiple queries in the same \
cluster have similar gaps, consolidate into one brief with multiple target_queries.

5. **Competitor exemplars**: Pull top_cited_exemplars URLs from the gap data.

6. **Target exactly the requested number of briefs** (max_briefs parameter).

## Style Guide Awareness

You will be provided with the company's writing style guide. Use it to inform:
- Content format choices (does the style guide prefer long-form or short-form?)
- Tone alignment with key_angles
- Structural element preferences (e.g., does the brand prefer numbered lists over bullets?)
Do NOT set style targets in structural_targets — the style guide is applied by downstream workers.
"""


def build_planner_user_prompt(
    *,
    company_name: str,
    domain: str,
    company_context_md: str,
    style_guide_md: str,
    gap_report_json: dict,
    generation_spec_json: dict,
    analysis_json: dict,
    persona_mds: list[str],
    max_briefs: int,
) -> str:
    """Build the user prompt for the planner with all context artifacts.

    Args:
        company_name: Company name.
        domain: Company domain.
        company_context_md: Full company context markdown.
        style_guide_md: Company writing style guide markdown.
        gap_report_json: Gap report as dict.
        generation_spec_json: Content generation spec as dict.
        analysis_json: Full analysis results as dict.
        persona_mds: List of persona profile markdowns.
        max_briefs: Maximum number of briefs to produce.
    """
    persona_section = ""
    if persona_mds:
        persona_section = "\n\n## Persona Profiles\n\n"
        for i, pmd in enumerate(persona_mds, 1):
            if pmd.strip():
                persona_section += f"### Persona {i}\n{pmd}\n\n"

    style_section = ""
    if style_guide_md and style_guide_md.strip():
        style_section = f"\n\n## Writing Style Guide\n\n{style_guide_md}"

    # Extract enriched gap data with exemplar structural intelligence
    gaps_summary = _build_gaps_summary(analysis_json)

    return f"""\
## Company
Name: {company_name}
Domain: {domain}

## Company Context
{company_context_md if company_context_md else "Not provided."}
{style_section}
{persona_section}
{gaps_summary}

## Generation Spec (from gap analysis)
```json
{_safe_json_str(generation_spec_json)}
```

## Gap Report Summary
```json
{_safe_json_str(gap_report_json)}
```

## Instructions
Produce exactly {max_briefs} content briefs as JSON. Prioritize the largest gaps first.
Ensure briefs cover different clusters for maximum coverage breadth.

For each brief, compute structural_targets from the cluster data and exemplar structural
fingerprints. Include exemplar_summaries with the top cited content for each brief's
target queries. Identify exemplar_themes from patterns across exemplars.
"""


def _build_gaps_summary(analysis_json: dict) -> str:
    """Extract enriched gap summary with exemplar structural data."""
    if not analysis_json:
        return ""

    parts = []

    # Top query gaps with exemplar data
    gaps = analysis_json.get("gaps", [])
    if gaps:
        sorted_gaps = sorted(gaps, key=lambda g: g.get("gap", 0) or 0, reverse=True)
        parts.append("\n## Top Query Gaps (sorted by gap size)\n")
        for g in sorted_gaps[:50]:  # Top 50 gaps (was 30)
            query_text = g.get("query_text", "N/A")
            cluster = g.get("cluster_name", "N/A")
            gap_val = g.get("gap", 0)
            company_sim = g.get("best_company_similarity", 0)
            citation_sim = g.get("avg_citation_similarity", 0)

            parts.append(
                f"\n### \"{query_text}\" (cluster: {cluster})\n"
                f"Gap: {gap_val:.2f} | Company sim: {company_sim:.2f} | "
                f"Citation sim: {citation_sim:.2f}"
            )

            # Include exemplar structural data if available
            exemplars = g.get("top_cited_exemplars", [])
            if exemplars:
                parts.append("\nTop cited exemplars:")
                for ex in exemplars[:5]:
                    url = ex.get("url", "")
                    signals = ex.get("structural_signals", {})
                    if signals:
                        wc = signals.get("word_count", 0)
                        hc = signals.get("header_count", 0)
                        lc = signals.get("list_item_count", 0)
                        sc = signals.get("stat_count", 0)
                        auth = signals.get("authority_type", "")
                        parts.append(
                            f"  - {url}: {wc} words, {hc} headers, "
                            f"{lc} lists, {sc} stats, authority={auth}"
                        )
                    elif url:
                        parts.append(f"  - {url}")

    # Cluster specs with authority/structural distributions
    cluster_specs = analysis_json.get("cluster_specs", [])
    if cluster_specs:
        parts.append("\n\n## Cluster Content Specs\n")
        for cs in cluster_specs:
            cluster_name = cs.get("cluster_name", "N/A")
            word_range = cs.get("word_count_range", [0, 0])
            req_elements = cs.get("required_elements", [])
            structural_rates = cs.get("structural_rates", {})
            authority_signals = cs.get("authority_signals", {})

            parts.append(
                f"\n### Cluster: {cluster_name}\n"
                f"Word count range: {word_range}\n"
                f"Required elements: {req_elements}\n"
                f"Structural rates: {_safe_json_str(structural_rates, max_len=2000)}"
            )

            if authority_signals:
                parts.append(
                    f"\nAuthority distribution: {_safe_json_str(authority_signals, max_len=1000)}"
                )

    return "\n".join(parts)


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
