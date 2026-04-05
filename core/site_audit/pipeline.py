"""Site audit pipeline orchestrator.

Wires the six steps into a sequential pipeline:
    s1_discover → s2_analyze_pages → s3_check_schema → s4_check_aeo →
    s5_aggregate → s6_report

Each step is independently skippable via ``skip_steps``.  Failures in
individual steps are caught and logged without crashing the pipeline
(except s1, which is required — if crawling fails, there's nothing to audit).

Usage::

    result = await run_site_audit(
        SiteAuditInput(company_name="Acme", domain="acme.com"),
        config=DEFAULT_AUDIT_CONFIG,
        on_progress=lambda msg: print(msg),
    )
"""
from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.shared_tools.structured_logging import scoped_bind

from core.models.site_audit import (
    AIBotAccessResult,
    AuditCheckSeverity,
    AuditDimension,
    PageAuditResult,
    SiteAuditInput,
    SiteAuditResult,
    SitemapHealthResult,
)
from core.site_audit.config import DEFAULT_AUDIT_CONFIG, AuditConfig
from core.site_audit.scoring import compute_grade, compute_overall_score
from core.site_audit.steps.s1_discover import S1DiscoveryOutput, discover_site
from core.site_audit.steps.s2_analyze_pages import analyze_all_pages
from core.site_audit.steps.s3_check_schema import detect_schema, generate_schema_findings
from core.site_audit.steps.s4_check_aeo import analyze_aeo_readiness
from core.site_audit.steps.s5_aggregate import aggregate_results
from core.site_audit.steps.s6_report import generate_report

logger = logging.getLogger(__name__)

# Maps each step number to the audit dimensions it is solely responsible for.
# Used to determine which dimensions are degraded when a step fails.
_STEP_DIMENSION_MAP: dict[int, list[str]] = {
    2: ["crawlability", "on_page_seo", "security", "eeat", "freshness", "performance"],
    3: ["schema_markup"],
    4: ["extractability"],
}


def _should_skip(step: int, skip_steps: Optional[list[int]]) -> bool:
    """Check whether a step number should be skipped.

    Args:
        step: Step number (1-6).
        skip_steps: List of step numbers to skip, or None.

    Returns:
        True if the step should be skipped.
    """
    return skip_steps is not None and step in skip_steps


def _emit(on_progress: Optional[Callable[[str], None]], message: str) -> None:
    """Safely invoke the progress callback.

    Args:
        on_progress: Optional callback, may be None.
        message: Progress message to emit.
    """
    if on_progress is not None:
        try:
            on_progress(message)
        except Exception:
            logger.debug("on_progress callback raised; ignoring", exc_info=True)


async def run_site_audit(
    input_data: SiteAuditInput,
    config: AuditConfig = DEFAULT_AUDIT_CONFIG,
    on_progress: Optional[Callable[[str], None]] = None,
    skip_steps: Optional[list[int]] = None,
    output_dir: Optional[Path] = None,
    _html_map_out: Optional[dict[str, str]] = None,
) -> SiteAuditResult:
    """Run the full site audit pipeline and return a :class:`SiteAuditResult`.

    Steps:
        1. s1_discover  — async BFS crawler + robots.txt + sitemap analysis.
        2. s2_analyze   — per-page structural signal extraction.
        3. s3_schema    — JSON-LD / Microdata detection and validation.
        4. s4_aeo       — Answer Engine Optimisation readiness scoring.
        5. s5_aggregate — Roll up per-page results into dimension scores.
        6. s6_report    — Generate findings list and executive summary.

    Args:
        input_data: Domain + options for this audit run.
        config: Scoring thresholds and concurrency limits.
            Defaults to :data:`DEFAULT_AUDIT_CONFIG`.
        on_progress: Optional callback invoked with a human-readable status
            message after each step completes.  Useful for SSE streaming.
        skip_steps: Step numbers to skip (e.g. ``[3, 4]`` to reuse cached
            schema/AEO results).  Mirrors the gap-analysis pipeline pattern.

    Returns:
        A :class:`SiteAuditResult` with ``status="completed"`` on success or
        ``status="failed"`` (with ``error_message`` set) on failure.
    """
    audit_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    t0 = time.monotonic()

    domain = input_data.domain
    if input_data.product_slug and input_data.company_slug:
        effective_slug = f"{input_data.company_slug}__{input_data.product_slug}"
    elif input_data.company_slug:
        effective_slug = input_data.company_slug
    else:
        effective_slug = ""

    failed_steps: list[int] = []

    logger.info(
        "Starting site audit: domain=%s audit_id=%s slug=%s",
        domain, audit_id, effective_slug,
    )
    _emit(on_progress, f"Starting site audit for {domain}")

    # ── Step 1: Discover ────────────────────────────────────────────────
    discovery: Optional[S1DiscoveryOutput] = None

    with scoped_bind(step_name="s1_discover"):
        if _should_skip(1, skip_steps):
            logger.info("s1_discover: SKIPPED")
            _emit(on_progress, "Step 1 (discovery): skipped")
            discovery = S1DiscoveryOutput()
        else:
            try:
                _emit(on_progress, "Step 1: Crawling site...")
                discovery = await discover_site(
                    domain=domain,
                    max_pages=input_data.max_pages,
                    max_depth=input_data.max_depth,
                    concurrency=config.page_analysis_concurrency,
                    respect_robots=True,
                    timeout=config.request_timeout,
                    config=config,
                    check_ai_bot_access=input_data.check_ai_bot_access,
                )
                _emit(
                    on_progress,
                    f"Step 1 complete: {len(discovery.pages_with_html)} pages crawled, "
                    f"{len(discovery.discovered_urls)} URLs discovered",
                )
                logger.info(
                    "s1_discover complete: %d pages, %d URLs discovered",
                    len(discovery.pages_with_html),
                    len(discovery.discovered_urls),
                )
            except Exception as exc:
                logger.exception("s1_discover failed: %s", exc)
                _emit(on_progress, f"Step 1 failed: {exc}")
                return SiteAuditResult(
                    audit_id=audit_id,
                    domain=domain,
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                    duration_seconds=round(time.monotonic() - t0, 2),
                    status="failed",
                    error_message=f"Discovery step failed: {exc}",
                )

    # Surface raw HTML for content inventory structural signal extraction
    if _html_map_out is not None and discovery.pages_with_html:
        for url, html in discovery.pages_with_html:
            _html_map_out[url] = html

    # ── Step 2: Analyze pages ───────────────────────────────────────────
    page_results: list[PageAuditResult] = []

    with scoped_bind(step_name="s2_analyze_pages"):
        if _should_skip(2, skip_steps):
            logger.info("s2_analyze_pages: SKIPPED")
            _emit(on_progress, "Step 2 (page analysis): skipped")
        else:
            try:
                _emit(on_progress, "Step 2: Analyzing pages...")
                page_results = await analyze_all_pages(
                    pages=discovery.pages_with_html,
                    depth_map=discovery.crawl_depth_map,
                    status_code_map=discovery.status_code_map,
                    redirect_map=discovery.redirect_map,
                    config=config,
                    check_core_web_vitals=input_data.check_core_web_vitals,
                    headers_map=discovery.headers_map,
                    sitemap_lastmod_map=discovery.sitemap_lastmod_map,
                )
                _emit(on_progress, f"Step 2 complete: {len(page_results)} pages analyzed")
                logger.info("s2_analyze_pages complete: %d results", len(page_results))
            except Exception as exc:
                logger.exception("s2_analyze_pages failed: %s", exc)
                _emit(on_progress, f"Step 2 failed: {exc}")
                failed_steps.append(2)
                # Continue with empty results — later steps handle empty gracefully

    # ── Step 3: Schema detection ────────────────────────────────────────
    with scoped_bind(step_name="s3_check_schema"):
        if _should_skip(3, skip_steps) or not input_data.check_schema_validation:
            logger.info("s3_check_schema: SKIPPED%s", "" if _should_skip(3, skip_steps) else " (check_schema_validation=False)")
            _emit(on_progress, "Step 3 (schema detection): skipped")
        else:
            try:
                _emit(on_progress, "Step 3: Detecting structured data...")
                # Schema detection needs the raw HTML from discovery
                html_map = {url: html for url, html in discovery.pages_with_html}
                s3_page_failures = 0
                s3_pages_attempted = 0
                for page in page_results:
                    try:
                        html = html_map.get(page.url, "")
                        if not html:
                            continue
                        s3_pages_attempted += 1
                        schema_result = detect_schema(html, page.url)
                        page.schema_result = schema_result
                        schema_findings = generate_schema_findings(page.url, schema_result)
                        page.findings.extend(schema_findings)
                    except Exception as page_exc:
                        s3_page_failures += 1
                        logger.warning("s3 failed for page %s: %s", page.url, page_exc)
                if s3_page_failures > 0 and s3_page_failures == s3_pages_attempted:
                    logger.error("s3_check_schema: all %d pages failed", s3_page_failures)
                    failed_steps.append(3)
                _emit(on_progress, "Step 3 complete: schema detection done")
                logger.info("s3_check_schema complete")
            except Exception as exc:
                logger.exception("s3_check_schema failed: %s", exc)
                _emit(on_progress, f"Step 3 failed: {exc}")
                failed_steps.append(3)

    # ── Step 4: AEO readiness ───────────────────────────────────────────
    with scoped_bind(step_name="s4_check_aeo"):
        if _should_skip(4, skip_steps):
            logger.info("s4_check_aeo: SKIPPED")
            _emit(on_progress, "Step 4 (AEO readiness): skipped")
        else:
            try:
                _emit(on_progress, "Step 4: Analyzing AEO readiness...")
                html_map = {url: html for url, html in discovery.pages_with_html}
                s4_page_failures = 0
                s4_pages_attempted = 0
                for page in page_results:
                    try:
                        html = html_map.get(page.url, "")
                        if not html:
                            continue
                        s4_pages_attempted += 1
                        aeo_result, aeo_findings = analyze_aeo_readiness(html, page.url, config)
                        page.aeo = aeo_result
                        page.findings.extend(aeo_findings)
                    except Exception as page_exc:
                        s4_page_failures += 1
                        logger.warning("s4 failed for page %s: %s", page.url, page_exc)
                if s4_page_failures > 0 and s4_page_failures == s4_pages_attempted:
                    logger.error("s4_check_aeo: all %d pages failed", s4_page_failures)
                    failed_steps.append(4)
                _emit(on_progress, "Step 4 complete: AEO analysis done")
                logger.info("s4_check_aeo complete")
            except Exception as exc:
                logger.exception("s4_check_aeo failed: %s", exc)
                _emit(on_progress, f"Step 4 failed: {exc}")
                failed_steps.append(4)

    # ── Step 5: Aggregate ───────────────────────────────────────────────
    with scoped_bind(step_name="s5_aggregate"):
        if _should_skip(5, skip_steps):
            logger.info("s5_aggregate: SKIPPED")
            _emit(on_progress, "Step 5 (aggregation): skipped")
            # Build a minimal result
            result = SiteAuditResult(
                audit_id=audit_id,
                domain=domain,
                pages_crawled=len(page_results),
                pages_discovered=len(discovery.discovered_urls),
                page_results=page_results,
                ai_bot_access=discovery.ai_bot_access,
                sitemap_health=discovery.sitemap_health,
                started_at=started_at,
                status="completed",
            )
        else:
            try:
                _emit(on_progress, "Step 5: Aggregating results...")
                result = aggregate_results(
                    page_results=page_results,
                    ai_bot_access=discovery.ai_bot_access,
                    sitemap_health=discovery.sitemap_health,
                    domain=domain,
                    audit_id=audit_id,
                    config=config,
                    internal_link_targets=discovery.internal_link_targets,
                )
                result.pages_discovered = len(discovery.discovered_urls)
                result.started_at = started_at
                _emit(
                    on_progress,
                    f"Step 5 complete: overall score {result.overall_score:.0f}/100 "
                    f"(grade {result.grade})",
                )
                logger.info(
                    "s5_aggregate complete: score=%.1f grade=%s",
                    result.overall_score, result.grade,
                )
            except Exception as exc:
                logger.exception("s5_aggregate failed: %s", exc)
                _emit(on_progress, f"Step 5 failed: {exc}")
                result = SiteAuditResult(
                    audit_id=audit_id,
                    domain=domain,
                    pages_crawled=len(page_results),
                    pages_discovered=len(discovery.discovered_urls),
                    page_results=page_results,
                    ai_bot_access=discovery.ai_bot_access,
                    sitemap_health=discovery.sitemap_health,
                    started_at=started_at,
                    status="failed",
                    error_message=f"Aggregation failed: {exc}",
                )

    # ── Degraded status for partial failures ────────────────────────────
    if failed_steps:
        degraded_dims: list[str] = []
        for step in failed_steps:
            degraded_dims.extend(_STEP_DIMENSION_MAP.get(step, []))
        degraded_dims = list(set(degraded_dims))

        result.failed_steps = failed_steps
        result.degraded_dimensions = degraded_dims
        result.status = "degraded"

        # Override degraded dimension scores to 0 (conservative)
        for ds in result.dimension_scores:
            if ds.dimension.value in degraded_dims:
                ds.score = 0.0
                ds.weighted_score = 0.0

        # Recompute overall from modified dimension scores
        result.overall_score = compute_overall_score(result.dimension_scores)
        result.grade = compute_grade(result.overall_score, config)

    # ── Crawl-delay findings (site-level, from robots.txt) ─────────────
    if discovery.ai_bot_access.crawl_delay_seconds is not None:
        delay = discovery.ai_bot_access.crawl_delay_seconds
        if delay > 30:
            result.top_findings.append({
                "finding_type": "crawl_delay_excessive",
                "dimension": AuditDimension.crawlability.value,
                "severity": AuditCheckSeverity.medium.value,
                "message": (
                    f"robots.txt specifies Crawl-delay: {delay}s — this significantly "
                    f"throttles AI crawlers and may reduce crawl coverage."
                ),
                "recommendation": (
                    "Review whether such a high Crawl-delay is necessary. "
                    "Consider reducing it to allow AI bots to index more pages."
                ),
            })
        elif delay > 10:
            result.top_findings.append({
                "finding_type": "crawl_delay_high",
                "dimension": AuditDimension.crawlability.value,
                "severity": AuditCheckSeverity.info.value,
                "message": (
                    f"robots.txt specifies Crawl-delay: {delay}s — this may slow "
                    f"AI crawler indexing of the site."
                ),
                "recommendation": (
                    "Monitor whether the Crawl-delay is impacting how quickly "
                    "AI search engines index new content."
                ),
            })

    # ── Step 6: Report ──────────────────────────────────────────────────
    with scoped_bind(step_name="s6_report"):
        if _should_skip(6, skip_steps):
            logger.info("s6_report: SKIPPED")
            _emit(on_progress, "Step 6 (report): skipped")
        else:
            try:
                _emit(on_progress, "Step 6: Generating report...")
                report_dir = output_dir if output_dir is not None else (
                    Path("artifacts") / "site_audit" / effective_slug / audit_id
                )
                await generate_report(result, report_dir)
                _emit(on_progress, "Step 6 complete: report generated")
                logger.info("s6_report complete: %s", report_dir)
            except Exception as exc:
                logger.exception("s6_report failed: %s", exc)
                _emit(on_progress, f"Step 6 failed: {exc}")

    # ── Finalize ────────────────────────────────────────────────────────
    completed_at = datetime.now(timezone.utc)
    result.completed_at = completed_at
    result.duration_seconds = round(time.monotonic() - t0, 2)

    logger.info(
        "Site audit complete: domain=%s score=%.1f grade=%s duration=%.1fs",
        domain, result.overall_score, result.grade, result.duration_seconds,
    )
    _emit(
        on_progress,
        f"Audit complete: {result.overall_score:.0f}/100 ({result.grade}) "
        f"in {result.duration_seconds:.1f}s",
    )

    return result
