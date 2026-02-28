"""E-E-A-T signal check functions for the site audit pipeline.

All functions are PURE — no I/O, no network calls, no side effects.
Each takes relevant page signals and returns list[AuditFinding].

Checks:
    - Author presence on article-type pages
    - Content freshness (publish date, modified date staleness)
"""
from __future__ import annotations

from datetime import datetime, timezone

from core.models.site_audit import AuditCheckSeverity, AuditDimension, AuditFinding


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
) -> list[AuditFinding]:
    """Generate findings for stale or undated content.

    AI search engines (Perplexity, ChatGPT, etc.) favour recent content,
    especially for time-sensitive topics.

    Args:
        url: Page URL.
        publish_date: ISO 8601 date string of original publication, or ``None``.
        modified_date: ISO 8601 date string of last modification, or ``None``.

    Returns:
        List of :class:`AuditFinding` objects.
    """
    findings: list[AuditFinding] = []

    # Use modified_date preferentially, fall back to publish_date
    best_date_str = modified_date or publish_date
    if not best_date_str:
        return findings  # No date available — cannot assess freshness

    # Try to parse the date
    parsed: datetime | None = None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            parsed = datetime.strptime(best_date_str[:len(fmt) + 6], fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            break
        except (ValueError, TypeError):
            continue

    if parsed is None:
        return findings  # Unparseable date — skip

    now = datetime.now(tz=timezone.utc)
    age_days = (now - parsed).days

    if age_days > 730:  # > 2 years
        findings.append(
            AuditFinding(
                finding_type="stale_content_2y",
                dimension=AuditDimension.eeat,
                severity=AuditCheckSeverity.low,
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
                dimension=AuditDimension.eeat,
                severity=AuditCheckSeverity.medium,
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
