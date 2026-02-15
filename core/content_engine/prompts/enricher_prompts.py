"""Prompts for the Fact Enricher worker (Step 3 of worker chain).

Uses Perplexity sonar-pro for web-grounded fact verification and enrichment.
"""

ENRICHER_SYSTEM_PROMPT = """\
You are a fact-checking and data enrichment specialist. Your task is to
enhance a draft article by:

1. Replacing [STAT: description] placeholders with real, sourced statistics
2. Verifying factual claims and adding source citations
3. Adding relevant data points that strengthen the article's authority
4. Ensuring all numerical claims are accurate and current

## Output Format

Return the complete article with all placeholders filled and facts enriched.
Add inline citations in the format [Source Name, Year] or [Source URL].
Do NOT change the article structure — only enhance with facts and citations.

Output raw Markdown only. Do NOT wrap in code fences.
"""


def build_enricher_user_prompt(
    *,
    draft_markdown: str,
    title: str,
    key_topics: list[str],
    company_name: str,
    domain: str,
) -> str:
    """Build the prompt sent to Perplexity sonar-pro for fact enrichment."""
    topics_str = ", ".join(key_topics) if key_topics else "the article's topics"

    return f"""\
## Article to Enrich

Title: {title}
Company: {company_name} ({domain})
Key Topics: {topics_str}

## Draft Content

{draft_markdown}

## Instructions

1. Find and replace ALL [STAT: ...] placeholders with real statistics from authoritative sources.
2. Verify any existing numerical claims — correct if inaccurate.
3. Add 2-3 additional relevant statistics or data points where they strengthen the argument.
4. Add inline source citations in [Source Name, Year] format.
5. Return the complete enriched article in Markdown.
"""
