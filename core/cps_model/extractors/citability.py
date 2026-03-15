"""Citability feature extractor."""
from __future__ import annotations

import logging
import re
from typing import Dict

from .base import BaseExtractor

logger = logging.getLogger(__name__)


class CitabilityFeatureExtractor(BaseExtractor):
    """Extract citability features from text."""

    def extract(self, content: str) -> Dict[str, object]:
        """Extract citability features from text content."""
        text = (content or "").strip()
        words = re.findall(r"\b\w+\b", text)
        sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]

        numeric_tokens = [w for w in words if re.search(r"\d", w)]
        factual_density = (len(numeric_tokens) / max(len(words), 1)) * 100

        specific_claims_count = 0
        for sentence in sentences:
            if re.search(r"\b(is|are|was|were|has|have)\b", sentence, re.IGNORECASE):
                specific_claims_count += 1

        data_points_count = len(numeric_tokens)
        self_contained_count = sum(1 for s in sentences if len(s.split()) >= 8)
        self_contained_ratio = self_contained_count / max(len(sentences), 1)

        definition_present = bool(re.search(r"\b\w+\s+is\s+\w+", text, re.IGNORECASE))
        explanation_present = bool(
            re.search(r"\b(because|therefore|which means|so that|as a result)\b", text, re.IGNORECASE)
        )

        reading_level = _flesch_kincaid_grade(text)
        has_key_takeaways = bool(re.search(r"\b(key takeaways|summary|in summary)\b", text, re.IGNORECASE))
        has_faq_section = bool(re.search(r"\b(faq|frequently asked questions)\b", text, re.IGNORECASE))

        features = {
            "factual_density": factual_density,
            "specific_claims_count": specific_claims_count,
            "data_points_count": data_points_count,
            "self_contained_ratio": self_contained_ratio,
            "definition_present": definition_present,
            "explanation_present": explanation_present,
            "reading_level": reading_level,
            "has_key_takeaways": has_key_takeaways,
            "has_faq_section": has_faq_section,
        }
        logger.debug(
            "Citability features: words=%d factual_density=%.2f reading_level=%.2f",
            len(words),
            factual_density,
            reading_level,
        )
        return features


def _flesch_kincaid_grade(text: str) -> float:
    """Compute Flesch-Kincaid grade level."""
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    words = re.findall(r"\b\w+\b", text)
    syllables = sum(_count_syllables(word) for word in words)

    if not sentences or not words:
        return 0.0

    words_per_sentence = len(words) / len(sentences)
    syllables_per_word = syllables / len(words)
    grade = 0.39 * words_per_sentence + 11.8 * syllables_per_word - 15.59
    # Clamp to 0 since Flesch-Kincaid can go negative for very short/simple text
    return max(0.0, grade)


def _count_syllables(word: str) -> int:
    """Very rough syllable count heuristic."""
    word = word.lower()
    vowels = "aeiouy"
    count = 0
    prev_is_vowel = False
    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_is_vowel:
            count += 1
        prev_is_vowel = is_vowel
    if word.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)
