"""MetricCalculator ABC — strategy pattern base for daily tracker metrics.

Every metric (mention rate, share of voice, citation rate, trend) is a
concrete subclass of ``MetricCalculator``.  The analytics engine iterates
over all registered calculators and calls ``compute()`` on each.

Design:
    - ``name`` property returns a unique metric identifier (e.g. "mention_rate").
    - ``compute()`` receives a list of ``PlatformResponse`` dicts and arbitrary
      kwargs (brand name, competitor list, date range, etc.) and returns the
      computed metric value.
    - All computation is 100% deterministic — no LLM calls.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MetricCalculator(ABC):
    """Strategy pattern base class for all daily tracker metrics.

    Subclasses implement one metric each.  The analytics engine discovers
    them via ``METRIC_REGISTRY`` in ``metrics/__init__.py``.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this metric (e.g. ``"mention_rate"``)."""
        ...

    @abstractmethod
    async def compute(self, responses: list[dict[str, Any]], **kwargs: Any) -> Any:
        """Compute the metric from platform responses.

        Args:
            responses: List of response dicts, each containing at minimum
                ``prompt_id``, ``engine``, ``response_text``, and
                ``mention_analysis`` (a ``MentionAnalysis`` dict).
            **kwargs: Additional context such as ``brand``, ``competitors``,
                ``date_range``, etc.

        Returns:
            Metric-specific result (float, dict, list, etc.).
        """
        ...
