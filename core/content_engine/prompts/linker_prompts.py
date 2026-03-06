"""Prompts for the Linker worker (Step 3 of the v1.3 worker chain).

The Linker resolves link placeholders inserted by the drafter:
  - [INTERNAL-LINK: anchor text] → real URLs from the company's site pages
  - [EXTERNAL-LINK: anchor text] → authoritative external URLs via web search
  - [STAT: description] → sourced statistics (secondary pass)

Uses Perplexity sonar-pro for web-grounded link resolution.
"""


LINKER_SYSTEM_PROMPT = """\
You are a link resolution and citation specialist. Your task is to resolve \
link placeholders in a draft article with real, working URLs.

## Your Responsibilities

1. **Internal links** — Replace [INTERNAL-LINK: anchor text] placeholders with real \
URLs from the provided site page list. Match the anchor text description to the most \
relevant page. Format as [anchor text](url).

2. **External links** — Replace [EXTERNAL-LINK: anchor text] placeholders with \
authoritative, high-quality external URLs. Prefer .gov, .edu, established industry \
publications, and peer-reviewed sources. Format as [anchor text](url).

3. **Remaining stat placeholders** — If any [STAT: description] placeholders remain \
from the drafter, replace them with real, sourced statistics and add [Source, Year] \
citations inline.

4. **Link balance** — Aim for 3-5 internal links and 5-8 external links per 2000 words. \
Adjust proportionally for shorter or longer articles.

## What You Must NOT Do
- Do NOT change the article's structure, arguments, or key points
- Do NOT add new paragraphs or sections
- Do NOT rephrase or rewrite content beyond the immediate placeholder context
- Do NOT use broken, paywalled, or low-authority links
- Do NOT link to competitor company pages for internal links
- Do NOT remove existing links that are already resolved

## Internal Link Matching Rules
- Only use URLs from the provided site page list
- If no site page matches the anchor text, remove the placeholder brackets and leave \
the anchor text as plain text (do NOT invent URLs)
- Prefer exact topic matches over partial keyword overlap

## Output Format
Return the complete article with all placeholders resolved. \
Output raw Markdown only. Do NOT wrap in code fences.
"""


def build_linker_user_prompt(
    *,
    draft_markdown: str,
    title: str,
    key_topics: list[str],
    company_name: str,
    domain: str,
    site_pages: list[str] | None = None,
) -> str:
    """Build the user prompt for the linker worker.

    Args:
        draft_markdown: Draft article with link placeholders.
        title: Article title.
        key_topics: Key topics for search context.
        company_name: Company name.
        domain: Company domain.
        site_pages: List of known site page URLs for internal linking.
    """
    topics_str = ", ".join(key_topics) if key_topics else "the article's topics"

    # Site pages section
    site_pages_section = ""
    if site_pages:
        pages_list = "\n".join(f"- {url}" for url in site_pages[:100])
        site_pages_section = f"""\
## Site Pages (for internal links — ONLY use these URLs)

{pages_list}
"""
    else:
        site_pages_section = """\
## Site Pages

No site pages provided. Convert any [INTERNAL-LINK: ...] placeholders to plain \
anchor text (remove the brackets, keep the text).
"""

    return f"""\
## Article to Link

Title: {title}
Company: {company_name} ({domain})
Key Topics: {topics_str}

{site_pages_section}

## Draft Content

{draft_markdown}

## Instructions

1. Replace ALL [INTERNAL-LINK: ...] placeholders with real URLs from the site pages \
list above. If no matching page exists, convert to plain text.
2. Replace ALL [EXTERNAL-LINK: ...] placeholders with authoritative external URLs. \
Use web search to find the best matching resource.
3. Replace any remaining [STAT: ...] placeholders with sourced statistics.
4. Add [Source, Year] citations for all new statistics.
5. Return the complete article with all placeholders resolved.
"""


# ---------------------------------------------------------------------------
# Hub getter (opt-in via settings.langsmith_use_hub)
# ---------------------------------------------------------------------------

_HUB_NAME = "linker-system"


def get_linker_system_prompt() -> str:
    """Get linker system prompt from Hub or local fallback."""
    from core.content_engine.prompt_registry import get_prompt

    return get_prompt(_HUB_NAME, LINKER_SYSTEM_PROMPT)
