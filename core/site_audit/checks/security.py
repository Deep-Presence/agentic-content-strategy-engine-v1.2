"""Security check functions for the site audit pipeline.

All functions are PURE — no I/O, no network calls, no side effects.
Each takes relevant page signals and returns list[AuditFinding].

Checks:
    - HTTPS enforcement
    - Mixed content detection
"""
from __future__ import annotations

from urllib.parse import urlparse

from core.models.site_audit import AuditCheckSeverity, AuditDimension, AuditFinding


def check_https(url: str) -> list[AuditFinding]:
    """Generate a critical finding when the page URL uses plain HTTP.

    HTTPS is required for AI bots and crawlers to trust page content.
    Insecure pages also generate browser security warnings that deter users.

    Args:
        url: Page URL string.

    Returns:
        List of :class:`AuditFinding` objects.  Empty when the URL uses HTTPS.
    """
    parsed = urlparse(url)
    if parsed.scheme.lower() == "https":
        return []

    return [
        AuditFinding(
            finding_type="not_https",
            dimension=AuditDimension.security,
            severity=AuditCheckSeverity.critical,
            url=url,
            message="Page is served over HTTP instead of HTTPS.",
            recommendation=(
                "Migrate the site to HTTPS. Obtain and install an SSL/TLS certificate, "
                "then enforce HTTPS via 301 redirects and HSTS headers."
            ),
            details={"scheme": parsed.scheme},
        )
    ]


def check_mixed_content(url: str, has_mixed_content: bool) -> list[AuditFinding]:
    """Generate a high-severity finding when an HTTPS page loads HTTP resources.

    Mixed content causes browser security warnings and may block resource
    loading in modern browsers, degrading user experience and crawlability.

    Args:
        url: Page URL.
        has_mixed_content: Whether HTTP-schemed resources (scripts, stylesheets,
            images, iframes) were detected in an HTTPS page.

    Returns:
        List of :class:`AuditFinding` objects.
    """
    if not has_mixed_content:
        return []

    return [
        AuditFinding(
            finding_type="mixed_content",
            dimension=AuditDimension.security,
            severity=AuditCheckSeverity.high,
            url=url,
            message="Page loads resources over insecure HTTP (mixed content).",
            recommendation=(
                "Update all resource URLs to use HTTPS. "
                "Mixed content triggers browser security warnings and blocks "
                "active resources (scripts, iframes) in Chrome and Firefox."
            ),
            details={"has_mixed_content": True},
        )
    ]
