"""Tests for the Formatter worker."""
from __future__ import annotations

import pytest

from core.content_engine.workers.formatter import _count_structural_elements, format_content


class TestCountStructuralElements:
    def test_headers(self):
        md = "# H1\n## H2\n### H3\ntext"
        result = _count_structural_elements(md)
        assert result["header_count"] == 3

    def test_lists(self):
        md = "- item 1\n- item 2\n1. numbered\n* star"
        result = _count_structural_elements(md)
        assert result["list_count"] == 4

    def test_stats(self):
        md = "Revenue grew 42% year over year.\nARR reached $10 million."
        result = _count_structural_elements(md)
        assert result["stat_count"] >= 2

    def test_citations(self):
        md = "According to [Gartner, 2024], the market grew. Also see [Forrester, 2023]."
        result = _count_structural_elements(md)
        assert result["citation_count"] == 2

    def test_empty(self):
        result = _count_structural_elements("")
        assert result["header_count"] == 0


@pytest.mark.asyncio
async def test_format_content(sample_enriched, mock_anthropic_formatter):
    """Formatter should produce formatted content with structural counts."""
    result = await format_content(
        enriched=sample_enriched,
        style_guide_md="Write clearly.",
    )

    assert result.brief_id == "brief-001"
    assert result.word_count > 0
    assert result.header_count >= 0
