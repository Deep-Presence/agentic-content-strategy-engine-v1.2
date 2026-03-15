"""Weakness Analyst specialist agent prompt.

Agent 4 — Deep-dives into competitor weaknesses using Perplexity sonar-deep-research.
Receives company overview + competitor registry as upstream context.
"""
from __future__ import annotations

from typing import Optional

from core.models.knowledge_base import KnowledgeBaseInput

WEAKNESS_ANALYST_SYSTEM_PROMPT = """\
You are a specialist competitive intelligence analyst focused on identifying and \
cataloguing competitor weaknesses for B2B SaaS companies. Your research will inform \
content strategy to help the company outperform competitors in AI search citations.

You will receive the company overview and competitor registry as context. Use them \
to focus your weakness research on the most relevant competitors.

## Required Output Sections

1. **Per-Competitor Weakness Analysis** — For each major competitor:
   - Weakness category (product gaps, UX issues, pricing, support, scalability, etc.)
   - Description of the weakness
   - Severity: critical / significant / minor
   - Evidence (links, quotes, review excerpts)
   - Opportunity for us — how the target company can exploit this weakness

2. **Systemic Industry Problems** — Weaknesses shared across multiple competitors
   - Problems that the entire category struggles with
   - Unmet needs in the market

3. **Strategic Opportunities** — Synthesized recommendations
   - Top 5 opportunities ranked by impact potential
   - Content angles that exploit competitor gaps
   - Differentiation vectors based on competitor weaknesses

## Output Requirements

- Write in analytical, evidence-based tone
- Use markdown formatting with clear section headers
- Include inline citations [1], [2], etc. from review sites, forums, social media
- Be specific — vague claims like "poor UX" must be backed by examples
- Minimum 1500 words, maximum 4000 words
- Focus on weaknesses that are relevant to content strategy and AI search positioning
"""

_HUB_NAME = "research-weakness-analyst-system"


def get_weakness_analyst_system_prompt() -> str:
    """Get weakness analyst system prompt (Hub with local fallback)."""
    from core.content_engine.prompt_registry import get_prompt

    return get_prompt(_HUB_NAME, WEAKNESS_ANALYST_SYSTEM_PROMPT)


def build_weakness_analyst_user_prompt(
    input_data: KnowledgeBaseInput,
    company_overview_md: str,
    competitor_registry_md: str,
    revision_note: Optional[str] = None,
) -> str:
    """Build user prompt for competitor weakness research.

    Args:
        input_data: Pipeline input with company details.
        company_overview_md: Upstream company overview markdown (Agent 1 output).
        competitor_registry_md: Upstream competitor registry markdown (Agent 3 output).
        revision_note: Optional reviewer feedback from a previous version.
    """
    # Truncate upstream docs to avoid excessive prompt length
    overview_truncated = company_overview_md[:32_000]  # ~8k tokens
    if len(company_overview_md) > 32_000:
        overview_truncated += "\n\n[... truncated ...]"

    competitor_truncated = competitor_registry_md[:48_000]  # ~12k tokens
    if len(competitor_registry_md) > 48_000:
        competitor_truncated += "\n\n[... truncated ...]"

    parts = [
        f"Analyze competitor weaknesses for the following company.",
        f"\nCompany: {input_data.company_name}",
    ]
    if input_data.domain:
        parts.append(f"Domain: {input_data.domain}")
    if input_data.additional_constraints:
        parts.append(f"\nAdditional instructions: {input_data.additional_constraints}")
    parts.append(f"\n## Company Overview (for context)\n\n{overview_truncated}")
    parts.append(f"\n## Competitor Registry (for context)\n\n{competitor_truncated}")
    if revision_note:
        parts.append(
            f"\n## Reviewer Feedback\n\n"
            f"A previous version was reviewed and revisions were requested. "
            f"Address the following feedback:\n\n{revision_note}"
        )
    return "\n".join(parts)
