"""Tests for content inventory URL normalization utility.

Verifies that ``normalize_url`` from ``core.content_inventory.url_utils``
is more aggressive than the site audit's version — strips query params,
forces HTTPS, and strips www.
"""
from __future__ import annotations

import pytest

from core.content_inventory.url_utils import normalize_url


class TestNormalizeUrl:
    """URL normalization for cross-source dedup."""

    def test_basic_normalization(self):
        assert normalize_url("https://example.com/blog/post") == "https://example.com/blog/post"

    def test_lowercase_scheme_and_host(self):
        assert normalize_url("HTTPS://EXAMPLE.COM/Blog") == "https://example.com/Blog"

    def test_strip_fragment(self):
        assert normalize_url("https://example.com/page#section") == "https://example.com/page"

    def test_strip_query_params(self):
        result = normalize_url("https://example.com/blog?utm_source=social&ref=123")
        assert result == "https://example.com/blog"

    def test_remove_trailing_slash(self):
        assert normalize_url("https://example.com/blog/") == "https://example.com/blog"

    def test_preserve_root_slash(self):
        """Root URL (just domain) should not have trailing slash after normalization."""
        result = normalize_url("https://example.com/")
        assert result == "https://example.com"

    def test_force_https(self):
        assert normalize_url("http://example.com/page") == "https://example.com/page"

    def test_strip_www(self):
        assert normalize_url("https://www.example.com/blog") == "https://example.com/blog"

    def test_combined_all_rules(self):
        """Test all normalization rules applied together."""
        result = normalize_url(
            "HTTP://WWW.Example.Com/Blog/Post/?utm_source=x#section"
        )
        assert result == "https://example.com/Blog/Post"

    def test_preserve_port(self):
        result = normalize_url("https://www.example.com:8080/page")
        assert result == "https://example.com:8080/page"

    def test_empty_string(self):
        assert normalize_url("") == ""

    def test_whitespace_only(self):
        assert normalize_url("   ") == "   "

    def test_url_without_scheme(self):
        """URLs without scheme should get https:// prepended."""
        result = normalize_url("example.com/blog")
        assert result == "https://example.com/blog"

    def test_url_with_path_only(self):
        """Relative-looking URL gets scheme prepended."""
        result = normalize_url("example.com")
        assert result == "https://example.com"

    def test_idempotent(self):
        """Normalizing an already-normalized URL should return the same result."""
        url = "https://example.com/blog/post"
        assert normalize_url(normalize_url(url)) == url

    def test_different_from_site_audit_on_query_params(self):
        """Content inventory strips query params; site audit preserves them.

        This is the key behavioral difference — content inventory needs
        cross-source dedup where the same page may appear with different
        query params from different sources.
        """
        url = "https://example.com/blog?page=2"
        result = normalize_url(url)
        assert "page=2" not in result
        assert result == "https://example.com/blog"

    def test_different_from_site_audit_on_www(self):
        """Content inventory strips www; site audit does not."""
        url = "https://www.example.com/page"
        result = normalize_url(url)
        assert "www." not in result

    def test_different_from_site_audit_on_https(self):
        """Content inventory forces https; site audit preserves scheme."""
        url = "http://example.com/page"
        result = normalize_url(url)
        assert result.startswith("https://")

    def test_nested_path_trailing_slash(self):
        assert normalize_url("https://example.com/a/b/c/") == "https://example.com/a/b/c"

    def test_www_with_port(self):
        """www. is stripped but port is preserved."""
        result = normalize_url("https://www.example.com:443/page")
        assert result == "https://example.com:443/page"

    def test_double_slash_protocol_relative(self):
        """Protocol-relative URLs like //example.com should become https."""
        result = normalize_url("//www.example.com/page")
        assert result == "https://example.com/page"
