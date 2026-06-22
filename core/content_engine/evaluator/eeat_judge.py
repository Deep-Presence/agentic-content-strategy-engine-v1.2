"""E-E-A-T evaluation dimension for the v1.3 content pipeline.

Assesses Experience, Expertise, Authoritativeness, and Trustworthiness
signals in content. This is critical for AI citation optimization — AI
platforms preferentially cite content that demonstrates these signals.

Uses LLM-as-judge pattern (consistent with style_judge.py and factual_judge.py).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from core.config.settings import settings
from core.content_engine.llm_client import llm_call, llm_call_for_agent
from core.content_engine.prompts.eeat_judge_prompts import (
    EEAT_JUDGE_SYSTEM_PROMPT,
    build_eeat_judge_user_prompt,
)
from core.content_engine.tracing_v13 import create_span, end_span, extract_provider, log_generation, log_score
from core.content_engine.utils import truncate_to_token_limit
from core.models.content_generation import ContentBrief, DimensionResult, FormattedContent

logger = logging.getLogger(__name__)


async def evaluate_eeat(
    content: FormattedContent,
    brief: ContentBrief,
    company_context_md: str = "",
    *,
    trace: Optional[Any] = None,
    company_slug: str = "",
    workspace_id: str = "",
) -> DimensionResult:
    """Evaluate E-E-A-T signals in content using LLM-as-judge.

    Args:
        content: The formatted content to evaluate.
        brief: The content brief (for topic context).
        company_context_md: Company context for authority assessment.
        trace: Optional parent trace/span for instrumentation.

    Returns:
        DimensionResult with E-E-A-T score, pass/fail, and feedback.
    """
    model = settings.content_engine_v13_eeat_judge_model
    span = create_span(
        trace, "eeat_judge",
        metadata={"brief_id": content.brief_id, "model": model},
        input={
            "brief_id": content.brief_id,
            "content_word_count": content.word_count,
        },
    )

    # Build prompt
    key_topics = ", ".join(brief.key_topics[:10]) if brief.key_topics else ""
    user_prompt = build_eeat_judge_user_prompt(
        content_markdown=content.markdown,
        title=content.title,
        company_name="",  # Extracted from company_context_md below
        domain="",
        key_topics=key_topics,
    )

    # Truncate to fit context window
    user_prompt = truncate_to_token_limit(
        user_prompt, max_tokens=150_000, label="eeat_judge_user"
    )

    response = None  # Sentinel: guards log_generation usage reporting on llm_call failure
    try:
        metadata = {
            "agent": "eeat_judge",
            "agent_key": "content.judge.eeat",
            "brief_id": content.brief_id,
            "pipeline": "content_engine",
            "pipeline_step": "eeat_judge",
            "provider": extract_provider(model),
            "model": model,
            "company_slug": company_slug,
        }
        if workspace_id:
            response = await llm_call_for_agent(
                workspace_id=workspace_id,
                workspace_slug=company_slug,
                agent_key="content.judge.eeat",
                system=EEAT_JUDGE_SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=2048,
                temperature=0.0,
                response_format={"type": "json_object"},
                metadata=metadata,
            )
        else:
            response = await llm_call(
                model=model,
                system=EEAT_JUDGE_SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=2048,
                temperature=0.0,
                response_format={"type": "json_object"},
                metadata=metadata,
            )

        # Parse JSON response
        import json_repair
        from core.content_engine.utils import _extract_json_block

        raw = _extract_json_block(response.content)
        parsed = json_repair.loads(raw)

        score = float(parsed.get("score", 0.0))
        passed = bool(parsed.get("passed", score >= 0.6))
        feedback = str(parsed.get("feedback", ""))
        details = {
            "dimension_scores": parsed.get("dimension_scores", {}),
            "specific_findings": parsed.get("specific_findings", []),
        }

        result = DimensionResult(
            dimension="eeat",
            passed=passed,
            score=score,
            feedback=feedback,
            details=details,
        )

    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning("E-E-A-T judge parse error: %s", exc)
        result = DimensionResult(
            dimension="eeat",
            passed=False,
            score=0.5,
            feedback=f"E-E-A-T evaluation parse error: {exc}",
            details={"error": str(exc)},
        )

    except Exception as exc:
        logger.error("E-E-A-T judge failed: %s", exc, exc_info=True)
        result = DimensionResult(
            dimension="eeat",
            passed=False,
            score=0.5,
            feedback=f"E-E-A-T evaluation error: {exc}",
            details={"error": str(exc)},
        )

    log_generation(
        span,
        name="eeat_judge",
        model=model,
        input_text=user_prompt[:2000],
        output_text=result.feedback[:500],
        model_parameters={"max_tokens": 2048},
        usage={
            "prompt_tokens": getattr(response, "input_tokens", 0) if response is not None else 0,
            "completion_tokens": getattr(response, "output_tokens", 0) if response is not None else 0,
            "total_tokens": getattr(response, "total_tokens", 0) if response is not None else 0,
        },
    )
    log_score(span, "eeat_score", round(result.score, 4))
    end_span(span, output={
        "score": round(result.score, 4),
        "passed": result.passed,
        "dimension_scores": result.details.get("dimension_scores", {}),
    })

    logger.info(
        "E-E-A-T Judge: %s → score=%.3f (%s)",
        content.brief_id,
        result.score,
        "PASSED" if result.passed else "FAILED",
    )

    return result
