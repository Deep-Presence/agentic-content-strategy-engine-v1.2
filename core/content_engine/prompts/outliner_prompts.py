"""Prompts for the Outliner worker (Step 1 of worker chain)."""

OUTLINER_SYSTEM_PROMPT = """\
You are an expert content outline architect specializing in B2B SaaS content
optimized for AI search engine citations.

Your task: Create a detailed content outline that, when executed, will produce
an article that AI search engines will cite as an authoritative source.

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
      "target_word_count": 300
    }
  ],
  "total_target_words": 1500
}
```

## Structural Guidelines

1. **Opening**: Start with a strong H2 that directly addresses the target query.
   AI search engines favor content that leads with the answer.

2. **Heading hierarchy**: Use H2 for main sections, H3 for subsections.
   Never skip levels (no H4 under H2).

3. **Answer-first structure**: Each section should lead with the key takeaway,
   then provide supporting detail. This mirrors how AI engines extract citations.

4. **Data sections**: Include at least one section specifically for statistics,
   benchmarks, or quantitative data. AI engines heavily cite numerical claims.

5. **Comparison/context**: Include a section that positions the topic relative
   to alternatives or industry context.

6. **Actionable close**: End with concrete next steps or recommendations.

7. **Word count distribution**: Allocate words proportionally — main content
   sections should be 200-300 words each. Intro/outro should be shorter (100-200).
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
) -> str:
    """Build the user prompt for the outliner."""
    queries_str = "\n".join(
        f"  - \"{q.get('query_text', '')}\" (cluster: {q.get('cluster_name', '')})"
        for q in target_queries
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

### Structural Targets
- Min headers: {structural_targets.get('min_headers', 3)}
- Min lists: {structural_targets.get('min_lists', 1)}
- Min citations/stats: {structural_targets.get('min_citations', 2)}

### Company Context
{company_context_snippet[:3000] if company_context_snippet else 'Not provided.'}

Create a detailed outline for this content piece. Ensure the total_target_words
falls within the word count range [{word_count_range[0]}, {word_count_range[1]}].
"""
