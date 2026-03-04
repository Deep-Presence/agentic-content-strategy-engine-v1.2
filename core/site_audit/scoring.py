"""Weighted dimension scoring for the site audit pipeline.

Takes per-page findings and aggregates them into per-dimension scores (0–100),
then computes a weighted overall score and letter grade.

Scoring algorithm per dimension (page-normalised):
    1. Separate site-level findings (``url=""``) from page-level findings.
    2. Site-level: sum penalties directly (applied once).
    3. Page-level: group by URL, dedup by ``finding_type`` (max severity per
       type per page), compute per-page penalty, then average across ALL
       crawled pages (unaffected pages contribute 0).
    4. total_penalty = site_penalty + mean(page_penalties).
    5. raw_score = clamp(100 - total_penalty, 0, 100).
    6. weighted_score = raw_score * dimension_weight.

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
    pages_crawled: int = 1,
) -> DimensionScore:
    """Compute the score for a single audit dimension.

    Uses page-normalised scoring so that large and small sites with the
    same issue-rate receive comparable scores.

    Args:
        dimension: The dimension to score.
        findings: All findings (will be filtered to this dimension).
        config: Audit configuration with penalties and weights.
        pages_crawled: Total pages crawled in this audit run.  Used to
            normalise page-level penalty accumulation.

    Returns:
        A :class:`DimensionScore` with raw score, weight, and severity counts.
    """
    dim_findings = [f for f in findings if f.dimension == dimension]
    weight = config.dimension_weights.get(dimension.value, 0.0)

    # Count by severity (raw counts for reporting)
    critical_count = sum(1 for f in dim_findings if f.severity == AuditCheckSeverity.critical)
    high_count = sum(1 for f in dim_findings if f.severity == AuditCheckSeverity.high)
    medium_count = sum(1 for f in dim_findings if f.severity == AuditCheckSeverity.medium)
    low_count = sum(1 for f in dim_findings if f.severity == AuditCheckSeverity.low)
    info_count = sum(1 for f in dim_findings if f.severity == AuditCheckSeverity.info)

    if not dim_findings:
        return DimensionScore(
            dimension=dimension,
            score=100.0,
            weight=weight,
            weighted_score=round(100.0 * weight, 2),
            finding_count=0,
            critical_count=0,
            high_count=0,
            medium_count=0,
            low_count=0,
            info_count=0,
        )

    # Separate site-level findings (url="") from page-level
    site_findings = [f for f in dim_findings if not f.url]
    page_findings = [f for f in dim_findings if f.url]

    # --- Site-level penalty (applied once, not per-page) ---
    site_penalty = sum(config.penalty_for(f.severity.value) for f in site_findings)

    # --- Page-level penalty: mean of per-page penalties ---
    page_penalty = 0.0
    effective_pages = max(1, pages_crawled)

    if page_findings:
        # Group by page URL
        by_page: dict[str, list[AuditFinding]] = {}
        for f in page_findings:
            by_page.setdefault(f.url, []).append(f)

        # Per-page: dedup by finding_type, take max severity per type
        page_penalties: list[float] = []
        for _url, url_findings in by_page.items():
            by_type: dict[str, float] = {}
            for f in url_findings:
                penalty = config.penalty_for(f.severity.value)
                by_type[f.finding_type] = max(by_type.get(f.finding_type, 0.0), penalty)
            page_penalties.append(sum(by_type.values()))

        # Mean across ALL crawled pages (unaffected pages contribute 0)
        page_penalty = sum(page_penalties) / effective_pages

    total_penalty = site_penalty + page_penalty
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
    pages_crawled: int = 1,
) -> list[DimensionScore]:
    """Compute scores for all eight audit dimensions.

    Args:
        findings: All findings across all pages and dimensions.
        config: Audit configuration.
        pages_crawled: Total pages crawled in this audit run.

    Returns:
        List of :class:`DimensionScore`, one per :class:`AuditDimension`.
    """
    return [
        compute_dimension_score(dim, findings, config, pages_crawled)
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
