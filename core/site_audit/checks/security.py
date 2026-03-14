"""Security check functions for the site audit pipeline.

All functions are PURE — no I/O, no network calls, no side effects.
Each takes relevant page signals and returns list[AuditFinding].

Checks:
    - HTTPS enforcement
    - Mixed content detection
    - HTTP security headers (HSTS, CSP, X-Content-Type-Options, X-Frame-Options)
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


def check_security_headers(
    url: str,
    headers: dict[str, str],
) -> list[AuditFinding]:
    """Check HTTP security headers on an HTTPS page.

    Evaluates: Strict-Transport-Security, Content-Security-Policy,
    X-Content-Type-Options, X-Frame-Options.

    Args:
        url: Page URL (should be HTTPS — caller gates this).
        headers: HTTP response headers dict (keys are case-insensitive in
            practice, so we normalise to lowercase for comparison).

    Returns:
        List of :class:`AuditFinding` objects.
    """
    findings: list[AuditFinding] = []
    lower_headers = {k.lower(): v for k, v in headers.items()}

    # --- HSTS ---
    hsts = lower_headers.get("strict-transport-security")
    if not hsts:
        findings.append(
            AuditFinding(
                finding_type="missing_hsts",
                dimension=AuditDimension.security,
                severity=AuditCheckSeverity.medium,
                url=url,
                message="Missing Strict-Transport-Security header.",
                recommendation=(
                    "Add a Strict-Transport-Security header with "
                    "max-age=31536000 (1 year) to enforce HTTPS."
                ),
                details={"header": "strict-transport-security"},
            )
        )
    else:
        # Check max-age value
        import re

        match = re.search(r"max-age=(\d+)", hsts, re.IGNORECASE)
        if match and int(match.group(1)) < 31536000:
            findings.append(
                AuditFinding(
                    finding_type="weak_hsts",
                    dimension=AuditDimension.security,
                    severity=AuditCheckSeverity.low,
                    url=url,
                    message=(
                        f"HSTS max-age is {match.group(1)}s — "
                        f"recommended minimum is 31536000 (1 year)."
                    ),
                    recommendation=(
                        "Increase Strict-Transport-Security max-age "
                        "to at least 31536000 seconds."
                    ),
                    details={
                        "header": "strict-transport-security",
                        "max_age": int(match.group(1)),
                    },
                )
            )

    # --- CSP ---
    csp = lower_headers.get("content-security-policy")
    if not csp:
        findings.append(
            AuditFinding(
                finding_type="missing_csp",
                dimension=AuditDimension.security,
                severity=AuditCheckSeverity.low,
                url=url,
                message="Missing Content-Security-Policy header.",
                recommendation=(
                    "Add a Content-Security-Policy header to mitigate "
                    "cross-site scripting and injection attacks."
                ),
                details={"header": "content-security-policy"},
            )
        )
    else:
        csp_lower = csp.lower()
        if "'unsafe-inline'" in csp_lower or "'unsafe-eval'" in csp_lower:
            findings.append(
                AuditFinding(
                    finding_type="weak_csp",
                    dimension=AuditDimension.security,
                    severity=AuditCheckSeverity.medium,
                    url=url,
                    message=(
                        "Content-Security-Policy contains unsafe-inline "
                        "or unsafe-eval directives."
                    ),
                    recommendation=(
                        "Replace unsafe-inline with nonce-based or "
                        "hash-based CSP. Remove unsafe-eval if possible."
                    ),
                    details={"header": "content-security-policy"},
                )
            )

    # --- X-Content-Type-Options ---
    if "x-content-type-options" not in lower_headers:
        findings.append(
            AuditFinding(
                finding_type="missing_x_content_type_options",
                dimension=AuditDimension.security,
                severity=AuditCheckSeverity.low,
                url=url,
                message="Missing X-Content-Type-Options header.",
                recommendation=(
                    "Add X-Content-Type-Options: nosniff to prevent "
                    "MIME type sniffing."
                ),
                details={"header": "x-content-type-options"},
            )
        )

    # --- X-Frame-Options ---
    if "x-frame-options" not in lower_headers:
        findings.append(
            AuditFinding(
                finding_type="missing_x_frame_options",
                dimension=AuditDimension.security,
                severity=AuditCheckSeverity.low,
                url=url,
                message="Missing X-Frame-Options header.",
                recommendation=(
                    "Add X-Frame-Options: DENY or SAMEORIGIN to prevent "
                    "clickjacking attacks."
                ),
                details={"header": "x-frame-options"},
            )
        )

    return findings
