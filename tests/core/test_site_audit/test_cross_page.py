"""Tests for cross-page analysis functions in s5_aggregate.py.

Covers:
  - _detect_duplicate_titles
  - _detect_duplicate_meta_descriptions
  - _detect_orphan_pages
  - _detect_thin_content
  - _cross_page_findings orchestrator
  - aggregate_results with internal_link_targets param
"""
from __future__ import annotations

import pytest

from core.models.site_audit import (
    AuditCheckSeverity,
    AuditDimension,
    PageAuditResult,
)
from core.site_audit.config import AuditConfig, DEFAULT_AUDIT_CONFIG
from core.models.site_audit import AIBotAccessResult, SitemapHealthResult
from core.site_audit.steps.s5_aggregate import (
    _detect_duplicate_meta_descriptions,
    _detect_duplicate_titles,
    _detect_orphan_pages,
    _detect_thin_content,
    _cross_page_findings,
    aggregate_results,
)


def _page(url: str, **kwargs) -> PageAuditResult:
    """Build a minimal PageAuditResult with overrides."""
    return PageAuditResult(url=url, status_code=200, crawl_depth=0, **kwargs)


# ---------------------------------------------------------------------------
# _detect_duplicate_titles
# ---------------------------------------------------------------------------


class TestDetectDuplicateTitles:
    def test_no_duplicates(self) -> None:
        pages = [_page("https://a.com/1", title="Page One"), _page("https://a.com/2", title="Page Two")]
        assert _detect_duplicate_titles(pages) == []

    def test_duplicates_found(self) -> None:
        pages = [
            _page("https://a.com/1", title="Same Title"),
            _page("https://a.com/2", title="same title"),  # case-insensitive
            _page("https://a.com/3", title="Different"),
        ]
        findings = _detect_duplicate_titles(pages)
        assert len(findings) == 1
        assert findings[0].finding_type == "duplicate_title"
        assert findings[0].dimension == AuditDimension.on_page_seo
        assert findings[0].severity == AuditCheckSeverity.high
        assert findings[0].url == ""  # site-level finding
        assert len(findings[0].details["urls"]) == 2

    def test_empty_titles_ignored(self) -> None:
        pages = [_page("https://a.com/1", title=""), _page("https://a.com/2", title="")]
        assert _detect_duplicate_titles(pages) == []

    def test_none_titles_ignored(self) -> None:
        pages = [_page("https://a.com/1"), _page("https://a.com/2")]
        assert _detect_duplicate_titles(pages) == []

    def test_multiple_duplicate_groups(self) -> None:
        pages = [
            _page("https://a.com/1", title="Group A"),
            _page("https://a.com/2", title="Group A"),
            _page("https://a.com/3", title="Group B"),
            _page("https://a.com/4", title="Group B"),
        ]
        findings = _detect_duplicate_titles(pages)
        assert len(findings) == 2


# ---------------------------------------------------------------------------
# _detect_duplicate_meta_descriptions
# ---------------------------------------------------------------------------


class TestDetectDuplicateMetaDescriptions:
    def test_no_duplicates(self) -> None:
        pages = [
            _page("https://a.com/1", meta_description="Desc one"),
            _page("https://a.com/2", meta_description="Desc two"),
        ]
        assert _detect_duplicate_meta_descriptions(pages) == []

    def test_duplicates_found(self) -> None:
        pages = [
            _page("https://a.com/1", meta_description="Same Desc"),
            _page("https://a.com/2", meta_description="same desc"),
        ]
        findings = _detect_duplicate_meta_descriptions(pages)
        assert len(findings) == 1
        assert findings[0].finding_type == "duplicate_meta_description"
        assert findings[0].severity == AuditCheckSeverity.medium

    def test_empty_descriptions_ignored(self) -> None:
        pages = [
            _page("https://a.com/1", meta_description=""),
            _page("https://a.com/2", meta_description=""),
        ]
        assert _detect_duplicate_meta_descriptions(pages) == []


# ---------------------------------------------------------------------------
# _detect_orphan_pages
# ---------------------------------------------------------------------------


class TestDetectOrphanPages:
    def test_no_orphans(self) -> None:
        sitemap = ["https://a.com/1", "https://a.com/2"]
        linked = {"https://a.com/1", "https://a.com/2"}
        assert _detect_orphan_pages(sitemap, linked) == []

    def test_orphans_detected(self) -> None:
        sitemap = ["https://a.com/1", "https://a.com/2", "https://a.com/orphan"]
        linked = {"https://a.com/1", "https://a.com/2"}
        findings = _detect_orphan_pages(sitemap, linked)
        assert len(findings) == 1
        assert findings[0].finding_type == "orphan_page"
        assert findings[0].dimension == AuditDimension.crawlability
        assert findings[0].url == "https://a.com/orphan"

    def test_empty_sitemap(self) -> None:
        assert _detect_orphan_pages([], {"https://a.com/1"}) == []

    def test_capped_at_20(self) -> None:
        sitemap = [f"https://a.com/orphan-{i}" for i in range(30)]
        linked: set[str] = set()
        findings = _detect_orphan_pages(sitemap, linked)
        assert len(findings) == 20
        # All report total_orphans = 30
        assert findings[0].details["total_orphans"] == 30


# ---------------------------------------------------------------------------
# _detect_thin_content
# ---------------------------------------------------------------------------


class TestDetectThinContent:
    def test_thin_page_flagged(self) -> None:
        pages = [_page("https://a.com/thin", word_count=50)]
        findings = _detect_thin_content(pages, DEFAULT_AUDIT_CONFIG)
        assert len(findings) == 1
        assert findings[0].finding_type == "thin_content"
        assert findings[0].severity == AuditCheckSeverity.medium

    def test_normal_page_ok(self) -> None:
        pages = [_page("https://a.com/ok", word_count=500)]
        assert _detect_thin_content(pages, DEFAULT_AUDIT_CONFIG) == []

    def test_noindex_skipped(self) -> None:
        pages = [_page("https://a.com/noindex", word_count=10, is_noindex=True)]
        assert _detect_thin_content(pages, DEFAULT_AUDIT_CONFIG) == []

    def test_redirect_skipped(self) -> None:
        pages = [_page("https://a.com/redir", word_count=10, redirect_url="https://a.com/dest")]
        assert _detect_thin_content(pages, DEFAULT_AUDIT_CONFIG) == []

    def test_custom_threshold(self) -> None:
        config = AuditConfig(thin_content_threshold=100)
        pages = [_page("https://a.com/p", word_count=150)]
        assert _detect_thin_content(pages, config) == []

    def test_zero_word_count(self) -> None:
        pages = [_page("https://a.com/empty", word_count=0)]
        findings = _detect_thin_content(pages, DEFAULT_AUDIT_CONFIG)
        assert len(findings) == 1


# ---------------------------------------------------------------------------
# _cross_page_findings orchestrator
# ---------------------------------------------------------------------------


class TestCrossPageFindings:
    def test_combines_all(self) -> None:
        pages = [
            _page("https://a.com/1", title="Dup", word_count=10),
            _page("https://a.com/2", title="Dup", word_count=500),
        ]
        findings = _cross_page_findings(
            pages,
            sitemap_urls=["https://a.com/orphan"],
            internal_link_targets=set(),
            config=DEFAULT_AUDIT_CONFIG,
        )
        types = {f.finding_type for f in findings}
        assert "duplicate_title" in types
        assert "thin_content" in types
        assert "orphan_page" in types


class TestAggregateResultsOrphanBackwardCompat:
    """Regression: aggregate_results without internal_link_targets must NOT generate orphan findings."""

    def test_no_orphans_when_link_targets_not_provided(self) -> None:
        """Old callers that don't pass internal_link_targets must not get orphan findings."""
        pages = [_page("https://a.com/p1", title="P1", word_count=500)]
        sitemap = SitemapHealthResult(
            has_sitemap=True,
            sitemap_url_count=2,
            sitemap_urls=["https://a.com/p1", "https://a.com/p2"],
        )
        result = aggregate_results(
            page_results=pages,
            ai_bot_access=AIBotAccessResult(),
            sitemap_health=sitemap,
            # internal_link_targets NOT passed (default None)
        )
        orphan_findings = [
            f for f in result.page_results[0].findings
            if f.finding_type == "orphan_page"
        ]
        # Also check cross-page findings (they're in all_findings but not on pages)
        all_types = {tf.get("finding_type") for tf in result.top_findings}
        assert "orphan_page" not in all_types
        assert orphan_findings == []

    def test_orphans_detected_when_link_targets_provided(self) -> None:
        """Orphan detection works when internal_link_targets IS provided."""
        pages = [_page("https://a.com/p1", title="P1", word_count=500)]
        sitemap = SitemapHealthResult(
            has_sitemap=True,
            sitemap_url_count=2,
            sitemap_urls=["https://a.com/p1", "https://a.com/orphan"],
        )
        result = aggregate_results(
            page_results=pages,
            ai_bot_access=AIBotAccessResult(),
            sitemap_health=sitemap,
            internal_link_targets={"https://a.com/p1"},
        )
        all_finding_types = set()
        for tf in result.top_findings:
            all_finding_types.add(tf.get("finding_type"))
        # orphan should be detected now
        assert result.total_findings > 0
