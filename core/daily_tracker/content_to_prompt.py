"""Content-to-Prompt Generation Service — LLM-based prompt generation from pages.

Given a published content page's metadata, generates k AI visibility tracking
prompts spanning buyer stages (TOFU/MOFU/BOFU) and intent types using a single
structured LLM call via OpenRouter.

Architecture follows ``QueryFanoutService`` — pure generation, no DB access.
Caller (orchestrator) handles dedup, persistence, and approval flow.

Does NOT:
    - Persist prompts (caller's responsibility via orchestrator)
    - Access the database
    - Own transaction boundaries
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
from typing import Any

from core.models.daily_tracker import (
    GeneratedPagePrompt,
    PageContext,
    PagePromptGenerationResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an AEO (Answer Engine Optimization) prompt strategist specializing \
in AI search engines (ChatGPT, Claude, Perplexity, Gemini, Google AI Mode).

Given metadata about a published web page, generate exactly {k} search \
prompts that real users would type into AI assistants where this page \
SHOULD appear as an authoritative source in the response.

Distribute prompts across three buyer stages:

**TOFU (Top-of-Funnel / Awareness):** Educational, problem-framing queries.
  "What is X?", "How does X work?", "Why is X important for Y?"

**MOFU (Middle-of-Funnel / Consideration):** Evaluative, comparison queries.
  "Best approaches to X", "X vs Y for Z use case", "How to choose X"

**BOFU (Bottom-of-Funnel / Decision):** Transactional, vendor-specific queries.
  "X pricing", "X vs [competitor]", "X for [specific use case]"

DISTRIBUTION RULES:
- At least 1 prompt per buyer stage (tofu, mofu, bofu)
- Mix intent types: informational, commercial, navigational, transactional
- Include 1-2 branded prompts (with the brand name) and the rest unbranded
- Vary query length (short 4-6 words to long 10-15 words)
- Prompts must be natural questions a human would actually ask an AI
- Each prompt must be answerable by the page content

Return ONLY valid JSON, no prose or markdown fences.\
"""


def _build_user_prompt(
    page: PageContext,
    brand_name: str,
    brand_category: str,
    competitors: list[str],
    k: int,
) -> str:
    """Build the user prompt for content-to-prompt generation."""
    cats = ", ".join(page.categories) if page.categories else "not specified"
    comps = ", ".join(competitors) if competitors else "none specified"
    preview = page.content_preview[:300] if page.content_preview else ""

    # Wrap untrusted page content in XML tags to mitigate prompt injection
    return (
        f"PAGE METADATA:\n"
        f"  <url>{page.url}</url>\n"
        f"  <title>{page.title}</title>\n"
        f"  <meta_description>{page.meta_description}</meta_description>\n"
        f"  <content_preview>{preview}</content_preview>\n"
        f"  <categories>{cats}</categories>\n"
        f"  <primary_topic>{page.detected_primary_topic}</primary_topic>\n"
        f"  <content_type>{page.content_type_detected}</content_type>\n"
        f"  <word_count>{page.word_count}</word_count>\n\n"
        f"BRAND: {brand_name}\n"
        f"CATEGORY: {brand_category or 'not specified'}\n"
        f"COMPETITORS: {comps}\n\n"
        f"Generate exactly {k} prompts as JSON:\n"
        '{{\n'
        '  "prompts": [\n'
        '    {{\n'
        '      "query_text": "example query here",\n'
        '      "buyer_stage": "tofu",\n'
        '      "intent_type": "informational",\n'
        '      "is_branded": false,\n'
        '      "reasoning": "why this query is relevant to this page"\n'
        '    }}\n'
        '  ]\n'
        '}}'
    )


def compute_content_hash(page: PageContext) -> str:
    """Compute a stable hash of page content for cache keying.

    If content hasn't changed, we can skip LLM regeneration.
    """
    payload = (
        f"{page.title}|{page.meta_description}|{page.content_preview[:300]}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ContentToPromptService:
    """Generates AI visibility prompts from content inventory page metadata.

    Uses the shared OpenRouter client (``core.shared_tools.openrouter_client``)
    and ``track_llm_cost()`` for cost tracking.  Architecture mirrors
    ``QueryFanoutService``.
    """

    def __init__(
        self,
        model: str = "anthropic/claude-sonnet-4-6",
        max_tokens: int = 4096,
        temperature: float = 0.4,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._max_retries = max_retries
        self._base_delay = base_delay

    async def generate_prompts_for_page(
        self,
        page: PageContext,
        brand_name: str,
        brand_category: str = "",
        competitors: list[str] | None = None,
        k: int = 6,
    ) -> PagePromptGenerationResult:
        """Generate k visibility prompts for a single page.

        Makes a single structured LLM call via OpenRouter to produce
        k prompts spanning buyer stages and intent types.

        Args:
            page: Page metadata context.
            brand_name: Brand name for context.
            brand_category: Optional brand category.
            competitors: Optional competitor names.
            k: Number of prompts to generate (4-12, default 6).

        Returns:
            PagePromptGenerationResult with generated prompts.

        Raises:
            RuntimeError: If OpenRouter API key is not configured.
            Exception: If all retries exhausted.
        """
        from core.shared_tools.openrouter_client import (
            _ensure_model_prefix,
            get_async_client,
        )
        from core.shared_tools.cost_tracker import track_llm_cost

        model = _ensure_model_prefix(self._model)
        client = get_async_client()

        system_prompt = _SYSTEM_PROMPT.replace("{k}", str(k))
        user_prompt = _build_user_prompt(
            page, brand_name, brand_category, competitors or [], k,
        )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
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
                response = await client.chat.completions.create(**kwargs)

                choice = response.choices[0]
                usage = response.usage
                raw_content = choice.message.content or "{}"

                track_llm_cost(
                    model=response.model or model,
                    provider="openrouter",
                    pipeline="content_to_prompt",
                    pipeline_step="generate_prompts",
                    prompt_tokens=usage.prompt_tokens if usage else 0,
                    completion_tokens=usage.completion_tokens if usage else 0,
                    company_slug="",
                    call_site="core.daily_tracker.content_to_prompt",
                    source="openrouter",
                )

                prompts = self._parse_response(raw_content)

                token_usage = {
                    "prompt_tokens": usage.prompt_tokens if usage else 0,
                    "completion_tokens": usage.completion_tokens if usage else 0,
                    "total_tokens": usage.total_tokens if usage else 0,
                }

                logger.info(
                    "Content-to-prompt generation completed: %d prompts for '%s' "
                    "(model=%s, tokens=%s)",
                    len(prompts),
                    page.title[:60],
                    model,
                    token_usage.get("total_tokens", 0),
                )

                return PagePromptGenerationResult(
                    inventory_id=page.inventory_id,
                    prompts=prompts,
                    model_used=response.model or model,
                    token_usage=token_usage,
                )

            except Exception as exc:
                last_error = exc
                if attempt < self._max_retries - 1:
                    delay = self._base_delay * (2**attempt) + random.uniform(
                        0, self._base_delay,
                    )
                    logger.warning(
                        "Content-to-prompt generation failed (attempt %d/%d): %s. "
                        "Retrying in %.1fs",
                        attempt + 1,
                        self._max_retries,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)

        raise last_error or RuntimeError("Content-to-prompt generation failed")

    async def generate_prompts_batch(
        self,
        pages: list[PageContext],
        brand_name: str,
        brand_category: str = "",
        competitors: list[str] | None = None,
        k: int = 6,
        concurrency: int = 8,
    ) -> list[PagePromptGenerationResult]:
        """Generate prompts for multiple pages with bounded concurrency.

        Args:
            pages: List of page contexts.
            brand_name: Brand name.
            brand_category: Optional category.
            competitors: Optional competitor names.
            k: Prompts per page.
            concurrency: Max concurrent LLM calls (default 8).

        Returns:
            List of results (one per page). Failed pages return empty prompts.
        """
        sem = asyncio.Semaphore(concurrency)
        results: list[PagePromptGenerationResult] = []

        async def _generate_one(page: PageContext) -> PagePromptGenerationResult:
            async with sem:
                try:
                    return await self.generate_prompts_for_page(
                        page, brand_name, brand_category, competitors, k,
                    )
                except Exception as exc:
                    logger.error(
                        "Failed to generate prompts for page %s: %s",
                        page.inventory_id,
                        exc,
                    )
                    return PagePromptGenerationResult(
                        inventory_id=page.inventory_id,
                        prompts=[],
                        model_used=self._model,
                    )

        tasks = [_generate_one(p) for p in pages]
        results = await asyncio.gather(*tasks)
        return list(results)

    @staticmethod
    def _parse_response(raw: str) -> list[GeneratedPagePrompt]:
        """Parse the LLM JSON response into GeneratedPagePrompt objects.

        Handles both ``{"prompts": [...]}`` and bare ``[...]`` formats.
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Failed to parse content-to-prompt JSON, attempting extraction")
            start = raw.find("[")
            end = raw.rfind("]")
            if start != -1 and end != -1:
                data = json.loads(raw[start : end + 1])
                data = {"prompts": data}
            else:
                logger.error("Cannot extract prompts from response")
                return []

        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("prompts", [])
        else:
            return []

        prompts: list[GeneratedPagePrompt] = []
        valid_stages = {"tofu", "mofu", "bofu"}
        valid_intents = {"informational", "commercial", "navigational", "transactional"}

        for item in items:
            if not isinstance(item, dict):
                continue
            query_text = item.get("query_text", item.get("text", "")).strip()
            if not query_text:
                continue

            stage = item.get("buyer_stage", "").strip().lower()
            intent = item.get("intent_type", "").strip().lower()

            prompts.append(
                GeneratedPagePrompt(
                    query_text=query_text,
                    buyer_stage=stage if stage in valid_stages else "",
                    intent_type=intent if intent in valid_intents else "",
                    is_branded=bool(item.get("is_branded", False)),
                    reasoning=item.get("reasoning", item.get("rationale", "")).strip(),
                )
            )

        return prompts
