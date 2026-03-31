"""Stage 1: Strategic Planner.

Single LLM call (Sonnet 4.5) that reads gap analysis outputs
and produces prioritized content briefs.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core.config.settings import settings
from core.shared_tools.openrouter_client import get_async_client, _ensure_model_prefix
from core.shared_tools.cost_tracker import track_llm_cost
from core.content_engine.prompts.planner_prompts import (
    PLANNER_SYSTEM_PROMPT,
    build_planner_user_prompt,
)
from core.content_engine.tracing_v13 import (
    create_span,
    create_trace,
    end_span,
    log_generation,
    log_score,
    update_trace_output,
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
    session_id: str = "",
    parent_span: Optional[Any] = None,
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
        session_id: Session ID.

    Returns:
        PlannerOutput with prioritized content briefs.
    """
    model = settings.content_engine_planner_model
    trace_metadata = {"model": model, "max_briefs": input_data.max_briefs}
    trace_input = {
        "company_name": input_data.company_name,
        "domain": input_data.domain,
        "max_briefs": input_data.max_briefs,
    }
    if parent_span is not None:
        trace = create_span(
            parent_span, "planner",
            metadata=trace_metadata,
            input=trace_input,
        )
    else:
        trace = create_trace(
            session_id,
            "planner",
            metadata=trace_metadata,
            input=trace_input,
            tags=["planner", f"model:{model}"],
            user_id=input_data.domain,
        )

    # Build product context block when product fields are set
    product_context_md = ""
    if input_data.product_slug and input_data.product_name:
        from core.content_engine.prompts.planner_prompts import _PRODUCT_FOCUS_BLOCK
        product_context_md = _PRODUCT_FOCUS_BLOCK.format(
            product_name=input_data.product_name,
            product_domain=input_data.domain or "N/A",
            product_description=input_data.product_description or "N/A",
        )

    # Build prompt
    user_prompt = build_planner_user_prompt(
        company_name=input_data.company_name,
        domain=input_data.domain,
        company_context_md=company_context_md,
        style_guide_md=style_guide_md,
        gap_report_json=gap_report_json,
        generation_spec_json=generation_spec_json,
        analysis_json=analysis_json,
        persona_mds=persona_mds,
        max_briefs=input_data.max_briefs,
        product_context_md=product_context_md,
    )

    # Context window guard
    user_prompt = truncate_to_token_limit(
        user_prompt, _MAX_INPUT_TOKENS, label="planner_prompt"
    )

    # Call LLM via OpenRouter
    client = get_async_client()
    prefixed_model = _ensure_model_prefix(model)

    async def _call():
        return await client.chat.completions.create(
            model=prefixed_model,
            max_tokens=16384,
            messages=[
                {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            extra_body={"metadata": {"pipeline": "content_engine", "step": "planner"}},
        )

    response = await _retry_async_anthropic(_call, max_retries=3, base_delay=2.0)

    # Extract text from response (OpenAI chat completion format)
    raw_text = response.choices[0].message.content or ""

    # Parse into PlannerOutput
    planner_output = safe_parse(raw_text, PlannerOutput)

    # Enrich metadata (OpenAI uses prompt_tokens / completion_tokens)
    usage = response.usage
    in_tokens = getattr(usage, "prompt_tokens", 0) or 0
    out_tokens = getattr(usage, "completion_tokens", 0) or 0
    planner_output.planning_metadata.update({
        "model": model,
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
    })

    # Cost tracking (never raises)
    track_llm_cost(
        model=model,
        provider="openrouter",
        pipeline="content_engine",
        pipeline_step="planner",
        prompt_tokens=in_tokens,
        completion_tokens=out_tokens,
        company_slug=getattr(input_data, "company_slug", "") or "",
        call_site="core.content_engine.planner",
        source="openrouter",
    )

    # LangSmith logging
    log_generation(
        trace,
        name="plan_content",
        model=model,
        input_text=user_prompt,
        output_text=raw_text,
        metadata={
            "system_prompt_length": len(PLANNER_SYSTEM_PROMPT),
            "user_prompt_length": len(user_prompt),
        },
        model_parameters={"max_tokens": 16384},
        usage={
            "prompt_tokens": in_tokens,
            "completion_tokens": out_tokens,
            "total_tokens": in_tokens + out_tokens,
        },
    )
    log_score(trace, "briefs_generated", len(planner_output.briefs))
    trace_output = {
        "briefs_count": len(planner_output.briefs),
        "brief_ids": [b.brief_id for b in planner_output.briefs],
        "brief_titles": [b.title for b in planner_output.briefs],
        "token_usage": {
            "input": in_tokens,
            "output": out_tokens,
        },
    }
    if parent_span is not None:
        end_span(trace, output=trace_output)
    else:
        update_trace_output(trace, output=trace_output)
        end_span(trace)

    logger.info(
        "Planner produced %d briefs (model=%s, tokens=%d+%d)",
        len(planner_output.briefs),
        model,
        in_tokens,
        out_tokens,
    )

    return planner_output
