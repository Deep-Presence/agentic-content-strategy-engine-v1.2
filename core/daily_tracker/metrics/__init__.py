"""Daily tracker metric calculators — strategy pattern registry.

Each metric is a ``MetricCalculator`` subclass living in its own module.
New metrics are added by creating a new file and registering the class
in ``METRIC_REGISTRY`` — existing calculator code is never modified (OCP).

Registry:
    Import concrete calculators here and add them to ``METRIC_REGISTRY``
    so the analytics engine can discover them automatically.
"""
from __future__ import annotations

from core.daily_tracker.metrics.base import MetricCalculator

# Why: a dict registry keyed by metric name lets the analytics engine
# discover all available calculators without hard-coding imports.
# Concrete calculators are registered here as they are implemented
# by the analytics teammate.
METRIC_REGISTRY: dict[str, type[MetricCalculator]] = {}

__all__ = ["MetricCalculator", "METRIC_REGISTRY"]
