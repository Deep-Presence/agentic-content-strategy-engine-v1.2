"""Trend Calculator — computes time-series data points for visibility metrics.

Groups platform responses by date and computes metric values per date,
producing a list of ``TrendDataPoint`` for charting.  Supports directional
trend detection (up / down / stable) and percentage change.

Why simple slope-based direction: avoids false positives from noisy data.
Two consecutive data points are enough to determine direction; for longer
series the first-minus-last comparison gives a clear macro signal.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

from core.daily_tracker.metrics.base import MetricCalculator
from core.models.daily_tracker import TrendDataPoint


class TrendCalculator(MetricCalculator):
    """Computes time-series trends from grouped platform responses.

    Groups responses by date (truncated to day), computes the specified
    metric per date, and returns ``TrendDataPoint`` objects.

    Input responses must contain:
        - ``mention_analysis.brand_mentioned`` (bool)
        - ``timestamp`` (datetime | str): when the response was generated.

    Kwargs:
        - ``metric`` (str): which metric to trend.  Currently only
          ``"mention_rate"`` is supported (default).

    Returns:
        list[TrendDataPoint] sorted chronologically.
    """

    @property
    def name(self) -> str:
        return "trend"

    async def compute(self, responses: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        """Compute time-series trend data.

        Args:
            responses: List of response dicts with ``timestamp`` and
                ``mention_analysis``.
            **kwargs: Optionally ``metric`` (str, default ``"mention_rate"``).

        Returns:
            {
                "data_points": list[TrendDataPoint],
                "direction": "up" | "down" | "stable",
                "change_pct": float,
            }
        """
        if not responses:
            return {
                "data_points": [],
                "direction": "stable",
                "change_pct": 0.0,
            }

        # Group responses by date
        by_date: dict[date, list[dict[str, Any]]] = defaultdict(list)
        for resp in responses:
            ts = resp.get("timestamp")
            resp_date = _to_date(ts)
            if resp_date is None:
                continue
            by_date[resp_date].append(resp)

        if not by_date:
            return {
                "data_points": [],
                "direction": "stable",
                "change_pct": 0.0,
            }

        # Compute mention rate per date
        data_points: list[TrendDataPoint] = []
        for d in sorted(by_date.keys()):
            day_responses = by_date[d]
            total = len(day_responses)
            mentioned = sum(
                1
                for r in day_responses
                if r.get("mention_analysis", {}).get("brand_mentioned", False)
            )
            rate = mentioned / total if total > 0 else 0.0
            data_points.append(
                TrendDataPoint(
                    date=datetime(d.year, d.month, d.day, tzinfo=timezone.utc),
                    mention_rate=rate,
                    response_count=total,
                    run_id=day_responses[0].get("run_id", ""),
                )
            )

        # Determine direction and change percentage
        direction, change_pct = _compute_direction(data_points)

        return {
            "data_points": data_points,
            "direction": direction,
            "change_pct": change_pct,
        }


def _to_date(ts: Any) -> date | None:
    """Convert a timestamp value to a ``date`` object.

    Handles ``datetime``, ``date``, and ISO-format strings.

    Args:
        ts: Timestamp value to convert.

    Returns:
        ``date`` object or ``None`` if conversion fails.
    """
    if isinstance(ts, datetime):
        return ts.date()
    if isinstance(ts, date):
        return ts
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts).date()
        except (ValueError, TypeError):
            return None
    return None


def _compute_direction(
    data_points: list[TrendDataPoint],
) -> tuple[str, float]:
    """Determine trend direction and percentage change.

    Compares the first and last data points in the series.

    Args:
        data_points: Sorted list of ``TrendDataPoint`` (chronological order).

    Returns:
        Tuple of (direction, change_pct) where direction is
        ``"up"``, ``"down"``, or ``"stable"``.
    """
    if len(data_points) < 2:
        # Why: a single data point means no trend — report "stable" with 0% change.
        return "stable", 0.0

    first_rate = data_points[0].mention_rate
    last_rate = data_points[-1].mention_rate

    if first_rate == 0.0:
        if last_rate == 0.0:
            return "stable", 0.0
        # Why: going from 0 to non-zero is technically infinite change,
        # but we cap it at 100% for display sanity.
        return "up", 100.0

    change_pct = ((last_rate - first_rate) / first_rate) * 100.0

    # Why: threshold of 1% prevents noise from triggering direction changes
    # on near-flat data.
    if change_pct > 1.0:
        return "up", round(change_pct, 2)
    elif change_pct < -1.0:
        return "down", round(change_pct, 2)
    else:
        return "stable", round(change_pct, 2)
