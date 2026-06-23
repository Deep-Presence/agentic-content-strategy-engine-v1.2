"""Query Fanout Generator — LLM-based intent-axis expansion for tracked prompts.

Given a parent prompt (e.g. "best CRM for small business"), generates 12-18
query variants across 6 intent axes via a single structured OpenRouter call.
These variants are stored as child ``tracked_prompts`` rows and tracked daily
alongside the parent prompt.

Uses workspace BYOK routing when workspace context is supplied, with the
legacy shared OpenRouter client retained for older tests and direct callers.

Does NOT:
    - Persist prompts (caller's responsibility via PromptLibraryService)
    - Execute prompts (PlatformRunnerService)
    - Access the database
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import Any

from core.models.daily_tracker import FanoutGenerationResult, FanoutQuery

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System prompt — defines the 6 intent axes
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a search behavior expert specializing in AI answer engines \
(ChatGPT, Claude, Perplexity, Gemini, Google AI Mode).

Given a tracked visibility prompt for a brand, generate query variants \
along 6 intent axes that represent how real users would phrase similar \
questions across AI platforms.

INTENT AXES (generate 2-3 queries per axis):

1. COMPARATIVE — "X vs Y", "best alternatives to X", "how does X compare to Y"
   User is evaluating competing options.

2. EVALUATIVE — "X reviews", "is X worth it", "pros and cons of X"
   User is doing due diligence on a specific solution.

3. PROBLEM_FRAMED — "how to solve Y", "what to do when Z", "why is Y happening"
   User has a specific problem and seeks solutions.

4. FEATURE_SPECIFIC — "X with feature Y", "X that supports Y", "does X have Y"
   User cares about a specific capability.

5. AUDIENCE_NARROWED — "X for startups", "X for enterprise", "X for {persona}"
   User is narrowing by their segment or role.

6. TEMPORAL — "best X in 2026", "latest X", "current best X", "X trends"
   User wants up-to-date information.

RULES:
- Each query must be unique and natural-sounding
- Vary query length (short 4-6 words to long 10-15 words)
- Do NOT always include the brand name — many queries should be category-level
- Match the semantic intent of the parent prompt but vary the angle
- Include queries that competitors might rank for
- Return ONLY valid JSON, no prose or markdown fences
"""


def _build_user_prompt(
    parent_text: str,
    brand_name: str,
    brand_category: str,
    competitors: list[str],
    target_count: int,
) -> str:
    """Build the user prompt for fanout generation."""
    competitors_csv = ", ".join(competitors) if competitors else "none specified"
    return (
        f'PARENT PROMPT: "{parent_text}"\n\n'
        f"BRAND: {brand_name}\n"
        f"CATEGORY: {brand_category or 'not specified'}\n"
        f"COMPETITORS: {competitors_csv}\n\n"
        f"Generate {target_count} query variants as JSON:\n"
        '{{\n'
        '  "queries": [\n'
        '    {{\n'
        '      "axis": "comparative",\n'
        '      "query_text": "example query here",\n'
        '      "reasoning": "why this query variant is useful"\n'
        '    }}\n'
        '  ]\n'
        '}}'
    )


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class QueryFanoutService:
    """Generates intent-axis query variants from a parent prompt via OpenRouter.

    Uses workspace BYOK routing when workspace context is supplied. The legacy
    shared OpenRouter client path is retained for older tests/direct callers.

    Constructor args match settings defaults — callers can override per-call
    or inject from ``core.config.settings``.
    """

    def __init__(
        self,
        model: str = "anthropic/claude-sonnet-4-6",
        max_tokens: int = 4096,
        temperature: float = 0.3,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._max_retries = max_retries
        self._base_delay = base_delay

    async def generate_fanout(
        self,
        parent_text: str,
        brand_name: str,
        brand_category: str = "",
        competitors: list[str] | None = None,
        target_count: int = 15,
        workspace_id: str = "",
        workspace_slug: str = "",
        company_slug: str = "",
    ) -> FanoutGenerationResult:
        """Generate query variants for a parent prompt.

        Makes a single structured LLM call via OpenRouter to produce
        ``target_count`` query variants across 6 intent axes.

        Args:
            parent_text: The parent prompt text to expand.
            brand_name: Brand name for context.
            brand_category: Optional brand category for context.
            competitors: Optional list of competitor names.
            target_count: Target number of variants (default 15).

        Returns:
            ``FanoutGenerationResult`` with generated queries and token usage.

        Raises:
            RuntimeError: If OpenRouter/BYOK API key is not configured.
            Exception: If all retries exhausted.
        """
        from core.shared_tools.openrouter_client import (
            _ensure_model_prefix,
            get_async_client,
        )
        from core.shared_tools.cost_tracker import track_llm_cost

        model = _ensure_model_prefix(self._model)
        user_prompt = _build_user_prompt(
            parent_text,
            brand_name,
            brand_category,
            competitors or [],
            target_count,
        )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
            "response_format": {"type": "json_object"},
        }

        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                if workspace_id:
                    from core.content_engine.llm_client import llm_call_for_agent

                    response = await llm_call_for_agent(
                        workspace_id=workspace_id,
                        workspace_slug=workspace_slug or company_slug,
                        agent_key="daily_tracker.fanout",
                        system=_SYSTEM_PROMPT,
                        user=user_prompt,
                        max_tokens=self._max_tokens,
                        temperature=self._temperature,
                        response_format={"type": "json_object"},
                        metadata={
                            "pipeline": "daily_tracker",
                            "pipeline_step": "fanout_generation",
                            "company_slug": company_slug or workspace_slug,
                        },
                        max_retries=1,
                        base_delay=self._base_delay,
                    )
                    raw_content = response.content or "{}"
                    token_usage = {
                        "prompt_tokens": response.input_tokens,
                        "completion_tokens": response.output_tokens,
                        "total_tokens": response.total_tokens,
                    }
                    response_model = response.model or model
                else:
                    client = get_async_client()
                    response = await client.chat.completions.create(**kwargs)

                    choice = response.choices[0]
                    usage = response.usage
                    raw_content = choice.message.content or "{}"

                    # Cost tracking (never raises)
                    track_llm_cost(
                        model=response.model or model,
                        provider="openrouter",
                        pipeline="daily_tracker",
                        pipeline_step="fanout_generation",
                        prompt_tokens=usage.prompt_tokens if usage else 0,
                        completion_tokens=usage.completion_tokens if usage else 0,
                        company_slug=company_slug,
                        call_site="core.daily_tracker.query_fanout",
                        source="openrouter",
                    )

                    token_usage = {
                        "prompt_tokens": usage.prompt_tokens if usage else 0,
                        "completion_tokens": usage.completion_tokens if usage else 0,
                        "total_tokens": usage.total_tokens if usage else 0,
                    }
                    response_model = response.model or model

                # Parse JSON response
                queries = self._parse_response(raw_content)

                logger.info(
                    "Fanout generation completed: %d queries from '%s' "
                    "(model=%s, tokens=%s)",
                    len(queries),
                    parent_text[:60],
                    response_model,
                    token_usage.get("total_tokens", 0),
                )

                return FanoutGenerationResult(
                    queries=queries,
                    model_used=response_model,
                    token_usage=token_usage,
                )

            except Exception as exc:
                last_error = exc
                if attempt < self._max_retries - 1:
                    delay = self._base_delay * (2**attempt) + random.uniform(
                        0, self._base_delay
                    )
                    logger.warning(
                        "Fanout generation failed (attempt %d/%d): %s. "
                        "Retrying in %.1fs",
                        attempt + 1,
                        self._max_retries,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)

        raise last_error or RuntimeError("Fanout generation failed")

    @staticmethod
    def _parse_response(raw: str) -> list[FanoutQuery]:
        """Parse the LLM JSON response into FanoutQuery objects.

        Handles both ``{"queries": [...]}`` and bare ``[...]`` formats.

        Args:
            raw: Raw JSON string from the LLM.

        Returns:
            List of validated FanoutQuery objects.
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(
                "Failed to parse fanout JSON, attempting extraction"
            )
            # Try to extract JSON from markdown fences
            start = raw.find("[")
            end = raw.rfind("]")
            if start != -1 and end != -1:
                data = json.loads(raw[start : end + 1])
                data = {"queries": data}
            else:
                logger.error("Cannot extract fanout queries from response")
                return []

        # Normalize structure
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("queries", [])
        else:
            return []

        queries: list[FanoutQuery] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            query_text = item.get("query_text", item.get("query", "")).strip()
            if not query_text:
                continue
            queries.append(
                FanoutQuery(
                    axis=item.get("axis", "").strip().lower(),
                    query_text=query_text,
                    reasoning=item.get("reasoning", "").strip(),
                )
            )

        return queries
