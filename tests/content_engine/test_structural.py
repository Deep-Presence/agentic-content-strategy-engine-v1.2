"""Tests for the structural evaluator (deterministic checks).

v2.0: Tests for weighted scoring, hard gates, and 6 new checks.
"""
from __future__ import annotations

import pytest

from core.content_engine.evaluator.structural import (
    _check_bullet_density,
    _check_faq_presence,
    _check_paragraph_length,
    _check_self_contained_claims,
    _check_sentence_length,
    _check_table_presence,
    _extract_paragraphs,
    evaluate_structural,
)
from core.models.content_generation import ContentBrief, FormattedContent, StructuralTargets


class TestStructuralEvaluator:
    def test_passing_content(self, sample_brief, sample_formatted):
        """Content meeting all structural targets should pass."""
        result = evaluate_structural(sample_formatted, sample_brief)
        assert result.dimension == "structural"
        # Should have a reasonable score (may not be 1.0 due to new checks)
        assert result.score >= 0.5

    def test_word_count_too_low(self, sample_brief):
        """Content below word count range should fail (hard gate)."""
        content = FormattedContent(
            brief_id="b-1",
            title="T",
            markdown="# Short\n\nToo short.",
            word_count=100,
            header_count=4,
            list_count=3,
            stat_count=2,
            citation_count=3,
        )
        result = evaluate_structural(content, sample_brief)
        assert result.details["word_count"]["passed"] is False
        assert result.details["word_count"]["hard_gate"] is True
        # Hard gate failure caps score at 0.5
        assert result.score <= 0.5

    def test_word_count_too_high(self, sample_brief):
        """Content above word count range should fail (hard gate)."""
        content = FormattedContent(
            brief_id="b-1",
            title="T",
            markdown="# Long\n\n" + "word " * 3000,
            word_count=3000,
            header_count=4,
            list_count=3,
            stat_count=2,
            citation_count=3,
        )
        result = evaluate_structural(content, sample_brief)
        assert result.details["word_count"]["passed"] is False
        assert result.score <= 0.5

    def test_missing_headers(self, sample_brief):
        """Content with too few headers should flag it."""
        content = FormattedContent(
            brief_id="b-1",
            title="T",
            markdown="# Only one\n\nContent here.",
            word_count=1500,
            header_count=1,
            list_count=3,
            stat_count=2,
            citation_count=3,
        )
        result = evaluate_structural(content, sample_brief)
        assert result.details["header_count"]["passed"] is False

    def test_missing_citations(self, sample_brief):
        """Content without citations should fail the citation check."""
        content = FormattedContent(
            brief_id="b-1",
            title="T",
            markdown="# Test\n\nNo citations.",
            word_count=1500,
            header_count=4,
            list_count=3,
            stat_count=2,
            citation_count=0,
        )
        result = evaluate_structural(content, sample_brief)
        assert result.details["citation_count"]["passed"] is False

    def test_heading_hierarchy_skip(self, sample_brief):
        """Headings that skip levels should be flagged (hard gate)."""
        content = FormattedContent(
            brief_id="b-1",
            title="T",
            markdown="## H2\n\nContent\n\n#### H4 skip\n\nMore content",
            word_count=1500,
            header_count=4,
            list_count=3,
            stat_count=2,
            citation_count=3,
        )
        result = evaluate_structural(content, sample_brief)
        assert result.details["heading_hierarchy"]["passed"] is False
        assert result.details["heading_hierarchy"]["hard_gate"] is True
        assert result.score <= 0.5

    def test_empty_sections(self, sample_brief):
        """Back-to-back headings (empty sections) should be flagged (hard gate)."""
        content = FormattedContent(
            brief_id="b-1",
            title="T",
            markdown="## Section 1\n\n## Section 2\n\nContent here",
            word_count=1500,
            header_count=4,
            list_count=3,
            stat_count=2,
            citation_count=3,
        )
        result = evaluate_structural(content, sample_brief)
        assert result.details["no_empty_sections"]["passed"] is False
        assert result.score <= 0.5

    def test_hard_gate_caps_score(self):
        """Hard gate failure should cap score at 0.5 even with perfect soft checks."""
        brief = ContentBrief(
            brief_id="b-1",
            title="T",
            word_count_range=(2000, 3000),  # Will fail
            structural_targets=StructuralTargets(min_headers=1, min_lists=0, min_citations=0),
        )
        content = FormattedContent(
            brief_id="b-1",
            title="T",
            markdown="## Header\n\nA decent paragraph with some content here that is reasonable in length.\n\n",
            word_count=100,  # Below range -> hard gate fail
            header_count=5,
            list_count=5,
            stat_count=5,
            citation_count=5,
        )
        result = evaluate_structural(content, brief)
        assert result.score <= 0.5
        assert result.passed is False

    def test_all_soft_checks_pass(self):
        """All soft checks passing with all gates passing should score high."""
        brief = ContentBrief(
            brief_id="b-1",
            title="T",
            word_count_range=(100, 500),
            structural_targets=StructuralTargets(
                min_headers=1, min_lists=1, min_citations=1, min_stats=1,
                avg_paragraph_word_count=0,  # Skip paragraph length check
                min_self_contained_claims=0,  # Skip claims check
                min_bullets_per_list=0,  # Skip bullet density
            ),
        )
        content = FormattedContent(
            brief_id="b-1",
            title="T",
            markdown="## Header\n\n- item 1\n- item 2\n\n50% stat [Source, 2024]",
            word_count=200,
            header_count=1,
            list_count=2,
            stat_count=1,
            citation_count=1,
        )
        result = evaluate_structural(content, brief)
        assert result.score >= 0.7
        assert result.passed is True

    def test_conditional_checks_skipped(self):
        """Checks with target=0 or rate<=0.3 should be skipped."""
        brief = ContentBrief(
            brief_id="b-1",
            title="T",
            word_count_range=(100, 500),
            structural_targets=StructuralTargets(
                faq_rate=0.0,  # No FAQ required
                table_rate=0.1,  # Below threshold
                avg_paragraph_word_count=0,  # Skip
                min_self_contained_claims=0,  # Skip
                min_bullets_per_list=0,  # Skip
            ),
        )
        content = FormattedContent(
            brief_id="b-1",
            title="T",
            markdown="## Header\n\n- item\n\nContent here.",
            word_count=200,
            header_count=1,
            list_count=1,
            stat_count=1,
            citation_count=1,
        )
        result = evaluate_structural(content, brief)
        assert result.details["faq_presence"]["skipped"] is True
        assert result.details["table_presence"]["skipped"] is True


class TestNewChecks:
    """Tests for the 6 new structural checks."""

    def test_faq_presence_required_and_present(self):
        brief = ContentBrief(
            brief_id="b-1", title="T",
            structural_targets=StructuralTargets(faq_rate=0.5),
        )
        content = FormattedContent(
            brief_id="b-1", title="T",
            markdown="## FAQ\n\n**Q: What is it?**\n\nA: It is a thing.",
            word_count=100,
        )
        passed, _, details = _check_faq_presence(content, brief)
        assert passed is True
        assert details["has_faq"] is True

    def test_faq_presence_required_and_missing(self):
        brief = ContentBrief(
            brief_id="b-1", title="T",
            structural_targets=StructuralTargets(faq_rate=0.5),
        )
        content = FormattedContent(
            brief_id="b-1", title="T",
            markdown="## Introduction\n\nSome content here.",
            word_count=100,
        )
        passed, feedback, _ = _check_faq_presence(content, brief)
        assert passed is False
        assert "FAQ" in feedback

    def test_table_presence_required_and_present(self):
        brief = ContentBrief(
            brief_id="b-1", title="T",
            structural_targets=StructuralTargets(table_rate=0.5),
        )
        content = FormattedContent(
            brief_id="b-1", title="T",
            markdown="## Comparison\n\n| Feature | Plan A | Plan B |\n|---|---|---|\n| Price | $10 | $20 |",
            word_count=100,
        )
        passed, _, details = _check_table_presence(content, brief)
        assert passed is True
        assert details["has_table"] is True

    def test_table_presence_required_and_missing(self):
        brief = ContentBrief(
            brief_id="b-1", title="T",
            structural_targets=StructuralTargets(table_rate=0.5),
        )
        content = FormattedContent(
            brief_id="b-1", title="T",
            markdown="## Introduction\n\nNo table here.",
            word_count=100,
        )
        passed, feedback, _ = _check_table_presence(content, brief)
        assert passed is False
        assert "table" in feedback.lower()

    def test_sentence_length_passes(self):
        brief = ContentBrief(brief_id="b-1", title="T")
        content = FormattedContent(
            brief_id="b-1", title="T",
            markdown="## Test\n\nThis is a short sentence. Another short one. And one more.",
            word_count=100,
        )
        passed, _, details = _check_sentence_length(content, brief)
        assert passed is True

    def test_bullet_density_passes(self):
        brief = ContentBrief(
            brief_id="b-1", title="T",
            structural_targets=StructuralTargets(min_bullets_per_list=3),
        )
        content = FormattedContent(
            brief_id="b-1", title="T",
            markdown="## Lists\n\n- item 1\n- item 2\n- item 3\n- item 4",
            word_count=100,
        )
        passed, _, details = _check_bullet_density(content, brief)
        assert passed is True
        assert details["avg_bullets_per_list"] >= 3

    def test_bullet_density_fails(self):
        brief = ContentBrief(
            brief_id="b-1", title="T",
            structural_targets=StructuralTargets(min_bullets_per_list=5),
        )
        content = FormattedContent(
            brief_id="b-1", title="T",
            markdown="## Lists\n\n- item 1\n- item 2",
            word_count=100,
        )
        passed, feedback, _ = _check_bullet_density(content, brief)
        assert passed is False
        assert "bullets" in feedback.lower()

    def test_self_contained_claims_passes(self):
        brief = ContentBrief(
            brief_id="b-1", title="T",
            structural_targets=StructuralTargets(min_self_contained_claims=1),
        )
        content = FormattedContent(
            brief_id="b-1", title="T",
            markdown=(
                "## Stats\n\n"
                "According to research shows, approximately 67% of Series A startups "
                "require a 409A valuation within their first year of operations. This "
                "represents a significant compliance requirement that many founders "
                "overlook during their early fundraising stages."
            ),
            word_count=100,
        )
        passed, _, details = _check_self_contained_claims(content, brief)
        assert passed is True
        assert details["claim_count"] >= 1


class TestExtractParagraphs:
    def test_basic(self):
        md = "## Header\n\nThis is a paragraph with enough words to pass the minimum threshold for counting.\n\n- list item\n\nAnother paragraph here with enough words to also pass the minimum threshold."
        paragraphs = _extract_paragraphs(md)
        assert len(paragraphs) >= 1

    def test_filters_short_fragments(self):
        md = "## H\n\nShort.\n\nThis is a longer paragraph that should pass the minimum word threshold for extraction."
        paragraphs = _extract_paragraphs(md)
        # "Short." should be filtered (< 10 words)
        for p in paragraphs:
            assert len(p.split()) >= 10
