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
    AuditCheckSeverity,
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


# ---------------------------------------------------------------------------
# Cross-page analysis helpers (pure, no I/O)
# ---------------------------------------------------------------------------


def _detect_duplicate_titles(
    page_results: list[PageAuditResult],
) -> list[AuditFinding]:
    """Flag pages that share the same title (case-insensitive).

    Duplicate titles confuse AI models trying to identify distinct content.
    Groups with 2+ URLs produce a single finding listing all affected URLs.
    """
    title_groups: dict[str, list[str]] = {}
    for page in page_results:
        title = (page.title or "").strip().lower()
        if not title:
            continue
        title_groups.setdefault(title, []).append(page.url)

    findings: list[AuditFinding] = []
    for title, urls in title_groups.items():
        if len(urls) < 2:
            continue
        findings.append(
            AuditFinding(
                finding_type="duplicate_title",
                dimension=AuditDimension.on_page_seo,
                severity=AuditCheckSeverity.high,
                url="",
                message=(
                    f"{len(urls)} pages share the same title: "
                    f"\"{title[:80]}{'…' if len(title) > 80 else ''}\""
                ),
                recommendation=(
                    "Give each page a unique, descriptive title. "
                    "Duplicate titles make it harder for AI models to "
                    "distinguish and cite individual pages."
                ),
                details={"title": title, "urls": urls},
            )
        )
    return findings


def _detect_duplicate_meta_descriptions(
    page_results: list[PageAuditResult],
) -> list[AuditFinding]:
    """Flag pages that share the same meta description (case-insensitive)."""
    desc_groups: dict[str, list[str]] = {}
    for page in page_results:
        desc = (page.meta_description or "").strip().lower()
        if not desc:
            continue
        desc_groups.setdefault(desc, []).append(page.url)

    findings: list[AuditFinding] = []
    for desc, urls in desc_groups.items():
        if len(urls) < 2:
            continue
        findings.append(
            AuditFinding(
                finding_type="duplicate_meta_description",
                dimension=AuditDimension.on_page_seo,
                severity=AuditCheckSeverity.medium,
                url="",
                message=(
                    f"{len(urls)} pages share the same meta description."
                ),
                recommendation=(
                    "Write unique meta descriptions for each page. "
                    "AI models use descriptions to understand page relevance."
                ),
                details={"description": desc[:200], "urls": urls},
            )
        )
    return findings


def _detect_orphan_pages(
    sitemap_urls: list[str],
    internal_link_targets: set[str],
) -> list[AuditFinding]:
    """Flag sitemap URLs that are not linked from any crawled page.

    Orphan pages are discoverable via sitemap but unreachable through
    internal navigation, reducing their crawl priority and citation chance.
    """
    orphans = set(sitemap_urls) - internal_link_targets
    if not orphans:
        return []

    findings: list[AuditFinding] = []
    orphan_list = sorted(orphans)
    # Cap at 20 individual findings
    for orphan_url in orphan_list[:20]:
        findings.append(
            AuditFinding(
                finding_type="orphan_page",
                dimension=AuditDimension.crawlability,
                severity=AuditCheckSeverity.medium,
                url=orphan_url,
                message="Page is in sitemap but has no internal links pointing to it.",
                recommendation=(
                    "Add internal links to this page from related content. "
                    "Orphan pages are less likely to be discovered and cited "
                    "by AI crawlers."
                ),
                details={"total_orphans": len(orphans)},
            )
        )
    return findings


def _detect_thin_content(
    page_results: list[PageAuditResult],
    config: AuditConfig,
) -> list[AuditFinding]:
    """Flag pages with very low word counts.

    Thin content pages provide insufficient substance for AI models
    to extract and cite meaningful information.
    """
    findings: list[AuditFinding] = []
    for page in page_results:
        # Skip noindex/redirect pages
        if page.is_noindex or page.redirect_url:
            continue
        wc = page.word_count or 0
        if wc < config.thin_content_threshold:
            findings.append(
                AuditFinding(
                    finding_type="thin_content",
                    dimension=AuditDimension.on_page_seo,
                    severity=AuditCheckSeverity.medium,
                    url=page.url,
                    message=(
                        f"Page has only {wc} words "
                        f"(threshold: {config.thin_content_threshold})."
                    ),
                    recommendation=(
                        "Expand this page with substantive content. "
                        "AI models need sufficient text to extract facts "
                        "and generate citations."
                    ),
                    details={
                        "word_count": wc,
                        "threshold": config.thin_content_threshold,
                    },
                )
            )
    return findings


def _cross_page_findings(
    page_results: list[PageAuditResult],
    sitemap_urls: list[str],
    internal_link_targets: set[str],
    config: AuditConfig,
) -> list[AuditFinding]:
    """Run all cross-page analysis checks.

    Orchestrator for site-wide findings that require comparing data
    across multiple pages.
    """
    findings: list[AuditFinding] = []
    findings.extend(_detect_duplicate_titles(page_results))
    findings.extend(_detect_duplicate_meta_descriptions(page_results))
    findings.extend(_detect_orphan_pages(sitemap_urls, internal_link_targets))
    findings.extend(_detect_thin_content(page_results, config))
    return findings


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
    internal_link_targets: set[str] | None = None,
) -> SiteAuditResult:
    """Aggregate per-page results into a site-level audit result.

    Steps:
        1. Run cross-page analysis (duplicate titles, orphan pages, etc.).
        2. Collect all findings from all pages.
        3. Compute per-dimension scores via the scoring module.
        4. Compute overall score and grade.
        5. Compute summary statistics (avg snippet readiness, schema coverage).
        6. Build the :class:`SiteAuditResult`.

    Args:
        page_results: Per-page audit results from s2 + s3/s4 enrichment.
        ai_bot_access: AI bot access summary from s1.
        sitemap_health: Sitemap health summary from s1.
        domain: Audited domain string.
        audit_id: Unique audit run identifier.
        config: Audit configuration with weights and thresholds.
        internal_link_targets: Set of URLs linked from crawled pages (for orphan detection).

    Returns:
        A :class:`SiteAuditResult` with all scores, findings, and summaries
        populated. ``status`` is set to ``"completed"``.
    """
    # Cross-page analysis (skip orphan detection when link targets not provided)
    cross_findings = _cross_page_findings(
        page_results,
        sitemap_urls=sitemap_health.sitemap_urls if internal_link_targets is not None else [],
        internal_link_targets=internal_link_targets or set(),
        config=config,
    )

    all_findings = _collect_all_findings(page_results)
    all_findings = cross_findings + all_findings

    # Per-dimension scores (page-normalised)
    pages_crawled = len(page_results)
    dimension_scores = compute_all_dimension_scores(all_findings, config, pages_crawled)
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
    pages_with_schema = sum(1 for p in page_results if p.schema_result.has_schema)

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
