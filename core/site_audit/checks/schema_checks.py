"""Schema detection and validation pure functions for the site audit pipeline.

All functions in this module are PURE — no I/O, no network calls, no side effects.
They take HTML strings or parsed data and return structured results.

Checks implemented:
    - JSON-LD block extraction (including @graph containers)
    - Schema type identification
    - Lightweight validation for Article, FAQPage, HowTo, Organization, BreadcrumbList
    - Page type inference from URL + HTML
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Match "application/ld+json" with optional charset suffix (case-insensitive).
_JSONLD_TYPE_RE = re.compile(r"^application/ld\+json\s*(;.*)?$", re.IGNORECASE)

# URI prefixes to strip from @type values.
_SCHEMA_ORG_PREFIXES = ("http://schema.org/", "https://schema.org/")

# Known schema types we recognise (subset of schema.org)
KNOWN_SCHEMA_TYPES: frozenset[str] = frozenset(
    {
        "Organization",
        "Article",
        "BlogPosting",
        "FAQPage",
        "HowTo",
        "Product",
        "BreadcrumbList",
        "LocalBusiness",
        "Person",
        "WebSite",
        "WebPage",
        "Speakable",
        "SpeakableSpecification",
    }
)


def parse_jsonld_blocks(html: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Extract all JSON-LD blocks from an HTML page.

    Handles:
    - Multiple ``<script type="application/ld+json">`` tags per page.
    - ``@graph`` containers (expands nested item array into flat list).
    - ``@type`` as both a string and a list.
    - Invalid JSON (skipped with error recorded).

    Args:
        html: Raw HTML string of the page.

    Returns:
        A 2-tuple of:
            - ``blocks``: Flat list of schema objects (dicts) found on the page.
              Each item from a ``@graph`` array is returned as its own entry.
            - ``errors``: List of human-readable parse/validation error strings.
    """
    blocks: list[dict[str, Any]] = []
    errors: list[str] = []

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as exc:  # pragma: no cover
        errors.append(f"HTML parse error: {exc}")
        return blocks, errors

    # Match type="application/ld+json" with optional charset suffix (case-insensitive)
    script_tags = soup.find_all("script", type=_JSONLD_TYPE_RE)
    for i, tag in enumerate(script_tags):
        # Use get_text() as fallback when tag.string is None (multi-node script content)
        raw_text = tag.string if tag.string is not None else tag.get_text()
        raw_text = raw_text.strip()
        if not raw_text:
            continue
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            errors.append(f"JSON-LD block {i + 1}: invalid JSON — {exc}")
            continue

        if isinstance(parsed, dict):
            # Handle @graph containers
            if "@graph" in parsed and isinstance(parsed["@graph"], list):
                for item in parsed["@graph"]:
                    if isinstance(item, dict):
                        blocks.append(item)
            else:
                blocks.append(parsed)
        elif isinstance(parsed, list):
            # Some implementations wrap everything in a JSON array
            for item in parsed:
                if isinstance(item, dict):
                    blocks.append(item)

    return blocks, errors


def _normalize_schema_type(raw_type: str) -> str:
    """Strip ``schema.org`` URI prefixes from a ``@type`` value.

    Converts ``"http://schema.org/Article"`` → ``"Article"`` etc.
    Short-form types like ``"Article"`` pass through unchanged.
    """
    for prefix in _SCHEMA_ORG_PREFIXES:
        if raw_type.startswith(prefix):
            return raw_type[len(prefix):]
    return raw_type


def identify_schema_types(blocks: list[dict[str, Any]]) -> list[str]:
    """Extract ``@type`` values from a list of schema blocks.

    Handles ``@type`` as both a string and a list of strings.
    URI-style values (``http://schema.org/Article``) are normalised to
    short form (``Article``).  Deduplicates while preserving order of
    first occurrence.

    Args:
        blocks: List of schema objects (typically from :func:`parse_jsonld_blocks`).

    Returns:
        Deduplicated list of normalised ``@type`` string values found
        across all blocks.
    """
    seen: set[str] = set()
    types: list[str] = []

    for block in blocks:
        raw_type = block.get("@type")
        if raw_type is None:
            continue
        if isinstance(raw_type, str):
            candidates = [raw_type]
        elif isinstance(raw_type, list):
            candidates = [t for t in raw_type if isinstance(t, str)]
        else:
            continue

        for t in candidates:
            normalized = _normalize_schema_type(t)
            if normalized not in seen:
                seen.add(normalized)
                types.append(normalized)

    return types


def validate_article_schema(block: dict[str, Any]) -> list[str]:
    """Validate an Article or BlogPosting schema block.

    Required fields: ``headline``, ``author`` (or ``author.name``), ``datePublished``.
    Optional (warning if absent): ``image``, ``dateModified``.

    Args:
        block: A single schema.org Article or BlogPosting object dict.

    Returns:
        List of validation error/warning strings.  Empty list = valid.
    """
    errors: list[str] = []

    if not block.get("headline"):
        errors.append("Article/BlogPosting missing required field: headline")

    author = block.get("author")
    if not author:
        errors.append("Article/BlogPosting missing required field: author")
    elif isinstance(author, dict) and not author.get("name"):
        errors.append("Article/BlogPosting author object missing field: name")
    elif isinstance(author, list):
        for idx, a in enumerate(author):
            if isinstance(a, dict) and not a.get("name"):
                errors.append(
                    f"Article/BlogPosting author[{idx}] object missing field: name"
                )

    if not block.get("datePublished"):
        errors.append("Article/BlogPosting missing required field: datePublished")

    # Optional warnings
    if not block.get("image"):
        errors.append("Article/BlogPosting missing recommended field: image")
    if not block.get("dateModified"):
        errors.append("Article/BlogPosting missing recommended field: dateModified")

    return errors


def validate_faq_schema(block: dict[str, Any]) -> list[str]:
    """Validate a FAQPage schema block.

    Required: ``mainEntity`` array where each item has ``@type: Question``,
    ``name`` (the question text), and ``acceptedAnswer`` with ``text``.

    Args:
        block: A single schema.org FAQPage object dict.

    Returns:
        List of validation error/warning strings.  Empty list = valid.
    """
    errors: list[str] = []

    main_entity = block.get("mainEntity")
    if main_entity is None or not isinstance(main_entity, list):
        errors.append("FAQPage missing required field: mainEntity (must be a list)")
        return errors

    if len(main_entity) == 0:
        errors.append("FAQPage mainEntity array is empty — no questions defined")
        return errors

    for idx, item in enumerate(main_entity):
        if not isinstance(item, dict):
            errors.append(f"FAQPage mainEntity[{idx}] is not an object")
            continue

        raw_type = item.get("@type")
        type_values = (
            [raw_type] if isinstance(raw_type, str) else (raw_type if isinstance(raw_type, list) else [])
        )
        if "Question" not in type_values:
            errors.append(
                f"FAQPage mainEntity[{idx}] missing @type: Question "
                f"(found {raw_type!r})"
            )

        if not item.get("name"):
            errors.append(f"FAQPage mainEntity[{idx}] missing field: name (the question text)")

        accepted_answer = item.get("acceptedAnswer")
        if not accepted_answer:
            errors.append(
                f"FAQPage mainEntity[{idx}] missing field: acceptedAnswer"
            )
        elif not isinstance(accepted_answer, dict):
            errors.append(
                f"FAQPage mainEntity[{idx}].acceptedAnswer must be an object, "
                f"got {type(accepted_answer).__name__}"
            )
        elif not accepted_answer.get("text"):
            errors.append(
                f"FAQPage mainEntity[{idx}].acceptedAnswer missing field: text"
            )

    return errors


def validate_howto_schema(block: dict[str, Any]) -> list[str]:
    """Validate a HowTo schema block.

    Required: ``name``, ``step`` array where each step has ``text`` or
    ``itemListElement``.

    Args:
        block: A single schema.org HowTo object dict.

    Returns:
        List of validation error/warning strings.  Empty list = valid.
    """
    errors: list[str] = []

    if not block.get("name"):
        errors.append("HowTo missing required field: name")

    steps = block.get("step")
    if not steps or not isinstance(steps, list):
        errors.append("HowTo missing required field: step (must be a list)")
        return errors

    if len(steps) == 0:
        errors.append("HowTo step list is empty — no steps defined")
        return errors

    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            errors.append(f"HowTo step[{idx}] is not an object")
            continue
        if not step.get("text") and not step.get("itemListElement"):
            errors.append(
                f"HowTo step[{idx}] missing required field: text or itemListElement"
            )

    return errors


def validate_organization_schema(block: dict[str, Any]) -> list[str]:
    """Validate an Organization schema block.

    Required: ``name``, ``url``.
    Optional (warning if absent): ``logo``.

    Args:
        block: A single schema.org Organization object dict.

    Returns:
        List of validation error/warning strings.  Empty list = valid.
    """
    errors: list[str] = []

    if not block.get("name"):
        errors.append("Organization missing required field: name")

    if not block.get("url"):
        errors.append("Organization missing required field: url")

    if not block.get("logo"):
        errors.append("Organization missing recommended field: logo")

    return errors


def validate_breadcrumb_schema(block: dict[str, Any]) -> list[str]:
    """Validate a BreadcrumbList schema block.

    Required: ``itemListElement`` array where each item has ``position`` and ``name``.

    Args:
        block: A single schema.org BreadcrumbList object dict.

    Returns:
        List of validation error/warning strings.  Empty list = valid.
    """
    errors: list[str] = []

    items = block.get("itemListElement")
    if items is None or not isinstance(items, list):
        errors.append(
            "BreadcrumbList missing required field: itemListElement (must be a list)"
        )
        return errors

    if len(items) == 0:
        errors.append("BreadcrumbList itemListElement array is empty")
        return errors

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"BreadcrumbList itemListElement[{idx}] is not an object")
            continue
        if item.get("position") is None:
            errors.append(
                f"BreadcrumbList itemListElement[{idx}] missing field: position"
            )
        # item["name"] can be a direct string, or nested in item["item"] which may be
        # a dict {"@type": "Thing", "name": "..."} OR a plain string URL — guard both
        nested_item = item.get("item")
        nested_name = (
            nested_item.get("name", "") if isinstance(nested_item, dict) else ""
        )
        if not item.get("name") and not nested_name:
            errors.append(
                f"BreadcrumbList itemListElement[{idx}] missing field: name"
            )

    return errors


def infer_page_type(url: str, html: str) -> str:  # noqa: ARG001
    """Infer the page type from the URL path using heuristics.

    Heuristics applied in priority order:
    - ``/blog/``, ``/posts/``, ``/articles/`` → ``"article"``
    - ``/product/``, ``/shop/`` → ``"product"``
    - ``/faq/``, ``/help/`` → ``"faq"``
    - ``/about/`` → ``"about"``
    - ``/pricing/`` → ``"pricing"``
    - Root path (``"/"`` or empty) → ``"homepage"``
    - Default → ``"page"``

    Args:
        url: Full URL of the page.
        html: Raw HTML of the page (reserved for future HTML-based heuristics;
            not currently used).

    Returns:
        A lowercase string page type identifier.
    """
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        path = parsed.path.lower()
    except Exception:
        path = ""

    # Homepage detection
    if path in ("", "/", "//"):
        return "homepage"

    # Path-based heuristics
    path_checks: list[tuple[list[str], str]] = [
        (["/blog/", "/posts/", "/articles/"], "article"),
        (["/product/", "/shop/"], "product"),
        (["/faq/", "/help/"], "faq"),
        (["/about/"], "about"),
        (["/pricing/"], "pricing"),
    ]
    for patterns, page_type in path_checks:
        for pattern in patterns:
            if pattern in path:
                return page_type

    # Also check trailing path component (e.g. /blog not /blog/)
    segments = [s for s in path.split("/") if s]
    if segments:
        last = f"/{segments[-1]}"
        for patterns, page_type in path_checks:
            for pattern in patterns:
                if last == pattern.rstrip("/"):
                    return page_type
        first = f"/{segments[0]}"
        for patterns, page_type in path_checks:
            for pattern in patterns:
                if first == pattern.rstrip("/"):
                    return page_type

    return "page"


def validate_product_schema(block: dict[str, Any]) -> list[str]:
    """Validate a Product schema block.

    Required: ``name``, pricing info (``offers`` OR ``price`` + ``priceCurrency``).
    Recommended (warning if absent): ``description``, ``image``, ``brand``, ``sku``.

    Args:
        block: A single schema.org Product object dict.

    Returns:
        List of validation error/warning strings.  Empty list = valid.
    """
    errors: list[str] = []

    if not block.get("name"):
        errors.append("Product missing required field: name")

    has_offers = bool(block.get("offers"))
    has_price = bool(block.get("price")) and bool(block.get("priceCurrency"))
    if not has_offers and not has_price:
        errors.append("Product missing pricing information: needs offers or price+priceCurrency")

    # Recommended warnings
    if not block.get("description"):
        errors.append("Product missing recommended field: description")
    if not block.get("image"):
        errors.append("Product missing recommended field: image")
    if not block.get("brand"):
        errors.append("Product missing recommended field: brand")
    if not block.get("sku"):
        errors.append("Product missing recommended field: sku")

    return errors


def validate_speakable_schema(block: dict[str, Any]) -> list[str]:
    """Validate a Speakable / SpeakableSpecification schema block.

    Required: ``cssSelector`` OR ``xpath``.
    Recommended (warning if absent): ``name``.

    Args:
        block: A single schema.org Speakable object dict.

    Returns:
        List of validation error/warning strings.  Empty list = valid.
    """
    errors: list[str] = []

    has_css = bool(block.get("cssSelector"))
    has_xpath = bool(block.get("xpath"))
    if not has_css and not has_xpath:
        errors.append("Speakable missing content selector: needs cssSelector or xpath")

    if not block.get("name"):
        errors.append("Speakable missing recommended field: name")

    return errors


def validate_schema_block(
    block: dict[str, Any],
) -> list[str]:
    """Dispatch validation to the correct validator based on ``@type``.

    Only validates known, supported types.  Unknown types are not validated
    and return an empty error list.

    Args:
        block: A single schema object dict.

    Returns:
        List of validation error/warning strings.  Empty if valid or unknown type.
    """
    raw_type = block.get("@type")
    if raw_type is None:
        return []

    types: list[str] = (
        [raw_type] if isinstance(raw_type, str) else
        raw_type if isinstance(raw_type, list) else []
    )

    all_errors: list[str] = []
    for t in (_normalize_schema_type(t) for t in types):
        if t in ("Article", "BlogPosting"):
            all_errors.extend(validate_article_schema(block))
            break  # Don't double-validate if both types appear
        elif t == "FAQPage":
            all_errors.extend(validate_faq_schema(block))
            break
        elif t == "HowTo":
            all_errors.extend(validate_howto_schema(block))
            break
        elif t == "Organization":
            all_errors.extend(validate_organization_schema(block))
            break
        elif t == "BreadcrumbList":
            all_errors.extend(validate_breadcrumb_schema(block))
            break
        elif t == "Product":
            all_errors.extend(validate_product_schema(block))
            break
        elif t in ("Speakable", "SpeakableSpecification"):
            all_errors.extend(validate_speakable_schema(block))
            break

    return all_errors
