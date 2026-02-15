"""Style judge — LLM-as-judge style alignment evaluation.

Uses Haiku 4.5 for fast, cost-effective style evaluation.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from anthropic import AsyncAnthropic

from core.config.settings import settings
from core.content_engine.prompts.style_judge_prompts import (
    STYLE_JUDGE_SYSTEM_PROMPT,
    build_style_judge_user_prompt,
)
from core.content_engine.tracing import create_span, end_span, log_generation, log_score
from core.content_engine.utils import _retry_async_anthropic, safe_parse
from core.models.content_generation import DimensionResult, FormattedContent

logger = logging.getLogger(__name__)


class _StyleJudgeResult:
    """Internal parse target for style judge JSON output."""
    pass


async def evaluate_style(
    content: FormattedContent,
    style_guide_md: str,
    *,
    trace: Optional[object] = None,
) -> DimensionResult:
    """Evaluate content style alignment using LLM-as-judge.

    Args:
        content: Formatted content to evaluate.
        style_guide_md: Company writing style guide.
        trace: Langfuse trace for instrumentation.

    Returns:
        DimensionResult with style evaluation.
    """
    model = settings.content_engine_style_judge_model
    span = create_span(trace, "style_judge", metadata={"brief_id": content.brief_id})

    user_prompt = build_style_judge_user_prompt(
        content_markdown=content.markdown,
        style_guide_md=style_guide_md,
        title=content.title,
    )

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def _call():
        return await client.messages.create(
            model=model,
            max_tokens=2048,
            system=STYLE_JUDGE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

    response = await _retry_async_anthropic(_call, max_retries=2)

    raw_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            raw_text += block.text

    # Parse the judge's JSON response
    try:
        from core.content_engine.utils import _extract_json_block

        json_str = _extract_json_block(raw_text)
        judge_result = json.loads(json_str)
        score = float(judge_result.get("score", 0.0))
        passed = judge_result.get("passed", score >= 0.7)
        feedback = judge_result.get("feedback", "")
        details = {
            "criteria_scores": judge_result.get("criteria_scores", {}),
        }
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.warning("Style judge output parse failed: %s", exc)
        score = 0.5
        passed = False
        feedback = f"Style evaluation parse error — manual review needed. Raw: {raw_text[:200]}"
        details = {"parse_error": str(exc)}

    log_generation(
        trace,
        name="style_judge",
        model=model,
        input_text=user_prompt[:1000],
        output_text=raw_text[:500],
        parent_span=span,
        usage={
            "input": response.usage.input_tokens,
            "output": response.usage.output_tokens,
        },
    )
    log_score(trace, "style_alignment", round(score, 4))
    end_span(span, output=f"score={score:.3f}, passed={passed}")

    logger.info(
        "Style Judge: %s → score=%.3f (%s)",
        content.brief_id,
        score,
        "PASSED" if passed else "FAILED",
    )

    return DimensionResult(
        dimension="style",
        passed=passed,
        score=round(score, 4),
        feedback=feedback,
        details=details,
    )
