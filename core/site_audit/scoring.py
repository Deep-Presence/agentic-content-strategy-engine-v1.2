"""Weighted dimension scoring for the site audit pipeline.

Takes per-page findings and aggregates them into per-dimension scores (0–100),
then computes a weighted overall score and letter grade.

Scoring algorithm per dimension:
    1. Start at 100.
    2. For each finding in that dimension, subtract ``penalty_for(severity)``.
    3. Clamp to [0, 100].
    4. Multiply by the dimension weight to get the weighted score.

Overall score = sum of all weighted scores (0–100).

Grade = ``config.grade_for_score(overall_score)``.

All functions are pure — no I/O, no network calls.
"""
from __future__ import annotations

from core.models.site_audit import (
    AuditCheckSeverity,
    AuditDimension,
    AuditFinding,
    DimensionScore,
)
from core.site_audit.config import AuditConfig, DEFAULT_AUDIT_CONFIG


def compute_dimension_score(
    dimension: AuditDimension,
    findings: list[AuditFinding],
    config: AuditConfig = DEFAULT_AUDIT_CONFIG,
) -> DimensionScore:
    """Compute the score for a single audit dimension.

    Starts at 100 and deducts ``config.penalty_for(severity)`` for each
    finding that belongs to *dimension*.  The raw score is clamped to [0, 100].

    Args:
        dimension: The dimension to score.
        findings: All findings (will be filtered to this dimension).
        config: Audit configuration with penalties and weights.

    Returns:
        A :class:`DimensionScore` with raw score, weight, and severity counts.
    """
    dim_findings = [f for f in findings if f.dimension == dimension]
    weight = config.dimension_weights.get(dimension.value, 0.0)

    # Count by severity
    critical_count = sum(1 for f in dim_findings if f.severity == AuditCheckSeverity.critical)
    high_count = sum(1 for f in dim_findings if f.severity == AuditCheckSeverity.high)
    medium_count = sum(1 for f in dim_findings if f.severity == AuditCheckSeverity.medium)
    low_count = sum(1 for f in dim_findings if f.severity == AuditCheckSeverity.low)
    info_count = sum(1 for f in dim_findings if f.severity == AuditCheckSeverity.info)

    # Compute penalty
    total_penalty = sum(config.penalty_for(f.severity.value) for f in dim_findings)
    raw_score = max(0.0, min(100.0, 100.0 - total_penalty))

    return DimensionScore(
        dimension=dimension,
        score=raw_score,
        weight=weight,
        weighted_score=round(raw_score * weight, 2),
        finding_count=len(dim_findings),
        critical_count=critical_count,
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        info_count=info_count,
    )


def compute_all_dimension_scores(
    findings: list[AuditFinding],
    config: AuditConfig = DEFAULT_AUDIT_CONFIG,
) -> list[DimensionScore]:
    """Compute scores for all eight audit dimensions.

    Args:
        findings: All findings across all pages and dimensions.
        config: Audit configuration.

    Returns:
        List of :class:`DimensionScore`, one per :class:`AuditDimension`.
    """
    return [
        compute_dimension_score(dim, findings, config)
        for dim in AuditDimension
    ]


def compute_overall_score(
    dimension_scores: list[DimensionScore],
) -> float:
    """Compute the weighted overall score from dimension scores.

    Args:
        dimension_scores: List of per-dimension scores (from
            :func:`compute_all_dimension_scores`).

    Returns:
        Float in [0, 100] — the weighted sum of all dimension scores.
    """
    total = sum(ds.weighted_score for ds in dimension_scores)
    return round(max(0.0, min(100.0, total)), 2)


def compute_grade(
    overall_score: float,
    config: AuditConfig = DEFAULT_AUDIT_CONFIG,
) -> str:
    """Derive the letter grade from an overall score.

    Args:
        overall_score: Numeric score 0–100.
        config: Audit configuration with grade thresholds.

    Returns:
        Letter grade string: ``"A"``, ``"B"``, ``"C"``, ``"D"``, or ``"F"``.
    """
    return config.grade_for_score(overall_score)
