"""Structural feature extractor."""
from __future__ import annotations

import logging
import re
from typing import Dict

from bs4 import BeautifulSoup

from .base import BaseExtractor

logger = logging.getLogger(__name__)


class StructuralFeatureExtractor(BaseExtractor):
    """Extract structural HTML features."""

    def extract(self, content: str) -> Dict[str, object]:
        """Extract structural features from HTML content."""
        soup = BeautifulSoup(content or "", "html.parser")
        text = soup.get_text(" ", strip=True)
        words = text.split()

        headers = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
        header_levels = [int(h.name[1]) for h in headers if h.name and h.name[1].isdigit()]

        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        paragraph_word_counts = [len(p.split()) for p in paragraphs if p]

        sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
        sentence_lengths = [len(s.split()) for s in sentences if s.strip()]

        features = {
            "has_ul_tags": bool(soup.find_all("ul")),
            "has_ol_tags": bool(soup.find_all("ol")),
            "has_table_tags": bool(soup.find_all("table")),
            "has_code_blocks": bool(soup.find_all(["code", "pre"])),
            "header_depth": max(header_levels) if header_levels else 0,
            "header_count": len(headers),
            "paragraph_count": len(paragraphs),
            "bullet_point_count": len(soup.find_all("li")),
            "snippet_length_words": len(words),
            "snippet_length_chars": len(text),
            "avg_sentence_length": sum(sentence_lengths) / len(sentence_lengths) if sentence_lengths else 0.0,
            "avg_paragraph_length": (
                sum(paragraph_word_counts) / len(paragraph_word_counts) if paragraph_word_counts else 0.0
            ),
        }
        logger.debug(
            "Structural features: headers=%d paragraphs=%d words=%d",
            features["header_count"],
            features["paragraph_count"],
            features["snippet_length_words"],
        )
        return features