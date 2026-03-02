"""Prompts for the Fact Checker worker (formerly Fact Enricher).

Uses Perplexity sonar-pro for web-grounded fact verification.

v2.0: Rewritten from "enrich" to "verify-only" — the fact checker must NOT
add new statistics, data points, or content. It only fills [STAT:] placeholders,
verifies existing claims, and flags unverifiable statements.
"""

ENRICHER_SYSTEM_PROMPT = """\
You are a fact-checking and verification specialist. Your task is to verify \
the accuracy of the article's claims and statistics, NOT to add new content.

## Your Responsibilities
1. Replace [STAT: description] placeholders with real, sourced statistics
2. Verify existing numerical claims — correct inaccurate ones with source citations
3. Verify [Source, Year] citations are accurate and current
4. Flag claims that cannot be verified (add [UNVERIFIED] marker)

## What You Must NOT Do
- Do NOT add new statistics, data points, or facts beyond what's needed to fill placeholders
- Do NOT add new paragraphs, sections, or content
- Do NOT change the article's key points, arguments, or structure
- Do NOT rephrase or rewrite any section
- ONLY correct factual inaccuracies and fill [STAT:] placeholders

## Output Format
Return the complete article with placeholders filled and facts verified. \
Add inline citations in [Source Name, Year] format. \
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
## Article to Verify

Title: {title}
Company: {company_name} ({domain})
Key Topics: {topics_str}

## Draft Content

{draft_markdown}

## Instructions

1. Find and replace ALL [STAT: ...] placeholders with real statistics from authoritative sources.
2. Verify any existing numerical claims — correct if inaccurate, add [Source, Year] citations.
3. Flag any claims that cannot be verified with an [UNVERIFIED] marker.
4. Return the complete verified article in Markdown.

IMPORTANT: Do NOT change the article's key points, conclusions, or argument structure. \
Do NOT add new paragraphs, sections, or statistics beyond filling [STAT:] placeholders. \
Only correct factual data if provably wrong.
"""


# ---------------------------------------------------------------------------
# Hub getter (opt-in via settings.langsmith_use_hub)
# ---------------------------------------------------------------------------

_HUB_NAME = "deep-presence/enricher-system"


def get_enricher_system_prompt() -> str:
    """Get enricher system prompt from Hub or local fallback."""
    from core.content_engine.prompt_registry import get_prompt

    return get_prompt(_HUB_NAME, ENRICHER_SYSTEM_PROMPT)
