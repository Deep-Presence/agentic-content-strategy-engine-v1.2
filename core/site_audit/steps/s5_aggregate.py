"""Step 5 — Aggregate per-page results into site-level audit scores.

Collects all findings from all pages, computes per-dimension scores using
the scoring module, and populates the site-level summary fields on
:class:`SiteAuditResult`.

This step is pure CPU — no I/O, no network calls.

Public API::

    result = aggregate_results(
        page_results=page_results,
        ai_bot_access=ai_bot_access,
        sitemap_health=sitemap_health,
        config=config,
    )
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from core.models.site_audit import (
    AIBotAccessResult,
    AuditDimension,
    AuditFinding,
    PageAuditResult,
    SiteAuditResult,
    SitemapHealthResult,
)
from core.site_audit.config import AuditConfig, DEFAULT_AUDIT_CONFIG
from core.site_audit.scoring import (
    compute_all_dimension_scores,
    compute_grade,
    compute_overall_score,
)


def _collect_all_findings(page_results: list[PageAuditResult]) -> list[AuditFinding]:
    """Flatten all findings from all pages into a single list.

    Args:
        page_results: Per-page audit results from s2/s3/s4.

    Returns:
        Flat list of all :class:`AuditFinding` objects.
    """
    all_findings: list[AuditFinding] = []
    for page in page_results:
        all_findings.extend(page.findings)
    return all_findings


def _compute_top_findings(
    findings: list[AuditFinding],
    max_count: int = 10,
) -> list[dict[str, Any]]:
    """Select the most impactful findings for the executive summary.

    Findings are ranked by severity (critical > high > medium > low > info),
    then deduplicated by finding_type (keeping the first occurrence).

    Args:
        findings: All findings across all pages.
        max_count: Maximum number of top findings to return.

    Returns:
        List of dicts with keys: finding_type, dimension, severity, message,
        recommendation, count (how many pages have this finding).
    """
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    sorted_findings = sorted(
        findings,
        key=lambda f: severity_order.get(f.severity.value, 5),
    )

    # Count occurrences of each finding type
    type_counts: Counter[str] = Counter(f.finding_type for f in findings)

    seen_types: set[str] = set()
    top: list[dict[str, Any]] = []

    for f in sorted_findings:
        if f.finding_type in seen_types:
            continue
        seen_types.add(f.finding_type)
        top.append({
            "finding_type": f.finding_type,
            "dimension": f.dimension.value,
            "severity": f.severity.value,
            "message": f.message,
            "recommendation": f.recommendation,
            "count": type_counts[f.finding_type],
        })
        if len(top) >= max_count:
            break

    return top


def aggregate_results(
    page_results: list[PageAuditResult],
    ai_bot_access: AIBotAccessResult,
    sitemap_health: SitemapHealthResult,
    domain: str = "",
    audit_id: str = "",
    config: AuditConfig = DEFAULT_AUDIT_CONFIG,
) -> SiteAuditResult:
    """Aggregate per-page results into a site-level audit result.

    Steps:
        1. Collect all findings from all pages.
        2. Compute per-dimension scores via the scoring module.
        3. Compute overall score and grade.
        4. Compute summary statistics (avg snippet readiness, schema coverage).
        5. Build the :class:`SiteAuditResult`.

    Args:
        page_results: Per-page audit results from s2 + s3/s4 enrichment.
        ai_bot_access: AI bot access summary from s1.
        sitemap_health: Sitemap health summary from s1.
        domain: Audited domain string.
        audit_id: Unique audit run identifier.
        config: Audit configuration with weights and thresholds.

    Returns:
        A :class:`SiteAuditResult` with all scores, findings, and summaries
        populated. ``status`` is set to ``"completed"``.
    """
    all_findings = _collect_all_findings(page_results)

    # Per-dimension scores
    dimension_scores = compute_all_dimension_scores(all_findings, config)
    overall_score = compute_overall_score(dimension_scores)
    grade = compute_grade(overall_score, config)

    # Severity breakdown
    findings_by_severity: dict[str, int] = Counter(
        f.severity.value for f in all_findings
    )

    # Dimension breakdown
    findings_by_dimension: dict[str, int] = Counter(
        f.dimension.value for f in all_findings
    )

    # AEO stats
    aeo_scores = [p.aeo.snippet_readiness_score for p in page_results]
    avg_snippet_readiness = (
        round(sum(aeo_scores) / len(aeo_scores), 2) if aeo_scores else 0.0
    )

    q_heading_ratios = [p.aeo.question_heading_ratio for p in page_results]
    avg_question_heading_ratio = (
        round(sum(q_heading_ratios) / len(q_heading_ratios), 4)
        if q_heading_ratios
        else 0.0
    )

    # Schema coverage
    pages_with_schema = sum(1 for p in page_results if p.schema.has_schema)

    # Top findings
    top_findings = _compute_top_findings(all_findings)

    return SiteAuditResult(
        audit_id=audit_id,
        domain=domain,
        overall_score=overall_score,
        grade=grade,
        pages_crawled=len(page_results),
        dimension_scores=dimension_scores,
        ai_bot_access=ai_bot_access,
        sitemap_health=sitemap_health,
        page_results=page_results,
        total_findings=len(all_findings),
        findings_by_severity=dict(findings_by_severity),
        findings_by_dimension=dict(findings_by_dimension),
        top_findings=top_findings,
        avg_snippet_readiness=avg_snippet_readiness,
        pages_with_schema=pages_with_schema,
        avg_question_heading_ratio=avg_question_heading_ratio,
        status="completed",
    )
