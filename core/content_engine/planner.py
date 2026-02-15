"""Stage 1: Strategic Planner.

Single LLM call (Sonnet 4.5) that reads gap analysis outputs
and produces prioritized content briefs.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from anthropic import AsyncAnthropic

from core.config.settings import settings
from core.content_engine.prompts.planner_prompts import (
    PLANNER_SYSTEM_PROMPT,
    build_planner_user_prompt,
)
from core.content_engine.tracing import (
    create_trace,
    log_generation,
    log_score,
)
from core.content_engine.utils import (
    _retry_async_anthropic,
    safe_parse,
    truncate_to_token_limit,
)
from core.models.content_generation import (
    ContentGenerationInput,
    PlannerOutput,
)

logger = logging.getLogger(__name__)

# Sonnet 4.5 context window is ~200K tokens; leave room for output
_MAX_INPUT_TOKENS = 150_000


async def plan_content(
    *,
    input_data: ContentGenerationInput,
    company_context_md: str,
    style_guide_md: str,
    persona_mds: List[str],
    gap_report_json: Dict[str, Any],
    generation_spec_json: Dict[str, Any],
    analysis_json: Dict[str, Any],
    session_id: str,
) -> PlannerOutput:
    """Generate content briefs from gap analysis data.

    Args:
        input_data: Pipeline input configuration.
        company_context_md: Company context markdown.
        style_guide_md: Writing style guide markdown.
        persona_mds: List of persona profile markdowns.
        gap_report_json: Gap report as dict.
        generation_spec_json: Content generation spec as dict.
        analysis_json: Full analysis results as dict.
        session_id: Langfuse session ID.

    Returns:
        PlannerOutput with prioritized content briefs.
    """
    model = settings.content_engine_planner_model
    trace = create_trace(session_id, "planner", metadata={"model": model})

    # Build prompt
    user_prompt = build_planner_user_prompt(
        company_name=input_data.company_name,
        domain=input_data.domain,
        company_context_md=company_context_md,
        gap_report_json=gap_report_json,
        generation_spec_json=generation_spec_json,
        analysis_json=analysis_json,
        persona_mds=persona_mds,
        max_briefs=input_data.max_briefs,
    )

    # Context window guard
    user_prompt = truncate_to_token_limit(
        user_prompt, _MAX_INPUT_TOKENS, label="planner_prompt"
    )

    # Call LLM
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def _call():
        return await client.messages.create(
            model=model,
            max_tokens=8192,
            system=PLANNER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

    response = await _retry_async_anthropic(_call, max_retries=3, base_delay=2.0)

    # Extract text from response
    raw_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            raw_text += block.text

    # Parse into PlannerOutput
    planner_output = safe_parse(raw_text, PlannerOutput)

    # Enrich metadata
    planner_output.planning_metadata.update({
        "model": model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    })

    # Langfuse logging
    log_generation(
        trace,
        name="plan_content",
        model=model,
        input_text=user_prompt[:2000],
        output_text=raw_text[:2000],
        usage={
            "input": response.usage.input_tokens,
            "output": response.usage.output_tokens,
        },
    )
    log_score(trace, "briefs_generated", len(planner_output.briefs))

    logger.info(
        "Planner produced %d briefs (model=%s, tokens=%d+%d)",
        len(planner_output.briefs),
        model,
        response.usage.input_tokens,
        response.usage.output_tokens,
    )

    return planner_output
