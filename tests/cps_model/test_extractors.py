"""Tests for CPS feature extractors on Markdown-converted HTML."""
from __future__ import annotations

import markdown as md

from core.cps_model.extractors import (
    AuthorityFeatureExtractor,
    CitabilityFeatureExtractor,
    StructuralFeatureExtractor,
)

_MD_EXTENSIONS = ["tables", "fenced_code", "nl2br", "sane_lists"]


def _md_to_html(markdown_text: str) -> str:
    converter = md.Markdown(extensions=_MD_EXTENSIONS)
    return converter.convert(markdown_text)


# ---------------------------------------------------------------------------
# Structural extractor
# ---------------------------------------------------------------------------


class TestStructuralExtractor:
    def test_headers_detected_from_markdown(self) -> None:
        html = _md_to_html("# H1\n\n## H2\n\n### H3\n")
        features = StructuralFeatureExtractor().extract(html)
        assert features["header_count"] == 3
        assert features["header_depth"] == 3

    def test_lists_detected_from_markdown(self) -> None:
        html = _md_to_html("- item1\n- item2\n- item3\n")
        features = StructuralFeatureExtractor().extract(html)
        assert features["has_ul_tags"] is True
        assert features["bullet_point_count"] == 3

    def test_table_detected_from_markdown(self) -> None:
        html = _md_to_html(
            "| Col A | Col B |\n|-------|-------|\n| val1  | val2  |\n"
        )
        features = StructuralFeatureExtractor().extract(html)
        assert features["has_table_tags"] is True

    def test_code_block_detected_from_markdown(self) -> None:
        html = _md_to_html("```python\nprint('hello')\n```\n")
        features = StructuralFeatureExtractor().extract(html)
        assert features["has_code_blocks"] is True

    def test_feature_count_is_12(self) -> None:
        features = StructuralFeatureExtractor().extract("<p>text</p>")
        assert len(features) == 12

    def test_empty_content(self) -> None:
        features = StructuralFeatureExtractor().extract("")
        assert features["header_count"] == 0
        assert features["snippet_length_words"] == 0


# ---------------------------------------------------------------------------
# Citability extractor
# ---------------------------------------------------------------------------


class TestCitabilityExtractor:
    def test_feature_count_is_9(self) -> None:
        features = CitabilityFeatureExtractor().extract("This is a test sentence.")
        assert len(features) == 9

    def test_factual_density_with_numbers(self) -> None:
        features = CitabilityFeatureExtractor().extract(
            "Revenue grew 25% in 2024 to $1.5 billion."
        )
        assert features["factual_density"] > 0
        assert features["data_points_count"] > 0

    def test_definition_and_explanation_detected(self) -> None:
        features = CitabilityFeatureExtractor().extract(
            "CPS is a citation signal predictor because it uses deep learning."
        )
        assert features["definition_present"] is True
        assert features["explanation_present"] is True

    def test_faq_section_detected(self) -> None:
        features = CitabilityFeatureExtractor().extract(
            "Frequently Asked Questions\nWhat is CPS? CPS is a model."
        )
        assert features["has_faq_section"] is True


# ---------------------------------------------------------------------------
# Authority extractor
# ---------------------------------------------------------------------------


class TestAuthorityExtractor:
    def test_feature_count_is_9(self) -> None:
        features = AuthorityFeatureExtractor().extract_from_url(
            "https://example.com", "<p>text</p>"
        )
        assert len(features) == 9

    def test_https_detected(self) -> None:
        features = AuthorityFeatureExtractor().extract_from_url(
            "https://example.com"
        )
        assert features["https_status"] is True

    def test_gov_edu_detected(self) -> None:
        features = AuthorityFeatureExtractor().extract_from_url(
            "https://mit.edu/research"
        )
        assert features["is_gov_edu"] is True
        assert features["domain_authority"] == 10.0

    def test_citations_detected_in_html(self) -> None:
        html = '<p>See reference [1] and doi:10.1234 for details.</p>'
        features = AuthorityFeatureExtractor().extract_from_url(
            "https://example.com", html
        )
        assert features["has_citations"] is True
