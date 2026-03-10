"""Crawlability check functions for the site audit pipeline.

All functions are PURE — no I/O, no network calls, no side effects.
Each takes relevant page data and returns list[AuditFinding].

Checks:
    - Status code (5xx = critical, 4xx = high, 3xx = info)
    - Crawl depth (>3 = medium, >5 = high)
    - Canonical tag presence and correctness
    - Noindex directive (flagged as info)
"""
from __future__ import annotations

from core.models.site_audit import AuditCheckSeverity, AuditDimension, AuditFinding


def check_status_code(url: str, status_code: int) -> list[AuditFinding]:
    """Generate findings for non-200 HTTP status codes.

    Args:
        url: Page URL.
        status_code: HTTP status code returned for this URL.
            A value of 0 indicates a timeout or connection error.

    Returns:
        List of :class:`AuditFinding` objects.  Empty if status is 2xx.
    """
    findings: list[AuditFinding] = []

    if status_code == 0:
        findings.append(
            AuditFinding(
                finding_type="timeout_or_connection_error",
                dimension=AuditDimension.crawlability,
                severity=AuditCheckSeverity.high,
                url=url,
                message=f"Page could not be fetched (timeout or connection error).",
                recommendation=(
                    "Ensure the page is reachable and responds within the timeout. "
                    "Check server logs for errors."
                ),
                details={"status_code": status_code},
            )
        )
    elif 500 <= status_code <= 599:
        findings.append(
            AuditFinding(
                finding_type="server_error",
                dimension=AuditDimension.crawlability,
                severity=AuditCheckSeverity.critical,
                url=url,
                message=f"Server returned HTTP {status_code} (server error).",
                recommendation=(
                    "Investigate and fix the server-side error. "
                    "5xx pages are uncrawlable and hurt AI citation potential."
                ),
                details={"status_code": status_code},
            )
        )
    elif 400 <= status_code <= 499:
        findings.append(
            AuditFinding(
                finding_type="client_error",
                dimension=AuditDimension.crawlability,
                severity=AuditCheckSeverity.high,
                url=url,
                message=f"Server returned HTTP {status_code} (client error).",
                recommendation=(
                    "Fix or remove the broken URL. "
                    "404 and other 4xx pages waste crawl budget."
                ),
                details={"status_code": status_code},
            )
        )
    elif 300 <= status_code <= 399:
        findings.append(
            AuditFinding(
                finding_type="redirect",
                dimension=AuditDimension.crawlability,
                severity=AuditCheckSeverity.info,
                url=url,
                message=f"Page returned HTTP {status_code} (redirect).",
                recommendation=(
                    "Ensure the redirect target is the canonical destination. "
                    "Redirect chains longer than 2 hops waste crawl budget."
                ),
                details={"status_code": status_code},
            )
        )

    return findings


def check_crawl_depth(
    url: str, depth: int, max_recommended: int = 3
) -> list[AuditFinding]:
    """Generate findings when a page is too deep in the site hierarchy.

    AI crawlers and search bots may not reach pages buried deeper than
    3–4 clicks from the homepage.

    Args:
        url: Page URL.
        depth: BFS depth at which this page was discovered (0 = seed).
        max_recommended: Recommended maximum depth.  Pages beyond this
            threshold generate a finding.

    Returns:
        List of :class:`AuditFinding` objects.
    """
    findings: list[AuditFinding] = []

    if depth > 5:
        findings.append(
            AuditFinding(
                finding_type="excessive_crawl_depth",
                dimension=AuditDimension.crawlability,
                severity=AuditCheckSeverity.high,
                url=url,
                message=f"Page is at crawl depth {depth} (recommended ≤ {max_recommended}).",
                recommendation=(
                    "Restructure internal linking so this page is reachable within "
                    f"{max_recommended} clicks from the homepage."
                ),
                details={"depth": depth, "max_recommended": max_recommended},
            )
        )
    elif depth > max_recommended:
        findings.append(
            AuditFinding(
                finding_type="deep_crawl_depth",
                dimension=AuditDimension.crawlability,
                severity=AuditCheckSeverity.medium,
                url=url,
                message=f"Page is at crawl depth {depth} (recommended ≤ {max_recommended}).",
                recommendation=(
                    "Add more internal links to this page from shallower pages "
                    "to improve discoverability."
                ),
                details={"depth": depth, "max_recommended": max_recommended},
            )
        )

    return findings


def check_canonical(
    url: str,
    has_canonical: bool,
    canonical_url: str | None,
) -> list[AuditFinding]:
    """Generate findings for missing or incorrect canonical tags.

    Args:
        url: Page URL (normalized).
        has_canonical: Whether ``<link rel="canonical">`` was found.
        canonical_url: The href value of the canonical tag, or ``None``.

    Returns:
        List of :class:`AuditFinding` objects.
    """
    findings: list[AuditFinding] = []

    if not has_canonical:
        findings.append(
            AuditFinding(
                finding_type="missing_canonical",
                dimension=AuditDimension.crawlability,
                severity=AuditCheckSeverity.medium,
                url=url,
                message="Page is missing a canonical URL tag.",
                recommendation=(
                    "Add ``<link rel='canonical' href='...' />`` to the ``<head>`` "
                    "to prevent duplicate content issues."
                ),
                details={},
            )
        )
    elif canonical_url and canonical_url != url:
        # Canonical points elsewhere — not necessarily wrong, but flag for review
        findings.append(
            AuditFinding(
                finding_type="canonical_mismatch",
                dimension=AuditDimension.crawlability,
                severity=AuditCheckSeverity.high,
                url=url,
                message=(
                    f"Canonical URL '{canonical_url}' differs from the page URL '{url}'."
                ),
                recommendation=(
                    "Verify this is intentional (e.g. pagination or syndicated content). "
                    "If not, update the canonical to point to this page's URL."
                ),
                details={"canonical_url": canonical_url},
            )
        )

    return findings


def check_noindex(url: str, is_noindex: bool) -> list[AuditFinding]:
    """Flag pages with ``noindex`` meta robots directives.

    This is informational only — noindex may be intentional (e.g. login pages).

    Args:
        url: Page URL.
        is_noindex: Whether a ``noindex`` directive was found in meta robots.

    Returns:
        List of :class:`AuditFinding` objects.
    """
    if not is_noindex:
        return []

    return [
        AuditFinding(
            finding_type="noindex_page",
            dimension=AuditDimension.crawlability,
            severity=AuditCheckSeverity.info,
            url=url,
            message="Page has a 'noindex' meta robots directive.",
            recommendation=(
                "Verify that this page should be excluded from search/AI indexing. "
                "Remove the noindex tag if the page contains content you want cited."
            ),
            details={"is_noindex": True},
        )
    ]
