"""Tests for the structural evaluator (deterministic checks)."""
from __future__ import annotations

import pytest

from core.content_engine.evaluator.structural import evaluate_structural
from core.models.content_generation import ContentBrief, FormattedContent, StructuralTargets


class TestStructuralEvaluator:
    def test_passing_content(self, sample_brief, sample_formatted):
        """Content meeting all structural targets should pass."""
        result = evaluate_structural(sample_formatted, sample_brief)
        assert result.dimension == "structural"
        assert result.passed is True
        assert result.score >= 0.8

    def test_word_count_too_low(self, sample_brief):
        """Content below word count range should fail."""
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
        assert "word_count" in result.details
        assert result.details["word_count"]["passed"] is False

    def test_word_count_too_high(self, sample_brief):
        """Content above word count range should fail."""
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
        """Headings that skip levels should be flagged."""
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

    def test_empty_sections(self, sample_brief):
        """Back-to-back headings (empty sections) should be flagged."""
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

    def test_score_computation(self):
        """Score should be passed_checks / total_checks."""
        brief = ContentBrief(
            brief_id="b-1",
            title="T",
            word_count_range=(100, 500),
            structural_targets=StructuralTargets(min_headers=1, min_lists=0, min_citations=0),
        )
        content = FormattedContent(
            brief_id="b-1",
            title="T",
            markdown="## Header\n\n- item\n\n200 words " * 20,
            word_count=200,
            header_count=1,
            list_count=1,
            stat_count=0,
            citation_count=0,
        )
        result = evaluate_structural(content, brief)
        # Most checks should pass with relaxed targets
        assert result.score > 0.5
