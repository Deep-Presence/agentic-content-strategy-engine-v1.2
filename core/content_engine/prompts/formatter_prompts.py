"""Prompts for the Formatter worker (Step 4 of worker chain).

Uses Haiku 4.5 for fast, lightweight style formatting.

v2.0: Structural targets awareness, full style guide (no truncation),
FAQ/table/takeaway formatting instructions.
"""

FORMATTER_SYSTEM_PROMPT = """\
You are a content formatting specialist. Your task is to polish an article's \
formatting for maximum readability and AI citation potential WITHOUT changing \
the substance or meaning.

## Formatting Rules

1. **Headers**: Ensure consistent heading hierarchy (H2 → H3 → H4, no skips)
2. **Lists**: Convert run-on enumerations into bullet or numbered lists. \
Ensure each list has at least 3 items where possible.
3. **Bold**: Bold key terms, product names, and critical metrics on first mention
4. **Statistics**: Ensure stats are prominently displayed (not buried in paragraphs). \
Format large numbers with commas, percentages with the % symbol.
5. **Whitespace**: Add line breaks between sections for readability
6. **Citation format**: Standardize inline citations to [Source, Year] format
7. **Remove artifacts**: Clean up any remaining [STAT: ...] placeholders or \
editorial notes
8. **FAQ formatting**: If the article has a FAQ section, format as proper Q&A \
with bold questions and paragraph answers
9. **Table formatting**: If the article has tables, ensure proper Markdown table \
syntax with aligned columns and header row
10. **Key takeaways**: If present, format as a highlighted summary section

## Output Format

Return the complete formatted article in Markdown. Do NOT wrap in code fences. \
Do NOT change the content substance — only format and polish.
"""


def build_formatter_user_prompt(
    *,
    enriched_markdown: str,
    style_guide_md: str,
    structural_targets: dict | None = None,
) -> str:
    """Build the user prompt for the formatter.

    Args:
        enriched_markdown: The enriched markdown to format.
        style_guide_md: Company writing style guide (full, not truncated).
        structural_targets: Structural targets dict for compliance checking.
    """
    style_section = ""
    if style_guide_md:
        style_section = f"""\
## Style Guide (follow these conventions)
{style_guide_md}
"""

    structural_section = ""
    if structural_targets:
        st = structural_targets
        structural_section = f"""\
## Structural Targets (last compliance pass — ensure formatting meets these)
- Min headers: {st.get('min_headers', 3)}
- Min lists: {st.get('min_lists', 1)}
- Min citations: {st.get('min_citations', 2)}
- Min bullets per list: {st.get('min_bullets_per_list', 3)}"""

        if st.get('faq_rate', 0) > 0.3:
            structural_section += (
                "\n- **FAQ section expected**: Format Q&A pairs with bold questions"
            )
        if st.get('table_rate', 0) > 0.3:
            structural_section += (
                "\n- **Table expected**: Ensure proper Markdown table syntax"
            )

    return f"""\
## Article to Format

{enriched_markdown}

{style_section}

{structural_section}

Polish the formatting of this article. Ensure:
- Clean heading hierarchy
- Consistent list formatting (min 3 items per list)
- Bold key terms on first mention
- Statistics are prominent and properly formatted
- Standard citation format [Source, Year]
- No leftover editorial markers or [STAT: ...] placeholders
- FAQ sections formatted as Q&A if present
- Tables use proper Markdown syntax if present

Return the complete formatted article.
"""
