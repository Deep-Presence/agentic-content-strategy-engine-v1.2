"""Pure structural performance checks — no I/O, no external APIs.

These checks analyse HTML structure metrics (page size, resource counts,
render-blocking resources, image optimization, inline code weight) and
generate :class:`AuditFinding` objects for the performance dimension.
"""
from __future__ import annotations

from core.models.site_audit import AuditCheckSeverity, AuditDimension, AuditFinding
from core.site_audit.config import AuditConfig


def check_page_size(
    url: str,
    html_bytes: int,
    config: AuditConfig,
) -> list[AuditFinding]:
    """Flag pages with excessively large HTML.

    Args:
        url: Page URL.
        html_bytes: Raw HTML size in bytes.
        config: Audit config with ``html_warn_size_kb`` and ``html_max_size_kb``.

    Returns:
        List of findings (empty if within limits).
    """
    size_kb = html_bytes / 1024
    if size_kb > config.html_max_size_kb:
        return [
            AuditFinding(
                finding_type="oversized_html",
                dimension=AuditDimension.performance,
                severity=AuditCheckSeverity.high,
                url=url,
                message=(
                    f"HTML document is {size_kb:.0f}KB — exceeds "
                    f"{config.html_max_size_kb}KB limit."
                ),
                recommendation=(
                    "Reduce HTML payload by deferring non-critical content, "
                    "removing unused markup, or splitting into smaller pages."
                ),
                details={"html_bytes": html_bytes, "size_kb": round(size_kb, 1)},
            )
        ]
    if size_kb > config.html_warn_size_kb:
        return [
            AuditFinding(
                finding_type="large_html",
                dimension=AuditDimension.performance,
                severity=AuditCheckSeverity.medium,
                url=url,
                message=(
                    f"HTML document is {size_kb:.0f}KB — above "
                    f"{config.html_warn_size_kb}KB warning threshold."
                ),
                recommendation=(
                    "Consider reducing HTML size. Large HTML documents slow "
                    "down parsing and increase time to first render."
                ),
                details={"html_bytes": html_bytes, "size_kb": round(size_kb, 1)},
            )
        ]
    return []


def check_resource_counts(
    url: str,
    external_script_count: int,
    external_css_count: int,
    config: AuditConfig,
) -> list[AuditFinding]:
    """Flag pages with too many external resources (scripts + stylesheets).

    Args:
        url: Page URL.
        external_script_count: Number of ``<script src="...">`` tags.
        external_css_count: Number of ``<link rel="stylesheet">`` tags.
        config: Audit config with resource count thresholds.

    Returns:
        List of findings (empty if within limits).
    """
    total = external_script_count + external_css_count
    if total > config.max_external_resources_critical:
        return [
            AuditFinding(
                finding_type="excessive_external_resources",
                dimension=AuditDimension.performance,
                severity=AuditCheckSeverity.high,
                url=url,
                message=(
                    f"Page loads {total} external resources "
                    f"({external_script_count} scripts, {external_css_count} CSS)."
                ),
                recommendation=(
                    "Reduce external resource count by bundling scripts and "
                    "stylesheets, removing unused dependencies, or lazy-loading "
                    "non-critical resources."
                ),
                details={
                    "total": total,
                    "scripts": external_script_count,
                    "css": external_css_count,
                },
            )
        ]
    if total > config.max_external_resources_warn:
        return [
            AuditFinding(
                finding_type="many_external_resources",
                dimension=AuditDimension.performance,
                severity=AuditCheckSeverity.medium,
                url=url,
                message=(
                    f"Page loads {total} external resources "
                    f"({external_script_count} scripts, {external_css_count} CSS)."
                ),
                recommendation=(
                    "Consider bundling or reducing external resources to "
                    "improve page load performance."
                ),
                details={
                    "total": total,
                    "scripts": external_script_count,
                    "css": external_css_count,
                },
            )
        ]
    return []


def check_render_blocking(
    url: str,
    blocking_scripts: list[str],
    blocking_css: list[str],
    config: AuditConfig,
) -> list[AuditFinding]:
    """Flag pages with render-blocking resources in ``<head>``.

    Args:
        url: Page URL.
        blocking_scripts: URLs of ``<script>`` tags without async/defer/module.
        blocking_css: URLs of ``<link rel="stylesheet">`` without
            ``disabled`` or print-only ``media``.
        config: Audit config with render-blocking thresholds.

    Returns:
        List of findings (empty if within limits).
    """
    total = len(blocking_scripts) + len(blocking_css)
    if total > config.max_render_blocking_critical:
        return [
            AuditFinding(
                finding_type="excessive_render_blocking",
                dimension=AuditDimension.performance,
                severity=AuditCheckSeverity.high,
                url=url,
                message=(
                    f"Page has {total} render-blocking resources in <head> "
                    f"({len(blocking_scripts)} scripts, {len(blocking_css)} CSS)."
                ),
                recommendation=(
                    "Add async or defer to non-critical scripts. Use "
                    "media='print' or preload for non-critical stylesheets."
                ),
                details={
                    "total": total,
                    "blocking_scripts": blocking_scripts,
                    "blocking_css": blocking_css,
                },
            )
        ]
    if total > config.max_render_blocking_warn:
        return [
            AuditFinding(
                finding_type="render_blocking_resources",
                dimension=AuditDimension.performance,
                severity=AuditCheckSeverity.medium,
                url=url,
                message=(
                    f"Page has {total} render-blocking resources in <head>."
                ),
                recommendation=(
                    "Consider deferring non-critical scripts and stylesheets "
                    "to improve first paint time."
                ),
                details={
                    "total": total,
                    "blocking_scripts": blocking_scripts,
                    "blocking_css": blocking_css,
                },
            )
        ]
    return []


def check_image_optimization(
    url: str,
    images_without_lazy: int,
    images_without_dimensions: int,
    images_without_srcset: int,
    total_images: int,
    uses_modern_formats: bool,
    config: AuditConfig,
) -> list[AuditFinding]:
    """Flag image optimization issues.

    Args:
        url: Page URL.
        images_without_lazy: Count of ``<img>`` missing ``loading="lazy"``.
        images_without_dimensions: Count of ``<img>`` missing width/height.
        images_without_srcset: Count of ``<img>`` missing ``srcset``.
        total_images: Total ``<img>`` count on the page.
        uses_modern_formats: Whether any image uses webp/avif.
        config: Audit config (reserved for future thresholds).

    Returns:
        List of findings (may contain multiple).
    """
    if total_images == 0:
        return []

    findings: list[AuditFinding] = []

    # >50% missing lazy loading
    if images_without_lazy > total_images / 2:
        findings.append(
            AuditFinding(
                finding_type="images_missing_lazy_loading",
                dimension=AuditDimension.performance,
                severity=AuditCheckSeverity.medium,
                url=url,
                message=(
                    f"{images_without_lazy}/{total_images} images lack "
                    f'loading="lazy" attribute.'
                ),
                recommendation=(
                    'Add loading="lazy" to below-the-fold images to defer '
                    "offscreen image loading and reduce initial page weight."
                ),
                details={
                    "without_lazy": images_without_lazy,
                    "total": total_images,
                },
            )
        )

    # >50% missing width/height (CLS risk)
    if images_without_dimensions > total_images / 2:
        findings.append(
            AuditFinding(
                finding_type="images_missing_dimensions",
                dimension=AuditDimension.performance,
                severity=AuditCheckSeverity.medium,
                url=url,
                message=(
                    f"{images_without_dimensions}/{total_images} images lack "
                    f"explicit width/height attributes (CLS risk)."
                ),
                recommendation=(
                    "Set width and height attributes on images to reserve "
                    "layout space and prevent Cumulative Layout Shift."
                ),
                details={
                    "without_dimensions": images_without_dimensions,
                    "total": total_images,
                },
            )
        )

    # No srcset at all
    if images_without_srcset == total_images:
        findings.append(
            AuditFinding(
                finding_type="no_responsive_images",
                dimension=AuditDimension.performance,
                severity=AuditCheckSeverity.low,
                url=url,
                message="No images use srcset for responsive loading.",
                recommendation=(
                    "Use srcset attribute to serve appropriately sized "
                    "images for different viewport widths."
                ),
                details={"total": total_images},
            )
        )

    # No modern formats
    if not uses_modern_formats:
        findings.append(
            AuditFinding(
                finding_type="no_modern_image_formats",
                dimension=AuditDimension.performance,
                severity=AuditCheckSeverity.low,
                url=url,
                message="No images use modern formats (WebP/AVIF).",
                recommendation=(
                    "Serve images in WebP or AVIF format for smaller file "
                    "sizes and faster loading."
                ),
                details={"total": total_images},
            )
        )

    return findings


def check_inline_code_weight(
    url: str,
    inline_js_bytes: int,
    inline_css_bytes: int,
    config: AuditConfig,
) -> list[AuditFinding]:
    """Flag pages with excessive inline JavaScript or CSS.

    Args:
        url: Page URL.
        inline_js_bytes: Total bytes of inline ``<script>`` content.
        inline_css_bytes: Total bytes of inline ``<style>`` content.
        config: Audit config with inline code thresholds.

    Returns:
        List of findings (may contain multiple).
    """
    findings: list[AuditFinding] = []

    js_kb = inline_js_bytes / 1024
    if js_kb > config.inline_js_max_kb:
        findings.append(
            AuditFinding(
                finding_type="excessive_inline_js",
                dimension=AuditDimension.performance,
                severity=AuditCheckSeverity.high,
                url=url,
                message=f"Inline JavaScript is {js_kb:.0f}KB — exceeds {config.inline_js_max_kb}KB limit.",
                recommendation=(
                    "Move inline scripts to external files for better "
                    "caching and smaller HTML payload."
                ),
                details={"inline_js_bytes": inline_js_bytes, "js_kb": round(js_kb, 1)},
            )
        )
    elif js_kb > config.inline_js_warn_kb:
        findings.append(
            AuditFinding(
                finding_type="large_inline_js",
                dimension=AuditDimension.performance,
                severity=AuditCheckSeverity.medium,
                url=url,
                message=f"Inline JavaScript is {js_kb:.0f}KB — above {config.inline_js_warn_kb}KB warning.",
                recommendation=(
                    "Consider externalising large inline scripts for better "
                    "caching."
                ),
                details={"inline_js_bytes": inline_js_bytes, "js_kb": round(js_kb, 1)},
            )
        )

    css_kb = inline_css_bytes / 1024
    if css_kb > config.inline_css_max_kb:
        findings.append(
            AuditFinding(
                finding_type="excessive_inline_css",
                dimension=AuditDimension.performance,
                severity=AuditCheckSeverity.medium,
                url=url,
                message=f"Inline CSS is {css_kb:.0f}KB — exceeds {config.inline_css_max_kb}KB limit.",
                recommendation=(
                    "Move large inline stylesheets to external CSS files "
                    "for better caching."
                ),
                details={"inline_css_bytes": inline_css_bytes, "css_kb": round(css_kb, 1)},
            )
        )

    return findings
