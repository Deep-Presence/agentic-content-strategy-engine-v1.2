"""E-E-A-T signal check functions for the site audit pipeline.

All functions are PURE — no I/O, no network calls, no side effects.
Each takes relevant page signals and returns list[AuditFinding].

Checks:
    - Author presence on article-type pages
    - Content freshness (publish date, modified date staleness)
"""
from __future__ import annotations

from datetime import datetime, timezone

from dateutil import parser as dateutil_parser

from core.models.site_audit import AuditCheckSeverity, AuditDimension, AuditFinding


# Maximum length for date strings to prevent DoS via fuzzy parsing.
_MAX_DATE_STR_LENGTH: int = 100


def _parse_date_robust(date_str: str) -> datetime | None:
    """Parse a date string using multiple strategies.

    1. Reject strings > 100 chars (prevents DoS via fuzzy parser).
    2. Try ``dateutil.parser.isoparse()`` first (ISO 8601 with timezones, Z, fractional seconds).
    3. Fallback to ``dateutil.parser.parse(fuzzy=False)`` for human-readable dates.
    4. Normalize timezone-naive results to UTC.

    Args:
        date_str: Raw date string from HTML meta tags.

    Returns:
        A timezone-aware datetime in UTC, or ``None`` if parsing fails.
    """
    if not date_str or len(date_str) > _MAX_DATE_STR_LENGTH:
        return None

    parsed: datetime | None = None

    # Strategy 1: ISO 8601 (fastest, strictest)
    try:
        parsed = dateutil_parser.isoparse(date_str)
    except (ValueError, TypeError):
        pass

    # Strategy 2: human-readable fallback (non-fuzzy)
    if parsed is None:
        try:
            parsed = dateutil_parser.parse(date_str, fuzzy=False)
        except (ValueError, TypeError, OverflowError):
            return None

    # Normalize naive datetimes to UTC
    if parsed is not None and parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed


def check_author(url: str, has_author: bool) -> list[AuditFinding]:
    """Flag article-type pages that lack author attribution.

    AI models use authorship signals to evaluate E-E-A-T (Experience,
    Expertise, Authoritativeness, Trustworthiness).  Missing author
    information weakens citation probability for factual content.

    Args:
        url: Page URL.
        has_author: Whether an author name/byline was detected on the page.

    Returns:
        List of :class:`AuditFinding` objects.
    """
    if has_author:
        return []

    return [
        AuditFinding(
            finding_type="missing_author",
            dimension=AuditDimension.eeat,
            severity=AuditCheckSeverity.medium,
            url=url,
            message="No author attribution detected on this page.",
            recommendation=(
                "Add a visible author byline with the author's name. "
                "Linking to an author bio page with credentials further strengthens "
                "E-E-A-T signals for AI citation systems."
            ),
            details={"has_author": False},
        )
    ]


def check_freshness(
    url: str,
    publish_date: str | None,
    modified_date: str | None,
    page_type: str = "page",
    http_last_modified: str | None = None,
    sitemap_lastmod: str | None = None,
) -> list[AuditFinding]:
    """Generate findings for stale or undated content.

    AI search engines (Perplexity, ChatGPT, etc.) favour recent content,
    especially for time-sensitive topics.

    Args:
        url: Page URL.
        publish_date: ISO 8601 date string of original publication, or ``None``.
        modified_date: ISO 8601 date string of last modification, or ``None``.
        page_type: Inferred page type (e.g. ``"article"``, ``"homepage"``).
            When ``"article"`` and no dates are found, generates a low-severity
            finding recommending date metadata.
        http_last_modified: Value of the HTTP ``Last-Modified`` header, or ``None``.
        sitemap_lastmod: ``<lastmod>`` value from sitemap XML, or ``None``.

    Returns:
        List of :class:`AuditFinding` objects.
    """
    findings: list[AuditFinding] = []

    # Use modified_date preferentially, fall back through chain
    best_date_str = modified_date or http_last_modified or sitemap_lastmod or publish_date
    if not best_date_str:
        # Article pages without any date metadata get a finding
        if page_type == "article":
            findings.append(
                AuditFinding(
                    finding_type="missing_date_metadata",
                    dimension=AuditDimension.freshness,
                    severity=AuditCheckSeverity.low,
                    url=url,
                    message="Article page has no publish or modified date metadata.",
                    recommendation=(
                        "Add article:published_time and article:modified_time "
                        "meta tags. AI models deprioritise undated articles when "
                        "assessing content freshness."
                    ),
                    details={"page_type": page_type},
                )
            )
        return findings  # No date available — cannot assess freshness

    # Parse the date using robust multi-strategy parser
    parsed = _parse_date_robust(best_date_str)
    if parsed is None:
        return findings  # Unparseable date — skip

    now = datetime.now(tz=timezone.utc)
    age_days = (now - parsed).days

    if age_days > 730:  # > 2 years
        findings.append(
            AuditFinding(
                finding_type="stale_content_2y",
                dimension=AuditDimension.freshness,
                severity=AuditCheckSeverity.medium,
                url=url,
                message=(
                    f"Content is over 2 years old (last updated: {best_date_str[:10]})."
                ),
                recommendation=(
                    "Review and update this page to reflect current information. "
                    "AI models deprioritise very outdated content for citation."
                ),
                details={
                    "best_date": best_date_str,
                    "age_days": age_days,
                    "publish_date": publish_date,
                    "modified_date": modified_date,
                },
            )
        )
    elif age_days > 365:  # > 1 year
        findings.append(
            AuditFinding(
                finding_type="stale_content_1y",
                dimension=AuditDimension.freshness,
                severity=AuditCheckSeverity.low,
                url=url,
                message=(
                    f"Content is over 1 year old (last updated: {best_date_str[:10]})."
                ),
                recommendation=(
                    "Consider refreshing this page with updated facts, statistics, "
                    "and examples to maintain relevance in AI search citations."
                ),
                details={
                    "best_date": best_date_str,
                    "age_days": age_days,
                    "publish_date": publish_date,
                    "modified_date": modified_date,
                },
            )
        )

    return findings
