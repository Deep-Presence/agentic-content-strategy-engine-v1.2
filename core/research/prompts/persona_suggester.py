"""Persona Suggester agent prompt (Agent 1).

Analyzes company context, customer reviews, and knowledge docs to suggest
3-5 distinct buyer persona briefs as structured JSON.
"""
from __future__ import annotations

from typing import Optional

from core.models.audience_persona import AudiencePersonaInput

PERSONA_SUGGESTER_SYSTEM_PROMPT = """\
You are a Strategic Audience Analyst specializing in B2B and B2C customer segmentation. Your job is to analyze raw business context — company overviews, customer reviews, support tickets, sales call transcripts, and any other available signals — and identify the 3–5 most strategically valuable audience personas for the given company.

You are NOT generating full persona profiles. You are making a strategic recommendation on WHICH personas the company should invest in understanding deeply. Think of yourself as the analyst who presents to the strategy team before the research phase begins.

---

## How You Think About Persona Selection

Work through these lenses in order. You don't need to show this reasoning explicitly, but it must inform every recommendation you make:

### 1. Signal Extraction (What the data tells you)
Before proposing any persona, mine the provided business context for:
- **Recurring pain language**: What frustrations, complaints, or desires appear repeatedly across reviews, tickets, and transcripts? Cluster them.
- **Job titles and roles**: Who is actually showing up in the data — buying, complaining, requesting features, churning?
- **Purchase triggers**: What events or situations pushed people toward this product/service?
- **Objection patterns**: What hesitations or deal-breakers surface in sales calls?
- **Underserved segments**: Are there recurring requests or frustrations that suggest a persona the company may be overlooking?

### 2. Strategic Filtering (Which personas actually matter)
Not every person who interacts with the company deserves a persona. Filter using:
- **Budget + Authority**: Can this person actually make or influence the purchase decision? If not, they may be an influencer persona (flag this explicitly).
- **Problem severity**: Is the problem urgent enough to drive action, or is it a "nice to have"? Prioritize personas where inaction has real consequences.
- **Workflow fit**: Does the company's product/service fit naturally into this persona's existing workflow, or does it require significant behavior change?
- **Revenue potential**: Consider deal size, retention likelihood, and expansion potential. Prioritize personas that represent sustainable revenue.
- **Addressable volume**: Is this persona a one-off or does it represent a meaningful segment of the market?

### 3. Portfolio Balance (The set matters, not just individuals)
The final set of 3–5 personas should:
- Cover different stages of the buying journey or awareness spectrum (some may know they have the problem, others may not yet).
- Represent distinct decision-making roles where relevant (e.g., end-user vs. budget-holder vs. technical evaluator).
- Avoid overlap — if two personas share >70% of the same pains and motivations, merge them or pick the higher-value one.
- Include at least one "growth persona" — a segment the company isn't fully serving yet but has clear potential to.

---

## Output Format

Return ONLY a valid JSON array. Each element must have:
- "persona_name": A realistic first name (e.g., "Sarah", "Marcus")
- "tagline": Role + context in <12 words (e.g., "VP of Finance at mid-market SaaS companies")
- "description": One sentence describing who this person is and what they care about
- "rationale": Array of 2-3 bullet points explaining why this persona is a good fit \
   for the company's product. What specific problem this persona faces that the company is positioned to solve. \
   Why this persona is strategically valuable (revenue, retention, market expansion, etc.).
   Reference specific evidence from the context.
---

## Rules

- Generate exactly 3–{max_personas} personas. Default to 3 unless the data clearly supports more distinct segments.
- Every recommendation must be grounded in the provided business context. Do NOT invent personas based on generic industry assumptions. If the data is thin for a particular segment, say so explicitly.
- The "Why This Persona" section is the most important part. It must convince a product or marketing lead that this persona is worth investing research time into. Vague reasoning like "they could benefit from the product" is unacceptable.
- Taglines should be specific enough that someone unfamiliar with the company could immediately picture this person. Avoid generic labels like "The Busy Professional."
- If the data suggests an important persona that doesn't neatly fit the company's current positioning, include it anyway and flag it as a potential expansion opportunity.
- If critical context is missing (e.g., no sales transcripts, no pricing info), note what additional data would strengthen your recommendations.
- Rank personas by strategic priority. Persona 1 = highest value.
- Do NOT include any text outside the JSON array
"""

_HUB_NAME = "research-persona-suggester-system"


def get_persona_suggester_system_prompt() -> str:
    """Get persona suggester system prompt (Hub with local fallback)."""
    from core.content_engine.prompt_registry import get_prompt

    return get_prompt(_HUB_NAME, PERSONA_SUGGESTER_SYSTEM_PROMPT)


def build_persona_suggester_user_prompt(
    input_data: AudiencePersonaInput,
    company_context_md: str,
    customer_reviews_md: str,
    knowledge_docs_text: str = "",
    support_tickets_md: str = "",
    sales_transcripts_md: str = "",
) -> str:
    """Build user prompt for persona suggester agent.

    Constructs a structured prompt that guides the LLM to analyze
    business context signals and recommend strategically valuable personas.
    """
    parts: list[str] = []

    # --- Header instruction ---
    parts.append(
        f"Analyze the following business context and recommend {input_data.max_personas} "
        f"audience personas that are most strategically valuable for **{input_data.company_name}**. "
        f"Rank them by priority."
    )
    parts.append("")
    parts.append("---")
    parts.append("")

    # --- Company Overview ---
    parts.append("### Company Overview")
    if company_context_md:
        parts.append(company_context_md[:80_000])  # ~15k tokens
        print(company_context_md[:80_000])
    else:
        parts.append("No company context available. Rely on other signals below.")
    parts.append("")
    parts.append("---")
    parts.append("")

    # --- Customer Reviews ---
    parts.append("### Customer Reviews")
    if customer_reviews_md:
        parts.append(customer_reviews_md[:40_000])  # ~10k tokens
    else:
        parts.append("No customer reviews available.")
    parts.append("")
    parts.append("---")
    parts.append("")

    # --- Support / Issue Tickets ---
    parts.append("### Support / Issue Tickets")
    if support_tickets_md:
        parts.append(support_tickets_md[:40_000])  # ~10k tokens
    else:
        parts.append("No support tickets available.")
    parts.append("")
    parts.append("---")
    parts.append("")

    # --- Sales Call Transcripts / Notes ---
    parts.append("### Sales Call Transcripts / Notes")
    if sales_transcripts_md:
        parts.append(sales_transcripts_md[:60_000])  # ~15k tokens
    else:
        parts.append("No sales call transcripts available.")
    parts.append("")
    parts.append("---")
    parts.append("")

    # --- Additional Context (knowledge docs + user constraints) ---
    parts.append("### Additional Context")
    additional_parts: list[str] = []

    if knowledge_docs_text:
        additional_parts.append("**Internal Documents (uploaded by company):**")
        additional_parts.append(knowledge_docs_text[:200_000])  # ~50k tokens
        additional_parts.append("")

    if input_data.domain:
        additional_parts.append(f"**Domain/Industry:** {input_data.domain}")
    if input_data.region:
        additional_parts.append(f"**Target Region:** {input_data.region}")
    else:
        additional_parts.append("**Target Region:** Global")
    if input_data.language:
        additional_parts.append(f"**Language:** {input_data.language}")
    if input_data.additional_constraints:
        additional_parts.append(f"**Additional Constraints:** {input_data.additional_constraints}")

    if input_data.seed_personas:
        additional_parts.append("")
        additional_parts.append("### User-Provided Persona Seeds")
        additional_parts.append(
            "The user has indicated these audience personas are important. "
            "You MUST include these in your recommendations (use them as the "
            "persona_name values), but validate against the business context. "
            "If a seed doesn't fit the data, flag it but still include it."
        )
        for i, name in enumerate(input_data.seed_personas, 1):
            additional_parts.append(f"{i}. {name}")

    if additional_parts:
        parts.extend(additional_parts)
    else:
        parts.append("No additional context provided.")

    parts.append("")
    parts.append("---")
    parts.append("")

    # --- Closing instruction ---
    parts.append(
        "Based on the signals in this data, identify the persona profiles this company "
        "should prioritize. For each, provide the role title, a tagline, and a clear "
        "justification grounded in the evidence above."
    )
    parts.append("")
    parts.append(
        f"Return your response as a JSON array of exactly {input_data.max_personas} objects. "
        "Each object must have this structure:"
    )
    parts.append("")
    parts.append("```json")
    parts.append('[')
    parts.append('  {')
    parts.append('    "rank": 1,')
    parts.append('    "role_title": "The [Specific Role/Archetype]",')
    parts.append('    "tagline": "A single sentence (max 15 words) capturing who they are and their core tension.",')
    parts.append('    "why_this_persona": "3-5 sentences explaining: (1) what evidence in the data points to this persona, (2) what specific problem they face that the company solves, (3) why they are strategically valuable.",')
    parts.append('    "confidence": "high | medium | low"')
    parts.append('  }')
    parts.append(']')
    parts.append("```")
    parts.append("")
    parts.append(
        "Set `confidence` to 'high' if multiple data sources support this persona, "
        "'medium' if supported by 1-2 signals, and 'low' if inferred from limited context. "
        "If critical data sources were missing, note what additional data would strengthen "
        "your recommendations in the `why_this_persona` field."
    )

    return "\n".join(parts)
