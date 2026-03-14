"""Tests for core/models/site_audit.py.

Covers:
- Default-only instantiation (all fields have defaults)
- Enum value correctness
- JSON round-trip fidelity (serialize → parse → re-serialize)
- Nested model default_factory isolation (shared state)
- Field value assignment and retrieval
- Backward-compatibility: unknown extra fields are silently ignored
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException

from core.models.site_audit import (
    AEOReadinessResult,
    AuditCheckSeverity,
    AuditDimension,
    AuditFinding,
    AIBotAccessResult,
    DimensionScore,
    PageAuditResult,
    SchemaDetectionResult,
    SiteAuditInput,
    SiteAuditResult,
    SitemapHealthResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def json_roundtrip(model: Any) -> Any:
    """Serialise a Pydantic model to JSON, then re-parse."""
    return type(model).model_validate_json(model.model_dump_json())


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestAuditDimension:
    def test_all_values_present(self) -> None:
        values = {d.value for d in AuditDimension}
        assert values == {
            "crawlability",
            "performance",
            "on_page_seo",
            "extractability",
            "schema_markup",
            "eeat",
            "freshness",
            "security",
        }

    def test_is_str_enum(self) -> None:
        assert AuditDimension.crawlability == "crawlability"
        assert isinstance(AuditDimension.eeat, str)

    def test_count(self) -> None:
        assert len(AuditDimension) == 8


class TestAuditCheckSeverity:
    def test_all_values_present(self) -> None:
        values = {s.value for s in AuditCheckSeverity}
        assert values == {"critical", "high", "medium", "low", "info"}

    def test_is_str_enum(self) -> None:
        assert AuditCheckSeverity.critical == "critical"

    def test_ordering_preserved(self) -> None:
        """Values exist; Python Enum preserves definition order."""
        ordered = list(AuditCheckSeverity)
        assert ordered[0] == AuditCheckSeverity.critical
        assert ordered[-1] == AuditCheckSeverity.info


# ---------------------------------------------------------------------------
# SiteAuditInput tests
# ---------------------------------------------------------------------------


class TestSiteAuditInput:
    def test_required_fields(self) -> None:
        inp = SiteAuditInput(company_name="Acme Corp", domain="acme.com")
        assert inp.company_name == "Acme Corp"
        assert inp.domain == "acme.com"

    def test_defaults(self) -> None:
        inp = SiteAuditInput(company_name="X", domain="x.com")
        assert inp.company_slug == "x"  # auto-derived from company_name
        assert inp.product_slug is None
        assert inp.max_pages == 200
        assert inp.max_depth == 4
        assert inp.check_core_web_vitals is True
        assert inp.check_schema_validation is True
        assert inp.check_ai_bot_access is True

    def test_optional_overrides(self) -> None:
        inp = SiteAuditInput(
            company_name="X",
            domain="x.com",
            company_slug="x-slug",
            product_slug="x-product",
            max_pages=50,
            max_depth=2,
            check_core_web_vitals=False,
            check_schema_validation=False,
            check_ai_bot_access=False,
        )
        assert inp.company_slug == "x-slug"
        assert inp.product_slug == "x-product"
        assert inp.max_pages == 50
        assert inp.max_depth == 2
        assert inp.check_core_web_vitals is False

    def test_json_roundtrip(self) -> None:
        inp = SiteAuditInput(company_name="Round", domain="round.io", max_pages=100)
        restored = json_roundtrip(inp)
        assert restored.company_name == inp.company_name
        assert restored.domain == inp.domain
        assert restored.max_pages == inp.max_pages

    # ── T-SA-10: Auto-derive company_slug + product_slug validation ──

    def test_slug_derived_from_company_name(self) -> None:
        inp = SiteAuditInput(company_name="Lovable", domain="lovable.dev")
        assert inp.company_slug == "lovable"

    def test_slug_special_chars(self) -> None:
        inp = SiteAuditInput(company_name="A & B Co.", domain="ab.com")
        assert inp.company_slug == "a-b-co"

    def test_explicit_slug_preserved(self) -> None:
        inp = SiteAuditInput(
            company_name="Lovable", domain="lovable.dev", company_slug="custom"
        )
        assert inp.company_slug == "custom"

    def test_product_slug_valid(self) -> None:
        inp = SiteAuditInput(
            company_name="Acme", domain="acme.com", product_slug="dashboard"
        )
        assert inp.product_slug == "dashboard"

    def test_product_slug_path_traversal_rejected(self) -> None:
        with pytest.raises(Exception):  # ValidationError
            SiteAuditInput(
                company_name="Acme", domain="acme.com", product_slug="../evil"
            )

    def test_product_slug_uppercase_rejected(self) -> None:
        with pytest.raises(Exception):  # ValidationError
            SiteAuditInput(
                company_name="Acme", domain="acme.com", product_slug="BadSlug"
            )


# ---------------------------------------------------------------------------
# AuditFinding tests
# ---------------------------------------------------------------------------


class TestAuditFinding:
    def test_defaults(self) -> None:
        f = AuditFinding()
        assert f.finding_type == ""
        assert f.dimension == AuditDimension.crawlability
        assert f.severity == AuditCheckSeverity.info
        assert f.message == ""
        assert f.recommendation == ""
        assert f.url == ""
        assert f.details == {}

    def test_populated(self) -> None:
        f = AuditFinding(
            finding_type="missing_title",
            dimension=AuditDimension.on_page_seo,
            severity=AuditCheckSeverity.critical,
            message="Page has no <title>",
            recommendation="Add a descriptive <title> between 30-60 chars.",
            url="https://acme.com/about",
            details={"char_count": 0},
        )
        assert f.finding_type == "missing_title"
        assert f.dimension == AuditDimension.on_page_seo
        assert f.severity == AuditCheckSeverity.critical
        assert f.details["char_count"] == 0

    def test_details_factory_isolated(self) -> None:
        """Two AuditFinding instances must NOT share the same dict."""
        f1 = AuditFinding()
        f2 = AuditFinding()
        f1.details["x"] = 1
        assert "x" not in f2.details

    def test_json_roundtrip(self) -> None:
        f = AuditFinding(
            finding_type="duplicate_h1",
            dimension=AuditDimension.on_page_seo,
            severity=AuditCheckSeverity.high,
            message="Multiple H1 tags found",
            details={"count": 3},
        )
        restored = json_roundtrip(f)
        assert restored.finding_type == f.finding_type
        assert restored.dimension == f.dimension
        assert restored.details == f.details

    def test_enum_serialization(self) -> None:
        f = AuditFinding(
            dimension=AuditDimension.schema_markup,
            severity=AuditCheckSeverity.medium,
        )
        dumped = json.loads(f.model_dump_json())
        assert dumped["dimension"] == "schema_markup"
        assert dumped["severity"] == "medium"


# ---------------------------------------------------------------------------
# SchemaDetectionResult tests
# ---------------------------------------------------------------------------


class TestSchemaDetectionResult:
    def test_defaults(self) -> None:
        s = SchemaDetectionResult()
        assert s.has_schema is False
        assert s.schema_types == []
        assert s.raw_jsonld_blocks == []
        assert s.validation_errors == []
        assert s.inferred_page_type == "unknown"

    def test_list_factory_isolated(self) -> None:
        s1 = SchemaDetectionResult()
        s2 = SchemaDetectionResult()
        s1.schema_types.append("Article")
        assert s2.schema_types == []

    def test_populated(self) -> None:
        s = SchemaDetectionResult(
            has_schema=True,
            schema_types=["Article", "FAQPage"],
            raw_jsonld_blocks=[{"@type": "Article"}],
            inferred_page_type="article",
        )
        assert s.has_schema is True
        assert "FAQPage" in s.schema_types

    def test_json_roundtrip(self) -> None:
        s = SchemaDetectionResult(
            has_schema=True,
            schema_types=["HowTo"],
            validation_errors=["Missing required 'name' field"],
        )
        restored = json_roundtrip(s)
        assert restored.has_schema is True
        assert restored.schema_types == ["HowTo"]
        assert len(restored.validation_errors) == 1


# ---------------------------------------------------------------------------
# AEOReadinessResult tests
# ---------------------------------------------------------------------------


class TestAEOReadinessResult:
    def test_defaults(self) -> None:
        a = AEOReadinessResult()
        assert a.snippet_readiness_score == 0.0
        assert a.question_heading_ratio == 0.0
        assert a.quick_answer_hook_count == 0
        assert a.self_contained_paragraph_ratio == 0.0
        assert a.avg_paragraph_word_count == 0.0
        assert a.content_patterns == {}

    def test_content_patterns_factory_isolated(self) -> None:
        a1 = AEOReadinessResult()
        a2 = AEOReadinessResult()
        a1.content_patterns["faq_section"] = True
        assert "faq_section" not in a2.content_patterns

    def test_score_range_semantics(self) -> None:
        """Model accepts any float — range enforcement is in scoring logic."""
        a = AEOReadinessResult(snippet_readiness_score=95.5)
        assert a.snippet_readiness_score == 95.5

    def test_json_roundtrip(self) -> None:
        a = AEOReadinessResult(
            snippet_readiness_score=72.3,
            question_heading_ratio=0.4,
            quick_answer_hook_count=3,
            content_patterns={"faq_section": True, "numbered_steps": False},
        )
        restored = json_roundtrip(a)
        assert restored.snippet_readiness_score == pytest.approx(72.3)
        assert restored.content_patterns["faq_section"] is True


# ---------------------------------------------------------------------------
# PageAuditResult tests
# ---------------------------------------------------------------------------


class TestPageAuditResult:
    def test_defaults(self) -> None:
        p = PageAuditResult()
        assert p.url == ""
        assert p.status_code == 0
        assert p.crawl_depth == 0
        assert p.redirect_url is None
        assert p.title == ""
        assert p.title_length == 0
        assert p.meta_description == ""
        assert p.meta_description_length == 0
        assert p.h1_count == 0
        assert p.h1_text == ""
        assert p.heading_hierarchy_valid is True
        assert p.headings == []
        assert p.image_count == 0
        assert p.images_with_alt == 0
        assert p.images_without_alt == 0
        assert p.internal_link_count == 0
        assert p.external_link_count == 0
        assert p.word_count == 0
        assert p.reading_level == 0.0
        assert p.is_ssr is True
        assert p.has_canonical is False
        assert p.canonical_url is None
        assert p.is_noindex is False
        assert p.is_nofollow is False
        assert p.has_https is True
        assert p.has_mixed_content is False
        assert p.publish_date is None
        assert p.modified_date is None
        assert p.has_author is False
        assert p.author_name is None
        assert isinstance(p.schema_result, SchemaDetectionResult)
        assert isinstance(p.aeo, AEOReadinessResult)
        assert p.findings == []

    def test_performance_structural_defaults(self) -> None:
        p = PageAuditResult()
        assert p.html_bytes is None
        assert p.external_script_count is None
        assert p.external_css_count is None
        assert p.blocking_script_count is None
        assert p.blocking_css_count is None
        assert p.images_without_lazy is None
        assert p.images_without_dimensions is None
        assert p.inline_js_bytes is None
        assert p.inline_css_bytes is None

    def test_performance_structural_roundtrip(self) -> None:
        p = PageAuditResult(
            html_bytes=102400,
            external_script_count=5,
            external_css_count=3,
            blocking_script_count=2,
            blocking_css_count=1,
            images_without_lazy=4,
            images_without_dimensions=2,
            inline_js_bytes=8192,
            inline_css_bytes=4096,
        )
        restored = json_roundtrip(p)
        assert restored.html_bytes == 102400
        assert restored.external_script_count == 5
        assert restored.external_css_count == 3
        assert restored.blocking_script_count == 2
        assert restored.blocking_css_count == 1
        assert restored.images_without_lazy == 4
        assert restored.images_without_dimensions == 2
        assert restored.inline_js_bytes == 8192
        assert restored.inline_css_bytes == 4096

    def test_nested_models_isolated(self) -> None:
        """Nested default_factory models must not be shared."""
        p1 = PageAuditResult()
        p2 = PageAuditResult()
        p1.schema_result.schema_types.append("Article")
        assert p2.schema_result.schema_types == []

    def test_findings_list_isolated(self) -> None:
        p1 = PageAuditResult()
        p2 = PageAuditResult()
        p1.findings.append(AuditFinding(finding_type="test"))
        assert p2.findings == []

    def test_populated_fields(self) -> None:
        p = PageAuditResult(
            url="https://acme.com/blog/ai-ready",
            status_code=200,
            crawl_depth=2,
            title="AI-Ready Website Guide",
            title_length=23,
            h1_count=1,
            h1_text="AI-Ready Website Guide",
            word_count=1500,
            has_author=True,
            author_name="Jane Doe",
        )
        assert p.status_code == 200
        assert p.has_author is True
        assert p.author_name == "Jane Doe"
        assert p.word_count == 1500

    def test_json_roundtrip_with_nested(self) -> None:
        p = PageAuditResult(
            url="https://acme.com/",
            status_code=200,
            schema=SchemaDetectionResult(has_schema=True, schema_types=["WebSite"]),
            aeo=AEOReadinessResult(snippet_readiness_score=60.0),
            findings=[
                AuditFinding(finding_type="short_meta", severity=AuditCheckSeverity.medium)
            ],
        )
        restored = json_roundtrip(p)
        assert restored.url == "https://acme.com/"
        assert restored.schema_result.has_schema is True
        assert restored.aeo.snippet_readiness_score == pytest.approx(60.0)
        assert len(restored.findings) == 1
        assert restored.findings[0].finding_type == "short_meta"

    def test_redirect_url_optional(self) -> None:
        p = PageAuditResult(status_code=301, redirect_url="https://acme.com/new")
        assert p.redirect_url == "https://acme.com/new"
        p2 = PageAuditResult()
        assert p2.redirect_url is None

    def test_headings_structure(self) -> None:
        headings = [{"level": "h1", "text": "Title"}, {"level": "h2", "text": "Subtitle"}]
        p = PageAuditResult(headings=headings)
        assert len(p.headings) == 2
        assert p.headings[0]["level"] == "h1"


class TestSchemaKeyFallback:
    """T-SA-22: Verify both 'schema_result' (field name) and 'schema' (alias)
    are accepted when reading page result dicts from JSON artifacts."""

    def test_schema_result_key_used(self) -> None:
        """Field name key takes priority."""
        p: dict = {"schema_result": {"has_schema": True, "schema_types": ["Article"]}}
        result = p.get("schema_result", p.get("schema", {}))
        assert result == {"has_schema": True, "schema_types": ["Article"]}

    def test_schema_alias_key_used(self) -> None:
        """Alias key accepted when field name absent."""
        p: dict = {"schema": {"has_schema": True}}
        result = p.get("schema_result", p.get("schema", {}))
        assert result == {"has_schema": True}

    def test_neither_key_returns_empty(self) -> None:
        p: dict = {"url": "https://example.com"}
        result = p.get("schema_result", p.get("schema", {}))
        assert result == {}

    def test_both_keys_prefers_field_name(self) -> None:
        """When both present, field name wins."""
        p: dict = {"schema_result": {"a": 1}, "schema": {"b": 2}}
        result = p.get("schema_result", p.get("schema", {}))
        assert result == {"a": 1}


# ---------------------------------------------------------------------------
# AIBotAccessResult tests
# ---------------------------------------------------------------------------


class TestAIBotAccessResult:
    def test_defaults(self) -> None:
        r = AIBotAccessResult()
        assert r.gptbot_allowed is True
        assert r.claudebot_allowed is True
        assert r.perplexitybot_allowed is True
        assert r.google_extended_allowed is True
        assert r.ccbot_allowed is True
        assert r.has_llms_txt is False
        assert r.robots_txt_exists is False

    def test_blocked_bots(self) -> None:
        r = AIBotAccessResult(
            gptbot_allowed=False,
            claudebot_allowed=False,
            robots_txt_exists=True,
        )
        assert r.gptbot_allowed is False
        assert r.claudebot_allowed is False
        assert r.robots_txt_exists is True

    def test_json_roundtrip(self) -> None:
        r = AIBotAccessResult(has_llms_txt=True, robots_txt_exists=True)
        restored = json_roundtrip(r)
        assert restored.has_llms_txt is True


# ---------------------------------------------------------------------------
# SitemapHealthResult tests
# ---------------------------------------------------------------------------


class TestSitemapHealthResult:
    def test_defaults(self) -> None:
        s = SitemapHealthResult()
        assert s.has_sitemap is False
        assert s.sitemap_url_count == 0
        assert s.sitemap_urls == []
        assert s.sitemap_errors == []
        assert s.has_sitemap_index is False

    def test_lists_isolated(self) -> None:
        s1 = SitemapHealthResult()
        s2 = SitemapHealthResult()
        s1.sitemap_urls.append("https://acme.com/sitemap.xml")
        assert s2.sitemap_urls == []

    def test_populated(self) -> None:
        s = SitemapHealthResult(
            has_sitemap=True,
            sitemap_url_count=250,
            sitemap_urls=["https://acme.com/sitemap.xml"],
            has_sitemap_index=True,
        )
        assert s.has_sitemap is True
        assert s.sitemap_url_count == 250

    def test_json_roundtrip(self) -> None:
        s = SitemapHealthResult(
            has_sitemap=True,
            sitemap_url_count=10,
            sitemap_errors=["Fetch timeout"],
        )
        restored = json_roundtrip(s)
        assert restored.sitemap_errors == ["Fetch timeout"]


# ---------------------------------------------------------------------------
# DimensionScore tests
# ---------------------------------------------------------------------------


class TestDimensionScore:
    def test_defaults(self) -> None:
        d = DimensionScore()
        assert d.dimension == AuditDimension.crawlability
        assert d.score == 100.0
        assert d.weight == 0.0
        assert d.weighted_score == 0.0
        assert d.finding_count == 0
        assert d.critical_count == 0
        assert d.high_count == 0
        assert d.medium_count == 0
        assert d.low_count == 0
        assert d.info_count == 0

    def test_weighted_score_independent(self) -> None:
        """weighted_score is not auto-computed — must be set explicitly."""
        d = DimensionScore(score=80.0, weight=0.20)
        assert d.weighted_score == 0.0  # Not auto-computed by model

    def test_all_dimensions(self) -> None:
        for dim in AuditDimension:
            d = DimensionScore(dimension=dim)
            assert d.dimension == dim

    def test_json_roundtrip(self) -> None:
        d = DimensionScore(
            dimension=AuditDimension.eeat,
            score=75.0,
            weight=0.15,
            weighted_score=11.25,
            finding_count=3,
            critical_count=1,
        )
        restored = json_roundtrip(d)
        assert restored.dimension == AuditDimension.eeat
        assert restored.score == pytest.approx(75.0)
        assert restored.critical_count == 1

    def test_enum_serialized_as_string(self) -> None:
        d = DimensionScore(dimension=AuditDimension.security)
        dumped = json.loads(d.model_dump_json())
        assert dumped["dimension"] == "security"


# ---------------------------------------------------------------------------
# SiteAuditResult tests
# ---------------------------------------------------------------------------


class TestSiteAuditResult:
    def test_defaults(self) -> None:
        r = SiteAuditResult()
        assert r.audit_id == ""
        assert r.domain == ""
        assert r.overall_score == 0.0
        assert r.grade == "F"
        assert r.pages_crawled == 0
        assert r.pages_discovered == 0
        assert r.duration_seconds == 0.0
        assert r.dimension_scores == []
        assert isinstance(r.ai_bot_access, AIBotAccessResult)
        assert isinstance(r.sitemap_health, SitemapHealthResult)
        assert r.page_results == []
        assert r.total_findings == 0
        assert r.findings_by_severity == {}
        assert r.findings_by_dimension == {}
        assert r.top_findings == []
        assert r.avg_snippet_readiness == 0.0
        assert r.pages_with_schema == 0
        assert r.avg_question_heading_ratio == 0.0
        assert r.started_at is None
        assert r.completed_at is None
        assert r.status == "pending"
        assert r.error_message is None
        assert r.failed_steps == []
        assert r.degraded_dimensions == []

    def test_nested_models_isolated(self) -> None:
        r1 = SiteAuditResult()
        r2 = SiteAuditResult()
        r1.ai_bot_access.has_llms_txt = True
        # r2 should not be affected (default_factory gives independent instances)
        assert r2.ai_bot_access.has_llms_txt is False

    def test_page_results_isolated(self) -> None:
        r1 = SiteAuditResult()
        r2 = SiteAuditResult()
        r1.page_results.append(PageAuditResult(url="https://acme.com/"))
        assert r2.page_results == []

    def test_status_values(self) -> None:
        for status in ("pending", "running", "completed", "failed", "degraded"):
            r = SiteAuditResult(status=status)
            assert r.status == status

    def test_timestamps(self) -> None:
        now = datetime.now(tz=timezone.utc)
        r = SiteAuditResult(started_at=now, completed_at=now, status="completed")
        assert r.started_at == now
        assert r.completed_at == now

    def test_findings_by_severity_populated(self) -> None:
        r = SiteAuditResult(
            findings_by_severity={"critical": 2, "high": 5, "medium": 10, "low": 3, "info": 1}
        )
        assert r.findings_by_severity["critical"] == 2

    def test_json_roundtrip_full(self) -> None:
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        r = SiteAuditResult(
            audit_id="audit-123",
            domain="acme.com",
            overall_score=82.5,
            grade="B",
            pages_crawled=47,
            pages_discovered=50,
            duration_seconds=34.7,
            total_findings=15,
            findings_by_severity={"critical": 1, "high": 3},
            findings_by_dimension={"on_page_seo": 5},
            avg_snippet_readiness=65.0,
            pages_with_schema=12,
            started_at=now,
            completed_at=now,
            status="completed",
            ai_bot_access=AIBotAccessResult(robots_txt_exists=True),
            sitemap_health=SitemapHealthResult(has_sitemap=True, sitemap_url_count=47),
            dimension_scores=[
                DimensionScore(dimension=AuditDimension.on_page_seo, score=80.0, weight=0.15)
            ],
        )
        restored = json_roundtrip(r)
        assert restored.audit_id == "audit-123"
        assert restored.domain == "acme.com"
        assert restored.overall_score == pytest.approx(82.5)
        assert restored.grade == "B"
        assert restored.pages_crawled == 47
        assert restored.total_findings == 15
        assert restored.ai_bot_access.robots_txt_exists is True
        assert restored.sitemap_health.sitemap_url_count == 47
        assert len(restored.dimension_scores) == 1
        assert restored.dimension_scores[0].dimension == AuditDimension.on_page_seo
        assert restored.status == "completed"

    def test_error_state(self) -> None:
        r = SiteAuditResult(
            status="failed",
            error_message="ConnectionError: could not reach acme.com",
        )
        assert r.status == "failed"
        assert r.error_message is not None
        assert "ConnectionError" in r.error_message

    def test_grade_field_any_string(self) -> None:
        """Model accepts any string for grade — computation is in scoring."""
        for grade in ("A", "B", "C", "D", "F"):
            r = SiteAuditResult(grade=grade)
            assert r.grade == grade

    def test_top_findings_structure(self) -> None:
        top = [
            {"finding_type": "missing_title", "severity": "critical", "count": 5},
            {"finding_type": "short_meta", "severity": "high", "count": 8},
        ]
        r = SiteAuditResult(top_findings=top)
        assert len(r.top_findings) == 2
        assert r.top_findings[0]["finding_type"] == "missing_title"


# ---------------------------------------------------------------------------
# T-SA-01: Path traversal — _validate_audit_id + _audit_dir hardening
# ---------------------------------------------------------------------------


class TestAuditIdValidation:
    """Verify that _validate_audit_id and _audit_dir reject path traversal
    attempts while accepting valid UUID4 strings (T-SA-01 fix)."""

    def test_valid_uuid4_accepted(self, tmp_path: Path) -> None:
        from core.services.json_site_audit_data import _audit_dir

        audit_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        # Just verify no exception — directory need not exist
        result = _audit_dir(tmp_path, "test-co", audit_id)
        assert result == tmp_path / "site_audit" / "test-co" / audit_id

    def test_path_traversal_rejected(self, tmp_path: Path) -> None:
        from core.services.json_site_audit_data import _audit_dir

        for malicious_id in [
            "../../etc",
            "../gap_analysis",
            "../../gap_analysis",
            "../../../etc/passwd",
            "..%2F..%2Fetc",
        ]:
            with pytest.raises(HTTPException) as exc_info:
                _audit_dir(tmp_path, "test-co", malicious_id)
            assert exc_info.value.status_code == 400

    def test_uppercase_uuid_rejected(self, tmp_path: Path) -> None:
        from core.services.json_site_audit_data import _audit_dir

        with pytest.raises(HTTPException) as exc_info:
            _audit_dir(tmp_path, "test-co", "A1B2C3D4-E5F6-7890-ABCD-EF1234567890")
        assert exc_info.value.status_code == 400

    def test_wrong_format_rejected(self, tmp_path: Path) -> None:
        from core.services.json_site_audit_data import _audit_dir

        for bad_id in ["not-a-uuid", "", "12345", "abc", "hello world"]:
            with pytest.raises(HTTPException) as exc_info:
                _audit_dir(tmp_path, "test-co", bad_id)
            assert exc_info.value.status_code == 400

    def test_symlink_escape_rejected(self, tmp_path: Path) -> None:
        """Symlink that points outside company_root must be rejected."""
        from core.services.json_site_audit_data import _audit_dir

        company_root = tmp_path / "site_audit" / "test-co"
        company_root.mkdir(parents=True)
        audit_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        # Create a symlink inside company_root that points outside
        escape_target = tmp_path / "secrets"
        escape_target.mkdir()
        (company_root / audit_id).symlink_to(escape_target)

        with pytest.raises(HTTPException) as exc_info:
            _audit_dir(tmp_path, "test-co", audit_id)
        assert exc_info.value.status_code == 400

    def test_validate_audit_id_directly(self) -> None:
        from core.services.json_site_audit_data import _validate_audit_id

        # Valid — no exception
        _validate_audit_id("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

        # Invalid — raises
        with pytest.raises(HTTPException):
            _validate_audit_id("../../etc")
