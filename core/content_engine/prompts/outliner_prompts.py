"""Prompts for the Outliner worker (Step 1 of worker chain).

v2.0: Full structural intelligence — structural_elements per section,
self_contained_claims, FAQ/table/takeaway flags, exemplar awareness.
"""
import json

OUTLINER_SYSTEM_PROMPT = """\
You are an expert content outline architect specializing in B2B SaaS content \
optimized for AI search engine citations.

Your task: Create a detailed content outline that, when executed, will produce \
an article that AI search engines will cite as an authoritative source. Use the \
structural targets and exemplar intelligence to design an outline that matches \
or exceeds the structural fingerprint of content that actually gets cited.

## Output Format

Respond with ONLY valid JSON matching this schema:

```json
{
  "brief_id": "brief-001",
  "title": "Article Title",
  "sections": [
    {
      "heading": "Section Heading",
      "level": 2,
      "key_points": ["Point 1", "Point 2"],
      "target_word_count": 300,
      "structural_elements": ["bullet_list", "statistics", "definition"],
      "self_contained_claims": 2
    }
  ],
  "total_target_words": 1500,
  "has_faq_section": false,
  "has_table_section": false,
  "has_key_takeaways": false
}
```

### Field definitions:
- **structural_elements**: List of structural elements this section should contain. \
Values: "bullet_list", "numbered_list", "table", "definition", "statistics", \
"data_point", "code_block", "quote", "comparison", "example", "faq_pairs"
- **self_contained_claims**: Number of self-contained factual statements in this section \
that can be independently extracted and cited by AI search engines. Each claim should be \
a 1-3 sentence paragraph that makes a complete factual assertion with supporting data.
- **has_faq_section**: Set true if the outline includes a dedicated FAQ section
- **has_table_section**: Set true if the outline includes a section with a comparison/data table
- **has_key_takeaways**: Set true if the outline includes a key takeaways/summary section

## Structural Guidelines

1. **Opening**: Start with a strong H2 that directly addresses the target query. \
AI search engines favor content that leads with the answer.

2. **Heading hierarchy**: Use H2 for main sections, H3 for subsections. \
Never skip levels (no H4 under H2).

3. **Answer-first structure**: Each section should lead with the key takeaway, \
then provide supporting detail. This mirrors how AI engines extract citations.

4. **Self-contained paragraphs**: Design sections so each paragraph of 50-150 words \
makes a complete, citable claim. AI search engines cite self-contained paragraphs, \
not fragments that depend on surrounding context.

5. **Data sections**: Include at least one section specifically for statistics, \
benchmarks, or quantitative data. AI engines heavily cite numerical claims.

6. **Comparison/context**: Include a section that positions the topic relative \
to alternatives or industry context.

7. **Structural elements per section**: Assign specific structural elements to each \
section based on the structural targets. If the targets call for tables, bullets, \
FAQ pairs, etc., distribute them across appropriate sections.

8. **Actionable close**: End with concrete next steps or recommendations.

9. **Word count distribution**: Allocate words proportionally — main content \
sections should get the most. Target the total_target_words to fall within the \
brief's word_count_range (use the midpoint as target).

## Structural Competitiveness

Study the exemplar summaries provided. Your outline must be at least as structurally \
rich as the top-cited exemplars:
- If exemplars average 7 headers, plan for at least 7 H2/H3 headings
- If exemplars have 12 list items, distribute bullet/numbered lists across sections
- If the faq_rate > 0.3, include a dedicated FAQ section with Q&A pairs
- If the table_rate > 0.3, include at least one comparison or data table
- If exemplars average 5+ stats, ensure stat-heavy sections
"""


def build_outliner_user_prompt(
    *,
    brief_id: str,
    title: str,
    target_queries: list[dict],
    content_format: str,
    funnel_stage: str,
    word_count_range: tuple[int, int],
    key_topics: list[str],
    key_angles: list[str],
    structural_targets: dict,
    company_context_snippet: str,
    exemplar_summaries: list[dict] | None = None,
    exemplar_themes: list[str] | None = None,
) -> str:
    """Build the user prompt for the outliner.

    Args:
        brief_id: Brief identifier.
        title: Content title.
        target_queries: List of query dicts.
        content_format: Content format type.
        funnel_stage: Funnel stage.
        word_count_range: Min/max word count.
        key_topics: Key topics to cover.
        key_angles: Unique angles or hooks.
        structural_targets: Full structural targets dict (22 fields).
        company_context_snippet: Company context markdown.
        exemplar_summaries: Structural fingerprints of top-cited content.
        exemplar_themes: Common themes across exemplars.
    """
    queries_str = "\n".join(
        f"  - \"{q.get('query_text', '')}\" (cluster: {q.get('cluster_name', '')})"
        for q in target_queries
    )

    # Build full structural targets section
    st = structural_targets
    structural_section = f"""\
### Structural Targets (from gap analysis — what gets cited)
- Min headers: {st.get('min_headers', 3)}
- Min lists: {st.get('min_lists', 1)}
- Min citations: {st.get('min_citations', 2)}
- Min stats: {st.get('min_stats', 2)}
- Min paragraphs: {st.get('min_paragraphs', 8)}
- Avg paragraph word count: {st.get('avg_paragraph_word_count', 80)}
- Max paragraph word count: {st.get('max_paragraph_word_count', 150)}
- Avg sentences per paragraph: {st.get('avg_sentence_count_per_paragraph', 3.5)}
- Min self-contained claims: {st.get('min_self_contained_claims', 5)}
- Min bullets per list: {st.get('min_bullets_per_list', 3)}
- FAQ rate (fraction of cited content with FAQ): {st.get('faq_rate', 0.0)}
- Table rate (fraction of cited content with tables): {st.get('table_rate', 0.0)}
- Definition rate: {st.get('definition_rate', 0.0)}
- Dominant authority type: {st.get('dominant_authority_type', 'N/A')}
- Dominant content type: {st.get('dominant_content_type', 'N/A')}
- Avg word count of cited content: {st.get('avg_word_count', 0)}"""

    # Exemplar intelligence section
    exemplar_section = ""
    if exemplar_summaries:
        exemplar_section = "\n\n### Exemplar Intelligence (top-cited content for these queries)\n"
        for i, ex in enumerate(exemplar_summaries[:5], 1):
            url = ex.get("url", "")
            wc = ex.get("word_count", 0)
            hc = ex.get("header_count", 0)
            lc = ex.get("list_item_count", 0)
            sc = ex.get("stat_count", 0)
            auth = ex.get("authority_type", "")
            ctype = ex.get("content_type", "")
            exemplar_section += (
                f"\nExemplar {i}: {url}\n"
                f"  {wc} words | {hc} headers | {lc} list items | {sc} stats | "
                f"authority: {auth} | type: {ctype}"
            )

    themes_section = ""
    if exemplar_themes:
        themes_section = (
            "\n\n### Exemplar Themes (common patterns in cited content)\n"
            + "\n".join(f"- {t}" for t in exemplar_themes)
        )

    return f"""\
## Content Brief

Brief ID: {brief_id}
Title: {title}
Format: {content_format}
Funnel Stage: {funnel_stage}
Word Count Range: {word_count_range[0]}-{word_count_range[1]} words

### Target Queries (optimize for these)
{queries_str}

### Key Topics
{', '.join(key_topics) if key_topics else 'Derive from target queries'}

### Key Angles
{', '.join(key_angles) if key_angles else 'Find unique, authoritative angles'}

{structural_section}
{exemplar_section}
{themes_section}

### Company Context
{company_context_snippet if company_context_snippet else 'Not provided.'}

Create a detailed outline for this content piece. Design each section with specific \
structural elements and self-contained claims. Ensure the total_target_words falls \
within the word count range [{word_count_range[0]}, {word_count_range[1]}].

If faq_rate > 0.3, include a dedicated FAQ section and set has_faq_section=true.
If table_rate > 0.3, include a section with a comparison/data table and set has_table_section=true.
Always include a Key Takeaways section at the end and set has_key_takeaways=true \
unless the format is short_faq.
"""
