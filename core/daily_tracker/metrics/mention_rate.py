"""Mention Rate Calculator — computes brand mention rate from daily run responses.

Computes the fraction of platform responses where the brand was mentioned.
Supports overall rate and per-engine breakdown.  All computation is 100%
deterministic — no LLM calls.

Why regex/string mention detection over LLM:
    Deterministic, free, sub-ms latency, reproducible results.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from core.daily_tracker.metrics.base import MetricCalculator


class MentionRateCalculator(MetricCalculator):
    """Computes mention rate: fraction of responses where the brand was mentioned.

    Variants:
        - Overall: across all engines and prompts.
        - By engine: per-engine breakdown.

    Input responses must contain at minimum:
        - ``engine`` (str): platform name
        - ``mention_analysis`` (dict): with ``brand_mentioned`` (bool)

    Returns:
        dict with ``overall`` (float 0-1) and ``by_engine`` (dict[str, float]).
    """

    @property
    def name(self) -> str:
        return "mention_rate"

    async def compute(self, responses: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        """Compute mention rate from platform responses.

        Args:
            responses: List of response dicts with ``engine`` and
                ``mention_analysis.brand_mentioned``.
            **kwargs: Unused — reserved for future filtering.

        Returns:
            {"overall": float, "by_engine": {"openai": float, ...}}
        """
        if not responses:
            # Why: 0 responses means 0.0 rate — not an error, just no data.
            return {"overall": 0.0, "by_engine": {}}

        total = 0
        mentioned = 0
        engine_total: dict[str, int] = defaultdict(int)
        engine_mentioned: dict[str, int] = defaultdict(int)

        for resp in responses:
            engine = resp.get("engine", "unknown")
            analysis = resp.get("mention_analysis", {})
            brand_mentioned = analysis.get("brand_mentioned", False)

            total += 1
            engine_total[engine] += 1
            if brand_mentioned:
                mentioned += 1
                engine_mentioned[engine] += 1

        # Why: guard against division by zero — 0/0 = 0.0 by convention.
        overall = mentioned / total if total > 0 else 0.0

        by_engine: dict[str, float] = {}
        for eng, eng_total in engine_total.items():
            eng_ment = engine_mentioned.get(eng, 0)
            by_engine[eng] = eng_ment / eng_total if eng_total > 0 else 0.0

        return {"overall": overall, "by_engine": by_engine}
