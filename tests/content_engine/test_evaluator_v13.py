"""Tests for v1.3 evaluator additions — dual feedback routing + targeted revision.

Tests classify_feedback() and _get_targeted_revision_plan() from loop.py.
No mocks needed — pure function tests with DimensionResult inputs.
"""
from __future__ import annotations

import pytest

from core.content_engine.evaluator.loop import classify_feedback, _get_targeted_revision_plan
from core.models.content_generation import DimensionResult


def _dim(dimension: str, passed: bool = True, score: float = 0.8) -> DimensionResult:
    """Shorthand DimensionResult factory."""
    return DimensionResult(dimension=dimension, passed=passed, score=score, feedback="")


# ═══════════════════════════════════════════════════════════════════════
# classify_feedback
# ═══════════════════════════════════════════════════════════════════════


class TestClassifyFeedback:
    """Tests for classify_feedback()."""

    def test_all_passed_returns_pass(self):
        dims = [_dim("structural"), _dim("semantic"), _dim("style"), _dim("factual")]
        assert classify_feedback(dims) == "pass"

    def test_single_non_semantic_fail_returns_section_level(self):
        dims = [
            _dim("structural", passed=False, score=0.4),
            _dim("semantic"),
            _dim("style"),
            _dim("factual"),
        ]
        assert classify_feedback(dims) == "section_level"

    def test_style_fail_returns_section_level(self):
        dims = [
            _dim("structural"),
            _dim("semantic"),
            _dim("style", passed=False, score=0.5),
            _dim("factual"),
        ]
        assert classify_feedback(dims) == "section_level"

    def test_semantic_below_half_returns_major_change(self):
        dims = [
            _dim("structural"),
            _dim("semantic", passed=False, score=0.3),
            _dim("style"),
            _dim("factual"),
        ]
        assert classify_feedback(dims) == "major_change"

    def test_semantic_at_half_returns_section_level(self):
        dims = [
            _dim("structural"),
            _dim("semantic", passed=False, score=0.5),
            _dim("style"),
            _dim("factual"),
        ]
        assert classify_feedback(dims) == "section_level"

    def test_eeat_fail_returns_section_level(self):
        dims = [
            _dim("structural"),
            _dim("semantic"),
            _dim("style"),
            _dim("factual"),
            _dim("eeat", passed=False, score=0.4),
        ]
        assert classify_feedback(dims) == "section_level"

    def test_multiple_non_semantic_fails_returns_section_level(self):
        dims = [
            _dim("structural", passed=False),
            _dim("semantic", score=0.6),
            _dim("style", passed=False),
            _dim("factual"),
        ]
        assert classify_feedback(dims) == "section_level"


# ═══════════════════════════════════════════════════════════════════════
# _get_targeted_revision_plan
# ═══════════════════════════════════════════════════════════════════════


class TestGetTargetedRevisionPlan:
    """Tests for _get_targeted_revision_plan()."""

    def test_all_passed_returns_empty(self):
        dims = [_dim("structural"), _dim("semantic"), _dim("style"), _dim("factual")]
        assert _get_targeted_revision_plan(dims) == []

    def test_structural_fail_returns_drafter_fact_checker(self):
        dims = [
            _dim("structural", passed=False),
            _dim("semantic"),
            _dim("style"),
            _dim("factual"),
        ]
        plan = _get_targeted_revision_plan(dims)
        assert plan == ["drafter", "fact_checker"]

    def test_style_fail_returns_drafter_fact_checker(self):
        dims = [
            _dim("structural"),
            _dim("semantic"),
            _dim("style", passed=False),
            _dim("factual"),
        ]
        plan = _get_targeted_revision_plan(dims)
        assert plan == ["drafter", "fact_checker"]

    def test_factual_fail_returns_fact_checker_only(self):
        dims = [
            _dim("structural"),
            _dim("semantic"),
            _dim("style"),
            _dim("factual", passed=False),
        ]
        plan = _get_targeted_revision_plan(dims)
        assert plan == ["fact_checker"]

    def test_semantic_fail_returns_drafter_fact_checker(self):
        dims = [
            _dim("structural"),
            _dim("semantic", passed=False),
            _dim("style"),
            _dim("factual"),
        ]
        plan = _get_targeted_revision_plan(dims)
        assert plan == ["drafter", "fact_checker"]

    def test_eeat_fail_returns_drafter_fact_checker(self):
        dims = [
            _dim("structural"),
            _dim("semantic"),
            _dim("style"),
            _dim("factual"),
            _dim("eeat", passed=False),
        ]
        plan = _get_targeted_revision_plan(dims)
        assert plan == ["drafter", "fact_checker"]

    def test_multiple_fails_deduplicated(self):
        dims = [
            _dim("structural", passed=False),
            _dim("style", passed=False),
            _dim("factual", passed=False),
        ]
        plan = _get_targeted_revision_plan(dims)
        # Style/structural fail triggers drafter + fact_checker
        # Factual fail triggers fact_checker (already included)
        assert plan == ["drafter", "fact_checker"]
