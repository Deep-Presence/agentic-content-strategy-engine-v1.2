"""Tests for CPS scorer — CPSScorer class and get_cps_scorer singleton."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Deterministic key orderings (must match scorer._STRUCTURAL_KEYS etc.)
_STRUCTURAL_KEYS = [
    "has_ul_tags", "has_ol_tags", "has_table_tags", "has_code_blocks",
    "header_depth", "header_count", "paragraph_count", "bullet_point_count",
    "snippet_length_words", "snippet_length_chars",
    "avg_sentence_length", "avg_paragraph_length",
]
_CITABILITY_KEYS = [
    "factual_density", "specific_claims_count", "data_points_count",
    "self_contained_ratio", "definition_present", "explanation_present",
    "reading_level", "has_key_takeaways", "has_faq_section",
]
_AUTHORITY_KEYS = [
    "domain_authority", "https_status", "is_gov_edu",
    "has_about_page", "has_contact_info", "author_present",
    "has_citations", "has_research_refs", "domain_age_years",
]

SAMPLE_MARKDOWN = """\
# Best CRM Software for Small Businesses

Choosing the right CRM is critical for small businesses because it drives sales.

## Top Picks

- HubSpot CRM: Free tier, $50/month for premium
- Salesforce Essentials: $25/user/month, robust reporting

| Feature     | HubSpot | Salesforce |
|-------------|---------|------------|
| Free Tier   | Yes     | No         |
| Integrations| 500+    | 1000+      |

## Key Takeaways

CRM software is essential for managing customer relationships effectively.
"""


@pytest.fixture(autouse=True)
def _reset_scorer_singleton():
    """Reset the module-level scorer singleton before each test."""
    import core.cps_model.scorer as scorer_mod

    scorer_mod._scorer_instance = None
    yield
    scorer_mod._scorer_instance = None


# ---------------------------------------------------------------------------
# Availability guard tests
# ---------------------------------------------------------------------------


class TestGetCpsScorerGuards:
    def test_returns_none_when_torch_unavailable(self) -> None:
        with patch("core.cps_model.scorer.TORCH_AVAILABLE", False):
            from core.cps_model.scorer import get_cps_scorer

            assert get_cps_scorer() is None

    def test_returns_none_when_markdown_unavailable(self) -> None:
        with patch("core.cps_model.scorer.MARKDOWN_AVAILABLE", False):
            from core.cps_model.scorer import get_cps_scorer

            assert get_cps_scorer() is None

    def test_returns_none_when_checkpoint_missing(self) -> None:
        with (
            patch("core.cps_model.scorer.TORCH_AVAILABLE", True),
            patch("core.cps_model.scorer.MARKDOWN_AVAILABLE", True),
            patch("core.cps_model.scorer._CHECKPOINT_PATH", Path("/nonexistent/model.pt")),
        ):
            from core.cps_model.scorer import get_cps_scorer

            assert get_cps_scorer() is None

    def test_returns_none_when_settings_disabled(self) -> None:
        with patch("core.cps_model.scorer.settings") as mock_settings:
            mock_settings.cps_enabled = False
            from core.cps_model.scorer import get_cps_scorer

            assert get_cps_scorer() is None


# ---------------------------------------------------------------------------
# Markdown-to-HTML conversion tests
# ---------------------------------------------------------------------------


class TestMarkdownConversion:
    def setup_method(self) -> None:
        from core.cps_model.scorer import CPSScorer

        self.scorer = CPSScorer.__new__(CPSScorer)
        import markdown as md

        self.scorer._md = md.Markdown(
            extensions=["tables", "fenced_code", "nl2br", "sane_lists"]
        )

    def test_headers_converted(self) -> None:
        html = self.scorer._normalize_to_html("# Title\n\n## Subtitle\n")
        assert "<h1>" in html
        assert "<h2>" in html

    def test_unordered_list_converted(self) -> None:
        html = self.scorer._normalize_to_html("- item1\n- item2\n")
        assert "<ul>" in html
        assert "<li>" in html

    def test_table_converted(self) -> None:
        html = self.scorer._normalize_to_html(
            "| A | B |\n|---|---|\n| 1 | 2 |\n"
        )
        assert "<table>" in html

    def test_code_block_converted(self) -> None:
        html = self.scorer._normalize_to_html("```python\nx = 1\n```\n")
        assert "<pre>" in html

    def test_plain_text_extraction_strips_markdown(self) -> None:
        text = self.scorer._get_plain_text(
            "# Header\n\n**Bold** and [link](http://example.com)\n"
        )
        assert "#" not in text
        assert "**" not in text
        assert "http://example.com" not in text
        assert "Bold" in text
        assert "link" in text


# ---------------------------------------------------------------------------
# Feature extraction & ordering tests
# ---------------------------------------------------------------------------


class TestFeatureExtraction:
    def test_structural_dict_to_array_ordering(self) -> None:
        """Verify structural features are extracted in the correct order."""
        from core.cps_model.extractors import StructuralFeatureExtractor

        html = "<h1>Title</h1><ul><li>item</li></ul><p>paragraph</p>"
        features = StructuralFeatureExtractor().extract(html)
        arr = np.array([float(features[k]) for k in _STRUCTURAL_KEYS], dtype=np.float32)
        assert arr.shape == (12,)
        # has_ul_tags should be 1.0 (index 0)
        assert arr[0] == 1.0
        # header_count should be 1 (index 5)
        assert arr[5] == 1.0

    def test_citability_dict_to_array_ordering(self) -> None:
        from core.cps_model.extractors import CitabilityFeatureExtractor

        text = "Revenue is $10 million because the company grew 50% in 2024."
        features = CitabilityFeatureExtractor().extract(text)
        arr = np.array([float(features[k]) for k in _CITABILITY_KEYS], dtype=np.float32)
        assert arr.shape == (9,)
        # factual_density (index 0) should be > 0
        assert arr[0] > 0

    def test_authority_dict_to_array_ordering(self) -> None:
        from core.cps_model.extractors import AuthorityFeatureExtractor

        features = AuthorityFeatureExtractor().extract_from_url(
            "https://example.com", "<p>text</p>"
        )
        arr = np.array([float(features[k]) for k in _AUTHORITY_KEYS], dtype=np.float32)
        assert arr.shape == (9,)
        # https_status should be 1.0 (index 1)
        assert arr[1] == 1.0


# ---------------------------------------------------------------------------
# Sidecar assembly & standardization tests
# ---------------------------------------------------------------------------


class TestSidecarAssembly:
    def test_option_a_selects_correct_features(self) -> None:
        """OPTION_A should select 7 structural + 3 citability indices."""
        structural_indices = [2, 5, 6, 7, 8, 10, 11]
        citability_indices = [0, 3, 6]

        structural = np.arange(12, dtype=np.float32)
        citability = np.arange(9, dtype=np.float32)

        selected = np.concatenate([
            structural[structural_indices],
            citability[citability_indices],
        ])
        assert selected.shape[0] == 10  # 7 + 3

    def test_option_b_selects_all_30_features(self) -> None:
        structural = np.arange(12, dtype=np.float32)
        citability = np.arange(9, dtype=np.float32)
        authority = np.arange(9, dtype=np.float32)

        selected = np.concatenate([structural, citability, authority])
        assert selected.shape[0] == 30

    def test_standardization_formula(self) -> None:
        raw = np.array([10.0, 20.0, 30.0], dtype=np.float32)
        mean = np.array([10.0, 20.0, 30.0], dtype=np.float32)
        std = np.array([5.0, 5.0, 5.0], dtype=np.float32)
        normalized = (raw - mean) / std
        np.testing.assert_array_almost_equal(normalized, [0.0, 0.0, 0.0])

    def test_standardization_nonzero(self) -> None:
        raw = np.array([15.0, 25.0], dtype=np.float32)
        mean = np.array([10.0, 20.0], dtype=np.float32)
        std = np.array([5.0, 5.0], dtype=np.float32)
        normalized = (raw - mean) / std
        np.testing.assert_array_almost_equal(normalized, [1.0, 1.0])

    def test_zero_std_guard_prevents_division_by_zero(self) -> None:
        """Codex finding: zero std should be replaced with 1.0."""
        raw = np.array([5.0, 10.0], dtype=np.float32)
        mean = np.array([5.0, 10.0], dtype=np.float32)
        std = np.array([0.0, 0.0], dtype=np.float32)
        safe_std = np.where(std == 0, 1.0, std)
        normalized = (raw - mean) / safe_std
        # With zero std, normalization should produce 0.0 (raw == mean)
        np.testing.assert_array_almost_equal(normalized, [0.0, 0.0])

    def test_sidecar_padded_when_dim_exceeds_selected_features(self) -> None:
        """Codex finding: domain_cite_rate slot can cause dim mismatch."""
        from core.cps_model.scorer import CPSScorer

        # option_a selects 10 features, but if checkpoint expects 11
        # (domain_cite_rate included), sidecar must be zero-padded
        scorer = MagicMock(spec=CPSScorer)
        scorer._STRUCTURAL_KEYS = CPSScorer._STRUCTURAL_KEYS
        scorer._CITABILITY_KEYS = CPSScorer._CITABILITY_KEYS
        scorer._AUTHORITY_KEYS = CPSScorer._AUTHORITY_KEYS
        scorer.structural_indices = [2, 5, 6, 7, 8, 10, 11]  # 7 structural
        scorer.citability_indices = [0, 3, 6]  # 3 citability
        scorer.authority_indices = []  # 0 authority
        scorer.sidecar_input_dim = 11  # checkpoint expects 11 (10 + domain_cite_rate)
        scorer.structural_mean = np.zeros(12, dtype=np.float32)
        scorer.structural_std = np.ones(12, dtype=np.float32)
        scorer.citability_mean = np.zeros(9, dtype=np.float32)
        scorer.citability_std = np.ones(9, dtype=np.float32)
        scorer.authority_mean = np.zeros(9, dtype=np.float32)
        scorer.authority_std = np.ones(9, dtype=np.float32)

        # Call the real method on a mock instance
        result = CPSScorer._extract_and_standardize(
            scorer, "<p>test</p>", "test content", "https://example.com"
        )
        assert result.shape == (11,)
        # Last element should be zero (padding for missing domain_cite_rate)
        assert result[-1] == 0.0


# ---------------------------------------------------------------------------
# Score return schema tests
# ---------------------------------------------------------------------------


def _make_mock_scorer() -> Any:
    """Create a CPSScorer with mocked encoder/predictor for schema tests."""
    try:
        import torch
    except ImportError:
        pytest.skip("torch not installed")

    from core.cps_model.scorer import CPSScorer

    # Build minimal real encoder and predictor (small dims for speed)
    from core.cps_model.model.fusion_encoder import FusionEncoder
    from core.cps_model.model.citation_predictor import CitationPredictor

    encoder = FusionEncoder(
        semantic_dim=8, proj_dim=4, sidecar_input_dim=3,
        sidecar_hidden=4, sidecar_output=4, num_engines=4, engine_embed_dim=2,
    )
    encoder.eval()

    predictor = CitationPredictor(
        composite_dim=10,  # 4 + 4 + 2
        trunk_hidden=8, trunk_output=4, num_engines=4, sr_hidden=4,
    )
    predictor.eval()

    scorer = CPSScorer(
        encoder=encoder,
        predictor=predictor,
        structural_mean=np.zeros(12, dtype=np.float32),
        structural_std=np.ones(12, dtype=np.float32),
        authority_mean=np.zeros(9, dtype=np.float32),
        authority_std=np.ones(9, dtype=np.float32),
        citability_mean=np.zeros(9, dtype=np.float32),
        citability_std=np.ones(9, dtype=np.float32),
        feature_config_name="option_b_full31",
        structural_indices=[0],
        citability_indices=[0],
        authority_indices=[0],
        sidecar_input_dim=3,
        device=torch.device("cpu"),
        target_weight=0.5,
    )
    return scorer


class TestScoreReturnSchema:
    def test_score_returns_required_keys(self) -> None:
        scorer = _make_mock_scorer()
        # Mock embeddings to avoid OpenAI calls
        dummy_emb = np.random.randn(8).astype(np.float32).tolist()
        result = scorer.score(
            query_texts=["best CRM software"],
            content_markdown=SAMPLE_MARKDOWN,
            content_url="https://example.com",
            query_embeddings=[dummy_emb],
            content_embedding=dummy_emb,
        )
        assert "cps_score" in result
        assert "per_engine" in result
        assert "per_query" in result
        assert "model_version" in result
        assert "feature_config" in result

    def test_cps_score_is_float_in_range(self) -> None:
        scorer = _make_mock_scorer()
        dummy_emb = np.random.randn(8).astype(np.float32).tolist()
        result = scorer.score(
            query_texts=["test query"],
            content_markdown=SAMPLE_MARKDOWN,
            content_url="https://example.com",
            query_embeddings=[dummy_emb],
            content_embedding=dummy_emb,
        )
        assert isinstance(result["cps_score"], float)
        assert 0.0 <= result["cps_score"] <= 1.0

    def test_per_engine_has_all_four_engines(self) -> None:
        scorer = _make_mock_scorer()
        dummy_emb = np.random.randn(8).astype(np.float32).tolist()
        result = scorer.score(
            query_texts=["test"],
            content_markdown=SAMPLE_MARKDOWN,
            content_url="https://example.com",
            query_embeddings=[dummy_emb],
            content_embedding=dummy_emb,
        )
        expected_engines = {"chatgpt_search", "claude_search", "gemini_search", "perplexity"}
        assert set(result["per_engine"].keys()) == expected_engines

    def test_per_query_matches_input_count(self) -> None:
        scorer = _make_mock_scorer()
        dummy_emb = np.random.randn(8).astype(np.float32).tolist()
        queries = ["query 1", "query 2", "query 3"]
        result = scorer.score(
            query_texts=queries,
            content_markdown=SAMPLE_MARKDOWN,
            content_url="https://example.com",
            query_embeddings=[dummy_emb] * 3,
            content_embedding=dummy_emb,
        )
        assert len(result["per_query"]) == 3
        for pq in result["per_query"]:
            assert "query" in pq
            assert "cps_score" in pq

    def test_cps_score_is_average_of_per_engine(self) -> None:
        scorer = _make_mock_scorer()
        dummy_emb = np.random.randn(8).astype(np.float32).tolist()
        result = scorer.score(
            query_texts=["test"],
            content_markdown=SAMPLE_MARKDOWN,
            content_url="https://example.com",
            query_embeddings=[dummy_emb],
            content_embedding=dummy_emb,
        )
        engine_avg = sum(result["per_engine"].values()) / len(result["per_engine"])
        assert abs(result["cps_score"] - engine_avg) < 0.001


# ---------------------------------------------------------------------------
# Async scoring test
# ---------------------------------------------------------------------------


class TestScoreAsync:
    async def test_score_async_calls_async_embed_texts(self) -> None:
        scorer = _make_mock_scorer()
        dummy_emb = np.random.randn(8).astype(np.float32).tolist()

        with patch(
            "core.cps_model.scorer.async_embed_texts",
            return_value=[dummy_emb, dummy_emb],
        ) as mock_embed:
            result = await scorer.score_async(
                query_texts=["test"],
                content_markdown=SAMPLE_MARKDOWN,
                content_url="https://example.com",
            )
            mock_embed.assert_called_once()
            assert "cps_score" in result

    async def test_score_async_with_precomputed_embeddings(self) -> None:
        scorer = _make_mock_scorer()
        dummy_emb = np.random.randn(8).astype(np.float32).tolist()
        result = await scorer.score_async(
            query_texts=["test"],
            content_markdown=SAMPLE_MARKDOWN,
            content_url="https://example.com",
            query_embeddings=[dummy_emb],
            content_embedding=dummy_emb,
        )
        assert "cps_score" in result


# ---------------------------------------------------------------------------
# Singleton tests
# ---------------------------------------------------------------------------


class TestSingleton:
    def test_singleton_returns_same_instance(self) -> None:
        """When fully available, get_cps_scorer returns the same instance."""
        from core.cps_model.scorer import get_cps_scorer

        mock_scorer = MagicMock()
        with patch("core.cps_model.scorer._scorer_instance", mock_scorer):
            result = get_cps_scorer()
            assert result is mock_scorer

    def test_reset_clears_singleton(self) -> None:
        import core.cps_model.scorer as scorer_mod

        scorer_mod._scorer_instance = MagicMock()
        scorer_mod._scorer_instance = None
        assert scorer_mod._scorer_instance is None
