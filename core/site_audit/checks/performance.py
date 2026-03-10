"""Performance check functions for the site audit pipeline.

Functions:
    check_ssr_content    — Detect client-side-rendered (CSR) pages.
    fetch_core_web_vitals — Optionally fetch PageSpeed Insights CWV data.

``check_ssr_content`` is PURE — no I/O, no network calls.
``fetch_core_web_vitals`` is async and performs an external HTTP call.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from bs4 import BeautifulSoup

from core.models.site_audit import AuditCheckSeverity, AuditDimension, AuditFinding

logger = logging.getLogger(__name__)

# PageSpeed Insights API endpoint
_PSI_API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

# Core Web Vitals "good" thresholds (Google's published values)
_CWV_THRESHOLDS: dict[str, float] = {
    "LCP": 2500.0,  # ms — Largest Contentful Paint
    "FID": 100.0,   # ms — First Input Delay (legacy)
    "INP": 200.0,   # ms — Interaction to Next Paint
    "CLS": 0.1,     # unitless — Cumulative Layout Shift
}


def check_ssr_content(html: str, url: str) -> list[AuditFinding]:
    """Detect pages that appear to be client-side rendered (CSR).

    Extracts visible text from the ``<body>`` element. If fewer than 100 words
    of visible text are found, the page is likely CSR — AI crawlers will see an
    empty or near-empty page.

    Args:
        html: Raw HTML string of the page.
        url: Page URL (used for finding metadata only).

    Returns:
        List of :class:`AuditFinding` objects. Empty if the page passes the SSR check.
    """
    findings: list[AuditFinding] = []

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as exc:
        logger.warning("check_ssr_content: HTML parse error for %s: %s", url, exc)
        return findings

    # Remove non-content tags
    for tag in soup.find_all(["script", "style", "noscript", "head", "meta", "link"]):
        tag.decompose()

    body = soup.find("body") or soup
    body_text = body.get_text(separator=" ", strip=True)
    words = [w for w in body_text.split() if w]
    word_count = len(words)

    if word_count < 100:
        findings.append(
            AuditFinding(
                finding_type="possible_csr_page",
                dimension=AuditDimension.performance,
                severity=AuditCheckSeverity.high,
                url=url,
                message=(
                    f"Page may be client-side rendered — only {word_count} visible "
                    "words detected. AI crawlers cannot extract content from CSR pages."
                ),
                recommendation=(
                    "Ensure the page is server-side rendered (SSR) or uses static "
                    "site generation (SSG). AI bots typically do not execute JavaScript, "
                    "so CSR pages appear blank to them. Implement SSR or pre-rendering "
                    "to make content accessible."
                ),
                details={"visible_word_count": word_count, "threshold": 100},
            )
        )

    return findings


async def fetch_core_web_vitals(
    url: str, api_key: Optional[str] = None
) -> Optional[dict[str, Any]]:
    """Fetch Core Web Vitals data from the PageSpeed Insights API.

    This is an OPTIONAL check.  If ``api_key`` is None or the API request fails
    for any reason, this function returns ``None`` (graceful degradation).

    CWV "good" thresholds applied:
    - LCP ≤ 2,500 ms
    - INP ≤ 200 ms (or FID ≤ 100 ms for legacy data)
    - CLS ≤ 0.1

    Args:
        url: The page URL to analyse.
        api_key: Google PageSpeed Insights API key.  Pass ``None`` to skip.

    Returns:
        A dict with keys ``"lcp_ms"``, ``"fid_ms"``, ``"inp_ms"``, ``"cls"``
        and ``"findings"`` (list of finding dicts), or ``None`` on failure/skip.
    """
    if not api_key:
        logger.debug("fetch_core_web_vitals: no API key — skipping CWV check for %s", url)
        return None

    try:
        import httpx  # already a project dependency

        params = {
            "url": url,
            "key": api_key,
            "strategy": "mobile",
            "category": "performance",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(_PSI_API_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning(
            "fetch_core_web_vitals: API request failed for %s: %s", url, exc
        )
        return None

    try:
        audits = (
            data.get("lighthouseResult", {})
            .get("audits", {})
        )
        categories = (
            data.get("lighthouseResult", {})
            .get("categories", {})
            .get("performance", {})
        )

        def _metric(key: str) -> Optional[float]:
            item = audits.get(key, {})
            val = item.get("numericValue")
            return float(val) if val is not None else None

        lcp_ms = _metric("largest-contentful-paint")
        fid_ms = _metric("max-potential-fid")
        inp_ms = _metric("interaction-to-next-paint")
        cls = _metric("cumulative-layout-shift")
        perf_score = categories.get("score")

        cwv_findings: list[dict[str, Any]] = []

        if lcp_ms is not None and lcp_ms > _CWV_THRESHOLDS["LCP"]:
            cwv_findings.append(
                {
                    "metric": "LCP",
                    "value_ms": lcp_ms,
                    "threshold_ms": _CWV_THRESHOLDS["LCP"],
                    "severity": "high" if lcp_ms > 4000 else "medium",
                }
            )
        if inp_ms is not None and inp_ms > _CWV_THRESHOLDS["INP"]:
            cwv_findings.append(
                {
                    "metric": "INP",
                    "value_ms": inp_ms,
                    "threshold_ms": _CWV_THRESHOLDS["INP"],
                    "severity": "high" if inp_ms > 500 else "medium",
                }
            )
        elif fid_ms is not None and fid_ms > _CWV_THRESHOLDS["FID"]:
            cwv_findings.append(
                {
                    "metric": "FID",
                    "value_ms": fid_ms,
                    "threshold_ms": _CWV_THRESHOLDS["FID"],
                    "severity": "medium",
                }
            )
        if cls is not None and cls > _CWV_THRESHOLDS["CLS"]:
            cwv_findings.append(
                {
                    "metric": "CLS",
                    "value": cls,
                    "threshold": _CWV_THRESHOLDS["CLS"],
                    "severity": "medium" if cls < 0.25 else "high",
                }
            )

        return {
            "lcp_ms": lcp_ms,
            "fid_ms": fid_ms,
            "inp_ms": inp_ms,
            "cls": cls,
            "performance_score": perf_score,
            "findings": cwv_findings,
        }

    except Exception as exc:
        logger.warning(
            "fetch_core_web_vitals: failed to parse PSI response for %s: %s", url, exc
        )
        return None
