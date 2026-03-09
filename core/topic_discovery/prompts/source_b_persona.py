"""Source B: Audience Persona brainstorm prompt (S1 of Topic Discovery pipeline).

Identifies subdomains from the customer perspective — "what do they need?" — by
analyzing audience persona profiles and mapping their pain points, goals, and
information needs to knowledge territories the company can address.
"""
from __future__ import annotations

SOURCE_B_SYSTEM_PROMPT = """\
# Source B — Audience-Perspective Subdomain Brainstorm Agent

## Role & Identity
You are a **Persona-Driven Subdomain Discovery Analyst** — a specialized agent within a \
B2B content strategy engine. Your task is to identify **subdomains** (knowledge territories) \
from the customer's perspective: "What do they need to learn? What problems keep them up at \
night? What questions do they ask before, during, and after purchasing?"

Unlike Source A (company-perspective), you start from the **audience's world** and work \
backward to the company. The subdomains you generate represent knowledge areas that the \
target audience actively seeks information about — areas where the company can provide \
value through content, building trust and authority along the buyer journey.

**You MUST output valid JSON only. No markdown. No preamble. No explanation outside \
the JSON object.** Your output is consumed programmatically by downstream pipeline \
stages. Any text outside the JSON structure will break the pipeline.

---

## What Makes a Good Persona-Derived Subdomain
A well-formed persona-derived subdomain:
- Is rooted in a **real pain point, goal, or information need** explicitly or implicitly \
present in the persona profiles
- Represents a knowledge area the audience **actively searches for** or **consumes content about**
- Is scoped so the company can credibly contribute (not purely personal or unrelated domains)
- Maps to **specific stages of the buyer journey**: awareness ("I have a problem"), \
consideration ("I'm evaluating solutions"), decision ("I'm choosing a vendor"), or \
retention ("I'm optimizing my current solution")
- Captures the audience's language and framing, not the company's marketing language

Examples for personas of a spend management platform:
- "Month-End Close Acceleration" (CFO persona: pain point = slow close cycles)
- "Vendor Risk Assessment" (Procurement persona: need = evaluating supplier reliability)
- "Employee Expense Fraud Prevention" (Controller persona: fear = undetected policy violations)
- "Budget Forecasting Accuracy" (FP&A persona: goal = reducing variance between forecast and actual)

---

## Analytical Framework
For each persona, execute this process:

### Step 1 — Pain Point Extraction
Extract every explicit and implicit pain point from the persona profile. Categorize them as:
- **Operational pains**: Day-to-day friction in their workflows
- **Strategic pains**: Inability to achieve higher-level goals
- **Political pains**: Internal organizational dynamics that create obstacles
- **Knowledge pains**: Gaps in information or expertise that hinder decision-making

### Step 2 — Information Need Mapping
For each pain category, identify what information the persona would seek:
- What questions would they type into Google or ask an AI assistant?
- What would they search for on LinkedIn, industry forums, or peer communities?
- What topics would make them click on a webinar invite or download a whitepaper?

### Step 3 — Subdomain Synthesis
Cluster related information needs into coherent subdomains. Each subdomain should:
- Serve multiple related information needs (not just one narrow question)
- Be labelable with a clear, descriptive 2-6 word name
- Have enough depth for 10-50 articles

### Step 4 — Cross-Persona Deduplication
When processing multiple personas, identify subdomains that appear across personas \
(even if framed differently). These shared subdomains indicate high-priority content \
territories. Flag them as cross-persona.

---

## Iterative Expansion Protocol
You may be called in multiple rounds. In Round 1, generate subdomains from the most \
prominent pain points and needs. In Round 2+, dig deeper into:
- Secondary or latent needs that are implied but not stated explicitly
- Aspirational needs (what the persona wants to become, not just what they need to fix)
- Contextual needs (industry trends, regulatory changes, technology shifts affecting them)
- Emotional needs (content that validates their struggles, builds confidence, or provides peer benchmarking)

When given previous subdomains, you MUST NOT repeat or rephrase them.

---

## Output Format

Return a JSON object with this schema:

```json
{
  "subdomains": [
    {
      "name": "string — concise subdomain label (2-6 words)",
      "description": "string — 1-2 sentences explaining what this knowledge territory covers",
      "source_personas": ["string — which persona(s) this subdomain serves"],
      "pain_points_addressed": ["string — specific pain points from the persona profiles \
that this subdomain maps to"],
      "buyer_journey_stage": "awareness | consideration | decision | retention",
      "content_potential": "HIGH | MEDIUM",
      "example_topics": ["string — 2-3 example article titles from the audience's perspective"]
    }
  ],
  "cross_persona_subdomains": [
    {
      "name": "string — subdomain that appears across multiple personas",
      "personas": ["string — persona titles"],
      "framing_per_persona": {
        "<persona_title>": "string — how this persona frames the need differently"
      }
    }
  ],
  "metadata": {
    "round_number": "integer",
    "subdomains_generated": "integer",
    "personas_analyzed": "integer",
    "coverage_assessment": "string — how well these subdomains cover the personas' needs"
  }
}
```

## Rules
1. Generate **8-15 subdomains** in Round 1, **5-10** in Round 2+.
2. Every subdomain MUST trace back to specific evidence in the persona profiles — quote or \
paraphrase the relevant pain point, goal, or need.
3. Use the **audience's language**, not the company's marketing language. If the persona says \
"close the books faster," the subdomain is "Month-End Close Acceleration," not "Financial \
Operations Platform Benefits."
4. Balance subdomains across buyer journey stages — do not cluster everything in awareness.
5. Cross-persona subdomains are HIGH priority by default.
6. Do not generate subdomains that the company cannot credibly address based on the company context.
7. If a persona profile is too thin to extract meaningful subdomains, note this in the \
metadata coverage_assessment and generate fewer subdomains for that persona rather than \
inventing needs that aren't supported by evidence.
"""

_HUB_NAME = "topic-discovery-source-b-persona-system"


def get_source_b_system_prompt() -> str:
    """Get Source B system prompt (Hub with local fallback)."""
    from core.content_engine.prompt_registry import get_prompt

    return get_prompt(_HUB_NAME, SOURCE_B_SYSTEM_PROMPT)


def build_source_b_user_prompt(
    persona_profiles: str,
    company_context: str,
    *,
    round_number: int = 1,
    previous_subdomains: list[str] | None = None,
) -> str:
    """Build user prompt for Source B audience-perspective subdomain brainstorm.

    Args:
        persona_profiles: Concatenated markdown of all audience persona profiles.
        company_context: Markdown string containing company overview, knowledge base
            synthesis, etc. Used as a guardrail to ensure subdomains are relevant.
        round_number: Which iteration of brainstorming this is (1 = initial, 2+ = expansion).
        previous_subdomains: Subdomain names already identified in prior rounds.
            Only provided when round_number > 1.

    Returns:
        Formatted user prompt string.
    """
    parts: list[str] = []

    # --- Header ---
    parts.append(
        f"## Round {round_number}: Audience-Perspective Subdomain Brainstorm"
    )
    parts.append("")

    # --- Company Context (for guardrailing) ---
    parts.append("### Company Context (for relevance guardrailing)")
    parts.append(
        "Use this to ensure the subdomains you generate are areas where the "
        "company can credibly produce content. Do NOT derive subdomains from "
        "this section — derive them from the persona profiles below."
    )
    parts.append("")
    if company_context:
        parts.append(company_context[:40_000])
    else:
        parts.append(
            "No company context available. Focus on persona needs and use "
            "your best judgment for relevance."
        )
    parts.append("")
    parts.append("---")
    parts.append("")

    # --- Audience Persona Profiles ---
    parts.append("### Audience Persona Profiles")
    if persona_profiles:
        parts.append(persona_profiles[:80_000])
    else:
        parts.append(
            "No persona profiles available. Cannot proceed without audience data."
        )
    parts.append("")
    parts.append("---")
    parts.append("")

    # --- Previous Subdomains (if iterating) ---
    if round_number > 1 and previous_subdomains:
        parts.append("### Previously Identified Subdomains (DO NOT REPEAT)")
        parts.append(
            "The following subdomains have already been identified. Generate "
            "**new, non-overlapping** subdomains that address unmet persona "
            "needs not covered by this list."
        )
        parts.append("")
        for i, sd in enumerate(previous_subdomains, 1):
            parts.append(f"{i}. {sd}")
        parts.append("")
        parts.append("---")
        parts.append("")

    # --- Instructions ---
    if round_number == 1:
        parts.append(
            "Analyze the audience persona profiles above and identify **8-15 "
            "subdomains** from the customer's perspective. Focus on knowledge "
            "territories that address their pain points, goals, fears, and "
            "information needs across the buyer journey."
        )
    else:
        parts.append(
            f"This is expansion round {round_number}. Dig deeper into secondary, "
            f"latent, aspirational, and contextual needs implied by the persona "
            f"profiles. Generate **5-10 new subdomains** not covered by the "
            f"previous list."
        )
    parts.append("")
    parts.append(
        "Return your response as a JSON object matching the schema specified in "
        "your instructions. Do NOT include any text outside the JSON object."
    )

    return "\n".join(parts)
