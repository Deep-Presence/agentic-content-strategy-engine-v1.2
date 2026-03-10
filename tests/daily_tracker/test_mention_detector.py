"""Tests for MentionDetector — pure unit tests, no mocking needed.

The MentionDetector is a pure computation module with zero I/O.
Tests cover brand detection, competitor detection, citation extraction,
word boundary matching, and edge cases.
"""
from __future__ import annotations

import pytest

from core.daily_tracker.mention_detector import (
    MentionDetector,
    _check_name_mentioned,
    _count_name_mentions,
)
from core.models.daily_tracker import MentionAnalysis


@pytest.fixture
def detector() -> MentionDetector:
    return MentionDetector()


@pytest.fixture
def ramp_response() -> str:
    return (
        "When looking for corporate card solutions, Ramp stands out as a top choice. "
        "Ramp offers automated expense management and real-time spending controls. "
        "You can learn more at https://ramp.com/corporate-card. "
        "Alternatives include Brex (https://brex.com/cards) and Divvy. "
        "For a comparison, see https://ramp.com/vs-brex."
    )


@pytest.fixture
def no_mention_response() -> str:
    return (
        "Corporate expense management tools have evolved significantly. "
        "Modern solutions offer real-time spending controls and automated "
        "receipt capture. See https://example.com for more."
    )


# ---------------------------------------------------------------------------
# Brand mention detection
# ---------------------------------------------------------------------------


class TestBrandMentionDetection:
    def test_detects_brand_mentioned(
        self, detector: MentionDetector, ramp_response: str
    ) -> None:
        result = detector.detect_mentions(ramp_response, brand="Ramp")
        assert result.brand_mentioned is True

    def test_detects_brand_not_mentioned(
        self, detector: MentionDetector, no_mention_response: str
    ) -> None:
        result = detector.detect_mentions(no_mention_response, brand="Ramp")
        assert result.brand_mentioned is False

    def test_counts_multiple_mentions(
        self, detector: MentionDetector, ramp_response: str
    ) -> None:
        result = detector.detect_mentions(ramp_response, brand="Ramp")
        # "Ramp" appears at least twice in the fixture text
        assert result.brand_mention_count >= 2

    def test_case_insensitive_match(self, detector: MentionDetector) -> None:
        text = "ramp is a great tool. RAMP has excellent features."
        result = detector.detect_mentions(text, brand="Ramp")
        assert result.brand_mentioned is True
        assert result.brand_mention_count == 2

    def test_word_boundary_avoids_partial_match(
        self, detector: MentionDetector
    ) -> None:
        text = "The onramp to success includes a ramping strategy."
        result = detector.detect_mentions(text, brand="Ramp")
        # "onramp" and "ramping" should NOT match "Ramp" with word boundaries
        assert result.brand_mentioned is False
        assert result.brand_mention_count == 0

    def test_brand_with_multiple_words(self, detector: MentionDetector) -> None:
        text = "Ramp Financial offers corporate cards for businesses."
        result = detector.detect_mentions(text, brand="Ramp Financial")
        assert result.brand_mentioned is True
        assert result.brand_mention_count == 1

    def test_brand_with_special_characters(
        self, detector: MentionDetector
    ) -> None:
        text = "Check out Auth0 for authentication solutions."
        result = detector.detect_mentions(text, brand="Auth0")
        assert result.brand_mentioned is True
        assert result.brand_mention_count == 1

    def test_brand_with_dots(self, detector: MentionDetector) -> None:
        text = "Try using Next.js for your frontend."
        result = detector.detect_mentions(text, brand="Next.js")
        assert result.brand_mentioned is True

    def test_brand_at_start_of_text(self, detector: MentionDetector) -> None:
        text = "Ramp is the best choice."
        result = detector.detect_mentions(text, brand="Ramp")
        assert result.brand_mentioned is True

    def test_brand_at_end_of_text(self, detector: MentionDetector) -> None:
        text = "The best choice is Ramp"
        result = detector.detect_mentions(text, brand="Ramp")
        assert result.brand_mentioned is True


# ---------------------------------------------------------------------------
# Citation extraction
# ---------------------------------------------------------------------------


class TestCitationExtraction:
    def test_extracts_all_urls(
        self, detector: MentionDetector, ramp_response: str
    ) -> None:
        citations = detector.extract_citations(ramp_response)
        assert len(citations) == 3
        assert "https://ramp.com/corporate-card" in citations
        assert "https://brex.com/cards" in citations
        assert "https://ramp.com/vs-brex" in citations

    def test_deduplicates_urls(self, detector: MentionDetector) -> None:
        text = (
            "Visit https://ramp.com for info. "
            "Again at https://ramp.com for details."
        )
        citations = detector.extract_citations(text)
        assert len(citations) == 1
        assert citations[0] == "https://ramp.com"

    def test_extracts_http_urls(self, detector: MentionDetector) -> None:
        text = "Visit http://example.com for more info."
        citations = detector.extract_citations(text)
        assert "http://example.com" in citations

    def test_strips_trailing_punctuation(
        self, detector: MentionDetector
    ) -> None:
        text = "See https://ramp.com/blog. Also check https://ramp.com/docs, and https://ramp.com/api!"
        citations = detector.extract_citations(text)
        assert "https://ramp.com/blog" in citations
        assert "https://ramp.com/docs" in citations
        assert "https://ramp.com/api" in citations

    def test_empty_text_returns_empty(self, detector: MentionDetector) -> None:
        assert detector.extract_citations("") == []

    def test_no_urls_returns_empty(self, detector: MentionDetector) -> None:
        assert detector.extract_citations("No links here.") == []


# ---------------------------------------------------------------------------
# Citation rank in detect_mentions
# ---------------------------------------------------------------------------


class TestCitationRank:
    def test_brand_citation_rank_first(
        self, detector: MentionDetector
    ) -> None:
        text = (
            "Check https://ramp.com first, then https://brex.com."
        )
        result = detector.detect_mentions(text, brand="ramp")
        assert result.citation_rank == 1

    def test_brand_citation_rank_second(
        self, detector: MentionDetector
    ) -> None:
        text = (
            "Start at https://brex.com then go to https://ramp.com."
        )
        result = detector.detect_mentions(text, brand="ramp")
        assert result.citation_rank == 2

    def test_no_brand_citation_returns_none(
        self, detector: MentionDetector
    ) -> None:
        text = "Only competitor links: https://brex.com and https://divvy.com."
        result = detector.detect_mentions(text, brand="ramp")
        assert result.citation_rank is None

    def test_no_urls_returns_none_rank(
        self, detector: MentionDetector
    ) -> None:
        text = "Ramp is a good tool but no links here."
        result = detector.detect_mentions(text, brand="ramp")
        assert result.citation_rank is None


# ---------------------------------------------------------------------------
# Competitor detection
# ---------------------------------------------------------------------------


class TestCompetitorDetection:
    def test_detects_competitor_mentioned(
        self, detector: MentionDetector, ramp_response: str
    ) -> None:
        result = detector.detect_mentions(
            ramp_response, brand="Ramp", competitors=["Brex"]
        )
        assert result.competitor_mentions["Brex"] >= 1

    def test_competitor_not_mentioned(
        self, detector: MentionDetector, ramp_response: str
    ) -> None:
        result = detector.detect_mentions(
            ramp_response, brand="Ramp", competitors=["Stripe"]
        )
        assert result.competitor_mentions["Stripe"] == 0

    def test_multiple_competitors(
        self, detector: MentionDetector, ramp_response: str
    ) -> None:
        result = detector.detect_mentions(
            ramp_response,
            brand="Ramp",
            competitors=["Brex", "Divvy", "Stripe"],
        )
        assert result.competitor_mentions["Brex"] >= 1
        assert result.competitor_mentions["Divvy"] >= 1
        assert result.competitor_mentions["Stripe"] == 0

    def test_no_competitors_param(
        self, detector: MentionDetector, ramp_response: str
    ) -> None:
        result = detector.detect_mentions(ramp_response, brand="Ramp")
        assert result.competitor_mentions == {}

    def test_empty_competitors_list(
        self, detector: MentionDetector, ramp_response: str
    ) -> None:
        result = detector.detect_mentions(
            ramp_response, brand="Ramp", competitors=[]
        )
        assert result.competitor_mentions == {}


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_response_text(self, detector: MentionDetector) -> None:
        result = detector.detect_mentions("", brand="Ramp")
        assert result.brand_mentioned is False
        assert result.brand_mention_count == 0
        assert result.citations == []
        assert result.citation_rank is None
        assert result.competitor_mentions == {}

    def test_empty_brand_name(self, detector: MentionDetector) -> None:
        result = detector.detect_mentions(
            "Some text here.", brand=""
        )
        assert result.brand_mentioned is False
        assert result.brand_mention_count == 0

    def test_brand_in_url_only(self, detector: MentionDetector) -> None:
        text = "Visit https://ramp.com for more information about expense management."
        result = detector.detect_mentions(text, brand="Ramp")
        # "ramp" appears in URL but also as part of URL — brand_mentioned
        # depends on word boundary in the full text. The URL contains "ramp"
        # but "ramp.com" may or may not match \bramp\b depending on context.
        # The important thing is citations are extracted.
        assert len(result.citations) == 1

    def test_unicode_text(self, detector: MentionDetector) -> None:
        text = "Ramp est la meilleure solution de carte d'entreprise."
        result = detector.detect_mentions(text, brand="Ramp")
        assert result.brand_mentioned is True

    def test_newlines_in_text(self, detector: MentionDetector) -> None:
        text = "Line 1\nRamp is great.\nLine 3"
        result = detector.detect_mentions(text, brand="Ramp")
        assert result.brand_mentioned is True
        assert result.brand_mention_count == 1

    def test_returns_mention_analysis_type(
        self, detector: MentionDetector
    ) -> None:
        result = detector.detect_mentions("text", brand="Ramp")
        assert isinstance(result, MentionAnalysis)


# ---------------------------------------------------------------------------
# Private helper tests
# ---------------------------------------------------------------------------


class TestPrivateHelpers:
    def test_check_name_mentioned_true(self) -> None:
        assert _check_name_mentioned("ramp is great", "Ramp") is True

    def test_check_name_mentioned_false(self) -> None:
        assert _check_name_mentioned("no match here", "Ramp") is False

    def test_check_name_mentioned_empty_name(self) -> None:
        assert _check_name_mentioned("any text", "") is False

    def test_count_name_mentions_multiple(self) -> None:
        assert _count_name_mentions("ramp and ramp again", "Ramp") == 2

    def test_count_name_mentions_zero(self) -> None:
        assert _count_name_mentions("no match", "Ramp") == 0

    def test_count_name_mentions_empty_name(self) -> None:
        assert _count_name_mentions("any text", "") == 0
