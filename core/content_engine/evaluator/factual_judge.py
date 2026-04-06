"""Factual judge — LLM-as-judge factual grounding evaluation.

Uses Sonnet 4.5 for high-quality factual accuracy assessment.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from core.config.settings import settings
from core.content_engine.llm_client import llm_call
from core.content_engine.prompts.factual_judge_prompts import (
    FACTUAL_JUDGE_SYSTEM_PROMPT,
    build_factual_judge_user_prompt,
)
from core.content_engine.tracing_v13 import create_span, end_span, extract_provider, log_generation, log_score
from core.content_engine.utils import truncate_to_token_limit
from core.models.content_generation import ContentBrief, DimensionResult, FormattedContent

logger = logging.getLogger(__name__)


async def evaluate_factual(
    content: FormattedContent,
    brief: ContentBrief,
    company_name: str,
    domain: str,
    *,
    trace: Optional[object] = None,
    company_slug: str = "",
) -> DimensionResult:
    """Evaluate content factual accuracy using LLM-as-judge.

    Args:
        content: Formatted content to evaluate.
        brief: Content brief for context.
        company_name: Company name.
        domain: Company domain.
        trace: Trace span for instrumentation.

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

    try:
        response = await llm_call(
            model=model,
            system=FACTUAL_JUDGE_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=2048,
            metadata={
                "agent": "factual_judge",
                "brief_id": content.brief_id,
                "pipeline": "content_engine",
                "pipeline_step": "factual_judge",
                "provider": extract_provider(model),
                "model": model,
                "company_slug": company_slug,
            },
            max_retries=2,
        )

        raw_text = response.content

        # Parse the judge's JSON response
        try:
            import json_repair
            from core.content_engine.utils import _extract_json_block

            json_str = _extract_json_block(raw_text)
            judge_result = json_repair.loads(json_str)
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
            span,
            name="factual_judge",
            model=model,
            input_text=user_prompt,
            output_text=raw_text,
            model_parameters={"max_tokens": 2048},
            usage={
                "prompt_tokens": response.input_tokens,
                "completion_tokens": response.output_tokens,
                "total_tokens": response.total_tokens,
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
    except Exception as exc:
        end_span(span, error=str(exc)[:500])
        raise
