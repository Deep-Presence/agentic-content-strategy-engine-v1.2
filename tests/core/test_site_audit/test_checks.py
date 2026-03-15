"""Tests for core/site_audit/checks/ — all pure check functions.

Every check function is tested with:
  - valid input → no findings (or expected info-level findings)
  - each distinct error condition → correct severity + dimension
  - edge cases (empty string, None-like values, boundary values)
"""
from __future__ import annotations

from core.models.site_audit import AuditCheckSeverity, AuditDimension
from core.site_audit.checks.crawlability import (
    check_canonical,
    check_crawl_depth,
    check_noindex,
    check_status_code,
)
from core.site_audit.checks.eeat_signals import check_author, check_freshness
from core.site_audit.checks.on_page_seo import (
    check_h1,
    check_heading_hierarchy,
    check_images,
    check_internal_links,
    check_meta_description,
    check_title,
)
from core.site_audit.checks.security import (
    check_https,
    check_mixed_content,
    check_security_headers,
)
from core.site_audit.config import AuditConfig, DEFAULT_AUDIT_CONFIG

_URL = "https://example.com/page"


# ---------------------------------------------------------------------------
# crawlability.py checks
# ---------------------------------------------------------------------------


class TestCheckStatusCode:
    """Tests for check_status_code()."""

    def test_200_returns_empty(self) -> None:
        assert check_status_code(_URL, 200) == []

    def test_201_returns_empty(self) -> None:
        assert check_status_code(_URL, 201) == []

    def test_204_returns_empty(self) -> None:
        assert check_status_code(_URL, 204) == []

    def test_301_returns_info(self) -> None:
        findings = check_status_code(_URL, 301)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.info
        assert findings[0].dimension == AuditDimension.crawlability

    def test_302_returns_info(self) -> None:
        findings = check_status_code(_URL, 302)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.info

    def test_404_returns_high(self) -> None:
        findings = check_status_code(_URL, 404)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.high

    def test_403_returns_high(self) -> None:
        findings = check_status_code(_URL, 403)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.high

    def test_500_returns_critical(self) -> None:
        findings = check_status_code(_URL, 500)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.critical

    def test_503_returns_critical(self) -> None:
        findings = check_status_code(_URL, 503)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.critical

    def test_timeout_zero_returns_high(self) -> None:
        findings = check_status_code(_URL, 0)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.high

    def test_finding_has_url(self) -> None:
        findings = check_status_code(_URL, 404)
        assert findings[0].url == _URL

    def test_finding_has_status_in_details(self) -> None:
        findings = check_status_code(_URL, 500)
        assert findings[0].details.get("status_code") == 500


class TestCheckCrawlDepth:
    """Tests for check_crawl_depth()."""

    def test_depth_0_no_finding(self) -> None:
        assert check_crawl_depth(_URL, 0) == []

    def test_depth_3_no_finding(self) -> None:
        assert check_crawl_depth(_URL, 3) == []

    def test_depth_4_medium(self) -> None:
        findings = check_crawl_depth(_URL, 4)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.medium

    def test_depth_5_medium(self) -> None:
        findings = check_crawl_depth(_URL, 5)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.medium

    def test_depth_6_high(self) -> None:
        findings = check_crawl_depth(_URL, 6)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.high

    def test_depth_10_high(self) -> None:
        findings = check_crawl_depth(_URL, 10)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.high

    def test_finding_has_depth_in_details(self) -> None:
        findings = check_crawl_depth(_URL, 6)
        assert findings[0].details.get("depth") == 6

    def test_custom_max_recommended(self) -> None:
        # With max_recommended=2: depth 3 → medium
        findings = check_crawl_depth(_URL, 3, max_recommended=2)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.medium

    def test_dimension_is_crawlability(self) -> None:
        findings = check_crawl_depth(_URL, 4)
        assert findings[0].dimension == AuditDimension.crawlability


class TestCheckCanonical:
    """Tests for check_canonical()."""

    def test_has_canonical_matching_url_no_finding(self) -> None:
        findings = check_canonical(_URL, has_canonical=True, canonical_url=_URL)
        assert findings == []

    def test_missing_canonical_medium(self) -> None:
        findings = check_canonical(_URL, has_canonical=False, canonical_url=None)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.medium
        assert findings[0].finding_type == "missing_canonical"

    def test_canonical_mismatch_high(self) -> None:
        other = "https://example.com/other"
        findings = check_canonical(_URL, has_canonical=True, canonical_url=other)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.high
        assert findings[0].finding_type == "canonical_mismatch"

    def test_dimension_is_crawlability(self) -> None:
        findings = check_canonical(_URL, has_canonical=False, canonical_url=None)
        assert findings[0].dimension == AuditDimension.crawlability


class TestCheckNoindex:
    """Tests for check_noindex()."""

    def test_not_noindex_empty(self) -> None:
        assert check_noindex(_URL, False) == []

    def test_noindex_true_info(self) -> None:
        findings = check_noindex(_URL, True)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.info
        assert findings[0].dimension == AuditDimension.crawlability

    def test_finding_type(self) -> None:
        findings = check_noindex(_URL, True)
        assert findings[0].finding_type == "noindex_page"


# ---------------------------------------------------------------------------
# on_page_seo.py checks
# ---------------------------------------------------------------------------


class TestCheckTitle:
    """Tests for check_title()."""

    def test_good_title_no_finding(self) -> None:
        title = "How B2B Companies Win AI Search Citations"
        findings = check_title(_URL, title, len(title))
        assert findings == []

    def test_missing_title_critical(self) -> None:
        findings = check_title(_URL, "", 0)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.critical

    def test_short_title_high(self) -> None:
        title = "Hi"
        findings = check_title(_URL, title, len(title))
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.high

    def test_long_title_high(self) -> None:
        title = "A" * 100
        findings = check_title(_URL, title, len(title))
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.high

    def test_boilerplate_home_high(self) -> None:
        findings = check_title(_URL, "Home", 4)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.high
        assert findings[0].finding_type == "boilerplate_title"

    def test_boilerplate_untitled_high(self) -> None:
        findings = check_title(_URL, "Untitled", 8)
        assert len(findings) == 1
        assert findings[0].finding_type == "boilerplate_title"

    def test_boilerplate_case_insensitive(self) -> None:
        findings = check_title(_URL, "HOME", 4)
        assert len(findings) == 1
        assert findings[0].finding_type == "boilerplate_title"

    def test_dimension_is_on_page_seo(self) -> None:
        findings = check_title(_URL, "", 0)
        assert findings[0].dimension == AuditDimension.on_page_seo

    def test_custom_config(self) -> None:
        cfg = AuditConfig(title_min_length=10, title_max_length=20)
        # Title of 25 chars → too long
        title = "A" * 25
        findings = check_title(_URL, title, len(title), cfg)
        assert any(f.finding_type == "title_too_long" for f in findings)


class TestCheckMetaDescription:
    """Tests for check_meta_description()."""

    def test_good_meta_no_finding(self) -> None:
        # Minimum is 120 chars, maximum is 160 chars — use a 130-char description
        desc = "This is a well-crafted meta description with enough detail to satisfy SEO best practices and modern AI search engines alike."
        assert 120 <= len(desc) <= 160, f"Test fixture must be 120-160 chars, got {len(desc)}"
        findings = check_meta_description(_URL, desc, len(desc))
        assert findings == []

    def test_missing_meta_high(self) -> None:
        findings = check_meta_description(_URL, "", 0)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.high

    def test_short_meta_medium(self) -> None:
        desc = "Short desc"
        findings = check_meta_description(_URL, desc, len(desc))
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.medium

    def test_long_meta_medium(self) -> None:
        desc = "A" * 200
        findings = check_meta_description(_URL, desc, len(desc))
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.medium

    def test_dimension_is_on_page_seo(self) -> None:
        findings = check_meta_description(_URL, "", 0)
        assert findings[0].dimension == AuditDimension.on_page_seo


class TestCheckH1:
    """Tests for check_h1()."""

    def test_single_h1_no_finding(self) -> None:
        assert check_h1(_URL, 1, "Our Company") == []

    def test_zero_h1_critical(self) -> None:
        findings = check_h1(_URL, 0, "")
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.critical
        assert findings[0].finding_type == "missing_h1"

    def test_two_h1_high(self) -> None:
        findings = check_h1(_URL, 2, "First H1")
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.high
        assert findings[0].finding_type == "multiple_h1"

    def test_fifty_h1_high(self) -> None:
        findings = check_h1(_URL, 50, "H1 text")
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.high

    def test_dimension_is_on_page_seo(self) -> None:
        findings = check_h1(_URL, 0, "")
        assert findings[0].dimension == AuditDimension.on_page_seo


class TestCheckHeadingHierarchy:
    """Tests for check_heading_hierarchy()."""

    def test_valid_hierarchy_no_finding(self) -> None:
        headings = [
            {"level": "h1", "text": "Title"},
            {"level": "h2", "text": "Section"},
            {"level": "h3", "text": "Sub"},
        ]
        assert check_heading_hierarchy(_URL, headings) == []

    def test_empty_headings_no_finding(self) -> None:
        assert check_heading_hierarchy(_URL, []) == []

    def test_h1_to_h3_skip_medium(self) -> None:
        headings = [
            {"level": "h1", "text": "Title"},
            {"level": "h3", "text": "Skipped H2"},
        ]
        findings = check_heading_hierarchy(_URL, headings)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.medium

    def test_h2_to_h4_skip_medium(self) -> None:
        headings = [
            {"level": "h1", "text": "Title"},
            {"level": "h2", "text": "Section"},
            {"level": "h4", "text": "Skipped H3"},
        ]
        findings = check_heading_hierarchy(_URL, headings)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.medium

    def test_finding_has_violation_details(self) -> None:
        headings = [
            {"level": "h1", "text": "Title"},
            {"level": "h3", "text": "Skipped"},
        ]
        findings = check_heading_hierarchy(_URL, headings)
        assert "violations" in findings[0].details

    def test_dimension_is_on_page_seo(self) -> None:
        headings = [
            {"level": "h1", "text": "Title"},
            {"level": "h3", "text": "Skip"},
        ]
        findings = check_heading_hierarchy(_URL, headings)
        assert findings[0].dimension == AuditDimension.on_page_seo

    def test_malformed_heading_level_ignored(self) -> None:
        headings = [
            {"level": "hx", "text": "Weird"},
            {"level": "h1", "text": "Title"},
        ]
        # Should not crash
        findings = check_heading_hierarchy(_URL, headings)
        assert isinstance(findings, list)


class TestCheckImages:
    """Tests for check_images()."""

    def test_all_images_have_alt_no_finding(self) -> None:
        assert check_images(_URL, total=5, without_alt=0) == []

    def test_no_images_no_finding(self) -> None:
        assert check_images(_URL, total=0, without_alt=0) == []

    def test_minority_missing_alt_medium(self) -> None:
        # 1 of 10 = 10% → medium
        findings = check_images(_URL, total=10, without_alt=1)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.medium

    def test_majority_missing_alt_high(self) -> None:
        # 6 of 10 = 60% → high
        findings = check_images(_URL, total=10, without_alt=6)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.high

    def test_exactly_50pct_missing_medium(self) -> None:
        # 5 of 10 = 50% — not strictly > 50% → medium
        findings = check_images(_URL, total=10, without_alt=5)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.medium

    def test_dimension_is_on_page_seo(self) -> None:
        findings = check_images(_URL, total=10, without_alt=5)
        assert findings[0].dimension == AuditDimension.on_page_seo

    def test_finding_has_ratio_in_details(self) -> None:
        findings = check_images(_URL, total=10, without_alt=5)
        assert "ratio" in findings[0].details


class TestCheckInternalLinks:
    """Tests for check_internal_links()."""

    def test_has_links_no_finding(self) -> None:
        assert check_internal_links(_URL, 5) == []

    def test_one_link_no_finding(self) -> None:
        assert check_internal_links(_URL, 1) == []

    def test_zero_links_medium(self) -> None:
        findings = check_internal_links(_URL, 0)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.medium

    def test_dimension_is_on_page_seo(self) -> None:
        findings = check_internal_links(_URL, 0)
        assert findings[0].dimension == AuditDimension.on_page_seo


# ---------------------------------------------------------------------------
# eeat_signals.py checks
# ---------------------------------------------------------------------------


class TestCheckAuthor:
    """Tests for check_author()."""

    def test_has_author_no_finding(self) -> None:
        assert check_author(_URL, has_author=True) == []

    def test_no_author_medium(self) -> None:
        findings = check_author(_URL, has_author=False)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.medium
        assert findings[0].dimension == AuditDimension.eeat

    def test_finding_type(self) -> None:
        findings = check_author(_URL, has_author=False)
        assert findings[0].finding_type == "missing_author"


class TestCheckFreshness:
    """Tests for check_freshness()."""

    def test_no_dates_no_finding(self) -> None:
        assert check_freshness(_URL, None, None) == []

    def test_recent_date_no_finding(self) -> None:
        # 6 months ago
        findings = check_freshness(_URL, "2025-08-01", None)
        assert findings == []

    def test_over_1y_medium(self) -> None:
        findings = check_freshness(_URL, "2023-01-01", None)
        assert len(findings) >= 1
        # Should be medium or low
        severities = {f.severity for f in findings}
        assert severities & {AuditCheckSeverity.medium, AuditCheckSeverity.low}

    def test_over_2y_medium(self) -> None:
        findings = check_freshness(_URL, "2020-01-01", None)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.medium

    def test_modified_date_takes_precedence(self) -> None:
        # Old publish but recently modified → no finding
        findings = check_freshness(_URL, "2020-01-01", "2025-12-01")
        assert findings == []

    def test_unparseable_date_no_crash(self) -> None:
        findings = check_freshness(_URL, "not-a-date", None)
        assert isinstance(findings, list)

    def test_dimension_is_freshness(self) -> None:
        findings = check_freshness(_URL, "2020-01-01", None)
        if findings:
            assert findings[0].dimension == AuditDimension.freshness

    def test_with_timezone_iso_string(self) -> None:
        findings = check_freshness(_URL, "2020-06-15T10:00:00Z", None)
        assert len(findings) == 1

    def test_empty_string_publish_date(self) -> None:
        findings = check_freshness(_URL, "", None)
        assert isinstance(findings, list)


class TestRobustDateParsing:
    """Tests for _parse_date_robust via check_freshness (T-SA-23)."""

    def test_iso8601_with_timezone_offset(self) -> None:
        """ISO 8601 with +05:30 timezone offset → parsed, stale finding."""
        findings = check_freshness(_URL, "2020-06-15T10:00:00+05:30", None)
        assert len(findings) == 1  # > 2 years old

    def test_iso8601_with_z_suffix(self) -> None:
        """ISO 8601 with Z suffix → parsed correctly."""
        findings = check_freshness(_URL, "2020-01-15T10:30:00Z", None)
        assert len(findings) == 1

    def test_iso8601_with_fractional_seconds(self) -> None:
        """ISO 8601 with fractional seconds → parsed."""
        findings = check_freshness(_URL, "2020-01-15T10:30:00.123456Z", None)
        assert len(findings) == 1

    def test_human_readable_full_month(self) -> None:
        """Human-readable 'January 15, 2024' → parsed."""
        findings = check_freshness(_URL, "January 15, 2020", None)
        assert len(findings) == 1  # > 2 years old

    def test_human_readable_short_month(self) -> None:
        """Human-readable '15 Jan 2020' → parsed."""
        findings = check_freshness(_URL, "15 Jan 2020", None)
        assert len(findings) == 1

    def test_invalid_date_no_findings(self) -> None:
        """Invalid date 'not-a-date' → no findings (graceful skip)."""
        findings = check_freshness(_URL, "not-a-date", None)
        assert findings == []

    def test_oversized_string_no_findings(self) -> None:
        """String >100 chars → no findings (guard)."""
        long_date = "2020-01-01" + "x" * 100
        findings = check_freshness(_URL, long_date, None)
        assert findings == []

    def test_partial_date_year_month(self) -> None:
        """Partial date '2020-01' → parsed as first of month."""
        findings = check_freshness(_URL, "2020-01", None)
        assert len(findings) == 1  # > 2 years old


class TestMissingDateMetadata:
    """Tests for missing_date_metadata finding on article pages (T-SA-24)."""

    def test_article_no_dates_generates_finding(self) -> None:
        findings = check_freshness(_URL, None, None, page_type="article")
        assert len(findings) == 1
        assert findings[0].finding_type == "missing_date_metadata"
        assert findings[0].severity == AuditCheckSeverity.low

    def test_homepage_no_dates_no_finding(self) -> None:
        findings = check_freshness(_URL, None, None, page_type="homepage")
        assert findings == []

    def test_product_no_dates_no_finding(self) -> None:
        findings = check_freshness(_URL, None, None, page_type="product")
        assert findings == []

    def test_article_with_dates_no_missing_finding(self) -> None:
        findings = check_freshness(_URL, "2025-12-01", None, page_type="article")
        # Should not have missing_date_metadata (has dates)
        missing = [f for f in findings if f.finding_type == "missing_date_metadata"]
        assert missing == []

    def test_default_page_type_no_finding(self) -> None:
        """Default page_type='page' should not generate finding."""
        findings = check_freshness(_URL, None, None)
        assert findings == []


# ---------------------------------------------------------------------------
# security.py checks
# ---------------------------------------------------------------------------


class TestCheckHttps:
    """Tests for check_https()."""

    def test_https_no_finding(self) -> None:
        assert check_https("https://example.com/page") == []

    def test_http_critical(self) -> None:
        findings = check_https("http://example.com/page")
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.critical

    def test_dimension_is_security(self) -> None:
        findings = check_https("http://example.com/page")
        assert findings[0].dimension == AuditDimension.security

    def test_finding_type(self) -> None:
        findings = check_https("http://example.com/page")
        assert findings[0].finding_type == "not_https"

    def test_finding_has_url(self) -> None:
        url = "http://example.com/page"
        findings = check_https(url)
        assert findings[0].url == url


class TestCheckMixedContent:
    """Tests for check_mixed_content()."""

    def test_no_mixed_content_no_finding(self) -> None:
        assert check_mixed_content(_URL, False) == []

    def test_has_mixed_content_high(self) -> None:
        findings = check_mixed_content(_URL, True)
        assert len(findings) == 1
        assert findings[0].severity == AuditCheckSeverity.high

    def test_dimension_is_security(self) -> None:
        findings = check_mixed_content(_URL, True)
        assert findings[0].dimension == AuditDimension.security

    def test_finding_type(self) -> None:
        findings = check_mixed_content(_URL, True)
        assert findings[0].finding_type == "mixed_content"


# ---------------------------------------------------------------------------
# check_security_headers
# ---------------------------------------------------------------------------


class TestCheckSecurityHeaders:
    def test_all_headers_present_no_findings(self) -> None:
        headers = {
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        }
        assert check_security_headers(_URL, headers) == []

    def test_missing_hsts(self) -> None:
        headers = {
            "Content-Security-Policy": "default-src 'self'",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        }
        findings = check_security_headers(_URL, headers)
        types = [f.finding_type for f in findings]
        assert "missing_hsts" in types

    def test_weak_hsts(self) -> None:
        headers = {
            "Strict-Transport-Security": "max-age=86400",
            "Content-Security-Policy": "default-src 'self'",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        }
        findings = check_security_headers(_URL, headers)
        types = [f.finding_type for f in findings]
        assert "weak_hsts" in types

    def test_missing_csp(self) -> None:
        headers = {
            "Strict-Transport-Security": "max-age=31536000",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        }
        findings = check_security_headers(_URL, headers)
        types = [f.finding_type for f in findings]
        assert "missing_csp" in types

    def test_weak_csp_unsafe_inline(self) -> None:
        headers = {
            "Strict-Transport-Security": "max-age=31536000",
            "Content-Security-Policy": "default-src 'self' 'unsafe-inline'",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        }
        findings = check_security_headers(_URL, headers)
        types = [f.finding_type for f in findings]
        assert "weak_csp" in types

    def test_missing_all_headers(self) -> None:
        findings = check_security_headers(_URL, {})
        types = [f.finding_type for f in findings]
        assert "missing_hsts" in types
        assert "missing_csp" in types
        assert "missing_x_content_type_options" in types
        assert "missing_x_frame_options" in types

    def test_all_security_dimension(self) -> None:
        findings = check_security_headers(_URL, {})
        for f in findings:
            assert f.dimension == AuditDimension.security

    def test_case_insensitive_headers(self) -> None:
        headers = {
            "strict-transport-security": "max-age=31536000",
            "content-security-policy": "default-src 'self'",
            "x-content-type-options": "nosniff",
            "x-frame-options": "SAMEORIGIN",
        }
        assert check_security_headers(_URL, headers) == []


# ---------------------------------------------------------------------------
# check_freshness — enhanced with http_last_modified / sitemap_lastmod
# ---------------------------------------------------------------------------


class TestCheckFreshnessEnhanced:
    def test_http_last_modified_fallback(self) -> None:
        """When no meta dates, falls back to HTTP Last-Modified."""
        findings = check_freshness(
            _URL, None, None, "article",
            http_last_modified="2026-01-01",
        )
        # Recent date — no staleness findings, but may have other findings
        stale_findings = [f for f in findings if "stale" in f.finding_type]
        assert stale_findings == []

    def test_sitemap_lastmod_fallback(self) -> None:
        """When no meta dates or HTTP header, falls back to sitemap lastmod."""
        findings = check_freshness(
            _URL, None, None, "article",
            sitemap_lastmod="2026-02-01",
        )
        stale_findings = [f for f in findings if "stale" in f.finding_type]
        assert stale_findings == []

    def test_modified_date_takes_priority(self) -> None:
        """Modified date is preferred over HTTP/sitemap fallbacks."""
        findings = check_freshness(
            _URL, None, "2026-01-01", "article",
            http_last_modified="2020-01-01",  # stale but should be ignored
            sitemap_lastmod="2020-01-01",
        )
        stale_findings = [f for f in findings if "stale" in f.finding_type]
        assert stale_findings == []

    def test_backward_compat_no_new_args(self) -> None:
        """Existing callers without new args still work."""
        findings = check_freshness(_URL, "2026-01-01", None)
        stale_findings = [f for f in findings if "stale" in f.finding_type]
        assert stale_findings == []
