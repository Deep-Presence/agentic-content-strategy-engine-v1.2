"""Tests for compute_structural_score() — composite 0-100 structural score.

Tests cover:
- None/empty signals → 0
- Full signals → high score
- Boolean signal scoring (present vs absent)
- Numeric signal capping (values above benchmark → full weight)
- Numeric signal proportional (values below benchmark → proportional)
- Score range always 0-100
- Individual signal categories contribute expected weights
"""
from __future__ import annotations

import pytest

from core.services.content_performance_service import (
    _STRUCTURAL_SCORE_SIGNALS,
    _TOTAL_WEIGHT,
    compute_structural_score,
)


class TestComputeStructuralScore:
    def test_none_signals_returns_zero(self):
        assert compute_structural_score(None) == 0

    def test_empty_dict_returns_zero(self):
        assert compute_structural_score({}) == 0

    def test_perfect_signals_returns_high_score(self):
        """A page with all signals at or above benchmark should score ~100."""
        signals = {
            # Text Composition
            "word_count": 2500,
            "sentence_count": 150,
            "paragraph_count": 30,
            "avg_paragraph_length": 100,
            "reading_level": 10,
            "self_contained_ratio": 0.9,
            # Structural Elements
            "h2_count": 8,
            "h3_count": 6,
            "list_block_count": 5,
            "table_count": 2,
            "ordered_list_count": 2,
            "code_block_count": 1,
            # Content Patterns (all True)
            "has_faq_section": True,
            "has_definition_opening": True,
            "has_key_takeaways": True,
            "has_comparison_table": True,
            "has_step_by_step": True,
            "has_research_refs": True,
            "has_expert_quotes": True,
            # Factual Density
            "data_point_count": 12,
            "citation_density": 0.008,
            "named_entity_density": 0.03,
        }
        score = compute_structural_score(signals)
        assert score == 100

    def test_minimal_blog_post_scores_moderate(self):
        """A basic blog post with some structure but no advanced patterns."""
        signals = {
            "word_count": 800,        # below 1800 benchmark
            "sentence_count": 50,
            "paragraph_count": 10,
            "h2_count": 3,            # below 6 benchmark
            "h3_count": 0,
            "list_block_count": 1,
            "has_faq_section": False,
            "has_key_takeaways": False,
            "has_step_by_step": False,
            "data_point_count": 2,
        }
        score = compute_structural_score(signals)
        # Should be moderate — has some structure but missing patterns
        assert 15 <= score <= 45

    def test_boolean_signals_full_weight_when_true(self):
        """Boolean signals should contribute their full weight when True."""
        signals_with = {"has_faq_section": True}
        signals_without = {"has_faq_section": False}

        score_with = compute_structural_score(signals_with)
        score_without = compute_structural_score(signals_without)
        assert score_with > score_without

    def test_boolean_false_scores_zero(self):
        signals = {"has_faq_section": False}
        assert compute_structural_score(signals) == 0

    def test_numeric_above_benchmark_caps_at_full(self):
        """Numeric values above benchmark should not score more than weight."""
        # word_count benchmark is 1800, weight is 10
        signals_at = {"word_count": 1800}
        signals_above = {"word_count": 5000}

        score_at = compute_structural_score(signals_at)
        score_above = compute_structural_score(signals_above)
        assert score_at == score_above  # both get full weight

    def test_numeric_below_benchmark_is_proportional(self):
        """Numeric values below benchmark should score proportionally."""
        # word_count benchmark=1800, weight=10
        signals_half = {"word_count": 900}  # 900/1800 = 0.5
        signals_full = {"word_count": 1800}

        score_half = compute_structural_score(signals_half)
        score_full = compute_structural_score(signals_full)
        assert score_half < score_full
        # Should be roughly half the contribution (within rounding)
        # word_count contributes 10/_TOTAL_WEIGHT*100 = 10 points max
        # Half of that = ~5 points

    def test_score_always_in_range(self):
        """Score should always be 0-100 regardless of input."""
        # Negative values
        signals_neg = {"word_count": -100, "h2_count": -5}
        score = compute_structural_score(signals_neg)
        assert 0 <= score <= 100

        # Extreme values
        signals_extreme = {"word_count": 1_000_000, "data_point_count": 99999}
        score = compute_structural_score(signals_extreme)
        assert 0 <= score <= 100

    def test_non_numeric_values_skipped(self):
        """Non-numeric values for numeric fields should be skipped, not crash."""
        signals = {"word_count": "not a number", "has_faq_section": True}
        score = compute_structural_score(signals)
        # Should only count has_faq_section (5 pts out of total)
        assert score > 0

    def test_integer_one_for_boolean_fields(self):
        """Integer 1 should be treated as True for boolean fields."""
        signals = {"has_faq_section": 1}
        score = compute_structural_score(signals)
        assert score > 0

    def test_total_weight_is_positive(self):
        """Verify signal weights sum to a positive value for normalization."""
        assert _TOTAL_WEIGHT > 0
        # Weights are intentionally not forced to 100 — the scoring function
        # normalizes via (score / _TOTAL_WEIGHT * 100) so any positive sum works.

    def test_content_pattern_category_weight(self):
        """Content patterns (7 boolean signals) should contribute ~30 points max."""
        bool_weight = sum(
            s["weight"] for s in _STRUCTURAL_SCORE_SIGNALS if s["type"] == "boolean"
        )
        assert bool_weight == 30

    def test_text_composition_category_weight(self):
        """Text composition signals should contribute ~25 points max."""
        text_fields = {"word_count", "sentence_count", "paragraph_count",
                       "avg_paragraph_length", "reading_level", "self_contained_ratio"}
        text_weight = sum(
            s["weight"] for s in _STRUCTURAL_SCORE_SIGNALS
            if s["field"] in text_fields
        )
        assert text_weight == 25

    def test_structural_elements_category_weight(self):
        """Structural element signals should contribute ~21 points max."""
        struct_fields = {"h2_count", "h3_count", "list_block_count",
                         "table_count", "ordered_list_count", "code_block_count"}
        struct_weight = sum(
            s["weight"] for s in _STRUCTURAL_SCORE_SIGNALS
            if s["field"] in struct_fields
        )
        assert struct_weight == 21

    def test_factual_density_category_weight(self):
        """Factual density signals should contribute ~15 points max."""
        density_fields = {"data_point_count", "citation_density", "named_entity_density"}
        density_weight = sum(
            s["weight"] for s in _STRUCTURAL_SCORE_SIGNALS
            if s["field"] in density_fields
        )
        assert density_weight == 15

    def test_reading_level_benchmark_scoring(self):
        """Reading level at grade ~10 should score near full, grade 5 should score ~half."""
        signals_10 = {"reading_level": 10.0}
        signals_5 = {"reading_level": 5.0}

        score_10 = compute_structural_score(signals_10)
        score_5 = compute_structural_score(signals_5)
        assert score_10 > score_5
