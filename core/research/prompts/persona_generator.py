"""Persona Profile Generator agent prompt (Agent 2).

Takes an approved persona brief + company context and produces a comprehensive,
evidence-backed persona profile via Perplexity sonar-deep-research.
"""
from __future__ import annotations

from typing import Optional

from core.models.audience_persona import AudiencePersonaInput, PersonaBrief

PERSONA_GENERATOR_SYSTEM_PROMPT = """\
You are a **Customer Research Strategist**. Generate **detailed audience personas** based on the persona-brief and business context provided. 
Each persona must follow the exact structure and bullet counts below. 
Specificity is critical — use vivid, concrete details, not vague generalities.

---

## Output Format (per persona)

### 1. Persona Title & Snapshot
* **Persona Title:** Clear archetype name (e.g., "The Scaling SaaS Founder").
* **Name & Snapshot (3–4 sentences):**
  * Fictional first name
  * Role / business type
  * Revenue / team size / years of experience (ranges are fine)
  * Short backstory that frames why they care about this problem

---

### 2. Daily Reality *(5–7 bullets)*
* Write in **day-in-the-life detail**
* Cover tools/software used, responsibilities, and where friction shows up
* Each bullet 1 sentence, max 20 words

---

### 3. Core Fears *(4–5 bullets)*
* List specific risks or "worst-case scenarios" this persona obsesses over
* Bullets should be short and sharp (≤15 words)

---

### 4. Deep Motivations *(3–4 bullets)*
* Capture **ultimate outcomes** they want (financial, emotional, professional)
* Blend practical (cash flow, efficiency) with aspirational (freedom, reputation, legacy)

---

### 5. Trust Builders *(3–5 bullets)*
* Signals that earn their confidence (e.g., proof types, integrations, expertise, validation)
* Write in customer-first framing ("Show me…", "Prove you…")

---

### 6. Trust Killers *(3–5 bullets)*
* Behaviors, gaps, or red flags that instantly destroy confidence
* Use blunt phrasing ("Generic advice", "Making me explain basics")

---

### 7. Critical Pain Points *(5–7 bullets)*
* Tactical, recurring problems they encounter that product/service should solve
* Each bullet should be industry-specific and phrased as a pain

---

## Company Fit Section

At the end of the personas, add:

**How We Serve Them** *(1–2 short paragraphs)*
* Explain how the company/product/service directly solves these personas' pains.
* Use their **own fears/motivations** as proof points.
* Show differentiation (why this solution vs. generic alternatives).

---

## General Rules
* **Length per persona:** 300–400 words.
* **Consistency:** Each section must have the prescribed bullet counts (don't skip).
* **Tone:** Professional but empathetic, as if presenting to marketing/sales team.
* **Specificity:** Replace generic phrasing with concrete realities (e.g., dollar amounts, tool names, percentages).
* Trust Killers are mandatory.


"""

_HUB_NAME = "research-persona-generator-system"


def get_persona_generator_system_prompt() -> str:
    """Get persona generator system prompt (Hub with local fallback)."""
    from core.content_engine.prompt_registry import get_prompt

    return get_prompt(_HUB_NAME, PERSONA_GENERATOR_SYSTEM_PROMPT)


def build_persona_generator_user_prompt(
    brief: PersonaBrief,
    input_data: AudiencePersonaInput,
    company_context_md: str,
    customer_reviews_md: str,
    knowledge_docs_text: str = "",
    revision_note: Optional[str] = None,
) -> str:
    """Build user prompt for persona profile generator agent."""
    parts: list[str] = []

    parts.append("## Persona Brief")
    parts.append(f"- Name: {brief.persona_name}")
    parts.append(f"- Tagline: {brief.tagline}")
    parts.append(f"- Description: {brief.description}")
    parts.append("- Why this persona fits:")
    for r in brief.rationale:
        parts.append(f"  - {r}")
    parts.append("")

    parts.append("## Company Context")
    parts.append(company_context_md[:15_000] if company_context_md else "No company context available.")
    parts.append("")

    parts.append("## Customer Reviews & Feedback")
    parts.append(customer_reviews_md[:10_000] if customer_reviews_md else "No customer reviews available.")
    parts.append("")

    parts.append("## Internal Documents")
    parts.append(knowledge_docs_text[:50_000] if knowledge_docs_text else "No internal documents provided.")
    parts.append("")

    parts.append("## Requirements")
    parts.append(f"- Company: {input_data.company_name}")
    if input_data.domain:
        parts.append(f"- Domain: {input_data.domain}")
    parts.append(f"- Language: {input_data.language}")
    parts.append(f"- Region: {input_data.region or 'Global'}")
    if input_data.additional_constraints:
        parts.append(f"- Additional constraints: {input_data.additional_constraints}")
    parts.append("")

    parts.append(
        f"""Using the format above, generate a detailed audience persona for:
        {input_data.company_name} ({input_data.domain})
        Make the detailed persona on the basis of the persona-brief above. 
        The persona must strictly include: Snapshot (3–4 sentences), Daily Reality (5–7 bullets), Core Fears (4–5 bullets), Deep Motivations (3–4 bullets), Trust Builders (3–5 bullets), Trust Killers (3–5 bullets), Critical Pain Points (5–7 bullets). 
        End with a Company Fit section tying back to their pains. Stay specific and avoid generic platitudes.
        """
    )

    if revision_note:
        parts.append("")
        parts.append("## Reviewer Feedback")
        parts.append("")
        parts.append(
            "A previous version was reviewed and revisions were requested. "
            "Address the following feedback:"
        )
        parts.append("")
        parts.append(revision_note)

    return "\n".join(parts)
