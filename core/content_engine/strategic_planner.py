"""Strategic Planner (Agent 1) for the v1.3 content pipeline.

Receives a lightweight PlannerScorecard (~11K tokens) and selects the
top-K highest-impact content opportunities. Unlike the v1.0 planner,
this agent does NOT produce content briefs — it performs triage only.

The Brief Builder (Agent 2) handles content architecture after HITL-1
approves the topic selections.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from core.config.settings import settings
from core.content_engine.context_router import format_scorecard_as_markdown
from core.content_engine.llm_client import llm_call, llm_call_for_agent
from core.content_engine.prompts.strategic_planner_prompts import (
    STRATEGIC_PLANNER_SYSTEM_PROMPT,
    build_strategic_planner_user_prompt,
)
from core.content_engine.tracing_v13 import create_span, end_span, extract_provider, log_generation
from core.content_engine.utils import safe_parse, truncate_to_token_limit
from core.models.content_generation_v13 import (
    PlannerScorecard,
    StrategicPlannerOutput,
)

logger = logging.getLogger(__name__)


async def select_topics(
    scorecard: PlannerScorecard,
    *,
    max_topics: int = 6,
    user_feedback: str = "",
    parent_span: Optional[Any] = None,
    company_slug: str = "",
    workspace_id: str = "",
) -> StrategicPlannerOutput:
    """Run the Strategic Planner to select top-K content opportunities.

    Args:
        scorecard: Lightweight scorecard extracted by context_router.
        max_topics: Number of topics to select (default 6).
        user_feedback: Optional feedback from HITL-1 retry.
        parent_span: Optional LangSmith parent span for tracing.

    Returns:
        StrategicPlannerOutput with ranked topic selections.

    Raises:
        ValueError: If the LLM output cannot be parsed.
    """
    span = create_span(parent_span, "strategic-planner")

    # Format scorecard as markdown tables
    scorecard_md = format_scorecard_as_markdown(scorecard)

    # Build prompts
    user_prompt = build_strategic_planner_user_prompt(
        scorecard_markdown=scorecard_md,
        max_topics=max_topics,
        user_feedback=user_feedback or None,
    )

    # Truncate to stay within context window (conservative 100K limit)
    user_prompt = truncate_to_token_limit(
        user_prompt, max_tokens=100_000, label="strategic_planner_user"
    )

    model = settings.content_engine_v13_planner_model

    logger.info(
        "Running Strategic Planner: %d queries, %d clusters, max_topics=%d",
        scorecard.total_queries,
        scorecard.total_clusters,
        max_topics,
    )

    metadata = {
        "agent": "strategic_planner",
        "agent_key": "content.strategic_planner",
        "total_queries": scorecard.total_queries,
        "max_topics": max_topics,
        "pipeline": "content_engine",
        "pipeline_step": "strategic_planner",
        "provider": extract_provider(model),
        "model": model,
        "company_slug": company_slug,
    }

    if workspace_id:
        response = await llm_call_for_agent(
            workspace_id=workspace_id,
            workspace_slug=company_slug,
            agent_key="content.strategic_planner",
            system=STRATEGIC_PLANNER_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=4096,
            temperature=0.0,
            response_format={"type": "json_object"},
            metadata=metadata,
        )
    else:
        # Direct/CLI calls keep the legacy platform client until the platform
        # entrypoints enforce workspace-scoped BYOK preflight.
        response = await llm_call(
            model=model,
            system=STRATEGIC_PLANNER_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=4096,
            temperature=0.0,
            response_format={"type": "json_object"},
            metadata=metadata,
        )

    # Parse output
    output = safe_parse(response.content, StrategicPlannerOutput)

    # Enrich metadata
    output.selection_metadata.update(
        {
            "model": response.model,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "total_tokens": response.total_tokens,
        }
    )

    # Log to LangSmith
    log_generation(
        parent=span,
        name="select_topics",
        model=model,
        input_text=user_prompt[:3000],
        output_text=response.content[:3000],
        usage={
            "prompt_tokens": response.input_tokens,
            "completion_tokens": response.output_tokens,
            "total_tokens": response.total_tokens,
        },
    )

    logger.info(
        "Strategic Planner selected %d topics (model=%s, tokens=%d)",
        len(output.selections),
        response.model,
        response.total_tokens,
    )

    end_span(span, output={"selections_count": len(output.selections)})
    return output
