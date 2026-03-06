"""Tests for core/site_audit/config.py.

Covers:
- Weight sum constraint (must equal 1.0)
- Grade threshold ordering and correctness
- Severity penalty values
- grade_for_score() helper (boundary values + ordering)
- penalty_for() helper (known + unknown severities)
- AuditConfig is frozen (immutable)
- DEFAULT_AUDIT_CONFIG usability
- Custom config construction
- Config independence (two instances are independent)
"""
from __future__ import annotations

import pytest

from core.site_audit.config import (
    DEFAULT_AUDIT_CONFIG,
    DEFAULT_DIMENSION_WEIGHTS,
    DEFAULT_GRADE_THRESHOLDS,
    DEFAULT_SEVERITY_PENALTIES,
    AuditConfig,
)


# ---------------------------------------------------------------------------
# Module-level constant tests
# ---------------------------------------------------------------------------


class TestDefaultDimensionWeights:
    def test_sum_exactly_one(self) -> None:
        total = sum(DEFAULT_DIMENSION_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"

    def test_all_eight_dimensions_present(self) -> None:
        expected = {
            "crawlability",
            "performance",
            "on_page_seo",
            "extractability",
            "schema_markup",
            "eeat",
            "freshness",
            "security",
        }
        assert set(DEFAULT_DIMENSION_WEIGHTS.keys()) == expected

    def test_all_weights_positive(self) -> None:
        for dim, weight in DEFAULT_DIMENSION_WEIGHTS.items():
            assert weight > 0, f"Weight for {dim} must be positive"

    def test_weight_values(self) -> None:
        assert DEFAULT_DIMENSION_WEIGHTS["crawlability"] == pytest.approx(0.20)
        assert DEFAULT_DIMENSION_WEIGHTS["performance"] == pytest.approx(0.10)
        assert DEFAULT_DIMENSION_WEIGHTS["on_page_seo"] == pytest.approx(0.15)
        assert DEFAULT_DIMENSION_WEIGHTS["extractability"] == pytest.approx(0.20)
        assert DEFAULT_DIMENSION_WEIGHTS["schema_markup"] == pytest.approx(0.10)
        assert DEFAULT_DIMENSION_WEIGHTS["eeat"] == pytest.approx(0.15)
        assert DEFAULT_DIMENSION_WEIGHTS["freshness"] == pytest.approx(0.05)
        assert DEFAULT_DIMENSION_WEIGHTS["security"] == pytest.approx(0.05)


class TestDefaultGradeThresholds:
    def test_all_grades_present(self) -> None:
        assert {"A", "B", "C", "D"} == set(DEFAULT_GRADE_THRESHOLDS.keys())

    def test_ordering(self) -> None:
        """A threshold must be highest, followed by B, C, D."""
        assert DEFAULT_GRADE_THRESHOLDS["A"] > DEFAULT_GRADE_THRESHOLDS["B"]
        assert DEFAULT_GRADE_THRESHOLDS["B"] > DEFAULT_GRADE_THRESHOLDS["C"]
        assert DEFAULT_GRADE_THRESHOLDS["C"] > DEFAULT_GRADE_THRESHOLDS["D"]

    def test_values(self) -> None:
        assert DEFAULT_GRADE_THRESHOLDS["A"] == pytest.approx(90.0)
        assert DEFAULT_GRADE_THRESHOLDS["B"] == pytest.approx(75.0)
        assert DEFAULT_GRADE_THRESHOLDS["C"] == pytest.approx(60.0)
        assert DEFAULT_GRADE_THRESHOLDS["D"] == pytest.approx(40.0)


class TestDefaultSeverityPenalties:
    def test_all_severities_present(self) -> None:
        assert {"critical", "high", "medium", "low", "info"} == set(
            DEFAULT_SEVERITY_PENALTIES.keys()
        )

    def test_values(self) -> None:
        assert DEFAULT_SEVERITY_PENALTIES["critical"] == pytest.approx(10.0)
        assert DEFAULT_SEVERITY_PENALTIES["high"] == pytest.approx(5.0)
        assert DEFAULT_SEVERITY_PENALTIES["medium"] == pytest.approx(2.0)
        assert DEFAULT_SEVERITY_PENALTIES["low"] == pytest.approx(1.0)
        assert DEFAULT_SEVERITY_PENALTIES["info"] == pytest.approx(0.0)

    def test_ordering(self) -> None:
        p = DEFAULT_SEVERITY_PENALTIES
        assert p["critical"] > p["high"] > p["medium"] > p["low"] >= p["info"]


# ---------------------------------------------------------------------------
# AuditConfig tests
# ---------------------------------------------------------------------------


class TestAuditConfig:
    def test_default_construction(self) -> None:
        cfg = AuditConfig()
        assert abs(cfg.weight_sum() - 1.0) < 1e-9

    def test_is_frozen(self) -> None:
        cfg = AuditConfig()
        with pytest.raises((AttributeError, TypeError)):
            cfg.title_min_length = 99  # type: ignore[misc]

    def test_default_scalar_values(self) -> None:
        cfg = AuditConfig()
        assert cfg.title_min_length == 30
        assert cfg.title_max_length == 60
        assert cfg.meta_min_length == 120
        assert cfg.meta_max_length == 160
        assert cfg.page_analysis_concurrency == 30
        assert cfg.request_timeout == pytest.approx(15.0)
        assert cfg.max_redirects == 5
        assert cfg.aeo_min_question_heading_ratio == pytest.approx(0.3)
        assert cfg.aeo_ideal_paragraph_word_count_min == 20
        assert cfg.aeo_ideal_paragraph_word_count_max == 80

    def test_weight_sum_helper(self) -> None:
        cfg = AuditConfig()
        assert cfg.weight_sum() == pytest.approx(1.0)

    def test_custom_weights_sum(self) -> None:
        custom_weights = {
            "crawlability": 0.125,
            "performance": 0.125,
            "on_page_seo": 0.125,
            "extractability": 0.125,
            "schema_markup": 0.125,
            "eeat": 0.125,
            "freshness": 0.125,
            "security": 0.125,
        }
        cfg = AuditConfig(dimension_weights=custom_weights)
        assert cfg.weight_sum() == pytest.approx(1.0)

    def test_two_instances_independent(self) -> None:
        cfg1 = AuditConfig()
        cfg2 = AuditConfig()
        # They are equal but distinct objects
        assert cfg1.dimension_weights == cfg2.dimension_weights
        # Mutating one's dict (after casting away frozen) shouldn't affect the other
        # Actually dataclass(frozen=True) prevents direct mutation — just verify
        assert cfg1 is not cfg2

    def test_dict_independence(self) -> None:
        """Config instances should not share underlying dict objects."""
        cfg1 = AuditConfig()
        cfg2 = AuditConfig()
        assert cfg1.dimension_weights is not cfg2.dimension_weights


# ---------------------------------------------------------------------------
# grade_for_score() tests
# ---------------------------------------------------------------------------


class TestGradeForScore:
    def setup_method(self) -> None:
        self.cfg = AuditConfig()

    def test_perfect_score_is_a(self) -> None:
        assert self.cfg.grade_for_score(100.0) == "A"

    def test_exactly_90_is_a(self) -> None:
        assert self.cfg.grade_for_score(90.0) == "A"

    def test_just_below_90_is_b(self) -> None:
        assert self.cfg.grade_for_score(89.9) == "B"

    def test_exactly_75_is_b(self) -> None:
        assert self.cfg.grade_for_score(75.0) == "B"

    def test_just_below_75_is_c(self) -> None:
        assert self.cfg.grade_for_score(74.9) == "C"

    def test_exactly_60_is_c(self) -> None:
        assert self.cfg.grade_for_score(60.0) == "C"

    def test_just_below_60_is_d(self) -> None:
        assert self.cfg.grade_for_score(59.9) == "D"

    def test_exactly_40_is_d(self) -> None:
        assert self.cfg.grade_for_score(40.0) == "D"

    def test_just_below_40_is_f(self) -> None:
        assert self.cfg.grade_for_score(39.9) == "F"

    def test_zero_score_is_f(self) -> None:
        assert self.cfg.grade_for_score(0.0) == "F"

    def test_negative_score_is_f(self) -> None:
        """Negative scores (shouldn't occur) fall back to F gracefully."""
        assert self.cfg.grade_for_score(-5.0) == "F"

    def test_boundary_values(self) -> None:
        """Test every exact threshold boundary."""
        cfg = self.cfg
        assert cfg.grade_for_score(cfg.grade_thresholds["A"]) == "A"
        assert cfg.grade_for_score(cfg.grade_thresholds["B"]) == "B"
        assert cfg.grade_for_score(cfg.grade_thresholds["C"]) == "C"
        assert cfg.grade_for_score(cfg.grade_thresholds["D"]) == "D"

    def test_custom_thresholds(self) -> None:
        custom = AuditConfig(
            grade_thresholds={"A": 95.0, "B": 80.0, "C": 65.0, "D": 50.0}
        )
        assert custom.grade_for_score(95.0) == "A"
        assert custom.grade_for_score(94.9) == "B"
        assert custom.grade_for_score(80.0) == "B"
        assert custom.grade_for_score(50.0) == "D"
        assert custom.grade_for_score(49.9) == "F"


# ---------------------------------------------------------------------------
# penalty_for() tests
# ---------------------------------------------------------------------------


class TestPenaltyFor:
    def setup_method(self) -> None:
        self.cfg = AuditConfig()

    def test_critical_penalty(self) -> None:
        assert self.cfg.penalty_for("critical") == pytest.approx(10.0)

    def test_high_penalty(self) -> None:
        assert self.cfg.penalty_for("high") == pytest.approx(5.0)

    def test_medium_penalty(self) -> None:
        assert self.cfg.penalty_for("medium") == pytest.approx(2.0)

    def test_low_penalty(self) -> None:
        assert self.cfg.penalty_for("low") == pytest.approx(1.0)

    def test_info_penalty(self) -> None:
        assert self.cfg.penalty_for("info") == pytest.approx(0.0)

    def test_unknown_severity_returns_zero(self) -> None:
        """Unrecognised severities should return 0.0, not raise."""
        assert self.cfg.penalty_for("unknown_level") == pytest.approx(0.0)
        assert self.cfg.penalty_for("") == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# DEFAULT_AUDIT_CONFIG singleton tests
# ---------------------------------------------------------------------------


class TestDefaultAuditConfig:
    def test_is_audit_config_instance(self) -> None:
        assert isinstance(DEFAULT_AUDIT_CONFIG, AuditConfig)

    def test_weight_sum(self) -> None:
        assert DEFAULT_AUDIT_CONFIG.weight_sum() == pytest.approx(1.0)

    def test_grade_for_score_works(self) -> None:
        assert DEFAULT_AUDIT_CONFIG.grade_for_score(91.0) == "A"
        assert DEFAULT_AUDIT_CONFIG.grade_for_score(0.0) == "F"

    def test_is_frozen(self) -> None:
        with pytest.raises((AttributeError, TypeError)):
            DEFAULT_AUDIT_CONFIG.title_min_length = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Pipeline smoke tests (replaced skeleton NotImplementedError tests)
# ---------------------------------------------------------------------------


class TestPipelineSignature:
    """Verify the pipeline function signature and basic behaviour."""

    def test_run_site_audit_is_importable(self) -> None:
        from core.site_audit.pipeline import run_site_audit

        assert callable(run_site_audit)

    def test_run_site_audit_accepts_skip_steps(self) -> None:
        """Verify the signature accepts skip_steps parameter."""
        import inspect
        from core.site_audit.pipeline import run_site_audit

        sig = inspect.signature(run_site_audit)
        assert "skip_steps" in sig.parameters
        assert "config" in sig.parameters
        assert "on_progress" in sig.parameters
