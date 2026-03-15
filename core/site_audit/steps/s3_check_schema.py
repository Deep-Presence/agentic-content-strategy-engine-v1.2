"""Step 3 — JSON-LD structured data detection and validation.

Parses every crawled page's HTML for ``<script type="application/ld+json">``
blocks, validates known schema types, infers the page type from the URL,
and generates :class:`AuditFinding` objects for missing or malformed schema.

Public API::

    result = detect_schema(html, url)
    findings = generate_schema_findings(url, result)

All checks are deterministic — no LLM calls, no network calls.
"""
from __future__ import annotations

import logging
from typing import Any

from core.models.site_audit import (
    AuditCheckSeverity,
    AuditDimension,
    AuditFinding,
    SchemaDetectionResult,
)
from core.site_audit.checks.schema_checks import (
    identify_schema_types,
    infer_page_type,
    parse_jsonld_blocks,
    validate_schema_block,
)

logger = logging.getLogger(__name__)


def detect_schema(html: str, url: str) -> SchemaDetectionResult:
    """Detect and validate JSON-LD structured data in a page's HTML.

    Steps:
    1. Parse all ``<script type="application/ld+json">`` blocks.
    2. Extract and deduplicate ``@type`` values.
    3. Run lightweight validation on known schema types.
    4. Infer the page type from the URL.

    Args:
        html: Raw HTML string of the page.
        url: Full URL of the page (used for page-type inference and logging).

    Returns:
        A :class:`SchemaDetectionResult` with all discovered schema information
        and any validation errors.
    """
    blocks, parse_errors = parse_jsonld_blocks(html)

    # Validate each block and collect errors
    all_validation_errors: list[str] = []
    all_validation_errors.extend(parse_errors)

    for block_idx, block in enumerate(blocks):
        try:
            block_errors = validate_schema_block(block)
            all_validation_errors.extend(block_errors)
        except Exception as exc:
            logger.warning(
                "detect_schema: unexpected error validating block %d for %s: %s",
                block_idx,
                url,
                exc,
            )
            all_validation_errors.append(
                f"Schema block {block_idx + 1}: validation failed unexpectedly — {exc}"
            )

    schema_types = identify_schema_types(blocks)
    has_schema = len(blocks) > 0 and len(schema_types) > 0

    page_type = infer_page_type(url, html)

    return SchemaDetectionResult(
        has_schema=has_schema,
        schema_types=schema_types,
        raw_jsonld_blocks=blocks,
        validation_errors=all_validation_errors,
        inferred_page_type=page_type,
    )


def generate_schema_findings(
    url: str,
    result: SchemaDetectionResult,
) -> list[AuditFinding]:
    """Generate audit findings for missing or malformed structured data.

    Finding rules (evaluated by page type):
    - ``"homepage"`` without ``Organization`` schema → **medium**
    - ``"article"`` without ``Article`` or ``BlogPosting`` schema → **high**
    - ``"faq"`` without ``FAQPage`` schema → **high**
    - ``"product"`` without ``Product`` schema → **medium**
    - Any page without ``BreadcrumbList`` schema → **low**
    - Schema present but has validation errors → **medium** per error

    Args:
        url: Full URL of the page (included in each finding).
        result: Output from :func:`detect_schema`.

    Returns:
        List of :class:`AuditFinding` objects.  May be empty if schema is complete
        and valid.
    """
    findings: list[AuditFinding] = []
    page_type = result.inferred_page_type
    schema_types_set = set(result.schema_types)

    # --- Missing recommended schema by page type ---
    if page_type == "homepage" and "Organization" not in schema_types_set:
        findings.append(
            AuditFinding(
                finding_type="missing_organization_schema",
                dimension=AuditDimension.schema_markup,
                severity=AuditCheckSeverity.medium,
                url=url,
                message=(
                    "Homepage is missing Organization schema markup. "
                    "AI engines use Organization schema to establish entity identity."
                ),
                recommendation=(
                    "Add an Organization JSON-LD block to your homepage with at least "
                    "name, url, and logo properties."
                ),
                details={"page_type": page_type, "found_types": result.schema_types},
            )
        )

    if page_type == "homepage" and "WebSite" not in schema_types_set:
        findings.append(
            AuditFinding(
                finding_type="missing_website_schema",
                dimension=AuditDimension.schema_markup,
                severity=AuditCheckSeverity.medium,
                url=url,
                message=(
                    "Homepage is missing WebSite schema markup. "
                    "WebSite schema with SearchAction helps AI engines "
                    "understand your site's search capabilities."
                ),
                recommendation=(
                    "Add a WebSite JSON-LD block to your homepage with url, name, "
                    "and a SearchAction potentialAction."
                ),
                details={"page_type": page_type, "found_types": result.schema_types},
            )
        )

    if page_type == "article" and not (
        "Article" in schema_types_set or "BlogPosting" in schema_types_set
    ):
        findings.append(
            AuditFinding(
                finding_type="missing_article_schema",
                dimension=AuditDimension.schema_markup,
                severity=AuditCheckSeverity.high,
                url=url,
                message=(
                    "Article page is missing Article or BlogPosting schema. "
                    "AI engines use Article schema to identify authoritative content."
                ),
                recommendation=(
                    "Add an Article or BlogPosting JSON-LD block with headline, "
                    "author, datePublished, and image fields."
                ),
                details={"page_type": page_type, "found_types": result.schema_types},
            )
        )

    if page_type == "faq" and "FAQPage" not in schema_types_set:
        findings.append(
            AuditFinding(
                finding_type="missing_faqpage_schema",
                dimension=AuditDimension.schema_markup,
                severity=AuditCheckSeverity.high,
                url=url,
                message=(
                    "FAQ page is missing FAQPage schema. "
                    "FAQPage schema dramatically increases the chance of AI engines "
                    "citing individual Q&A pairs."
                ),
                recommendation=(
                    "Add a FAQPage JSON-LD block with mainEntity array listing each "
                    "question (name) and its acceptedAnswer (text)."
                ),
                details={"page_type": page_type, "found_types": result.schema_types},
            )
        )

    if page_type == "product" and "Product" not in schema_types_set:
        findings.append(
            AuditFinding(
                finding_type="missing_product_schema",
                dimension=AuditDimension.schema_markup,
                severity=AuditCheckSeverity.medium,
                url=url,
                message=(
                    "Product page is missing Product schema. "
                    "Product schema helps AI engines extract pricing and feature data."
                ),
                recommendation=(
                    "Add a Product JSON-LD block with name, description, "
                    "and offers properties."
                ),
                details={"page_type": page_type, "found_types": result.schema_types},
            )
        )

    # --- Missing BreadcrumbList (applies to all pages) ---
    if "BreadcrumbList" not in schema_types_set:
        findings.append(
            AuditFinding(
                finding_type="missing_breadcrumb_schema",
                dimension=AuditDimension.schema_markup,
                severity=AuditCheckSeverity.low,
                url=url,
                message="Page is missing BreadcrumbList schema.",
                recommendation=(
                    "Add a BreadcrumbList JSON-LD block to help AI engines understand "
                    "the page's position in the site hierarchy."
                ),
                details={"page_type": page_type, "found_types": result.schema_types},
            )
        )

    # --- Validation errors for present schema ---
    for error in result.validation_errors:
        findings.append(
            AuditFinding(
                finding_type="schema_validation_error",
                dimension=AuditDimension.schema_markup,
                severity=AuditCheckSeverity.medium,
                url=url,
                message=f"Schema validation error: {error}",
                recommendation=(
                    "Fix the schema markup error to ensure AI engines can parse and "
                    "trust the structured data on this page."
                ),
                details={"validation_error": error},
            )
        )

    return findings
