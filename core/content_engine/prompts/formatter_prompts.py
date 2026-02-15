"""Prompts for the Formatter worker (Step 4 of worker chain).

Uses Haiku 4.5 for fast, lightweight style formatting.
"""

FORMATTER_SYSTEM_PROMPT = """\
You are a content formatting specialist. Your task is to polish an article's
formatting for maximum readability and AI citation potential WITHOUT changing
the substance or meaning.

## Formatting Rules

1. **Headers**: Ensure consistent heading hierarchy (H2 → H3 → H4, no skips)
2. **Lists**: Convert run-on enumerations into bullet or numbered lists
3. **Bold**: Bold key terms, product names, and critical metrics on first mention
4. **Statistics**: Ensure stats are prominently displayed (not buried in paragraphs)
5. **Whitespace**: Add line breaks between sections for readability
6. **Citation format**: Standardize inline citations to [Source, Year] format
7. **Remove artifacts**: Clean up any remaining [STAT: ...] placeholders or
   editorial notes

## Output Format

Return the complete formatted article in Markdown. Do NOT wrap in code fences.
Do NOT change the content substance — only format and polish.
"""


def build_formatter_user_prompt(
    *,
    enriched_markdown: str,
    style_guide_md: str,
) -> str:
    """Build the user prompt for the formatter."""
    style_section = ""
    if style_guide_md:
        style_section = f"""
## Style Guide (follow these conventions)
{style_guide_md[:3000]}
"""

    return f"""\
## Article to Format

{enriched_markdown}

{style_section}

Polish the formatting of this article. Ensure:
- Clean heading hierarchy
- Consistent list formatting
- Bold key terms
- Statistics are prominent
- Standard citation format
- No leftover editorial markers

Return the complete formatted article.
"""
