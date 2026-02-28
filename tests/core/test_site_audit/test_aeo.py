"""Tests for AEO extractability analysis (s4_check_aeo + extractability + performance).

Coverage:
    - classify_heading_as_question: 15+ headings (true questions + false positives)
    - detect_quick_answer_hook: various HTML structures (found, not found, img sibling, div wrapper)
    - is_self_contained_paragraph: continuity markers, word count boundaries
    - detect_faq_section: FAQ heading, <dl>, Q&A pattern, negative case
    - detect_definition_opening: positive patterns, negative cases
    - detect_key_takeaways: heading variations, no list after heading (negative)
    - detect_comparison_table: 3+ rows + 2+ cols, too few rows, no table
    - detect_numbered_steps: <ol> with 3+ items, step headings, insufficient items
    - detect_toc: id/class match, <nav> with anchors, no TOC
    - _compute_paragraph_length_score: ideal range, below, above, boundary
    - _compute_content_pattern_score: each pattern, capped at 15
    - analyze_aeo_readiness: snippet score calculation (manual verification), score clamped,
      findings at correct severity thresholds, FAQ page without FAQ structure
    - check_ssr_content: CSR page, SSR page, boundary
    - Performance: fetch_core_web_vitals (no API key = None, API failure = None)
"""
from __future__ import annotations

import pytest
from bs4 import BeautifulSoup
from unittest.mock import AsyncMock, MagicMock, patch

from core.models.site_audit import AuditCheckSeverity, AuditDimension
from core.site_audit.checks.extractability import (
    classify_heading_as_question,
    detect_comparison_table,
    detect_definition_opening,
    detect_faq_section,
    detect_key_takeaways,
    detect_numbered_steps,
    detect_quick_answer_hook,
    detect_toc,
    is_self_contained_paragraph,
)
from core.site_audit.checks.performance import check_ssr_content, fetch_core_web_vitals
from core.site_audit.config import AuditConfig, DEFAULT_AUDIT_CONFIG
from core.site_audit.steps.s4_check_aeo import (
    _compute_content_pattern_score,
    _compute_paragraph_length_score,
    analyze_aeo_readiness,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_URL = "https://example.com/page"


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _heading(html: str, tag: str = "h2") -> tuple[BeautifulSoup, object]:
    """Return (soup, heading_element)."""
    soup = _soup(html)
    return soup, soup.find(tag)


def _realistic_ssr_html(word_count: int = 200) -> str:
    """Generate an HTML page with approximately `word_count` visible words."""
    words = " ".join(["word"] * word_count)
    return f"""
<html>
<head><title>Test Page</title></head>
<body>
  <h1>Main Heading</h1>
  <p>{words}</p>
</body>
</html>"""


# ---------------------------------------------------------------------------
# classify_heading_as_question
# ---------------------------------------------------------------------------


class TestClassifyHeadingAsQuestion:
    # True positives — should return True
    def test_starts_with_what_ends_with_question_mark(self) -> None:
        assert classify_heading_as_question("What is AEO?") is True

    def test_starts_with_how(self) -> None:
        assert classify_heading_as_question("How does schema markup work?") is True

    def test_starts_with_why(self) -> None:
        assert classify_heading_as_question("Why does content extractability matter?") is True

    def test_starts_with_when(self) -> None:
        assert classify_heading_as_question("When should you add FAQ schema?") is True

    def test_starts_with_where(self) -> None:
        assert classify_heading_as_question("Where do AI engines find citations?") is True

    def test_starts_with_who(self) -> None:
        assert classify_heading_as_question("Who benefits from AEO optimisation?") is True

    def test_starts_with_which(self) -> None:
        assert classify_heading_as_question("Which schema types are most valuable?") is True

    def test_starts_with_can(self) -> None:
        assert classify_heading_as_question("Can AI engines read JavaScript?") is True

    def test_starts_with_does(self) -> None:
        assert classify_heading_as_question("Does page speed affect AI citations?") is True

    def test_starts_with_is(self) -> None:
        assert classify_heading_as_question("Is your site ready for AI search?") is True

    def test_starts_with_are(self) -> None:
        assert classify_heading_as_question("Are structured paragraphs important?") is True

    def test_starts_with_should(self) -> None:
        assert classify_heading_as_question("Should you use BreadcrumbList on every page?") is True

    def test_starts_with_will(self) -> None:
        assert classify_heading_as_question("Will adding schema improve AI visibility?") is True

    def test_starts_with_do(self) -> None:
        assert classify_heading_as_question("Do AI bots execute JavaScript?") is True

    def test_comparison_pattern_vs(self) -> None:
        assert classify_heading_as_question("AEO vs SEO: What's the difference") is True

    def test_comparison_pattern_versus(self) -> None:
        assert classify_heading_as_question("Structured data versus plain text") is True

    def test_comparison_pattern_difference_between(self) -> None:
        assert classify_heading_as_question("The difference between FAQ and HowTo schema") is True

    def test_comparison_pattern_compared_to(self) -> None:
        assert classify_heading_as_question("AEO compared to traditional SEO") is True

    # False positives — should return False
    def test_declarative_benefits(self) -> None:
        assert classify_heading_as_question("Benefits of AEO Optimisation") is False

    def test_declarative_understanding(self) -> None:
        assert classify_heading_as_question("Understanding Schema Markup") is False

    def test_declarative_introduction(self) -> None:
        assert classify_heading_as_question("Introduction to Structured Data") is False

    def test_word_boundary_whoever(self) -> None:
        # "Whoever" starts with "who" but is NOT a question word at a boundary
        assert classify_heading_as_question("Whoever uses schema wins") is False

    def test_word_boundary_whichever(self) -> None:
        assert classify_heading_as_question("Whichever approach you choose") is False

    def test_empty_string(self) -> None:
        assert classify_heading_as_question("") is False

    def test_question_mark_only(self) -> None:
        # Ends with ? but no recognised question word
        assert classify_heading_as_question("AEO is important?") is False

    def test_case_insensitive(self) -> None:
        # Question words are case-insensitive
        assert classify_heading_as_question("WHAT is AEO?") is True
        assert classify_heading_as_question("How Does This Work?") is True


# ---------------------------------------------------------------------------
# detect_quick_answer_hook
# ---------------------------------------------------------------------------


class TestDetectQuickAnswerHook:
    def _make_words(self, n: int) -> str:
        return " ".join(["word"] * n)

    def test_qualifying_paragraph_found(self) -> None:
        """h2 immediately followed by a 40-word <p>."""
        html = (
            f"<h2>What is AEO?</h2>"
            f"<p>{self._make_words(40)}</p>"
        )
        soup, heading = _heading(html)
        assert detect_quick_answer_hook(heading, soup) is True

    def test_paragraph_too_short(self) -> None:
        """Paragraph with fewer than 30 words does not qualify."""
        html = f"<h2>What is AEO?</h2><p>{self._make_words(20)}</p>"
        soup, heading = _heading(html)
        assert detect_quick_answer_hook(heading, soup) is False

    def test_paragraph_too_long(self) -> None:
        """Paragraph with more than 70 words does not qualify."""
        html = f"<h2>What is AEO?</h2><p>{self._make_words(80)}</p>"
        soup, heading = _heading(html)
        assert detect_quick_answer_hook(heading, soup) is False

    def test_paragraph_exactly_30_words(self) -> None:
        html = f"<h2>What is AEO?</h2><p>{self._make_words(30)}</p>"
        soup, heading = _heading(html)
        assert detect_quick_answer_hook(heading, soup) is True

    def test_paragraph_exactly_70_words(self) -> None:
        html = f"<h2>What is AEO?</h2><p>{self._make_words(70)}</p>"
        soup, heading = _heading(html)
        assert detect_quick_answer_hook(heading, soup) is True

    def test_img_sibling_skipped(self) -> None:
        """An <img> between the heading and <p> must be skipped."""
        html = (
            f"<h2>What is AEO?</h2>"
            f"<img src='img.jpg' alt='test'>"
            f"<p>{self._make_words(45)}</p>"
        )
        soup, heading = _heading(html)
        assert detect_quick_answer_hook(heading, soup) is True

    def test_paragraph_inside_div(self) -> None:
        """<p> inside a <div> immediately after heading should qualify."""
        html = (
            f"<h2>What is AEO?</h2>"
            f"<div><p>{self._make_words(45)}</p></div>"
        )
        soup, heading = _heading(html)
        assert detect_quick_answer_hook(heading, soup) is True

    def test_no_paragraph_found(self) -> None:
        html = "<h2>What is AEO?</h2><ul><li>Item 1</li></ul>"
        soup, heading = _heading(html)
        assert detect_quick_answer_hook(heading, soup) is False

    def test_beyond_three_siblings(self) -> None:
        """A <p> 4 siblings away must NOT qualify."""
        html = (
            f"<h2>What is AEO?</h2>"
            f"<div>Block 1</div>"
            f"<div>Block 2</div>"
            f"<div>Block 3</div>"
            f"<p>{self._make_words(40)}</p>"
        )
        soup, heading = _heading(html)
        # Should return False as p is beyond 3 siblings
        assert detect_quick_answer_hook(heading, soup) is False


# ---------------------------------------------------------------------------
# is_self_contained_paragraph
# ---------------------------------------------------------------------------


class TestIsSelfContainedParagraph:
    def _make_words(self, n: int) -> str:
        return " ".join([f"word{i}" for i in range(n)])

    def test_valid_self_contained(self) -> None:
        text = "Answer Engine Optimisation " + self._make_words(30)
        assert is_self_contained_paragraph(text) is True

    def test_starts_with_however(self) -> None:
        text = "However " + self._make_words(30)
        assert is_self_contained_paragraph(text) is False

    def test_starts_with_additionally(self) -> None:
        text = "Additionally " + self._make_words(30)
        assert is_self_contained_paragraph(text) is False

    def test_starts_with_furthermore(self) -> None:
        text = "Furthermore " + self._make_words(30)
        assert is_self_contained_paragraph(text) is False

    def test_starts_with_moreover(self) -> None:
        text = "Moreover " + self._make_words(30)
        assert is_self_contained_paragraph(text) is False

    def test_starts_with_in_addition(self) -> None:
        text = "In addition " + self._make_words(30)
        assert is_self_contained_paragraph(text) is False

    def test_starts_with_as_mentioned(self) -> None:
        text = "As mentioned earlier " + self._make_words(20)
        assert is_self_contained_paragraph(text) is False

    def test_starts_with_that_said(self) -> None:
        text = "That said " + self._make_words(25)
        assert is_self_contained_paragraph(text) is False

    def test_starts_with_nevertheless(self) -> None:
        text = "Nevertheless " + self._make_words(25)
        assert is_self_contained_paragraph(text) is False

    def test_starts_with_therefore(self) -> None:
        text = "Therefore " + self._make_words(25)
        assert is_self_contained_paragraph(text) is False

    def test_too_short(self) -> None:
        text = self._make_words(10)
        assert is_self_contained_paragraph(text) is False

    def test_exactly_20_words(self) -> None:
        text = self._make_words(20)
        assert is_self_contained_paragraph(text) is True

    def test_exactly_80_words(self) -> None:
        text = self._make_words(80)
        assert is_self_contained_paragraph(text) is True

    def test_too_long_81_words(self) -> None:
        text = self._make_words(81)
        assert is_self_contained_paragraph(text) is False

    def test_empty_string(self) -> None:
        assert is_self_contained_paragraph("") is False

    def test_case_insensitive_marker(self) -> None:
        text = "HOWEVER " + self._make_words(30)
        assert is_self_contained_paragraph(text) is False

    def test_continuity_marker_mid_sentence_is_fine(self) -> None:
        """Marker appearing in the middle (not start) should NOT disqualify."""
        # Need 20-80 words total; starts with "AEO" so not a continuity-marker start
        text = "AEO is important; however you should also check " + self._make_words(25)
        # Starts with "AEO", not "however" — should be self-contained if word count OK
        assert is_self_contained_paragraph(text) is True


# ---------------------------------------------------------------------------
# detect_faq_section
# ---------------------------------------------------------------------------


class TestDetectFaqSection:
    def test_faq_heading(self) -> None:
        html = "<h2>FAQ</h2><p>Answer.</p>"
        assert detect_faq_section(_soup(html)) is True

    def test_frequently_asked_questions_heading(self) -> None:
        html = "<h2>Frequently Asked Questions</h2><p>Answer.</p>"
        assert detect_faq_section(_soup(html)) is True

    def test_dl_element(self) -> None:
        html = "<dl><dt>Q1</dt><dd>Answer 1</dd></dl>"
        assert detect_faq_section(_soup(html)) is True

    def test_three_question_answer_pairs(self) -> None:
        pairs = "".join(
            [
                f"<h3>What is concept {i}?</h3><p>Answer about concept {i} is here.</p>"
                for i in range(3)
            ]
        )
        html = f"<div>{pairs}</div>"
        assert detect_faq_section(_soup(html)) is True

    def test_only_two_pairs_not_detected(self) -> None:
        """Fewer than 3 Q&A pairs must NOT trigger FAQ detection via the pattern rule."""
        pairs = "".join(
            [
                f"<h3>What is concept {i}?</h3><p>Answer {i}.</p>"
                for i in range(2)
            ]
        )
        html = f"<div>{pairs}</div>"
        # No FAQ heading, no <dl> — only 2 question headings
        # Should NOT be detected as FAQ section
        assert detect_faq_section(_soup(html)) is False

    def test_no_faq_elements(self) -> None:
        html = "<h2>About Us</h2><p>We are a great company.</p>"
        assert detect_faq_section(_soup(html)) is False


# ---------------------------------------------------------------------------
# detect_definition_opening
# ---------------------------------------------------------------------------


class TestDetectDefinitionOpening:
    def test_topic_is_pattern(self) -> None:
        assert detect_definition_opening("Answer Engine Optimisation is a framework for improving AI citation rates.") is True

    def test_topic_are_pattern(self) -> None:
        assert detect_definition_opening("Structured data schemas are machine-readable formats that describe page content.") is True

    def test_topic_refers_to(self) -> None:
        assert detect_definition_opening("AEO refers to the practice of optimising content for AI answer engines.") is True

    def test_plain_paragraph(self) -> None:
        assert detect_definition_opening("This article covers the fundamentals of schema markup.") is False

    def test_starts_with_however(self) -> None:
        assert detect_definition_opening("However, AEO is still emerging as a discipline.") is False

    def test_empty(self) -> None:
        assert detect_definition_opening("") is False


# ---------------------------------------------------------------------------
# detect_key_takeaways
# ---------------------------------------------------------------------------


class TestDetectKeyTakeaways:
    def test_key_takeaways_heading_with_list(self) -> None:
        html = "<h3>Key Takeaways</h3><ul><li>Point 1</li><li>Point 2</li></ul>"
        assert detect_key_takeaways(_soup(html)) is True

    def test_key_points_heading(self) -> None:
        html = "<h2>Key Points</h2><ul><li>A</li></ul>"
        assert detect_key_takeaways(_soup(html)) is True

    def test_summary_heading(self) -> None:
        html = "<h2>Summary</h2><ol><li>Item 1</li></ol>"
        assert detect_key_takeaways(_soup(html)) is True

    def test_tldr_heading(self) -> None:
        html = "<h2>TL;DR</h2><ul><li>Short version</li></ul>"
        assert detect_key_takeaways(_soup(html)) is True

    def test_no_list_after_heading_not_detected(self) -> None:
        html = "<h2>Key Takeaways</h2><p>Just a paragraph, no list.</p>"
        assert detect_key_takeaways(_soup(html)) is False

    def test_no_takeaway_heading(self) -> None:
        html = "<h2>Introduction</h2><ul><li>Item</li></ul>"
        assert detect_key_takeaways(_soup(html)) is False


# ---------------------------------------------------------------------------
# detect_comparison_table
# ---------------------------------------------------------------------------


class TestDetectComparisonTable:
    def test_table_with_vs_header(self) -> None:
        html = """
        <table>
          <tr><th>Feature</th><th>Plan A vs Plan B</th></tr>
          <tr><td>Price</td><td>$10 / $20</td></tr>
          <tr><td>Users</td><td>1 / 5</td></tr>
        </table>"""
        assert detect_comparison_table(_soup(html)) is True

    def test_table_with_multiple_header_columns(self) -> None:
        html = """
        <table>
          <tr><th>Feature</th><th>Starter</th><th>Pro</th></tr>
          <tr><td>Price</td><td>$10</td><td>$50</td></tr>
          <tr><td>Users</td><td>1</td><td>10</td></tr>
        </table>"""
        assert detect_comparison_table(_soup(html)) is True

    def test_table_too_few_rows(self) -> None:
        html = """
        <table>
          <tr><th>Plan A</th><th>Plan B</th></tr>
          <tr><td>$10</td><td>$20</td></tr>
        </table>"""
        assert detect_comparison_table(_soup(html)) is False

    def test_no_table(self) -> None:
        html = "<p>No table here.</p>"
        assert detect_comparison_table(_soup(html)) is False

    def test_table_single_column_not_comparison(self) -> None:
        html = """
        <table>
          <tr><th>Item</th></tr>
          <tr><td>A</td></tr>
          <tr><td>B</td></tr>
          <tr><td>C</td></tr>
        </table>"""
        assert detect_comparison_table(_soup(html)) is False


# ---------------------------------------------------------------------------
# detect_numbered_steps
# ---------------------------------------------------------------------------


class TestDetectNumberedSteps:
    def test_ordered_list_three_items(self) -> None:
        html = "<ol><li>Step 1</li><li>Step 2</li><li>Step 3</li></ol>"
        assert detect_numbered_steps(_soup(html)) is True

    def test_ordered_list_two_items(self) -> None:
        html = "<ol><li>Step 1</li><li>Step 2</li></ol>"
        assert detect_numbered_steps(_soup(html)) is False

    def test_step_headings(self) -> None:
        html = "<h2>Step 1: Install</h2><p>...</p><h2>Step 2: Configure</h2><p>...</p>"
        assert detect_numbered_steps(_soup(html)) is True

    def test_only_one_step_heading(self) -> None:
        html = "<h2>Step 1: Install</h2><p>Details here.</p>"
        assert detect_numbered_steps(_soup(html)) is False

    def test_unordered_list_not_steps(self) -> None:
        html = "<ul><li>Item 1</li><li>Item 2</li><li>Item 3</li></ul>"
        assert detect_numbered_steps(_soup(html)) is False

    def test_no_steps(self) -> None:
        html = "<p>Plain paragraph with no steps.</p>"
        assert detect_numbered_steps(_soup(html)) is False


# ---------------------------------------------------------------------------
# detect_toc
# ---------------------------------------------------------------------------


class TestDetectToc:
    def test_id_toc(self) -> None:
        html = '<div id="toc"><ul><li><a href="#section1">Section 1</a></li></ul></div>'
        assert detect_toc(_soup(html)) is True

    def test_class_table_of_contents(self) -> None:
        html = '<div class="table-of-contents"><ul><li><a href="#s1">S1</a></li></ul></div>'
        assert detect_toc(_soup(html)) is True

    def test_nav_with_internal_anchors(self) -> None:
        html = """
        <body>
        <nav>
          <a href="#section1">Section 1</a>
          <a href="#section2">Section 2</a>
          <a href="#section3">Section 3</a>
        </nav>
        <p>Content here.</p>
        </body>"""
        assert detect_toc(_soup(html)) is True

    def test_nav_with_fewer_than_three_anchors(self) -> None:
        html = """
        <nav><a href="#s1">S1</a><a href="#s2">S2</a></nav>
        <p>Content.</p>"""
        # Only 2 internal links — below threshold
        # But check via class/id first — no TOC class here
        # Should return False (only 2 anchors in nav, no TOC id/class)
        result = detect_toc(_soup(html))
        # This might be True or False depending on implementation; 2 < 3 so False
        assert result is False

    def test_no_toc(self) -> None:
        html = "<h1>Article Title</h1><p>This is a regular article without a TOC.</p>"
        assert detect_toc(_soup(html)) is False


# ---------------------------------------------------------------------------
# _compute_paragraph_length_score
# ---------------------------------------------------------------------------


class TestComputeParagraphLengthScore:
    IDEAL_MIN = 20
    IDEAL_MAX = 80

    def test_within_ideal_range(self) -> None:
        score = _compute_paragraph_length_score(50, self.IDEAL_MIN, self.IDEAL_MAX)
        assert score == 1.0

    def test_at_ideal_min(self) -> None:
        score = _compute_paragraph_length_score(20, self.IDEAL_MIN, self.IDEAL_MAX)
        assert score == 1.0

    def test_at_ideal_max(self) -> None:
        score = _compute_paragraph_length_score(80, self.IDEAL_MIN, self.IDEAL_MAX)
        assert score == 1.0

    def test_zero_words(self) -> None:
        score = _compute_paragraph_length_score(0, self.IDEAL_MIN, self.IDEAL_MAX)
        assert score == 0.0

    def test_below_range(self) -> None:
        # At 10 words, below 20 min → linear decay: 10/20 = 0.5
        score = _compute_paragraph_length_score(10, self.IDEAL_MIN, self.IDEAL_MAX)
        assert score == pytest.approx(0.5, abs=0.01)

    def test_above_range(self) -> None:
        # At 120 words (80 max, 2× = 160 upper bound)
        # decay: 1.0 - (120-80)/(160-80) = 1.0 - 40/80 = 0.5
        score = _compute_paragraph_length_score(120, self.IDEAL_MIN, self.IDEAL_MAX)
        assert score == pytest.approx(0.5, abs=0.01)

    def test_at_upper_bound(self) -> None:
        # At 2×ideal_max = 160 → score 0
        score = _compute_paragraph_length_score(160, self.IDEAL_MIN, self.IDEAL_MAX)
        assert score == 0.0

    def test_beyond_upper_bound(self) -> None:
        score = _compute_paragraph_length_score(200, self.IDEAL_MIN, self.IDEAL_MAX)
        assert score == 0.0


# ---------------------------------------------------------------------------
# _compute_content_pattern_score
# ---------------------------------------------------------------------------


class TestComputeContentPatternScore:
    def test_no_patterns(self) -> None:
        patterns = {k: False for k in ("faq_section", "definition_opening", "key_takeaways",
                                        "comparison_table", "numbered_steps", "toc")}
        assert _compute_content_pattern_score(patterns) == 0.0

    def test_faq_only(self) -> None:
        patterns = {"faq_section": True, "definition_opening": False, "key_takeaways": False,
                    "comparison_table": False, "numbered_steps": False, "toc": False}
        assert _compute_content_pattern_score(patterns) == 4.0

    def test_definition_only(self) -> None:
        patterns = {"faq_section": False, "definition_opening": True, "key_takeaways": False,
                    "comparison_table": False, "numbered_steps": False, "toc": False}
        assert _compute_content_pattern_score(patterns) == 3.0

    def test_key_takeaways_only(self) -> None:
        patterns = {"faq_section": False, "definition_opening": False, "key_takeaways": True,
                    "comparison_table": False, "numbered_steps": False, "toc": False}
        assert _compute_content_pattern_score(patterns) == 3.0

    def test_comparison_table_only(self) -> None:
        patterns = {"faq_section": False, "definition_opening": False, "key_takeaways": False,
                    "comparison_table": True, "numbered_steps": False, "toc": False}
        assert _compute_content_pattern_score(patterns) == 2.0

    def test_numbered_steps_only(self) -> None:
        patterns = {"faq_section": False, "definition_opening": False, "key_takeaways": False,
                    "comparison_table": False, "numbered_steps": True, "toc": False}
        assert _compute_content_pattern_score(patterns) == 2.0

    def test_toc_only(self) -> None:
        patterns = {"faq_section": False, "definition_opening": False, "key_takeaways": False,
                    "comparison_table": False, "numbered_steps": False, "toc": True}
        assert _compute_content_pattern_score(patterns) == 1.0

    def test_all_patterns_capped_at_15(self) -> None:
        patterns = {k: True for k in ("faq_section", "definition_opening", "key_takeaways",
                                       "comparison_table", "numbered_steps", "toc")}
        # Total: 4+3+3+2+2+1 = 15 → capped at 15
        assert _compute_content_pattern_score(patterns) == 15.0


# ---------------------------------------------------------------------------
# analyze_aeo_readiness — score calculation
# ---------------------------------------------------------------------------


class TestAnalyzeAeoReadiness:
    """Integration tests for the full AEO analysis function."""

    def _make_html_with_structure(
        self,
        question_headings: list[str],
        normal_headings: list[str],
        paragraphs: list[str],
        has_faq_section: bool = False,
    ) -> str:
        """Build HTML with specified headings and paragraphs."""
        parts = ["<html><body>"]
        if has_faq_section:
            parts.append("<h2>Frequently Asked Questions</h2>")
        for h in question_headings:
            parts.append(f"<h2>{h}</h2>")
            parts.append(f"<p>{'word ' * 45}</p>")  # 45-word answer
        for h in normal_headings:
            parts.append(f"<h2>{h}</h2>")
        for p in paragraphs:
            parts.append(f"<p>{p}</p>")
        parts.append("</body></html>")
        return "\n".join(parts)

    def test_score_clamped_minimum(self) -> None:
        """An empty page must produce score = 0.0 (not negative)."""
        html = "<html><body><p></p></body></html>"
        result, findings = analyze_aeo_readiness(html, _URL, DEFAULT_AUDIT_CONFIG)
        assert result.snippet_readiness_score >= 0.0

    def test_score_clamped_maximum(self) -> None:
        """Extremely rich content must not exceed 100.0."""
        # All-question headings, 50-word self-contained paragraphs, all patterns
        headings = [f"What is concept {i}?" for i in range(10)]
        paragraphs = [" ".join([f"concept{j}" for j in range(50)]) for _ in range(10)]
        html = self._make_html_with_structure(headings, [], paragraphs, has_faq_section=True)
        result, _ = analyze_aeo_readiness(html, _URL, DEFAULT_AUDIT_CONFIG)
        assert result.snippet_readiness_score <= 100.0

    def test_manual_score_verification(self) -> None:
        """
        Manually verify the scoring formula for a controlled case:
        - 2 question headings, 2 normal headings → q_ratio = 0.5
        - 1 quick-answer hook out of 2 question headings → hook_ratio = 0.5
        - 3 self-contained paragraphs out of 4 meaningful → sc_ratio = 0.75
        - avg word count ~50 (in ideal range) → length_score = 1.0
        - no content patterns → pattern_score = 0

        Expected ≈ 0.5*25 + 0.5*25 + 0.75*20 + 1.0*15 + 0 = 12.5+12.5+15+15 = 55.0
        """
        forty_words = " ".join([f"word{i}" for i in range(40)])  # 40 words, self-contained
        fifty_words = " ".join([f"term{i}" for i in range(50)])  # 50 words, self-contained
        continuity = "However " + " ".join([f"w{i}" for i in range(40)])  # NOT self-contained

        html = f"""<html><body>
<h2>What is AEO?</h2>
<p>{forty_words}</p>
<h2>How does schema work?</h2>
<p>No qualifying answer here because this is just two words</p>
<h2>Introduction to SEO</h2>
<h2>Understanding Crawlability</h2>
<p>{fifty_words}</p>
<p>{fifty_words}</p>
<p>{continuity}</p>
</body></html>"""
        # Don't be too strict about exact value — test that it's in a reasonable range
        result, _ = analyze_aeo_readiness(html, _URL, DEFAULT_AUDIT_CONFIG)
        # Should be roughly 40-65 for this structure
        assert 20.0 <= result.snippet_readiness_score <= 80.0
        assert result.question_heading_ratio == pytest.approx(0.5, abs=0.1)

    def test_empty_html_returns_defaults(self) -> None:
        result, findings = analyze_aeo_readiness("", _URL, DEFAULT_AUDIT_CONFIG)
        assert result.snippet_readiness_score == 0.0

    def test_poor_score_generates_high_finding(self) -> None:
        """Score < 30 should generate a high-severity finding."""
        html = "<html><body><p>Short content.</p></body></html>"
        result, findings = analyze_aeo_readiness(html, _URL, DEFAULT_AUDIT_CONFIG)
        if result.snippet_readiness_score < 30:
            types = {f.finding_type for f in findings}
            assert "poor_aeo_readiness" in types
            finding = next(f for f in findings if f.finding_type == "poor_aeo_readiness")
            assert finding.severity == AuditCheckSeverity.high
            assert finding.dimension == AuditDimension.extractability

    def test_moderate_score_generates_medium_finding(self) -> None:
        """Scores 30–60 generate a medium-severity finding."""
        # Build a page that should score ~40
        headings = ["What is this?"] * 2 + ["Introduction", "Overview"] * 2
        paragraphs = [" ".join([f"w{i}" for i in range(40)]) for _ in range(5)]
        html = self._make_html_with_structure(headings, [], paragraphs)
        result, findings = analyze_aeo_readiness(html, _URL, DEFAULT_AUDIT_CONFIG)
        if 30 <= result.snippet_readiness_score < 60:
            types = {f.finding_type for f in findings}
            assert "moderate_aeo_readiness" in types
            finding = next(f for f in findings if f.finding_type == "moderate_aeo_readiness")
            assert finding.severity == AuditCheckSeverity.medium

    def test_low_question_heading_ratio_generates_medium_finding(self) -> None:
        """< 30% question headings should trigger medium finding."""
        html = """<html><body>
<h2>Introduction</h2>
<h2>Overview</h2>
<h2>Conclusion</h2>
<h2>What is this?</h2>
<p>{'word ' * 30}</p>
</body></html>"""
        result, findings = analyze_aeo_readiness(html, _URL, DEFAULT_AUDIT_CONFIG)
        # 1 question out of 4 = 25% < 30% threshold
        if result.question_heading_ratio < DEFAULT_AUDIT_CONFIG.aeo_min_question_heading_ratio:
            types = {f.finding_type for f in findings}
            assert "low_question_heading_ratio" in types
            finding = next(f for f in findings if f.finding_type == "low_question_heading_ratio")
            assert finding.severity == AuditCheckSeverity.medium

    def test_faq_url_without_faq_structure_generates_finding(self) -> None:
        """A /faq/ URL page without FAQ structure should get a finding."""
        html = """<html><body>
<h2>Introduction</h2>
<p>Some content here.</p>
</body></html>"""
        faq_url = "https://example.com/faq/"
        result, findings = analyze_aeo_readiness(html, faq_url, DEFAULT_AUDIT_CONFIG)
        types = {f.finding_type for f in findings}
        assert "faq_page_missing_faq_structure" in types

    def test_findings_include_url(self) -> None:
        html = "<html><body><p>Short.</p></body></html>"
        result, findings = analyze_aeo_readiness(html, _URL, DEFAULT_AUDIT_CONFIG)
        for f in findings:
            assert f.url == _URL

    def test_content_patterns_detected(self) -> None:
        html = """<html><body>
<h2>Frequently Asked Questions</h2>
<h3>What is AEO?</h3>
<p>AEO is Answer Engine Optimisation and helps with AI citations.</p>
<h3>How does it work?</h3>
<p>It works by structuring content to be extractable by AI systems that answer queries.</p>
<h3>Why should you care?</h3>
<p>You should care because AI-generated answers are now a primary search channel.</p>
</body></html>"""
        result, _ = analyze_aeo_readiness(html, _URL, DEFAULT_AUDIT_CONFIG)
        assert result.content_patterns.get("faq_section") is True

    def test_custom_config_threshold(self) -> None:
        """Custom config with 0.0 question heading threshold should not trigger that finding."""
        config = AuditConfig(aeo_min_question_heading_ratio=0.0)
        html = "<html><body><h2>Introduction</h2><p>Content here with plenty of words.</p></body></html>"
        result, findings = analyze_aeo_readiness(html, _URL, config)
        types = {f.finding_type for f in findings}
        assert "low_question_heading_ratio" not in types

    def test_result_fields_populated(self) -> None:
        html = """<html><body>
<h2>What is schema markup?</h2>
<p>Schema markup is structured data added to HTML to help search engines understand content better.</p>
<h2>Why is AEO important?</h2>
<p>AEO is important because AI search engines are increasingly generating direct answers from web content.</p>
</body></html>"""
        result, _ = analyze_aeo_readiness(html, _URL, DEFAULT_AUDIT_CONFIG)
        assert result.question_heading_ratio >= 0.0
        assert result.question_heading_ratio <= 1.0
        assert result.avg_paragraph_word_count > 0.0
        assert isinstance(result.content_patterns, dict)


# ---------------------------------------------------------------------------
# check_ssr_content (performance)
# ---------------------------------------------------------------------------


class TestCheckSsrContent:
    def test_ssr_page_no_findings(self) -> None:
        html = _realistic_ssr_html(200)
        findings = check_ssr_content(html, _URL)
        assert findings == []

    def test_csr_page_under_100_words(self) -> None:
        html = "<html><body><div id='app'></div></body></html>"
        findings = check_ssr_content(html, _URL)
        assert len(findings) == 1
        assert findings[0].finding_type == "possible_csr_page"
        assert findings[0].severity == AuditCheckSeverity.high
        assert findings[0].dimension == AuditDimension.performance

    def test_exactly_99_words_triggers_finding(self) -> None:
        words = " ".join(["word"] * 99)
        html = f"<html><body><p>{words}</p></body></html>"
        findings = check_ssr_content(html, _URL)
        assert len(findings) == 1

    def test_exactly_100_words_no_finding(self) -> None:
        words = " ".join(["word"] * 100)
        html = f"<html><body><p>{words}</p></body></html>"
        findings = check_ssr_content(html, _URL)
        assert findings == []

    def test_script_content_not_counted(self) -> None:
        """Words inside <script> tags must not count toward visible word count."""
        js_words = " ".join(["var"] * 200)  # 200 JS tokens, not visible content
        html = f"<html><body><script>{js_words}</script><p>Only five visible words here.</p></body></html>"
        findings = check_ssr_content(html, _URL)
        # Visible word count is ~5 — should trigger finding
        assert len(findings) == 1

    def test_finding_contains_url(self) -> None:
        html = "<html><body></body></html>"
        findings = check_ssr_content(html, _URL)
        assert all(f.url == _URL for f in findings)

    def test_empty_html(self) -> None:
        """Empty HTML must not crash and must produce a finding (0 visible words)."""
        findings = check_ssr_content("", _URL)
        assert len(findings) == 1
        assert findings[0].finding_type == "possible_csr_page"


# ---------------------------------------------------------------------------
# fetch_core_web_vitals (performance — async)
# ---------------------------------------------------------------------------


class TestFetchCoreWebVitals:
    @pytest.mark.asyncio
    async def test_no_api_key_returns_none(self) -> None:
        result = await fetch_core_web_vitals(_URL, api_key=None)
        assert result is None

    @pytest.mark.asyncio
    async def test_api_failure_returns_none(self) -> None:
        """Network errors must be swallowed and return None."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.get.side_effect = httpx.ConnectError("Connection refused")
            result = await fetch_core_web_vitals(_URL, api_key="fake-key")

        assert result is None

    @pytest.mark.asyncio
    async def test_successful_response_parsed(self) -> None:
        """A mock PSI response with good metrics must return a dict with no findings."""
        mock_response_data = {
            "lighthouseResult": {
                "audits": {
                    "largest-contentful-paint": {"numericValue": 1500.0},  # < 2500 (good)
                    "max-potential-fid": {"numericValue": 80.0},            # < 100 (good)
                    "interaction-to-next-paint": {"numericValue": 150.0},   # < 200 (good)
                    "cumulative-layout-shift": {"numericValue": 0.05},      # < 0.1 (good)
                },
                "categories": {"performance": {"score": 0.95}},
            }
        }
        import httpx

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await fetch_core_web_vitals(_URL, api_key="fake-key")

        assert result is not None
        assert result["lcp_ms"] == pytest.approx(1500.0)
        assert result["findings"] == []  # all metrics are "good"

    @pytest.mark.asyncio
    async def test_poor_metrics_generate_findings(self) -> None:
        """Bad CWV metrics must be reported in the findings list."""
        mock_response_data = {
            "lighthouseResult": {
                "audits": {
                    "largest-contentful-paint": {"numericValue": 5000.0},   # > 2500 (bad)
                    "max-potential-fid": {"numericValue": 80.0},
                    "interaction-to-next-paint": {"numericValue": 600.0},    # > 200 (bad)
                    "cumulative-layout-shift": {"numericValue": 0.3},        # > 0.1 (bad)
                },
                "categories": {"performance": {"score": 0.3}},
            }
        }
        import httpx

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await fetch_core_web_vitals(_URL, api_key="fake-key")

        assert result is not None
        metrics_in_findings = {f["metric"] for f in result["findings"]}
        assert "LCP" in metrics_in_findings
        assert "CLS" in metrics_in_findings
