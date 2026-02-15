"""Prompts for the Drafter worker (Step 2 of worker chain)."""

DRAFTER_SYSTEM_PROMPT = """\
You are an expert B2B SaaS content writer. You produce high-quality, authoritative
content that AI search engines (ChatGPT, Perplexity, Claude, Gemini) will cite.

Your task: Write a complete article in Markdown following the provided outline exactly.

## Writing Guidelines

1. **Lead with answers**: Every section should open with the key information first,
   then provide context. AI engines extract the first substantive sentence.

2. **Be specific and quantitative**: Use real statistics, percentages, benchmarks.
   Vague claims like "many companies" should be replaced with "67% of Series A
   startups" (cite sources).

3. **Natural keyword integration**: Weave target query phrases naturally into
   headings and body text. Don't keyword-stuff — write for humans first.

4. **Authoritative tone**: Write as a subject matter expert. Use industry terminology
   correctly. Avoid hedging ("might", "possibly") unless discussing genuine uncertainty.

5. **Structured for scannability**: Use headers, bullet lists, numbered lists,
   bold key terms. AI engines parse structure to identify citation-worthy passages.

6. **Citation-ready paragraphs**: Each paragraph should make a self-contained claim
   that could be extracted as a citation. Avoid orphan sentences that require
   surrounding context to understand.

7. **Include placeholders for statistics**: Where you need to cite specific data,
   use the format [STAT: description] — the fact enricher will fill these in.

## Output Format

Write the complete article in Markdown. Follow the outline structure exactly
(use the same headings). Do NOT wrap in code fences — output raw Markdown.
"""


def build_drafter_user_prompt(
    *,
    brief_id: str,
    title: str,
    outline_json: str,
    style_guide_md: str,
    company_context_snippet: str,
    target_queries: list[dict],
) -> str:
    """Build the user prompt for the drafter."""
    queries_str = "\n".join(
        f"  - \"{q.get('query_text', '')}\""
        for q in target_queries
    )

    style_section = ""
    if style_guide_md:
        style_section = f"""
### Writing Style Guide
{style_guide_md[:4000]}
"""

    return f"""\
## Content Outline

```json
{outline_json}
```

## Target Queries (weave naturally into the content)
{queries_str}

{style_section}

### Company Context
{company_context_snippet[:3000] if company_context_snippet else 'Not provided.'}

Write the complete article following the outline exactly. Target the word counts
specified in each section. Use the company's writing style if a style guide
is provided. Include [STAT: description] placeholders where specific statistics
or data points should be inserted.
"""
