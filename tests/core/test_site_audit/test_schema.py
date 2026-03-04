"""Tests for schema detection and validation (s3_check_schema + schema_checks).

Coverage:
    - parse_jsonld_blocks: valid single type, @graph, multiple blocks,
      invalid JSON, @type as array, nested objects, empty script tag, @graph with non-dicts
    - identify_schema_types: deduplication, mixed str/list @type
    - Validators: Article (valid + missing fields), FAQPage (valid + missing mainEntity +
      missing Q/A fields), HowTo (valid + missing name/step), Organization (valid + missing),
      BreadcrumbList (valid + missing items)
    - infer_page_type: /blog/, /posts/, /articles/, /product/, /shop/, /faq/, /help/,
      /about/, /pricing/, /, /random-path, bare segments (no trailing slash)
    - detect_schema (integration): with and without schema, @graph, validation errors
    - generate_schema_findings: homepage, article, faq, product pages; breadcrumb always;
      validation errors; correct severities; page WITH correct schema → no findings
"""
from __future__ import annotations

import json

import pytest

from core.models.site_audit import AuditCheckSeverity, AuditDimension, SchemaDetectionResult
from core.site_audit.checks.schema_checks import (
    identify_schema_types,
    infer_page_type,
    parse_jsonld_blocks,
    validate_article_schema,
    validate_breadcrumb_schema,
    validate_faq_schema,
    validate_howto_schema,
    validate_organization_schema,
    validate_product_schema,
    validate_schema_block,
    validate_speakable_schema,
)
from core.site_audit.steps.s3_check_schema import detect_schema, generate_schema_findings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE_URL = "https://example.com"


def _make_html(jsonld_blocks: list[dict]) -> str:
    """Wrap JSON-LD blocks in a minimal HTML page."""
    scripts = ""
    for block in jsonld_blocks:
        scripts += f'<script type="application/ld+json">{json.dumps(block)}</script>\n'
    return f"""<!DOCTYPE html>
<html>
<head><title>Test Page</title>{scripts}</head>
<body><p>Content here for testing purposes only.</p></body>
</html>"""


def _make_html_raw(raw_script: str) -> str:
    """Wrap a raw script string in a minimal HTML page."""
    return f"""<!DOCTYPE html>
<html>
<head>{raw_script}</head>
<body><p>Content.</p></body>
</html>"""


# ---------------------------------------------------------------------------
# parse_jsonld_blocks
# ---------------------------------------------------------------------------


class TestParseJsonldBlocks:
    def test_single_valid_block(self) -> None:
        html = _make_html([{"@type": "Organization", "name": "Acme", "url": "https://acme.com"}])
        blocks, errors = parse_jsonld_blocks(html)
        assert len(blocks) == 1
        assert blocks[0]["@type"] == "Organization"
        assert errors == []

    def test_graph_container_is_expanded(self) -> None:
        """@graph containers must be expanded into individual items."""
        graph_data = {
            "@context": "https://schema.org",
            "@graph": [
                {"@type": "Organization", "name": "Acme", "url": "https://acme.com"},
                {"@type": "WebSite", "url": "https://acme.com"},
            ],
        }
        html = _make_html_raw(
            f'<script type="application/ld+json">{json.dumps(graph_data)}</script>'
        )
        blocks, errors = parse_jsonld_blocks(html)
        assert len(blocks) == 2
        types = {b["@type"] for b in blocks}
        assert "Organization" in types
        assert "WebSite" in types
        assert errors == []

    def test_multiple_jsonld_blocks(self) -> None:
        """Multiple <script> tags on the same page must all be collected."""
        html = _make_html(
            [
                {"@type": "Organization", "name": "Acme", "url": "https://acme.com"},
                {"@type": "BreadcrumbList", "itemListElement": []},
            ]
        )
        blocks, errors = parse_jsonld_blocks(html)
        assert len(blocks) == 2
        assert errors == []

    def test_invalid_json_does_not_crash(self) -> None:
        """Invalid JSON inside a <script> tag must produce an error, not an exception."""
        bad_html = _make_html_raw('<script type="application/ld+json">{ not valid json }</script>')
        blocks, errors = parse_jsonld_blocks(bad_html)
        assert blocks == []
        assert len(errors) == 1
        assert "invalid JSON" in errors[0].lower() or "json" in errors[0].lower()

    def test_type_as_array(self) -> None:
        """@type may be a list of strings — should be preserved in raw blocks."""
        html = _make_html([{"@type": ["Article", "BlogPosting"], "headline": "Test"}])
        blocks, errors = parse_jsonld_blocks(html)
        assert len(blocks) == 1
        assert isinstance(blocks[0]["@type"], list)
        assert "Article" in blocks[0]["@type"]
        assert errors == []

    def test_nested_objects_preserved(self) -> None:
        """Nested objects (e.g., author with name) must be kept as-is."""
        block = {
            "@type": "Article",
            "headline": "Test Article",
            "author": {"@type": "Person", "name": "Jane Doe"},
            "datePublished": "2024-01-01",
        }
        html = _make_html([block])
        blocks, errors = parse_jsonld_blocks(html)
        assert blocks[0]["author"]["name"] == "Jane Doe"

    def test_empty_script_tag_skipped(self) -> None:
        """Empty <script> tags must produce no blocks and no errors."""
        html = _make_html_raw('<script type="application/ld+json"></script>')
        blocks, errors = parse_jsonld_blocks(html)
        assert blocks == []
        assert errors == []

    def test_whitespace_only_script_skipped(self) -> None:
        html = _make_html_raw('<script type="application/ld+json">   \n   </script>')
        blocks, errors = parse_jsonld_blocks(html)
        assert blocks == []
        assert errors == []

    def test_graph_skips_non_dict_items(self) -> None:
        """Non-dict items in @graph array must be skipped without crashing."""
        graph_data = {
            "@graph": [
                {"@type": "Organization", "name": "Acme", "url": "https://acme.com"},
                "not_a_dict",
                42,
                None,
            ]
        }
        html = _make_html_raw(
            f'<script type="application/ld+json">{json.dumps(graph_data)}</script>'
        )
        blocks, errors = parse_jsonld_blocks(html)
        # Only the dict item should be extracted
        assert len(blocks) == 1
        assert blocks[0]["@type"] == "Organization"

    def test_json_array_of_schemas(self) -> None:
        """JSON-LD wrapped in a top-level array must be unpacked."""
        schemas = [
            {"@type": "Organization", "name": "Acme", "url": "https://acme.com"},
            {"@type": "WebSite", "url": "https://acme.com"},
        ]
        html = _make_html_raw(
            f'<script type="application/ld+json">{json.dumps(schemas)}</script>'
        )
        blocks, errors = parse_jsonld_blocks(html)
        assert len(blocks) == 2
        assert errors == []

    def test_no_jsonld_in_page(self) -> None:
        """Pages with no JSON-LD must return empty lists."""
        html = "<html><head></head><body><p>Just text.</p></body></html>"
        blocks, errors = parse_jsonld_blocks(html)
        assert blocks == []
        assert errors == []

    def test_mixed_valid_and_invalid_blocks(self) -> None:
        """Valid blocks must be collected even if other blocks are invalid."""
        html = (
            '<script type="application/ld+json">{"@type": "WebSite"}</script>'
            '<script type="application/ld+json">{ invalid }</script>'
        )
        blocks, errors = parse_jsonld_blocks(html)
        assert len(blocks) == 1
        assert len(errors) == 1

    def test_charset_utf8_suffix_matched(self) -> None:
        """T-SA-14: script type with charset=utf-8 suffix must be found."""
        html = '<script type="application/ld+json; charset=utf-8">{"@type": "Article"}</script>'
        blocks, errors = parse_jsonld_blocks(html)
        assert len(blocks) == 1
        assert blocks[0]["@type"] == "Article"
        assert errors == []

    def test_charset_uppercase_matched(self) -> None:
        """T-SA-14: charset=UTF-8 uppercase variant."""
        html = '<script type="application/ld+json; charset=UTF-8">{"@type": "WebSite"}</script>'
        blocks, _ = parse_jsonld_blocks(html)
        assert len(blocks) == 1

    def test_case_insensitive_type_attribute(self) -> None:
        """T-SA-14: case-insensitive matching of MIME type."""
        html = '<script type="Application/LD+JSON">{"@type": "Organization"}</script>'
        blocks, _ = parse_jsonld_blocks(html)
        assert len(blocks) == 1
        assert blocks[0]["@type"] == "Organization"


# ---------------------------------------------------------------------------
# identify_schema_types
# ---------------------------------------------------------------------------


class TestIdentifySchemaTypes:
    def test_single_string_type(self) -> None:
        blocks = [{"@type": "Article"}]
        assert identify_schema_types(blocks) == ["Article"]

    def test_list_type(self) -> None:
        blocks = [{"@type": ["Article", "BlogPosting"]}]
        types = identify_schema_types(blocks)
        assert "Article" in types
        assert "BlogPosting" in types

    def test_deduplication(self) -> None:
        blocks = [{"@type": "Article"}, {"@type": "Article"}]
        types = identify_schema_types(blocks)
        assert types.count("Article") == 1

    def test_multiple_blocks_different_types(self) -> None:
        blocks = [
            {"@type": "Organization"},
            {"@type": "BreadcrumbList"},
            {"@type": "Article"},
        ]
        types = identify_schema_types(blocks)
        assert set(types) == {"Organization", "BreadcrumbList", "Article"}

    def test_block_without_type(self) -> None:
        blocks = [{"name": "No type here"}]
        assert identify_schema_types(blocks) == []

    def test_empty_blocks(self) -> None:
        assert identify_schema_types([]) == []

    def test_uri_http_prefix_normalized(self) -> None:
        """T-SA-14: http://schema.org/ prefix stripped from @type."""
        blocks = [{"@type": "http://schema.org/Article"}]
        assert identify_schema_types(blocks) == ["Article"]

    def test_uri_https_prefix_normalized(self) -> None:
        """T-SA-14: https://schema.org/ prefix stripped from @type."""
        blocks = [{"@type": "https://schema.org/Article"}]
        assert identify_schema_types(blocks) == ["Article"]

    def test_short_form_unchanged(self) -> None:
        """T-SA-14: short form @type preserved as-is."""
        blocks = [{"@type": "Article"}]
        assert identify_schema_types(blocks) == ["Article"]

    def test_mixed_uri_and_short_form_deduplicated(self) -> None:
        """T-SA-14: URI and short form of same type → single entry."""
        blocks = [
            {"@type": "http://schema.org/Article"},
            {"@type": "Article"},
        ]
        types = identify_schema_types(blocks)
        assert types == ["Article"]

    def test_list_type_with_uri(self) -> None:
        """T-SA-14: @type as list with URI prefix."""
        blocks = [{"@type": ["http://schema.org/Article", "BlogPosting"]}]
        types = identify_schema_types(blocks)
        assert "Article" in types
        assert "BlogPosting" in types
        assert len(types) == 2


# ---------------------------------------------------------------------------
# validate_article_schema
# ---------------------------------------------------------------------------


class TestValidateArticleSchema:
    def test_valid_article(self) -> None:
        block = {
            "@type": "Article",
            "headline": "Test Headline",
            "author": {"@type": "Person", "name": "Jane Doe"},
            "datePublished": "2024-01-01",
            "image": "https://example.com/img.jpg",
            "dateModified": "2024-06-01",
        }
        errors = validate_article_schema(block)
        # Only optional field warnings; headline/author/datePublished present
        assert not any("headline" in e or "author" in e or "datePublished" in e for e in errors)

    def test_missing_headline(self) -> None:
        block = {
            "@type": "Article",
            "author": {"name": "Jane"},
            "datePublished": "2024-01-01",
        }
        errors = validate_article_schema(block)
        assert any("headline" in e.lower() for e in errors)

    def test_missing_author(self) -> None:
        block = {
            "@type": "Article",
            "headline": "Test",
            "datePublished": "2024-01-01",
        }
        errors = validate_article_schema(block)
        assert any("author" in e.lower() for e in errors)

    def test_author_dict_missing_name(self) -> None:
        block = {
            "@type": "Article",
            "headline": "Test",
            "author": {"@type": "Person"},  # missing name
            "datePublished": "2024-01-01",
        }
        errors = validate_article_schema(block)
        assert any("author" in e.lower() and "name" in e.lower() for e in errors)

    def test_missing_date_published(self) -> None:
        block = {
            "@type": "Article",
            "headline": "Test",
            "author": {"name": "Jane"},
        }
        errors = validate_article_schema(block)
        assert any("datePublished" in e for e in errors)

    def test_missing_optional_image_flagged(self) -> None:
        block = {
            "@type": "Article",
            "headline": "Test",
            "author": {"name": "Jane"},
            "datePublished": "2024-01-01",
        }
        errors = validate_article_schema(block)
        assert any("image" in e.lower() for e in errors)

    def test_missing_optional_date_modified_flagged(self) -> None:
        block = {
            "@type": "Article",
            "headline": "Test",
            "author": {"name": "Jane"},
            "datePublished": "2024-01-01",
        }
        errors = validate_article_schema(block)
        assert any("dateModified" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_faq_schema
# ---------------------------------------------------------------------------


class TestValidateFaqSchema:
    def test_valid_faq(self) -> None:
        block = {
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": "What is AEO?",
                    "acceptedAnswer": {"@type": "Answer", "text": "AEO stands for Answer Engine Optimisation."},
                }
            ],
        }
        errors = validate_faq_schema(block)
        assert errors == []

    def test_missing_main_entity(self) -> None:
        block = {"@type": "FAQPage"}
        errors = validate_faq_schema(block)
        assert any("mainEntity" in e for e in errors)

    def test_main_entity_not_list(self) -> None:
        block = {"@type": "FAQPage", "mainEntity": "not a list"}
        errors = validate_faq_schema(block)
        assert any("mainEntity" in e for e in errors)

    def test_empty_main_entity(self) -> None:
        block = {"@type": "FAQPage", "mainEntity": []}
        errors = validate_faq_schema(block)
        assert any("empty" in e.lower() for e in errors)

    def test_question_missing_type(self) -> None:
        block = {
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "name": "What is AEO?",
                    "acceptedAnswer": {"text": "AEO is ..."},
                }
            ],
        }
        errors = validate_faq_schema(block)
        assert any("Question" in e for e in errors)

    def test_question_missing_name(self) -> None:
        block = {
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "acceptedAnswer": {"text": "AEO is ..."},
                }
            ],
        }
        errors = validate_faq_schema(block)
        assert any("name" in e.lower() for e in errors)

    def test_question_missing_accepted_answer(self) -> None:
        block = {
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": "What is AEO?",
                }
            ],
        }
        errors = validate_faq_schema(block)
        assert any("acceptedAnswer" in e for e in errors)

    def test_accepted_answer_missing_text(self) -> None:
        block = {
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": "What is AEO?",
                    "acceptedAnswer": {"@type": "Answer"},  # missing text
                }
            ],
        }
        errors = validate_faq_schema(block)
        assert any("text" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# validate_howto_schema
# ---------------------------------------------------------------------------


class TestValidateHowtoSchema:
    def test_valid_howto(self) -> None:
        block = {
            "@type": "HowTo",
            "name": "How to optimise for AEO",
            "step": [
                {"@type": "HowToStep", "text": "Step 1 description."},
                {"@type": "HowToStep", "text": "Step 2 description."},
                {"@type": "HowToStep", "text": "Step 3 description."},
            ],
        }
        errors = validate_howto_schema(block)
        assert errors == []

    def test_missing_name(self) -> None:
        block = {
            "@type": "HowTo",
            "step": [{"text": "Step 1"}],
        }
        errors = validate_howto_schema(block)
        assert any("name" in e.lower() for e in errors)

    def test_missing_step(self) -> None:
        block = {"@type": "HowTo", "name": "How to do something"}
        errors = validate_howto_schema(block)
        assert any("step" in e.lower() for e in errors)

    def test_step_missing_text(self) -> None:
        block = {
            "@type": "HowTo",
            "name": "How to do something",
            "step": [{"@type": "HowToStep"}],  # no text
        }
        errors = validate_howto_schema(block)
        assert any("text" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# validate_organization_schema
# ---------------------------------------------------------------------------


class TestValidateOrganizationSchema:
    def test_valid_organization(self) -> None:
        block = {
            "@type": "Organization",
            "name": "Acme Corp",
            "url": "https://acme.com",
            "logo": "https://acme.com/logo.png",
        }
        errors = validate_organization_schema(block)
        assert errors == []

    def test_missing_name(self) -> None:
        block = {"@type": "Organization", "url": "https://acme.com"}
        errors = validate_organization_schema(block)
        assert any("name" in e.lower() for e in errors)

    def test_missing_url(self) -> None:
        block = {"@type": "Organization", "name": "Acme"}
        errors = validate_organization_schema(block)
        assert any("url" in e.lower() for e in errors)

    def test_missing_logo_warning(self) -> None:
        block = {"@type": "Organization", "name": "Acme", "url": "https://acme.com"}
        errors = validate_organization_schema(block)
        assert any("logo" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# validate_breadcrumb_schema
# ---------------------------------------------------------------------------


class TestValidateBreadcrumbSchema:
    def test_valid_breadcrumb(self) -> None:
        block = {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://example.com"},
                {"@type": "ListItem", "position": 2, "name": "Blog", "item": "https://example.com/blog"},
            ],
        }
        errors = validate_breadcrumb_schema(block)
        assert errors == []

    def test_missing_item_list_element(self) -> None:
        block = {"@type": "BreadcrumbList"}
        errors = validate_breadcrumb_schema(block)
        assert any("itemListElement" in e for e in errors)

    def test_empty_item_list_element(self) -> None:
        block = {"@type": "BreadcrumbList", "itemListElement": []}
        errors = validate_breadcrumb_schema(block)
        assert any("empty" in e.lower() for e in errors)

    def test_item_missing_position(self) -> None:
        block = {
            "@type": "BreadcrumbList",
            "itemListElement": [{"name": "Home"}],
        }
        errors = validate_breadcrumb_schema(block)
        assert any("position" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# infer_page_type
# ---------------------------------------------------------------------------


class TestInferPageType:
    def test_homepage_root(self) -> None:
        assert infer_page_type("https://example.com/", "") == "homepage"

    def test_homepage_empty_path(self) -> None:
        assert infer_page_type("https://example.com", "") == "homepage"

    def test_blog_path(self) -> None:
        assert infer_page_type("https://example.com/blog/my-post", "") == "article"

    def test_posts_path(self) -> None:
        assert infer_page_type("https://example.com/posts/2024/my-post", "") == "article"

    def test_articles_path(self) -> None:
        assert infer_page_type("https://example.com/articles/seo-guide", "") == "article"

    def test_product_path(self) -> None:
        assert infer_page_type("https://example.com/product/widget-pro", "") == "product"

    def test_shop_path(self) -> None:
        assert infer_page_type("https://example.com/shop/items", "") == "product"

    def test_faq_path(self) -> None:
        assert infer_page_type("https://example.com/faq/", "") == "faq"

    def test_help_path(self) -> None:
        assert infer_page_type("https://example.com/help/setup", "") == "faq"

    def test_about_path(self) -> None:
        assert infer_page_type("https://example.com/about/", "") == "about"

    def test_pricing_path(self) -> None:
        assert infer_page_type("https://example.com/pricing/", "") == "pricing"

    def test_random_path(self) -> None:
        assert infer_page_type("https://example.com/contact-us", "") == "page"

    def test_random_path_2(self) -> None:
        assert infer_page_type("https://example.com/features/automation", "") == "page"

    def test_blog_without_trailing_slash(self) -> None:
        # /blog without trailing slash as the segment
        result = infer_page_type("https://example.com/blog", "")
        assert result == "article"

    def test_faq_without_trailing_slash(self) -> None:
        result = infer_page_type("https://example.com/faq", "")
        assert result == "faq"


# ---------------------------------------------------------------------------
# detect_schema (integration)
# ---------------------------------------------------------------------------


class TestDetectSchema:
    def test_page_with_no_schema(self) -> None:
        html = "<html><head></head><body><p>No schema here.</p></body></html>"
        result = detect_schema(html, "https://example.com/blog/post")
        assert result.has_schema is False
        assert result.schema_types == []
        assert result.raw_jsonld_blocks == []

    def test_page_with_valid_article_schema(self) -> None:
        block = {
            "@type": "Article",
            "headline": "Test Article",
            "author": {"name": "Jane"},
            "datePublished": "2024-01-01",
            "image": "img.jpg",
            "dateModified": "2024-06-01",
        }
        html = _make_html([block])
        result = detect_schema(html, "https://example.com/blog/test-article")
        assert result.has_schema is True
        assert "Article" in result.schema_types
        assert result.inferred_page_type == "article"

    def test_graph_container_detected(self) -> None:
        graph_data = {
            "@graph": [
                {"@type": "Organization", "name": "Acme", "url": "https://acme.com"},
                {"@type": "WebSite", "url": "https://acme.com"},
            ]
        }
        html = _make_html_raw(
            f'<script type="application/ld+json">{json.dumps(graph_data)}</script>'
        )
        result = detect_schema(html, "https://acme.com/")
        assert result.has_schema is True
        assert "Organization" in result.schema_types
        assert "WebSite" in result.schema_types

    def test_invalid_json_produces_validation_errors(self) -> None:
        html = _make_html_raw('<script type="application/ld+json">{ broken }</script>')
        result = detect_schema(html, "https://example.com/")
        assert len(result.validation_errors) > 0

    def test_article_with_missing_fields_has_errors(self) -> None:
        block = {"@type": "Article", "headline": "Missing author"}
        html = _make_html([block])
        result = detect_schema(html, "https://example.com/blog/test")
        assert len(result.validation_errors) > 0

    def test_page_type_inferred_correctly(self) -> None:
        html = "<html><body><p>FAQ content.</p></body></html>"
        result = detect_schema(html, "https://example.com/faq/")
        assert result.inferred_page_type == "faq"


# ---------------------------------------------------------------------------
# generate_schema_findings
# ---------------------------------------------------------------------------


class TestGenerateSchemaFindings:
    def _result(self, **kwargs) -> SchemaDetectionResult:
        defaults = dict(
            has_schema=False,
            schema_types=[],
            raw_jsonld_blocks=[],
            validation_errors=[],
            inferred_page_type="page",
        )
        defaults.update(kwargs)
        return SchemaDetectionResult(**defaults)

    def test_homepage_missing_organization_is_medium(self) -> None:
        result = self._result(inferred_page_type="homepage")
        findings = generate_schema_findings("https://example.com/", result)
        types = {f.finding_type for f in findings}
        assert "missing_organization_schema" in types
        org_finding = next(f for f in findings if f.finding_type == "missing_organization_schema")
        assert org_finding.severity == AuditCheckSeverity.medium
        assert org_finding.dimension == AuditDimension.schema_markup

    def test_article_page_missing_article_schema_is_high(self) -> None:
        result = self._result(inferred_page_type="article")
        findings = generate_schema_findings("https://example.com/blog/test", result)
        types = {f.finding_type for f in findings}
        assert "missing_article_schema" in types
        finding = next(f for f in findings if f.finding_type == "missing_article_schema")
        assert finding.severity == AuditCheckSeverity.high

    def test_faq_page_missing_faqpage_schema_is_high(self) -> None:
        result = self._result(inferred_page_type="faq")
        findings = generate_schema_findings("https://example.com/faq/", result)
        types = {f.finding_type for f in findings}
        assert "missing_faqpage_schema" in types
        finding = next(f for f in findings if f.finding_type == "missing_faqpage_schema")
        assert finding.severity == AuditCheckSeverity.high

    def test_product_page_missing_product_schema_is_medium(self) -> None:
        result = self._result(inferred_page_type="product")
        findings = generate_schema_findings("https://example.com/product/widget", result)
        types = {f.finding_type for f in findings}
        assert "missing_product_schema" in types
        finding = next(f for f in findings if f.finding_type == "missing_product_schema")
        assert finding.severity == AuditCheckSeverity.medium

    def test_any_page_missing_breadcrumb_is_low(self) -> None:
        result = self._result(inferred_page_type="page")
        findings = generate_schema_findings("https://example.com/about", result)
        types = {f.finding_type for f in findings}
        assert "missing_breadcrumb_schema" in types
        finding = next(f for f in findings if f.finding_type == "missing_breadcrumb_schema")
        assert finding.severity == AuditCheckSeverity.low

    def test_validation_errors_generate_medium_findings(self) -> None:
        result = self._result(
            has_schema=True,
            schema_types=["Article"],
            validation_errors=["Article/BlogPosting missing required field: headline"],
            inferred_page_type="article",
        )
        findings = generate_schema_findings("https://example.com/blog/test", result)
        validation_findings = [f for f in findings if f.finding_type == "schema_validation_error"]
        assert len(validation_findings) == 1
        assert validation_findings[0].severity == AuditCheckSeverity.medium

    def test_article_with_correct_schema_no_article_finding(self) -> None:
        """A valid Article page with Article schema must not trigger the missing-article finding."""
        result = self._result(
            has_schema=True,
            schema_types=["Article", "BreadcrumbList"],
            inferred_page_type="article",
        )
        findings = generate_schema_findings("https://example.com/blog/test", result)
        types = {f.finding_type for f in findings}
        assert "missing_article_schema" not in types
        assert "missing_breadcrumb_schema" not in types

    def test_homepage_with_organization_and_breadcrumb_no_findings(self) -> None:
        result = self._result(
            has_schema=True,
            schema_types=["Organization", "BreadcrumbList", "WebSite"],
            inferred_page_type="homepage",
        )
        findings = generate_schema_findings("https://example.com/", result)
        # Should only have validation errors (none in this case)
        assert findings == []

    def test_findings_include_url(self) -> None:
        url = "https://example.com/faq/"
        result = self._result(inferred_page_type="faq")
        findings = generate_schema_findings(url, result)
        assert all(f.url == url for f in findings)

    def test_blogposting_satisfies_article_requirement(self) -> None:
        """BlogPosting is equivalent to Article for the missing-article check."""
        result = self._result(
            has_schema=True,
            schema_types=["BlogPosting", "BreadcrumbList"],
            inferred_page_type="article",
        )
        findings = generate_schema_findings("https://example.com/blog/test", result)
        types = {f.finding_type for f in findings}
        assert "missing_article_schema" not in types


# ---------------------------------------------------------------------------
# Codex F-1: validate_schema_block dispatches on normalized @type
# ---------------------------------------------------------------------------


class TestValidateSchemaBlockURIType:
    """Codex F-1: validate_schema_block must normalize URI-style @type before dispatch."""

    def test_uri_article_type_validates(self) -> None:
        """https://schema.org/Article should trigger Article validation."""
        block = {
            "@type": "https://schema.org/Article",
            "headline": "Test Article",
            "author": {"@type": "Person", "name": "Alice"},
            "datePublished": "2026-01-01",
        }
        errors = validate_schema_block(block)
        # Should have no errors since all required fields are present
        assert not any("headline" in e.lower() for e in errors)

    def test_uri_article_type_missing_fields_detected(self) -> None:
        """URI-style Article type → missing fields should be flagged."""
        block = {
            "@type": "http://schema.org/Article",
            # Missing headline, author, datePublished
        }
        errors = validate_schema_block(block)
        assert len(errors) > 0  # Should flag missing required fields

    def test_uri_faqpage_type_validates(self) -> None:
        """https://schema.org/FAQPage should trigger FAQ validation."""
        block = {
            "@type": "https://schema.org/FAQPage",
            # Missing mainEntity — should flag it
        }
        errors = validate_schema_block(block)
        assert any("mainEntity" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_product_schema (T-SA-26)
# ---------------------------------------------------------------------------


class TestValidateProductSchema:
    def test_valid_product(self) -> None:
        block = {"@type": "Product", "name": "Widget", "offers": {"price": "9.99"}}
        errors = validate_product_schema(block)
        # Only recommended warnings expected
        assert not any("required" in e.lower() for e in errors)

    def test_missing_name(self) -> None:
        block = {"@type": "Product", "offers": {"price": "9.99"}}
        errors = validate_product_schema(block)
        assert any("name" in e for e in errors)

    def test_missing_offers_and_price(self) -> None:
        block = {"@type": "Product", "name": "Widget"}
        errors = validate_product_schema(block)
        assert any("pricing" in e.lower() for e in errors)

    def test_offers_present_no_pricing_error(self) -> None:
        block = {"@type": "Product", "name": "W", "offers": {"price": "5"}}
        errors = validate_product_schema(block)
        assert not any("pricing" in e.lower() for e in errors)

    def test_price_and_currency_present(self) -> None:
        block = {"@type": "Product", "name": "W", "price": "5", "priceCurrency": "USD"}
        errors = validate_product_schema(block)
        assert not any("pricing" in e.lower() for e in errors)

    def test_missing_description_warning(self) -> None:
        block = {"@type": "Product", "name": "W", "offers": {}, "image": "x", "brand": "B", "sku": "S"}
        errors = validate_product_schema(block)
        assert any("description" in e for e in errors)

    def test_missing_image_warning(self) -> None:
        block = {"@type": "Product", "name": "W", "offers": {}, "description": "D", "brand": "B", "sku": "S"}
        errors = validate_product_schema(block)
        assert any("image" in e for e in errors)

    def test_brand_and_sku_warnings(self) -> None:
        block = {"@type": "Product", "name": "W", "offers": {}, "description": "D", "image": "I"}
        errors = validate_product_schema(block)
        assert any("brand" in e for e in errors)
        assert any("sku" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_speakable_schema (T-SA-26)
# ---------------------------------------------------------------------------


class TestValidateSpeakableSchema:
    def test_valid_with_css_selector(self) -> None:
        block = {"@type": "Speakable", "cssSelector": ".article-body", "name": "Main content"}
        errors = validate_speakable_schema(block)
        assert errors == []

    def test_valid_with_xpath(self) -> None:
        block = {"@type": "Speakable", "xpath": "//article", "name": "Main content"}
        errors = validate_speakable_schema(block)
        assert errors == []

    def test_missing_both_selectors(self) -> None:
        block = {"@type": "Speakable", "name": "Test"}
        errors = validate_speakable_schema(block)
        assert any("selector" in e.lower() for e in errors)

    def test_speakable_specification_type(self) -> None:
        """SpeakableSpecification alias works."""
        block = {"@type": "SpeakableSpecification", "cssSelector": ".main"}
        errors = validate_speakable_schema(block)
        assert not any("selector" in e.lower() for e in errors)

    def test_missing_name_warning(self) -> None:
        block = {"@type": "Speakable", "cssSelector": ".main"}
        errors = validate_speakable_schema(block)
        assert any("name" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_schema_block dispatches Product/Speakable (T-SA-26)
# ---------------------------------------------------------------------------


class TestValidateSchemaBlockProductSpeakable:
    def test_dispatches_product(self) -> None:
        block = {"@type": "Product", "name": "Widget", "offers": {}}
        errors = validate_schema_block(block)
        # Should have run product validation (recommended warnings present)
        assert any("description" in e for e in errors)

    def test_dispatches_speakable(self) -> None:
        block = {"@type": "Speakable"}
        errors = validate_schema_block(block)
        assert any("selector" in e.lower() for e in errors)

    def test_dispatches_speakable_specification(self) -> None:
        block = {"@type": "SpeakableSpecification", "cssSelector": ".main"}
        errors = validate_schema_block(block)
        # Should have run speakable validation (name warning)
        assert any("name" in e for e in errors)
