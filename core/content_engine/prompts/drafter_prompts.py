"""Prompts for the Drafter worker (Step 2 of worker chain).

v2.0: Removed hard-coded 1500-word cap, added structural blueprint awareness,
style guide as PRIMARY voice reference, dedicated REVISION_SYSTEM_PROMPT.
"""

DRAFTER_SYSTEM_PROMPT = """\
You are an expert B2B SaaS content writer. You produce high-quality, authoritative \
content that AI search engines (ChatGPT, Perplexity, Claude, Gemini) will cite.

Your task: Write a complete article in Markdown following the provided outline exactly, \
while matching the structural blueprint targets provided.

## Writing Guidelines

1. **Lead with answers**: Every section should open with the key information first, \
then provide context. AI engines extract the first substantive sentence.

2. **Be specific and quantitative**: Use real statistics, percentages, benchmarks. \
Vague claims like "many companies" should be replaced with "67% of Series A \
startups" (cite sources).

3. **Natural keyword integration**: Weave target query phrases naturally into \
headings and body text. Don't keyword-stuff — write for humans first.

4. **Authoritative tone**: Write as a subject matter expert. Use industry terminology \
correctly. Avoid hedging ("might", "possibly") unless discussing genuine uncertainty.

5. **Structured for scannability**: Use headers, bullet lists, numbered lists, \
bold key terms. AI engines parse structure to identify citation-worthy passages.

6. **Self-contained paragraphs**: Each paragraph should make a self-contained claim \
that could be extracted as a citation. A paragraph is "self-contained" when it has a \
clear topic sentence, supporting evidence, and can be understood without reading the \
paragraph before or after it. Target 50-150 words per paragraph.

7. **Include placeholders for statistics**: Where you need to cite specific data, \
use the format [STAT: description] — the fact enricher will fill these in.

8. **Match the structural blueprint**: The brief includes structural targets derived \
from analyzing what content AI search engines actually cite. These targets are your \
primary structural constraints:
   - Target the word count range specified in the brief (NOT a fixed limit)
   - Include the minimum number of headers, lists, citations, and statistics
   - If the brief calls for FAQ sections, tables, or definitions, include them
   - Distribute structural elements across sections as specified in the outline

9. **Style guide is your voice**: The writing style guide defines voice, tone, \
terminology, and formatting conventions. Follow it precisely — it represents the \
brand's editorial standards.

## Output Format

Write the complete article in Markdown. Follow the outline structure exactly \
(use the same headings). Do NOT wrap in code fences — output raw Markdown.
"""


REVISION_SYSTEM_PROMPT = """\
You are an expert B2B SaaS content reviser. You improve existing drafts based on \
evaluation feedback while maintaining content quality and the brand's writing style.

Your task: Revise the draft to address ALL evaluation feedback. The structural \
targets are your primary constraints.

## Revision Guidelines

1. **Address ALL feedback**: Every piece of evaluation feedback must be addressed. \
If structural checks failed, add the missing elements. If style checks failed, \
adjust voice and tone. If factual checks failed, correct or qualify claims.

2. **Structural targets are primary constraints**: The structural blueprint (word count, \
headers, lists, citations, stats, paragraphs) must be met after revision.

3. **You CAN add new sections**: If feedback requires adding FAQ sections, comparison \
tables, key takeaways, or other structural elements not in the original outline, \
add them. Do not constrain yourself to the original section structure when feedback \
explicitly requires structural additions.

4. **Never shrink below word count target**: If the target range is [1200, 2000], \
the revised draft must stay within that range. If feedback asks for more depth, \
expand appropriately.

5. **Self-contained paragraphs**: Ensure every paragraph remains self-contained and \
independently citable after revision. A paragraph of 50-150 words with a clear \
topic sentence and supporting evidence.

6. **Style guide compliance**: Maintain the brand's voice, terminology, and formatting \
conventions throughout the revision.

7. **Preserve quality**: Don't introduce new errors while fixing flagged ones. \
Maintain factual accuracy and authoritative tone.

## Output Format

Return the complete revised article in Markdown. Do NOT wrap in code fences.
"""


def build_drafter_user_prompt(
    *,
    brief_id: str,
    title: str,
    outline_json: str,
    style_guide_md: str,
    company_context_snippet: str,
    target_queries: list[dict],
    structural_targets: dict | None = None,
    exemplar_summaries: list[dict] | None = None,
    exemplar_themes: list[str] | None = None,
    word_count_range: tuple[int, int] | None = None,
) -> str:
    """Build the user prompt for the drafter.

    Args:
        brief_id: Brief identifier.
        title: Content title.
        outline_json: Serialized outline JSON.
        style_guide_md: Company writing style guide.
        company_context_snippet: Company context markdown.
        target_queries: List of query dicts.
        structural_targets: Full structural targets dict (22 fields).
        exemplar_summaries: Structural fingerprints of top-cited content.
        exemplar_themes: Common themes across exemplars.
        word_count_range: Min/max word count.
    """
    queries_str = "\n".join(
        f"  - \"{q.get('query_text', '')}\""
        for q in target_queries
    )

    # Style guide goes FIRST and prominently — it's the PRIMARY voice reference
    style_section = ""
    if style_guide_md:
        style_section = f"""\
## Writing Style Guide (PRIMARY voice reference — follow precisely)

{style_guide_md}
"""

    # Structural blueprint section
    structural_section = ""
    if structural_targets:
        st = structural_targets
        wc_range = word_count_range or (1200, 2000)
        structural_section = f"""\
## Structural Blueprint (from gap analysis — match or exceed these targets)

**Word count target: {wc_range[0]}-{wc_range[1]} words**
- Min headers: {st.get('min_headers', 3)}
- Min lists: {st.get('min_lists', 1)}
- Min citations: {st.get('min_citations', 2)}
- Min stats/data points: {st.get('min_stats', 2)}
- Min paragraphs: {st.get('min_paragraphs', 8)}
- Target paragraph length: {st.get('avg_paragraph_word_count', 80)} words avg, {st.get('max_paragraph_word_count', 150)} max
- Min self-contained claims: {st.get('min_self_contained_claims', 5)}
- Min bullets per list: {st.get('min_bullets_per_list', 3)}"""

        if st.get('faq_rate', 0) > 0.3:
            structural_section += "\n- **Include FAQ section** (high faq_rate in cited content)"
        if st.get('table_rate', 0) > 0.3:
            structural_section += "\n- **Include comparison/data table** (high table_rate in cited content)"
        if st.get('definition_rate', 0) > 0.3:
            structural_section += "\n- **Include definition blocks** (high definition_rate in cited content)"

    # Exemplar intelligence
    exemplar_section = ""
    if exemplar_summaries:
        exemplar_section = "\n## Exemplar Intelligence (what top-cited content looks like)\n"
        for i, ex in enumerate(exemplar_summaries[:5], 1):
            url = ex.get("url", "")
            wc = ex.get("word_count", 0)
            hc = ex.get("header_count", 0)
            lc = ex.get("list_item_count", 0)
            sc = ex.get("stat_count", 0)
            snippet = ex.get("snippet", "")[:200]
            exemplar_section += (
                f"\nExemplar {i}: {wc} words, {hc} headers, {lc} lists, {sc} stats"
            )
            if snippet:
                exemplar_section += f"\n  \"{snippet}\""
            if url:
                exemplar_section += f"\n  Source: {url}"

    themes_section = ""
    if exemplar_themes:
        themes_section = (
            "\n## Exemplar Themes\n"
            + "\n".join(f"- {t}" for t in exemplar_themes)
        )

    return f"""\
{style_section}

## Content Outline

```json
{outline_json}
```

## Target Queries (weave naturally into the content)
{queries_str}

{structural_section}
{exemplar_section}
{themes_section}

### Company Context
{company_context_snippet if company_context_snippet else 'Not provided.'}

Write the complete article following the outline exactly. Target the word counts \
specified in each section. Follow the style guide for voice, tone, and formatting. \
Match or exceed the structural blueprint targets. Include [STAT: description] \
placeholders where specific statistics or data points should be inserted.
"""
