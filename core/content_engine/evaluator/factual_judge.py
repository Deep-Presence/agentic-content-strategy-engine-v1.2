"""Factual judge — LLM-as-judge factual grounding evaluation.

Uses Sonnet 4.5 for high-quality factual accuracy assessment.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from anthropic import AsyncAnthropic

from core.config.settings import settings
from core.content_engine.prompts.factual_judge_prompts import (
    FACTUAL_JUDGE_SYSTEM_PROMPT,
    build_factual_judge_user_prompt,
)
from core.content_engine.tracing import create_span, end_span, log_generation, log_score
from core.content_engine.utils import _retry_async_anthropic, truncate_to_token_limit
from core.models.content_generation import ContentBrief, DimensionResult, FormattedContent

logger = logging.getLogger(__name__)


async def evaluate_factual(
    content: FormattedContent,
    brief: ContentBrief,
    company_name: str,
    domain: str,
    *,
    trace: Optional[object] = None,
) -> DimensionResult:
    """Evaluate content factual accuracy using LLM-as-judge.

    Args:
        content: Formatted content to evaluate.
        brief: Content brief for context.
        company_name: Company name.
        domain: Company domain.
        trace: Langfuse trace for instrumentation.

    Returns:
        DimensionResult with factual evaluation.
    """
    model = settings.content_engine_factual_judge_model
    span = create_span(
        trace, "factual_judge",
        metadata={"brief_id": content.brief_id, "model": model},
        input={
            "brief_id": content.brief_id,
            "content_word_count": content.word_count,
            "company_name": company_name,
            "domain": domain,
        },
    )

    user_prompt = build_factual_judge_user_prompt(
        content_markdown=content.markdown,
        title=content.title,
        company_name=company_name,
        domain=domain,
        key_topics=brief.key_topics,
    )

    user_prompt = truncate_to_token_limit(
        user_prompt, 150_000, label="factual_judge_prompt"
    )

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def _call():
        return await client.messages.create(
            model=model,
            max_tokens=2048,
            system=FACTUAL_JUDGE_SYSTEM_PROMPT,
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
            "flagged_claims": judge_result.get("flagged_claims", []),
        }
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.warning("Factual judge output parse failed: %s", exc)
        score = 0.5
        passed = False
        feedback = f"Factual evaluation parse error — manual review needed. Raw: {raw_text[:200]}"
        details = {"parse_error": str(exc)}

    log_generation(
        trace,
        name="factual_judge",
        model=model,
        input_text=user_prompt,
        output_text=raw_text,
        parent_span=span,
        model_parameters={"max_tokens": 2048},
        usage={
            "input": response.usage.input_tokens,
            "output": response.usage.output_tokens,
        },
    )
    log_score(span, "factual_grounding", round(score, 4))
    end_span(span, output={
        "score": round(score, 4),
        "passed": passed,
        "flagged_claims": details.get("flagged_claims", []),
    })

    logger.info(
        "Factual Judge: %s → score=%.3f (%s)",
        content.brief_id,
        score,
        "PASSED" if passed else "FAILED",
    )

    return DimensionResult(
        dimension="factual",
        passed=passed,
        score=round(score, 4),
        feedback=feedback,
        details=details,
    )
