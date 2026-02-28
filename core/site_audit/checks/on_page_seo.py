"""On-page SEO check functions for the site audit pipeline.

All functions are PURE — no I/O, no network calls, no side effects.
Each takes relevant page signals and returns list[AuditFinding].

Checks:
    - Title tag presence, length, and boilerplate detection
    - Meta description presence and length
    - H1 presence and uniqueness
    - Heading hierarchy (no skipped levels)
    - Image alt text coverage
    - Internal link count
"""
from __future__ import annotations

from core.models.site_audit import AuditCheckSeverity, AuditDimension, AuditFinding
from core.site_audit.config import AuditConfig, DEFAULT_AUDIT_CONFIG

#: Boilerplate title strings that add no SEO value.
_BOILERPLATE_TITLES: frozenset[str] = frozenset({
    "home",
    "untitled",
    "untitled document",
    "page",
    "new page",
    "index",
    "welcome",
})


def check_title(
    url: str,
    title: str,
    title_length: int,
    config: AuditConfig = DEFAULT_AUDIT_CONFIG,
) -> list[AuditFinding]:
    """Generate findings for missing, short, long, or boilerplate titles.

    Args:
        url: Page URL.
        title: The ``<title>`` tag content (empty string if absent).
        title_length: Character length of *title*.
        config: Audit configuration providing ``title_min_length`` and
            ``title_max_length`` thresholds.

    Returns:
        List of :class:`AuditFinding` objects.
    """
    findings: list[AuditFinding] = []

    if not title:
        findings.append(
            AuditFinding(
                finding_type="missing_title",
                dimension=AuditDimension.on_page_seo,
                severity=AuditCheckSeverity.critical,
                url=url,
                message="Page is missing a <title> tag.",
                recommendation=(
                    "Add a descriptive <title> tag between "
                    f"{config.title_min_length} and {config.title_max_length} characters."
                ),
                details={},
            )
        )
        return findings

    # Boilerplate check
    if title.strip().lower() in _BOILERPLATE_TITLES:
        findings.append(
            AuditFinding(
                finding_type="boilerplate_title",
                dimension=AuditDimension.on_page_seo,
                severity=AuditCheckSeverity.high,
                url=url,
                message=f"Title '{title}' appears to be a boilerplate/placeholder.",
                recommendation=(
                    "Replace with a descriptive title that includes the page's "
                    "primary keyword and brand name."
                ),
                details={"title": title},
            )
        )
        return findings

    if title_length < config.title_min_length:
        findings.append(
            AuditFinding(
                finding_type="title_too_short",
                dimension=AuditDimension.on_page_seo,
                severity=AuditCheckSeverity.high,
                url=url,
                message=(
                    f"Title is too short ({title_length} chars; "
                    f"minimum: {config.title_min_length})."
                ),
                recommendation=(
                    f"Expand the title to at least {config.title_min_length} characters "
                    "to improve keyword coverage and click-through rates."
                ),
                details={"title_length": title_length, "min": config.title_min_length},
            )
        )
    elif title_length > config.title_max_length:
        findings.append(
            AuditFinding(
                finding_type="title_too_long",
                dimension=AuditDimension.on_page_seo,
                severity=AuditCheckSeverity.high,
                url=url,
                message=(
                    f"Title is too long ({title_length} chars; "
                    f"maximum: {config.title_max_length})."
                ),
                recommendation=(
                    f"Shorten the title to {config.title_max_length} characters or fewer "
                    "to prevent truncation in search and AI results."
                ),
                details={"title_length": title_length, "max": config.title_max_length},
            )
        )

    return findings


def check_meta_description(
    url: str,
    meta_desc: str,
    meta_length: int,
    config: AuditConfig = DEFAULT_AUDIT_CONFIG,
) -> list[AuditFinding]:
    """Generate findings for missing, short, or long meta descriptions.

    Args:
        url: Page URL.
        meta_desc: Meta description content (empty string if absent).
        meta_length: Character length of *meta_desc*.
        config: Audit configuration providing ``meta_min_length`` and
            ``meta_max_length`` thresholds.

    Returns:
        List of :class:`AuditFinding` objects.
    """
    findings: list[AuditFinding] = []

    if not meta_desc:
        findings.append(
            AuditFinding(
                finding_type="missing_meta_description",
                dimension=AuditDimension.on_page_seo,
                severity=AuditCheckSeverity.high,
                url=url,
                message="Page is missing a meta description.",
                recommendation=(
                    "Add a meta description between "
                    f"{config.meta_min_length} and {config.meta_max_length} characters "
                    "summarising the page content."
                ),
                details={},
            )
        )
        return findings

    if meta_length < config.meta_min_length:
        findings.append(
            AuditFinding(
                finding_type="meta_description_too_short",
                dimension=AuditDimension.on_page_seo,
                severity=AuditCheckSeverity.medium,
                url=url,
                message=(
                    f"Meta description is too short ({meta_length} chars; "
                    f"minimum: {config.meta_min_length})."
                ),
                recommendation=(
                    f"Expand the meta description to at least {config.meta_min_length} "
                    "characters to improve snippet quality in AI and search results."
                ),
                details={"meta_length": meta_length, "min": config.meta_min_length},
            )
        )
    elif meta_length > config.meta_max_length:
        findings.append(
            AuditFinding(
                finding_type="meta_description_too_long",
                dimension=AuditDimension.on_page_seo,
                severity=AuditCheckSeverity.medium,
                url=url,
                message=(
                    f"Meta description is too long ({meta_length} chars; "
                    f"maximum: {config.meta_max_length})."
                ),
                recommendation=(
                    f"Shorten the meta description to {config.meta_max_length} characters "
                    "or fewer to avoid truncation."
                ),
                details={"meta_length": meta_length, "max": config.meta_max_length},
            )
        )

    return findings


def check_h1(url: str, h1_count: int, h1_text: str) -> list[AuditFinding]:
    """Generate findings for missing or duplicate H1 tags.

    Args:
        url: Page URL.
        h1_count: Number of ``<h1>`` elements on the page.
        h1_text: Text content of the first H1 (empty if none).

    Returns:
        List of :class:`AuditFinding` objects.
    """
    findings: list[AuditFinding] = []

    if h1_count == 0:
        findings.append(
            AuditFinding(
                finding_type="missing_h1",
                dimension=AuditDimension.on_page_seo,
                severity=AuditCheckSeverity.critical,
                url=url,
                message="Page has no H1 heading.",
                recommendation=(
                    "Add exactly one H1 tag containing the page's primary keyword. "
                    "AI models use the H1 as a strong signal for page topic."
                ),
                details={"h1_count": h1_count},
            )
        )
    elif h1_count > 1:
        findings.append(
            AuditFinding(
                finding_type="multiple_h1",
                dimension=AuditDimension.on_page_seo,
                severity=AuditCheckSeverity.high,
                url=url,
                message=f"Page has {h1_count} H1 headings (should be exactly 1).",
                recommendation=(
                    "Consolidate to a single H1. Use H2–H6 for sub-sections. "
                    "Multiple H1s dilute topic focus."
                ),
                details={"h1_count": h1_count, "h1_text": h1_text},
            )
        )

    return findings


def check_heading_hierarchy(
    url: str, headings: list[dict[str, str]]
) -> list[AuditFinding]:
    """Generate findings when heading levels are skipped.

    A valid heading hierarchy does not skip levels: H1 → H2 → H3 is valid,
    but H1 → H3 (skipping H2) is a violation.

    Args:
        url: Page URL.
        headings: Ordered list of heading dicts, each with keys ``"level"``
            (e.g. ``"h2"``) and ``"text"``.

    Returns:
        List of :class:`AuditFinding` objects.
    """
    if not headings:
        return []

    violations: list[dict[str, str | int]] = []
    prev_level = 0

    for heading in headings:
        level_str = (heading.get("level") or "").lower()
        if not level_str or not level_str.startswith("h"):
            continue
        try:
            level = int(level_str[1:])
        except (ValueError, IndexError):
            continue

        if prev_level > 0 and level > prev_level + 1:
            violations.append({
                "from_level": prev_level,
                "to_level": level,
                "text": heading.get("text", ""),
            })
        prev_level = level

    if not violations:
        return []

    return [
        AuditFinding(
            finding_type="heading_hierarchy_skip",
            dimension=AuditDimension.on_page_seo,
            severity=AuditCheckSeverity.medium,
            url=url,
            message=(
                f"Heading hierarchy skips level(s): "
                + ", ".join(
                    f"H{v['from_level']}→H{v['to_level']}" for v in violations
                )
            ),
            recommendation=(
                "Ensure headings follow a sequential hierarchy (H1→H2→H3). "
                "Skipped levels confuse screen readers and AI content parsers."
            ),
            details={"violations": violations},
        )
    ]


def check_images(
    url: str, total: int, without_alt: int
) -> list[AuditFinding]:
    """Generate findings when images are missing alt text.

    Args:
        url: Page URL.
        total: Total number of ``<img>`` elements on the page.
        without_alt: Number of ``<img>`` elements without an alt attribute
            (or with empty alt).

    Returns:
        List of :class:`AuditFinding` objects.
    """
    findings: list[AuditFinding] = []

    if total == 0:
        return findings

    if without_alt > 0:
        ratio = without_alt / total
        if ratio > 0.5:
            findings.append(
                AuditFinding(
                    finding_type="images_missing_alt_majority",
                    dimension=AuditDimension.on_page_seo,
                    severity=AuditCheckSeverity.high,
                    url=url,
                    message=(
                        f"{without_alt} of {total} images ({ratio:.0%}) are missing alt text."
                    ),
                    recommendation=(
                        "Add descriptive alt text to all meaningful images. "
                        "Alt text is used by AI models for content understanding."
                    ),
                    details={
                        "total_images": total,
                        "without_alt": without_alt,
                        "ratio": round(ratio, 3),
                    },
                )
            )
        else:
            findings.append(
                AuditFinding(
                    finding_type="images_missing_alt",
                    dimension=AuditDimension.on_page_seo,
                    severity=AuditCheckSeverity.medium,
                    url=url,
                    message=(
                        f"{without_alt} of {total} images are missing alt text."
                    ),
                    recommendation=(
                        "Add descriptive alt text to all images that convey information."
                    ),
                    details={
                        "total_images": total,
                        "without_alt": without_alt,
                        "ratio": round(ratio, 3),
                    },
                )
            )

    return findings


def check_internal_links(url: str, count: int) -> list[AuditFinding]:
    """Generate a finding when a page has no internal links.

    Pages with zero internal links are isolated nodes that receive no link
    equity and are harder for crawlers to discover or re-discover.

    Args:
        url: Page URL.
        count: Number of internal links on the page.

    Returns:
        List of :class:`AuditFinding` objects.
    """
    if count > 0:
        return []

    return [
        AuditFinding(
            finding_type="no_internal_links",
            dimension=AuditDimension.on_page_seo,
            severity=AuditCheckSeverity.medium,
            url=url,
            message="Page has no internal links.",
            recommendation=(
                "Add at least 2–3 internal links to related pages. "
                "Internal links help AI crawlers discover related content and "
                "distribute link equity across the site."
            ),
            details={"internal_link_count": count},
        )
    ]
