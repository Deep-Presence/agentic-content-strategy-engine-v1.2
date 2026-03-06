"""Tests for AuditConfig __post_init__ validation (T-SA-31).

Verifies that AuditConfig rejects invalid configurations with ValueError.
"""
from __future__ import annotations

import pytest

from core.site_audit.config import AuditConfig, DEFAULT_DIMENSION_WEIGHTS, DEFAULT_GRADE_THRESHOLDS, DEFAULT_SEVERITY_PENALTIES


class TestAuditConfigValidation:
    """Validate __post_init__ checks raise ValueError for invalid configs."""

    def test_valid_default_config(self) -> None:
        """Default config must pass validation."""
        config = AuditConfig()
        assert config.weight_sum() == pytest.approx(1.0, abs=0.01)

    def test_weights_not_summing_to_one(self) -> None:
        bad_weights = dict(DEFAULT_DIMENSION_WEIGHTS)
        bad_weights["crawlability"] = 0.50  # pushes sum over 1.0
        with pytest.raises(ValueError, match="dimension_weights must sum to 1.0"):
            AuditConfig(dimension_weights=bad_weights)

    def test_missing_required_grade(self) -> None:
        bad_grades = {"A": 90.0, "B": 75.0, "C": 60.0}  # missing D
        with pytest.raises(ValueError, match="missing required grade"):
            AuditConfig(grade_thresholds=bad_grades)

    def test_grade_thresholds_not_monotonic(self) -> None:
        bad_grades = {"A": 90.0, "B": 95.0, "C": 60.0, "D": 40.0}  # B > A
        with pytest.raises(ValueError, match="monotonically decreasing"):
            AuditConfig(grade_thresholds=bad_grades)

    def test_title_min_greater_than_max(self) -> None:
        with pytest.raises(ValueError, match="title_min_length"):
            AuditConfig(title_min_length=100, title_max_length=50)

    def test_meta_min_greater_than_max(self) -> None:
        with pytest.raises(ValueError, match="meta_min_length"):
            AuditConfig(meta_min_length=200, meta_max_length=100)

    def test_negative_severity_penalty(self) -> None:
        bad_penalties = dict(DEFAULT_SEVERITY_PENALTIES)
        bad_penalties["medium"] = -1.0
        with pytest.raises(ValueError, match="severity_penalties.*medium.*>= 0"):
            AuditConfig(severity_penalties=bad_penalties)

    def test_aeo_question_heading_ratio_above_one(self) -> None:
        with pytest.raises(ValueError, match="aeo_min_question_heading_ratio"):
            AuditConfig(aeo_min_question_heading_ratio=1.5)

    def test_aeo_question_heading_ratio_negative(self) -> None:
        with pytest.raises(ValueError, match="aeo_min_question_heading_ratio"):
            AuditConfig(aeo_min_question_heading_ratio=-0.1)

    def test_aeo_paragraph_word_count_min_greater_than_max(self) -> None:
        with pytest.raises(ValueError, match="aeo_ideal_paragraph_word_count_min"):
            AuditConfig(
                aeo_ideal_paragraph_word_count_min=100,
                aeo_ideal_paragraph_word_count_max=50,
            )

    def test_boundary_weights_sum_within_tolerance(self) -> None:
        """Weights summing to 0.995 should pass (within 0.01 tolerance)."""
        weights = dict(DEFAULT_DIMENSION_WEIGHTS)
        weights["security"] = 0.045  # sum = 0.995
        config = AuditConfig(dimension_weights=weights)
        assert config is not None
