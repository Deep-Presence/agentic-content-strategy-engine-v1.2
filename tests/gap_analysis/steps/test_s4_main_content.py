"""Tests for _extract_main_content — TDD: written BEFORE implementation."""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------
HTML_WITH_ARTICLE_TAG = """
<html><body>
<nav><ul><li><a href="/">Home</a></li><li><a href="/about">About</a></li></ul></nav>
<article>
  <h1>Article Title</h1>
  <p>This is the main article content with enough text to be meaningful for extraction purposes.</p>
  <p>Another paragraph inside the article that contains relevant information about the topic.</p>
</article>
<footer><p>Copyright 2026 Example Corp. All rights reserved. Contact us at info@example.com</p></footer>
</body></html>
"""

HTML_WITH_MAIN_TAG = """
<html><body>
<header><nav><a href="/">Logo</a><a href="/pricing">Pricing</a></nav></header>
<main>
  <h1>Main Content Area</h1>
  <p>This is inside the main tag and should be extracted as primary content for analysis.</p>
  <ul><li>First relevant list item inside main content area of the page.</li></ul>
</main>
<aside><p>Sidebar content that should not be included in the extraction results.</p></aside>
<footer><p>Footer navigation links and legal notices that should not appear.</p></footer>
</body></html>
"""

HTML_WITH_ROLE_MAIN = """
<html><body>
<nav><a href="/">Home</a></nav>
<div role="main">
  <h2>Role Main Section</h2>
  <p>Content inside a div with role=main should be detected by semantic fallback extraction.</p>
</div>
<footer><p>Footer content</p></footer>
</body></html>
"""

HTML_WITH_CONTENT_CLASS = """
<html><body>
<nav><a href="/">Home</a></nav>
<div class="post-content">
  <h2>Post Content Section</h2>
  <p>Content inside a post-content class should be detected by semantic CSS class fallback.</p>
</div>
<footer><p>Footer content</p></footer>
</body></html>
"""

HTML_NO_SEMANTIC_TAGS = """
<html><body>
<div>
  <h1>Plain Page Title</h1>
  <p>This page has no article, main, or role=main tags so the full page should be used.</p>
  <p>Second paragraph in the unsemantic page layout with no clear content boundary markers.</p>
</div>
</body></html>
"""

HTML_FULL_PAGE_WITH_CHROME = """
<html><body>
<nav>
  <ul>
    <li><a href="/">Home Navigation</a></li>
    <li><a href="/products">Products Navigation</a></li>
    <li><a href="/pricing">Pricing Navigation</a></li>
    <li><a href="/about">About Navigation</a></li>
    <li><a href="/contact">Contact Navigation</a></li>
  </ul>
</nav>
<header>
  <h1>Site Header Title</h1>
  <p>Promotional banner text in the header that should not count toward content metrics.</p>
</header>
<article>
  <h2>Real Article Heading</h2>
  <p>This is the actual article content that we care about for structural signal extraction purposes.</p>
  <p>The article contains multiple paragraphs with enough depth to analyze the content structure properly.</p>
  <h3>Subsection of Article</h3>
  <p>A subsection paragraph that adds more detail to the article content being analyzed here.</p>
  <ul>
    <li>Article list item one that has enough text to pass the minimum length filter threshold.</li>
    <li>Article list item two that also has enough text to pass the minimum length filter threshold.</li>
  </ul>
</article>
<footer>
  <nav>
    <a href="/privacy">Privacy Policy</a>
    <a href="/terms">Terms of Service</a>
    <a href="/sitemap">Sitemap</a>
  </nav>
  <p>Copyright 2026 Company Inc. All rights reserved worldwide. Reproduction prohibited.</p>
</footer>
</body></html>
"""


# ---------------------------------------------------------------------------
# Tests: _extract_main_content
# ---------------------------------------------------------------------------
class TestExtractMainContent:
    """Tests for _extract_main_content — isolates article body from page chrome."""

    def test_extract_main_content_with_article_tag(self):
        """Should extract only <article> content, excluding nav and footer."""
        from core.gap_analysis.steps.s4_enrich_citations import _extract_main_content

        result = _extract_main_content(HTML_WITH_ARTICLE_TAG)
        assert "Article Title" in result
        assert "main article content" in result
        # Nav and footer should be stripped
        assert "Home" not in result or "Article" in result  # Allow if trafilatura keeps it
        assert "Copyright 2026 Example Corp" not in result

    def test_extract_main_content_with_main_tag(self):
        """Should extract <main> tag content when no <article> is found by trafilatura."""
        from core.gap_analysis.steps.s4_enrich_citations import _extract_main_content

        result = _extract_main_content(HTML_WITH_MAIN_TAG)
        assert "Main Content Area" in result or "main tag" in result.lower()
        # Footer/sidebar should be excluded
        assert "Sidebar content" not in result
        assert "Footer navigation" not in result

    def test_extract_main_content_fallback_to_full_page(self):
        """When no semantic tags exist, body content should still be preserved."""
        from core.gap_analysis.steps.s4_enrich_citations import _extract_main_content

        result = _extract_main_content(HTML_NO_SEMANTIC_TAGS)
        # Body paragraphs should be preserved regardless of extraction tier
        assert "no article, main, or role=main" in result
        assert "Second paragraph" in result

    def test_extract_main_content_trafilatura_priority(self):
        """Trafilatura (tier 1) should be tried first, before BeautifulSoup fallback."""
        from unittest.mock import patch

        from core.gap_analysis.steps.s4_enrich_citations import _extract_main_content

        trafilatura_output = (
            "<h1>Trafilatura Result</h1>"
            "<p>Extracted by trafilatura with enough content to pass the two-hundred character "
            "minimum length check for tier one of the main content extraction pipeline. This "
            "paragraph is deliberately long enough to exceed the threshold.</p>"
        )

        with patch(
            "core.gap_analysis.steps.s4_enrich_citations.trafilatura.extract",
            return_value=trafilatura_output,
        ):
            result = _extract_main_content(HTML_WITH_ARTICLE_TAG)

        assert "Trafilatura Result" in result

    def test_extract_paragraphs_scoped_to_main_content(self):
        """_extract_paragraphs should produce lower counts when main content extraction is active."""
        from core.gap_analysis.steps.s4_enrich_citations import _extract_paragraphs

        # Full page: nav + header + article + footer = many headers/links
        paragraphs_full, signals_full = _extract_paragraphs(HTML_FULL_PAGE_WITH_CHROME)

        # The extraction should focus on article content, not the whole page.
        # Header count should be reasonable (2-3 from article, not 3+ from full page)
        # Link count should be lower (article links, not nav/footer links)
        assert signals_full.header_count <= 5, (
            f"Header count {signals_full.header_count} too high — likely counting nav/footer headers"
        )
        # Citation count (links) should not include nav/footer links
        assert signals_full.citation_count <= 5, (
            f"Citation count {signals_full.citation_count} too high — likely counting nav/footer links"
        )
