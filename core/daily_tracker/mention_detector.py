"""Mention Detector — deterministic brand/competitor mention and citation detection.

Analyzes LLM platform responses for brand name mentions, competitor mentions,
and citation URL extraction.  All detection is regex/string-based with word
boundary matching — no LLM calls, sub-millisecond latency per response.

Why regex over LLM for mention detection:
    - Deterministic: same input always produces same output
    - Free: no API cost per detection
    - Fast: sub-ms latency vs seconds for LLM calls
    - Testable: pure functions, trivial to unit-test

Implements ``MentionDetectorProtocol`` from ``core.daily_tracker.protocols``.
"""
from __future__ import annotations

import re
import logging

from core.models.daily_tracker import MentionAnalysis

logger = logging.getLogger(__name__)

# Why: pre-compiled URL pattern for extraction performance across many responses.
# Matches http:// and https:// URLs, stops at whitespace or common delimiters.
_URL_PATTERN = re.compile(r"https?://[^\s<>\"')\]\},]+")


class MentionDetector:
    """Detects brand and competitor mentions in LLM response text.

    Pure computation — no database, no API calls, no I/O.
    Implements ``MentionDetectorProtocol``.

    Detection strategy:
        - Brand/competitor names: case-insensitive word-boundary regex matching.
        - Citations: URL extraction via regex, then domain matching.
        - Citation rank: 1-indexed position of first brand-domain URL among all URLs.
    """

    def detect_mentions(
        self,
        response_text: str,
        brand: str,
        competitors: list[str] | None = None,
    ) -> MentionAnalysis:
        """Detect brand and competitor mentions in a response.

        Args:
            response_text: Full LLM response text to analyze.
            brand: Primary brand name to detect (e.g. "Ramp").
            competitors: Optional list of competitor names to detect.

        Returns:
            MentionAnalysis with mention flags, counts, citations, and rank.
        """
        if not response_text:
            return MentionAnalysis()

        text_lower = response_text.lower()

        # Brand mention detection
        brand_mentioned = _check_name_mentioned(text_lower, brand)
        brand_mention_count = _count_name_mentions(text_lower, brand)

        # Competitor mention detection
        competitor_mentions: dict[str, int] = {}
        if competitors:
            for comp in competitors:
                count = _count_name_mentions(text_lower, comp)
                # Why: include all competitors in the map, even with 0 mentions,
                # so consumers can see the full competitive landscape.
                competitor_mentions[comp] = count

        # Citation extraction
        citations = self.extract_citations(response_text)

        # Citation rank: 1-indexed position of first URL in the full response
        # (not just brand URLs — rank is position among ALL URLs)
        citation_rank: int | None = None
        all_urls = _URL_PATTERN.findall(response_text)
        if all_urls and brand:
            brand_lower = brand.lower()
            for idx, url in enumerate(all_urls, start=1):
                if brand_lower in url.lower():
                    citation_rank = idx
                    break

        return MentionAnalysis(
            brand_mentioned=brand_mentioned,
            brand_mention_count=brand_mention_count,
            competitor_mentions=competitor_mentions,
            citations=citations,
            citation_rank=citation_rank,
        )

    def extract_citations(self, response_text: str) -> list[str]:
        """Extract all URLs from response text.

        Args:
            response_text: Full LLM response text.

        Returns:
            De-duplicated list of URLs found in the text, preserving order.
        """
        if not response_text:
            return []

        raw_urls = _URL_PATTERN.findall(response_text)

        # Why: deduplicate while preserving first-occurrence order.
        seen: set[str] = set()
        unique: list[str] = []
        for url in raw_urls:
            # Strip trailing punctuation that regex might capture
            url = url.rstrip(".,;:!?")
            if url not in seen:
                seen.add(url)
                unique.append(url)

        return unique


# ---------------------------------------------------------------------------
# Private helpers — pure functions
# ---------------------------------------------------------------------------


def _check_name_mentioned(text_lower: str, name: str) -> bool:
    """Check if a name appears in text with word boundary matching.

    Args:
        text_lower: Lowercased text to search.
        name: Name to search for (will be lowercased internally).

    Returns:
        True if the name appears as a whole word in the text.
    """
    if not name:
        return False
    pattern = r"\b" + re.escape(name.lower()) + r"\b"
    return bool(re.search(pattern, text_lower))


def _count_name_mentions(text_lower: str, name: str) -> int:
    """Count occurrences of a name in text with word boundary matching.

    Args:
        text_lower: Lowercased text to search.
        name: Name to count (will be lowercased internally).

    Returns:
        Number of word-boundary matches found.
    """
    if not name:
        return 0
    pattern = r"\b" + re.escape(name.lower()) + r"\b"
    return len(re.findall(pattern, text_lower))
