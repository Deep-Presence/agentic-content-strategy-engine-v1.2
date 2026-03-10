"""Share of Voice Calculator — computes brand's mention share vs competitors.

SOV = brand_mentions / (brand_mentions + sum(competitor_mentions)).
All SOV values should sum to approximately 1.0 (the remainder is
``unattributed`` — responses where no tracked entity was mentioned).

Why SOV normalized to sum to 1.0: enables percentage display in dashboards
and fair comparison across time periods with different response counts.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from core.daily_tracker.metrics.base import MetricCalculator


class ShareOfVoiceCalculator(MetricCalculator):
    """Computes share of voice: brand mentions relative to competitor mentions.

    Input responses must contain:
        - ``mention_analysis.brand_mentioned`` (bool)
        - ``mention_analysis.brand_mention_count`` (int)
        - ``mention_analysis.competitor_mentions`` (dict[str, int])

    Kwargs:
        - ``brand`` (str): brand name (for labeling output).
        - ``competitors`` (list[str]): competitor names to track.

    Returns:
        dict with ``brand_sov`` (float), ``competitor_sov`` (dict[str, float]),
        ``total_mentions`` (int).
    """

    @property
    def name(self) -> str:
        return "share_of_voice"

    async def compute(self, responses: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        """Compute share of voice from platform responses.

        Args:
            responses: List of response dicts with mention analysis data.
            **kwargs: Must include ``brand`` (str).  Optionally
                ``competitors`` (list[str]) to restrict tracked competitor names.

        Returns:
            {
                "brand_sov": float,
                "competitor_sov": {"CompA": float, ...},
                "total_mentions": int,
            }
        """
        brand_name: str = kwargs.get("brand", "brand")
        tracked_competitors: list[str] | None = kwargs.get("competitors")

        brand_mentions = 0
        competitor_mention_counts: dict[str, int] = defaultdict(int)

        for resp in responses:
            analysis = resp.get("mention_analysis", {})

            # Brand mentions
            brand_count = analysis.get("brand_mention_count", 0)
            if brand_count == 0 and analysis.get("brand_mentioned", False):
                # Why: fallback to 1 when brand_mentioned=True but count is 0
                # — older data may not have brand_mention_count.
                brand_count = 1
            brand_mentions += brand_count

            # Competitor mentions
            comp_mentions = analysis.get("competitor_mentions", {})
            for comp_name, count in comp_mentions.items():
                if tracked_competitors is not None and comp_name not in tracked_competitors:
                    continue
                # Why: count can be bool (True/False) in legacy data,
                # so coerce to int for safety.
                if isinstance(count, bool):
                    count = 1 if count else 0
                competitor_mention_counts[comp_name] += count

        total_competitor = sum(competitor_mention_counts.values())
        total_mentions = brand_mentions + total_competitor

        if total_mentions == 0:
            # Why: no mentions at all — SOV is 0 for everyone rather than
            # dividing equally, because there is truly no visibility signal.
            result: dict[str, Any] = {
                "brand_sov": 0.0,
                "competitor_sov": {c: 0.0 for c in (tracked_competitors or [])},
                "total_mentions": 0,
            }
            return result

        # Why: SOV = mentions / total_mentions — normalizes to [0, 1].
        brand_sov = brand_mentions / total_mentions

        competitor_sov: dict[str, float] = {}
        for comp_name, count in competitor_mention_counts.items():
            competitor_sov[comp_name] = count / total_mentions

        return {
            "brand_sov": brand_sov,
            "competitor_sov": competitor_sov,
            "total_mentions": total_mentions,
        }
