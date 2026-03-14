"""Tests for core/site_audit/checks/performance_structural.py.

Covers all five pure check functions with passing, warning, and critical cases.
"""
from __future__ import annotations

from core.models.site_audit import AuditCheckSeverity, AuditDimension
from core.site_audit.checks.performance_structural import (
    check_image_optimization,
    check_inline_code_weight,
    check_page_size,
    check_render_blocking,
    check_resource_counts,
)
from core.site_audit.config import AuditConfig

_URL = "https://example.com/page"
_CFG = AuditConfig()


# ---------------------------------------------------------------------------
# check_page_size
# ---------------------------------------------------------------------------


class TestCheckPageSize:
    def test_small_page_no_finding(self) -> None:
        assert check_page_size(_URL, 50 * 1024, _CFG) == []

    def test_warn_threshold(self) -> None:
        findings = check_page_size(_URL, 250 * 1024, _CFG)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.medium
        assert findings[0].finding_type == "large_html"
        assert findings[0].dimension == AuditDimension.performance

    def test_critical_threshold(self) -> None:
        findings = check_page_size(_URL, 600 * 1024, _CFG)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.high
        assert findings[0].finding_type == "oversized_html"

    def test_exact_warn_boundary(self) -> None:
        # Exactly at warn boundary — not above, so no finding
        assert check_page_size(_URL, 200 * 1024, _CFG) == []

    def test_just_above_warn(self) -> None:
        findings = check_page_size(_URL, 200 * 1024 + 1, _CFG)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.medium


# ---------------------------------------------------------------------------
# check_resource_counts
# ---------------------------------------------------------------------------


class TestCheckResourceCounts:
    def test_low_count_no_finding(self) -> None:
        assert check_resource_counts(_URL, 5, 3, _CFG) == []

    def test_warn_threshold(self) -> None:
        findings = check_resource_counts(_URL, 10, 8, _CFG)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.medium
        assert findings[0].finding_type == "many_external_resources"

    def test_critical_threshold(self) -> None:
        findings = check_resource_counts(_URL, 20, 15, _CFG)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.high
        assert findings[0].finding_type == "excessive_external_resources"

    def test_details_contain_counts(self) -> None:
        findings = check_resource_counts(_URL, 20, 15, _CFG)
        assert findings[0].details["scripts"] == 20
        assert findings[0].details["css"] == 15


# ---------------------------------------------------------------------------
# check_render_blocking
# ---------------------------------------------------------------------------


class TestCheckRenderBlocking:
    def test_no_blocking_no_finding(self) -> None:
        assert check_render_blocking(_URL, [], [], _CFG) == []

    def test_warn_threshold(self) -> None:
        scripts = ["/a.js", "/b.js", "/c.js"]
        findings = check_render_blocking(_URL, scripts, [], _CFG)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.medium

    def test_critical_threshold(self) -> None:
        scripts = [f"/s{i}.js" for i in range(4)]
        css = ["/a.css", "/b.css"]
        findings = check_render_blocking(_URL, scripts, css, _CFG)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.high
        assert findings[0].finding_type == "excessive_render_blocking"

    def test_at_warn_boundary_no_finding(self) -> None:
        # Exactly at warn boundary (2) — not above
        assert check_render_blocking(_URL, ["/a.js"], ["/b.css"], _CFG) == []


# ---------------------------------------------------------------------------
# check_image_optimization
# ---------------------------------------------------------------------------


class TestCheckImageOptimization:
    def test_no_images_no_finding(self) -> None:
        assert check_image_optimization(_URL, 0, 0, 0, 0, False, _CFG) == []

    def test_majority_missing_lazy(self) -> None:
        findings = check_image_optimization(_URL, 6, 0, 0, 10, True, _CFG)
        types = [f.finding_type for f in findings]
        assert "images_missing_lazy_loading" in types

    def test_majority_missing_dimensions(self) -> None:
        findings = check_image_optimization(_URL, 0, 6, 0, 10, True, _CFG)
        types = [f.finding_type for f in findings]
        assert "images_missing_dimensions" in types

    def test_no_srcset(self) -> None:
        findings = check_image_optimization(_URL, 0, 0, 5, 5, True, _CFG)
        types = [f.finding_type for f in findings]
        assert "no_responsive_images" in types

    def test_no_modern_formats(self) -> None:
        findings = check_image_optimization(_URL, 0, 0, 0, 5, False, _CFG)
        types = [f.finding_type for f in findings]
        assert "no_modern_image_formats" in types

    def test_all_optimized(self) -> None:
        # All images have lazy, dimensions, srcset, and at least one modern format
        findings = check_image_optimization(_URL, 2, 2, 0, 10, True, _CFG)
        # Less than 50% missing lazy/dims, some srcset present, modern formats
        types = [f.finding_type for f in findings]
        assert "images_missing_lazy_loading" not in types
        assert "images_missing_dimensions" not in types

    def test_multiple_issues_combined(self) -> None:
        findings = check_image_optimization(_URL, 8, 8, 10, 10, False, _CFG)
        assert len(findings) == 4  # lazy + dims + srcset + modern formats


# ---------------------------------------------------------------------------
# check_inline_code_weight
# ---------------------------------------------------------------------------


class TestCheckInlineCodeWeight:
    def test_small_inline_no_finding(self) -> None:
        assert check_inline_code_weight(_URL, 1024, 1024, _CFG) == []

    def test_js_warn_threshold(self) -> None:
        findings = check_inline_code_weight(_URL, 60 * 1024, 0, _CFG)
        types = [f.finding_type for f in findings]
        assert "large_inline_js" in types

    def test_js_critical_threshold(self) -> None:
        findings = check_inline_code_weight(_URL, 110 * 1024, 0, _CFG)
        types = [f.finding_type for f in findings]
        assert "excessive_inline_js" in types

    def test_css_threshold(self) -> None:
        findings = check_inline_code_weight(_URL, 0, 60 * 1024, _CFG)
        types = [f.finding_type for f in findings]
        assert "excessive_inline_css" in types

    def test_both_js_and_css(self) -> None:
        findings = check_inline_code_weight(_URL, 110 * 1024, 60 * 1024, _CFG)
        assert len(findings) == 2

    def test_all_dimension_performance(self) -> None:
        findings = check_inline_code_weight(_URL, 110 * 1024, 60 * 1024, _CFG)
        for f in findings:
            assert f.dimension == AuditDimension.performance
