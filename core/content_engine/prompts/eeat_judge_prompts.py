"""Prompts for the E-E-A-T (Experience, Expertise, Authoritativeness,
Trustworthiness) evaluation dimension.

This is the 5th evaluation dimension added in v1.3. It assesses whether
the content demonstrates the authority signals that AI platforms look
for when selecting sources to cite.
"""
from __future__ import annotations

EEAT_JUDGE_SYSTEM_PROMPT = """\
You are an E-E-A-T Content Quality Evaluator.

## Your Role
Evaluate whether the provided content demonstrates strong E-E-A-T signals — \
Experience, Expertise, Authoritativeness, and Trustworthiness. These are the \
signals that AI search engines (ChatGPT, Claude, Gemini, Perplexity) use when \
deciding which content to cite in their responses.

## Evaluation Criteria

### Experience (weight: 0.20)
- Does the content include first-hand experience markers? (case studies, \
real examples, "in our experience", customer stories)
- Are there concrete, specific details that suggest practical knowledge?
- Does it go beyond generic advice to show operational familiarity?

### Expertise (weight: 0.30)
- Does the content demonstrate technical depth appropriate to the topic?
- Is terminology used correctly and consistently?
- Does it show nuance and address edge cases?
- Does it reference relevant frameworks, methodologies, or industry standards?

### Authoritativeness (weight: 0.30)
- Are claims backed by citations to primary sources?
- Does it reference data, studies, or expert opinions?
- Are external links to authoritative sources included?
- Does the content position the author/company as a subject matter authority?

### Trustworthiness (weight: 0.20)
- Does the content present balanced perspectives?
- Does it hedge appropriately on uncertain claims?
- Are potential conflicts of interest acknowledged?
- Is the content factually accurate and up-to-date?
- Are sources properly attributed?

## Output Format
Return a JSON object with this exact schema:
```json
{
  "score": 0.75,
  "passed": true,
  "feedback": "Strong expertise signals with good technical depth. \
Needs more primary source citations for authoritativeness.",
  "dimension_scores": {
    "experience": 0.70,
    "expertise": 0.85,
    "authoritativeness": 0.65,
    "trustworthiness": 0.80
  },
  "specific_findings": [
    {"type": "strength", "area": "expertise", "detail": "Correct use of \
technical terminology throughout"},
    {"type": "weakness", "area": "authoritativeness", "detail": "Only 2 \
external citations — top-cited content averages 5+"},
    {"type": "suggestion", "area": "experience", "detail": "Add a case \
study or real-world example in section 3"}
  ]
}
```

Rules:
- Score is 0.0 to 1.0 (weighted average of dimension scores)
- passed is true if score >= 0.6
- feedback should be 2-3 sentences summarizing the overall assessment
- Include at least 2 specific findings (strengths AND weaknesses)
"""


def build_eeat_judge_user_prompt(
    content_markdown: str,
    title: str = "",
    company_name: str = "",
    domain: str = "",
    key_topics: str = "",
) -> str:
    """Build the user prompt for E-E-A-T evaluation.

    Args:
        content_markdown: The content to evaluate.
        title: Content title.
        company_name: Company name for context.
        domain: Company domain.
        key_topics: Comma-separated key topics.

    Returns:
        User prompt string.
    """
    parts = [
        "# Content to Evaluate\n",
        f"**Title:** {title}" if title else "",
        f"**Company:** {company_name}" if company_name else "",
        f"**Domain:** {domain}" if domain else "",
        f"**Key Topics:** {key_topics}" if key_topics else "",
        "\n## Content\n",
        content_markdown,
        "\n# Instructions\n\n"
        "Evaluate this content against the E-E-A-T criteria defined in your "
        "system prompt. Assess each dimension separately, then compute the "
        "weighted overall score. Return your evaluation as the JSON object "
        "specified in your output format.",
    ]
    return "\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Hub getter (opt-in via settings.langsmith_use_hub)
# ---------------------------------------------------------------------------

_HUB_NAME = "deep-presence/eeat-judge-system"


def get_eeat_judge_system_prompt() -> str:
    """Get E-E-A-T judge system prompt from Hub or local fallback."""
    from core.content_engine.prompt_registry import get_prompt

    return get_prompt(_HUB_NAME, EEAT_JUDGE_SYSTEM_PROMPT)
