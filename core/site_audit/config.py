"""Audit configuration dataclass and default values.

``AuditConfig`` is a frozen dataclass so that it can be safely shared across
async tasks without mutation risk.  All numeric thresholds are collected here
so that callers never need to hard-code magic numbers.

Usage::

    from core.site_audit.config import DEFAULT_AUDIT_CONFIG, AuditConfig

    # Use the default (production) config:
    result = await run_site_audit(input_data, config=DEFAULT_AUDIT_CONFIG)

    # Override for testing:
    fast_config = AuditConfig(
        dimension_weights=DEFAULT_DIMENSION_WEIGHTS,
        grade_thresholds=DEFAULT_GRADE_THRESHOLDS,
        severity_penalties=DEFAULT_SEVERITY_PENALTIES,
        page_analysis_concurrency=5,
        request_timeout=5.0,
    )
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Default lookup tables (module-level constants)
# ---------------------------------------------------------------------------

DEFAULT_DIMENSION_WEIGHTS: dict[str, float] = {
    "crawlability": 0.20,
    "performance": 0.10,
    "on_page_seo": 0.15,
    "extractability": 0.20,
    "schema_markup": 0.10,
    "eeat": 0.15,
    "freshness": 0.05,
    "security": 0.05,
}
"""Relative weight of each dimension in the overall score.

Weights must sum to 1.0.  Verified at module import via the assertion below.
"""

assert (
    abs(sum(DEFAULT_DIMENSION_WEIGHTS.values()) - 1.0) < 1e-9
), f"DEFAULT_DIMENSION_WEIGHTS must sum to 1.0, got {sum(DEFAULT_DIMENSION_WEIGHTS.values())}"

DEFAULT_GRADE_THRESHOLDS: dict[str, float] = {
    "A": 90.0,
    "B": 75.0,
    "C": 60.0,
    "D": 40.0,
}
"""Minimum score required for each grade (inclusive).

Grades below D threshold map to F.
"""

DEFAULT_SEVERITY_PENALTIES: dict[str, float] = {
    "critical": 10.0,
    "high": 5.0,
    "medium": 2.0,
    "low": 1.0,
    "info": 0.0,
}
"""Score penalty applied per finding occurrence, by severity level."""


# ---------------------------------------------------------------------------
# Config dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditConfig:
    """Immutable configuration for a single site audit run.

    Attributes:
        dimension_weights: Weight of each dimension in the overall score.
            Values must sum to 1.0.
        grade_thresholds: Minimum score for each letter grade.
            Keys: ``"A"``, ``"B"``, ``"C"``, ``"D"`` (everything below D → F).
        severity_penalties: Score penalty per finding, keyed by severity value.
        title_min_length: Minimum acceptable ``<title>`` character length.
        title_max_length: Maximum acceptable ``<title>`` character length.
        meta_min_length: Minimum acceptable meta-description character length.
        meta_max_length: Maximum acceptable meta-description character length.
        page_analysis_concurrency: Max concurrent page-analysis HTTP requests.
        request_timeout: Per-request HTTP timeout in seconds.
        max_redirects: Maximum redirect hops before marking a URL as broken.
        aeo_min_question_heading_ratio: Minimum fraction of headings that should
            be phrased as questions for a good AEO score.
        aeo_ideal_paragraph_word_count_min: Lower bound of the ideal paragraph
            word count range for AEO.
        aeo_ideal_paragraph_word_count_max: Upper bound of the ideal paragraph
            word count range for AEO.
    """

    dimension_weights: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_DIMENSION_WEIGHTS)
    )
    grade_thresholds: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_GRADE_THRESHOLDS)
    )
    severity_penalties: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_SEVERITY_PENALTIES)
    )
    title_min_length: int = 30
    title_max_length: int = 60
    meta_min_length: int = 120
    meta_max_length: int = 160
    page_analysis_concurrency: int = 30
    request_timeout: float = 15.0
    max_redirects: int = 5
    aeo_min_question_heading_ratio: float = 0.3
    aeo_ideal_paragraph_word_count_min: int = 20
    aeo_ideal_paragraph_word_count_max: int = 80
    aeo_quick_answer_min_words: int = 15
    aeo_quick_answer_max_words: int = 150

    def __post_init__(self) -> None:
        """Validate invariants on a frozen dataclass."""
        # 1. Weights must sum to 1.0
        if abs(sum(self.dimension_weights.values()) - 1.0) >= 0.01:
            raise ValueError(
                f"dimension_weights must sum to 1.0, got {sum(self.dimension_weights.values()):.4f}"
            )
        # 2. Required grades present
        required_grades = {"A", "B", "C", "D"}
        missing = required_grades - set(self.grade_thresholds.keys())
        if missing:
            raise ValueError(f"grade_thresholds missing required grades: {sorted(missing)}")
        # 3. Grade thresholds monotonically decreasing: A >= B >= C >= D
        t = self.grade_thresholds
        if not (t["A"] >= t["B"] >= t["C"] >= t["D"]):
            raise ValueError(
                f"grade_thresholds must be monotonically decreasing: "
                f"A({t['A']}) >= B({t['B']}) >= C({t['C']}) >= D({t['D']})"
            )
        # 4. Title length bounds
        if self.title_min_length > self.title_max_length:
            raise ValueError(
                f"title_min_length ({self.title_min_length}) must be <= "
                f"title_max_length ({self.title_max_length})"
            )
        # 5. Meta description length bounds
        if self.meta_min_length > self.meta_max_length:
            raise ValueError(
                f"meta_min_length ({self.meta_min_length}) must be <= "
                f"meta_max_length ({self.meta_max_length})"
            )
        # 6. All severity penalties >= 0
        for sev, pen in self.severity_penalties.items():
            if pen < 0:
                raise ValueError(
                    f"severity_penalties['{sev}'] must be >= 0, got {pen}"
                )
        # 7. AEO question heading ratio in [0, 1]
        if not (0.0 <= self.aeo_min_question_heading_ratio <= 1.0):
            raise ValueError(
                f"aeo_min_question_heading_ratio must be in [0.0, 1.0], "
                f"got {self.aeo_min_question_heading_ratio}"
            )
        # 8. AEO paragraph word count bounds
        if self.aeo_ideal_paragraph_word_count_min > self.aeo_ideal_paragraph_word_count_max:
            raise ValueError(
                f"aeo_ideal_paragraph_word_count_min ({self.aeo_ideal_paragraph_word_count_min}) "
                f"must be <= aeo_ideal_paragraph_word_count_max "
                f"({self.aeo_ideal_paragraph_word_count_max})"
            )

    def weight_sum(self) -> float:
        """Return the sum of dimension weights (should be 1.0).

        Useful for validation in tests.
        """
        return sum(self.dimension_weights.values())

    def grade_for_score(self, score: float) -> str:
        """Derive the letter grade for a given overall score.

        Args:
            score: Numeric score in the range 0–100.

        Returns:
            A letter grade string: ``"A"``, ``"B"``, ``"C"``, ``"D"``, or ``"F"``.
        """
        for grade in ("A", "B", "C", "D"):
            if score >= self.grade_thresholds.get(grade, 0.0):
                return grade
        return "F"

    def penalty_for(self, severity: str) -> float:
        """Return the score penalty for a given severity string.

        Args:
            severity: Severity value, e.g. ``"critical"``.

        Returns:
            Float penalty (0.0 if severity not recognised).
        """
        return self.severity_penalties.get(severity, 0.0)


# ---------------------------------------------------------------------------
# Default config singleton
# ---------------------------------------------------------------------------

DEFAULT_AUDIT_CONFIG: AuditConfig = AuditConfig()
"""Production-ready default config — import and use directly."""
