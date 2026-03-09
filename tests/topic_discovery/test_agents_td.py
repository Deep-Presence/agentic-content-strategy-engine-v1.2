"""Tests for Topic Discovery agents.

Covers: statistical functions (pure math), LLM agent functions (mocked),
deduplication (mocked embeddings), helper functions.
"""
from __future__ import annotations

import asyncio
import json
import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.topic_discovery import (
    CaptureRecaptureResult,
    SourceResult,
    SubdomainCandidate,
    TDSource,
    TopicAssignment,
)
from core.topic_discovery.agents import (
    _cosine_similarity,
    _count_frequency_classes,
    _count_tree_stats,
    _parse_hierarchy_nodes,
    _strip_code_fences,
    compute_all_coverage_metrics,
    compute_capture_recapture,
    compute_chao1_lower_bound,
    compute_sample_coverage,
    deduplicate_subdomains,
    run_hierarchy_construction,
    run_relevance_filtering,
    run_source_a_company_brainstorm,
    run_source_b_persona_brainstorm,
    run_source_c_competitor_sitemaps,
    run_source_d_adversarial,
    run_topic_generation,
)


# ── Statistical Functions ────────────────────────────────────────────────


class TestCaptureRecapture:
    def test_basic_estimate(self):
        """N̂ = (80 × 70) / 50 = 112.0"""
        assert compute_capture_recapture(80, 70, 50) == 112.0

    def test_perfect_overlap(self):
        """All items overlap: N̂ = count."""
        assert compute_capture_recapture(50, 50, 50) == 50.0

    def test_no_overlap_returns_zero(self):
        assert compute_capture_recapture(80, 70, 0) == 0.0

    def test_negative_overlap_returns_zero(self):
        assert compute_capture_recapture(80, 70, -1) == 0.0

    def test_single_overlap(self):
        """N̂ = (10 × 10) / 1 = 100.0"""
        assert compute_capture_recapture(10, 10, 1) == 100.0


class TestChao1LowerBound:
    def test_no_singletons(self):
        """If no singletons, estimate = observed."""
        assert compute_chao1_lower_bound(100, 0, 5) == 100.0

    def test_with_singletons_and_doubletons(self):
        """S_obs + f₁²/(2f₂) = 100 + 16/4 = 104.0"""
        assert compute_chao1_lower_bound(100, 4, 2) == 104.0

    def test_zero_doubletons_bias_corrected(self):
        """S_obs + f₁(f₁-1)/2 = 100 + 4*3/2 = 106.0"""
        assert compute_chao1_lower_bound(100, 4, 0) == 106.0

    def test_large_singletons(self):
        """S_obs + f₁²/(2f₂) = 50 + 100/4 = 75.0"""
        assert compute_chao1_lower_bound(50, 10, 2) == 75.0


class TestSampleCoverage:
    def test_basic_coverage(self):
        """Ĉ = 1 - 5/100 = 0.95"""
        assert compute_sample_coverage(5, 100) == 0.95

    def test_zero_total(self):
        assert compute_sample_coverage(5, 0) == 0.0

    def test_no_singletons(self):
        """Perfect coverage when no singletons."""
        assert compute_sample_coverage(0, 100) == 1.0

    def test_all_singletons(self):
        """Ĉ = 1 - 10/10 = 0.0"""
        assert compute_sample_coverage(10, 10) == 0.0


class TestComputeAllCoverageMetrics:
    def test_basic_computation(self):
        sr_a = SourceResult(
            source=TDSource.source_a,
            candidates=[
                SubdomainCandidate(name="expense mgmt", source=TDSource.source_a),
                SubdomainCandidate(name="corporate cards", source=TDSource.source_a),
                SubdomainCandidate(name="compliance", source=TDSource.source_a),
            ],
            singletons=1,
            doubletons=0,
        )
        sr_b = SourceResult(
            source=TDSource.source_b,
            candidates=[
                SubdomainCandidate(name="expense mgmt", source=TDSource.source_b),
                SubdomainCandidate(name="budgeting", source=TDSource.source_b),
            ],
            singletons=1,
            doubletons=0,
        )
        result = compute_all_coverage_metrics([sr_a, sr_b])
        assert isinstance(result, CaptureRecaptureResult)
        assert result.observed_count == 4  # expense, cards, compliance, budgeting
        assert len(result.pairwise_estimates) >= 1
        assert result.total_singletons == 2

    def test_empty_sources(self):
        result = compute_all_coverage_metrics([])
        assert result.observed_count == 0
        assert result.median_estimate == 0.0

    def test_no_overlap_no_pairwise(self):
        sr_a = SourceResult(
            source=TDSource.source_a,
            candidates=[SubdomainCandidate(name="A", source=TDSource.source_a)],
        )
        sr_b = SourceResult(
            source=TDSource.source_b,
            candidates=[SubdomainCandidate(name="B", source=TDSource.source_b)],
        )
        result = compute_all_coverage_metrics([sr_a, sr_b])
        assert result.observed_count == 2
        assert len(result.pairwise_estimates) == 0


# ── Helper Functions ─────────────────────────────────────────────────────


class TestStripCodeFences:
    def test_strips_json_fence(self):
        text = '```json\n{"key": "value"}\n```'
        assert _strip_code_fences(text) == '{"key": "value"}'

    def test_strips_plain_fence(self):
        text = '```\n{"key": "value"}\n```'
        assert _strip_code_fences(text) == '{"key": "value"}'

    def test_no_fence_passthrough(self):
        text = '{"key": "value"}'
        assert _strip_code_fences(text) == '{"key": "value"}'

    def test_strips_whitespace(self):
        text = '  ```json\n{"key": "value"}\n```  '
        assert _strip_code_fences(text) == '{"key": "value"}'


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 0.0, 1.0]
        assert math.isclose(_cosine_similarity(v, v), 1.0)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert math.isclose(_cosine_similarity(a, b), 0.0)

    def test_zero_vector(self):
        a = [0.0, 0.0]
        b = [1.0, 1.0]
        assert _cosine_similarity(a, b) == 0.0


class TestCountFrequencyClasses:
    def test_basic_counting(self):
        candidates = [
            SubdomainCandidate(name="A", source=TDSource.source_a),
            SubdomainCandidate(name="B", source=TDSource.source_a),
            SubdomainCandidate(name="A", source=TDSource.source_a),
            SubdomainCandidate(name="C", source=TDSource.source_a),
            SubdomainCandidate(name="C", source=TDSource.source_a),
            SubdomainCandidate(name="C", source=TDSource.source_a),
        ]
        singletons, doubletons = _count_frequency_classes(candidates)
        assert singletons == 1  # B appears once
        assert doubletons == 1  # A appears twice

    def test_empty_candidates(self):
        singletons, doubletons = _count_frequency_classes([])
        assert singletons == 0
        assert doubletons == 0


class TestParseHierarchyNodes:
    def test_basic_parsing(self):
        data = [
            {
                "name": "Parent",
                "description": "desc",
                "children": [
                    {"name": "Child", "description": "child desc"},
                ],
            },
        ]
        nodes = _parse_hierarchy_nodes(data)
        assert len(nodes) == 1
        assert nodes[0].name == "Parent"
        assert len(nodes[0].children) == 1
        assert nodes[0].children[0].name == "Child"

    def test_empty_input(self):
        assert _parse_hierarchy_nodes([]) == []

    def test_non_list_input(self):
        assert _parse_hierarchy_nodes("not a list") == []


class TestCountTreeStats:
    def test_basic_stats(self):
        from core.models.topic_discovery import SubdomainNode
        tree = [
            SubdomainNode(name="A", depth=0, children=[
                SubdomainNode(name="B", depth=1),
                SubdomainNode(name="C", depth=1, children=[
                    SubdomainNode(name="D", depth=2),
                ]),
            ]),
        ]
        total, max_depth = _count_tree_stats(tree)
        assert total == 4
        assert max_depth == 2

    def test_empty_tree(self):
        total, max_depth = _count_tree_stats([])
        assert total == 0
        assert max_depth == 0


# ── LLM Agent Functions (mocked) ────────────────────────────────────────

def _make_mock_response(content: str):
    """Create a mock LiteLLM response."""
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_choice.finish_reason = "stop"
    mock_response.choices = [mock_choice]
    return mock_response


@pytest.fixture
def mock_litellm():
    """Patch litellm.acompletion to return controlled responses."""
    with patch("core.topic_discovery.agents.litellm") as mock:
        yield mock


class TestSourceABrainstorm:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_litellm):
        response_json = json.dumps({
            "subdomains": [
                {"name": "expense management", "description": "desc", "confidence": 0.9},
                {"name": "corporate cards", "description": "desc", "confidence": 0.8},
            ]
        })
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_mock_response(response_json)
        )
        result = await run_source_a_company_brainstorm(
            "Test company context", max_rounds=1, timeout_s=10.0
        )
        assert result.source == TDSource.source_a
        assert len(result.candidates) == 2
        assert result.candidates[0].name == "expense management"
        assert result.error is None

    @pytest.mark.asyncio
    async def test_timeout_returns_error(self, mock_litellm):
        mock_litellm.acompletion = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )
        result = await run_source_a_company_brainstorm(
            "context", max_rounds=1, timeout_s=1.0
        )
        assert result.error is not None
        assert result.source == TDSource.source_a

    @pytest.mark.asyncio
    async def test_malformed_json_returns_error(self, mock_litellm):
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_mock_response("NOT JSON")
        )
        result = await run_source_a_company_brainstorm(
            "context", max_rounds=1, timeout_s=10.0
        )
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_empty_subdomains_stops_iteration(self, mock_litellm):
        response_json = json.dumps({"subdomains": []})
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_mock_response(response_json)
        )
        result = await run_source_a_company_brainstorm(
            "context", max_rounds=4, timeout_s=10.0
        )
        assert len(result.candidates) == 0
        # Should have called only once since first round returned empty
        assert mock_litellm.acompletion.call_count == 1


class TestSourceBBrainstorm:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_litellm):
        response_json = json.dumps({
            "subdomains": [
                {"name": "budgeting tools", "description": "desc", "confidence": 0.7},
            ]
        })
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_mock_response(response_json)
        )
        result = await run_source_b_persona_brainstorm(
            "Persona profiles", "Company context", max_rounds=1, timeout_s=10.0
        )
        assert result.source == TDSource.source_b
        assert len(result.candidates) == 1
        assert result.error is None


class TestSourceCSitemaps:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_litellm):
        response_json = json.dumps({
            "subdomains": [
                {"name": "integration guides", "description": "desc", "confidence": 0.6},
            ]
        })
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_mock_response(response_json)
        )
        result = await run_source_c_competitor_sitemaps(
            "sitemap data", "ramp.com", timeout_s=10.0
        )
        assert result.source == TDSource.source_c
        assert len(result.candidates) == 1
        assert result.total_rounds == 1


class TestSourceDAdversarial:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_litellm):
        response_json = json.dumps({
            "subdomains": [
                {"name": "SOC2 compliance", "description": "desc", "confidence": 0.6},
            ]
        })
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_mock_response(response_json)
        )
        result = await run_source_d_adversarial(
            "Company context",
            ["expense mgmt"],
            specialist_lenses=["regulatory expert"],
            max_rounds=1,
            timeout_s=10.0,
        )
        assert result.source == TDSource.source_d
        assert len(result.candidates) == 1
        assert result.candidates[0].specialist_lens == "regulatory expert"


class TestDeduplication:
    @pytest.mark.asyncio
    async def test_removes_duplicates(self):
        candidates = [
            SubdomainCandidate(name="expense management", source=TDSource.source_a),
            SubdomainCandidate(name="expense tracking", source=TDSource.source_b),
            SubdomainCandidate(name="corporate cards", source=TDSource.source_a),
        ]
        # Mock embed_texts to return deterministic vectors
        # expense management and expense tracking get similar vectors
        def mock_embed(texts):
            vectors = []
            for t in texts:
                if "expense" in t.lower():
                    vectors.append([0.9, 0.1, 0.0])
                else:
                    vectors.append([0.1, 0.9, 0.0])
            return vectors

        with patch("core.shared_tools.embedding_client.embed_texts", side_effect=mock_embed):
            result = await deduplicate_subdomains(candidates, threshold=0.5)
        # expense tracking should be removed (duplicate of expense management)
        assert len(result) == 2
        names = {c.name for c in result}
        assert "expense management" in names
        assert "corporate cards" in names

    @pytest.mark.asyncio
    async def test_empty_candidates(self):
        result = await deduplicate_subdomains([])
        assert result == []


class TestHierarchyConstruction:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_litellm):
        response_json = json.dumps({
            "taxonomy": [
                {
                    "name": "Finance",
                    "description": "Financial tools",
                    "children": [
                        {"name": "Expense Management", "description": "desc"},
                        {"name": "Budgeting", "description": "desc"},
                    ],
                },
            ]
        })
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_mock_response(response_json)
        )
        tree = await run_hierarchy_construction(
            ["Expense Management", "Budgeting"], "fintech", timeout_s=10.0
        )
        assert tree.domain_name == "fintech"
        assert tree.total_subdomains == 3
        assert tree.max_depth == 1
        assert len(tree.root_nodes) == 1
        assert len(tree.root_nodes[0].children) == 2


class TestRelevanceFiltering:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_litellm):
        response_json = json.dumps({
            "classifications": [
                {"buyer_stage": "tofu", "intent_type": "informational", "relevance": "relevant"},
                {"buyer_stage": "bofu", "intent_type": "transactional", "relevance": "irrelevant"},
            ]
        })
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_mock_response(response_json)
        )
        dims = [
            {"buyer_stage": "tofu", "intent_type": "informational", "audience_segment": "CFO"},
            {"buyer_stage": "bofu", "intent_type": "transactional", "audience_segment": "CFO"},
        ]
        result = await run_relevance_filtering(
            "expense mgmt", dims, "Ramp fintech", timeout_s=10.0
        )
        assert len(result) == 2
        assert result[0]["relevance"] == "relevant"


class TestTopicGeneration:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_litellm):
        response_json = json.dumps({
            "topics": [
                {"topic_text": "Best expense tools for startups", "priority_score": 0.9},
                {"topic_text": "How to automate expense reports", "priority_score": 0.7},
            ]
        })
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_mock_response(response_json)
        )
        result = await run_topic_generation(
            "expense management", "tofu", "informational", "CFO",
            "Ramp fintech company", timeout_s=10.0
        )
        assert len(result) == 2
        assert isinstance(result[0], TopicAssignment)
        assert result[0].topic_text == "Best expense tools for startups"
        assert result[0].priority_score == 0.9
