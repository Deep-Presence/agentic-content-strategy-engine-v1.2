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
    PerSourceCoverage,
    SourceResult,
    SubdomainCandidate,
    TDSource,
    TopicAssignment,
)
from core.topic_discovery.agents import (
    _cosine_similarity,
    _count_frequency_classes,
    _count_frequency_classes_by_round,
    _count_total_round_observations,
    _count_tree_stats,
    _parse_hierarchy_nodes,
    _parse_json_response,
    _safe_float,
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
        """Two sources with overlap → pairwise CR + per-source coverage."""
        sr_a = SourceResult(
            source=TDSource.source_a,
            candidates=[
                SubdomainCandidate(name="expense mgmt", source=TDSource.source_a, round_number=1),
                SubdomainCandidate(name="corporate cards", source=TDSource.source_a, round_number=1),
                SubdomainCandidate(name="compliance", source=TDSource.source_a, round_number=2),
            ],
            total_rounds=2,
            singletons=2,  # cards, compliance each in 1 round
            doubletons=0,
            chao1_estimate=5.0,
            source_sample_coverage=0.33,
        )
        sr_b = SourceResult(
            source=TDSource.source_b,
            candidates=[
                SubdomainCandidate(name="expense mgmt", source=TDSource.source_b, round_number=1),
                SubdomainCandidate(name="budgeting", source=TDSource.source_b, round_number=1),
            ],
            total_rounds=1,
            singletons=2,
            doubletons=0,
            chao1_estimate=3.0,
            source_sample_coverage=0.0,
        )
        result = compute_all_coverage_metrics([sr_a, sr_b])
        assert isinstance(result, CaptureRecaptureResult)
        assert result.observed_count == 4  # expense, cards, compliance, budgeting
        assert len(result.pairwise_estimates) >= 1
        # Per-source coverage populated
        assert "source_a" in result.per_source_coverage
        assert "source_b" in result.per_source_coverage
        assert result.per_source_coverage["source_a"].chao1_estimate == 5.0
        assert result.per_source_coverage["source_b"].source == TDSource.source_b
        # Aggregate = min of per-source coverages with coverage > 0
        # Source B has 0.0 coverage (single round, all singletons) → excluded
        assert result.aggregate_sample_coverage == 0.33
        # Backward-compat field mirrors aggregate
        assert result.sample_coverage == result.aggregate_sample_coverage

    def test_empty_sources(self):
        result = compute_all_coverage_metrics([])
        assert result.observed_count == 0
        assert result.median_estimate == 0.0
        assert result.per_source_coverage == {}
        assert result.aggregate_sample_coverage == 0.0

    def test_no_overlap_no_pairwise(self):
        sr_a = SourceResult(
            source=TDSource.source_a,
            candidates=[SubdomainCandidate(name="A", source=TDSource.source_a, round_number=1)],
            total_rounds=1,
            singletons=1,
            doubletons=0,
            chao1_estimate=1.0,
            source_sample_coverage=0.0,
        )
        sr_b = SourceResult(
            source=TDSource.source_b,
            candidates=[SubdomainCandidate(name="B", source=TDSource.source_b, round_number=1)],
            total_rounds=1,
            singletons=1,
            doubletons=0,
            chao1_estimate=1.0,
            source_sample_coverage=0.0,
        )
        result = compute_all_coverage_metrics([sr_a, sr_b])
        assert result.observed_count == 2
        assert len(result.pairwise_estimates) == 0

    def test_per_source_coverage_independent(self):
        """Cross-source overlap must NOT affect within-source metrics."""
        # Source A: "X" in rounds 1+2 (doubleton), "Y" in round 1 (singleton)
        sr_a = SourceResult(
            source=TDSource.source_a,
            candidates=[
                SubdomainCandidate(name="X", source=TDSource.source_a, round_number=1),
                SubdomainCandidate(name="X", source=TDSource.source_a, round_number=2),
                SubdomainCandidate(name="Y", source=TDSource.source_a, round_number=1),
            ],
            total_rounds=2,
            singletons=1,   # Y
            doubletons=1,    # X
            chao1_estimate=2.5,
            source_sample_coverage=0.67,
        )
        # Source B: "X" also in round 1 (same topic, different source)
        sr_b = SourceResult(
            source=TDSource.source_b,
            candidates=[
                SubdomainCandidate(name="X", source=TDSource.source_b, round_number=1),
            ],
            total_rounds=1,
            singletons=1,
            doubletons=0,
            chao1_estimate=1.0,
            source_sample_coverage=0.0,
        )
        result = compute_all_coverage_metrics([sr_a, sr_b])
        # Source A's per-source coverage should reflect what was passed in,
        # not be contaminated by Source B's "X"
        assert result.per_source_coverage["source_a"].singletons == 1
        assert result.per_source_coverage["source_a"].doubletons == 1
        assert result.per_source_coverage["source_a"].chao1_estimate == 2.5


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


class TestCountFrequencyClassesByRound:
    """Test round-level frequency counting (correct unit for Chao1 within a source)."""

    def test_single_round_all_singletons(self):
        """All names in 1 round → all singletons."""
        candidates = [
            SubdomainCandidate(name="A", round_number=1),
            SubdomainCandidate(name="B", round_number=1),
        ]
        s, d = _count_frequency_classes_by_round(candidates)
        assert s == 2
        assert d == 0

    def test_name_in_two_rounds_is_doubleton(self):
        """A name appearing in round 1 and round 2 → doubleton."""
        candidates = [
            SubdomainCandidate(name="A", round_number=1),
            SubdomainCandidate(name="A", round_number=2),
            SubdomainCandidate(name="B", round_number=1),
        ]
        s, d = _count_frequency_classes_by_round(candidates)
        assert s == 1  # B in 1 round
        assert d == 1  # A in 2 rounds

    def test_name_in_three_rounds_neither(self):
        """A name in 3+ rounds is neither singleton nor doubleton."""
        candidates = [
            SubdomainCandidate(name="A", round_number=1),
            SubdomainCandidate(name="A", round_number=2),
            SubdomainCandidate(name="A", round_number=3),
        ]
        s, d = _count_frequency_classes_by_round(candidates)
        assert s == 0
        assert d == 0

    def test_duplicate_in_same_round_counts_once(self):
        """LLM returns same name twice in one round → still 1 round presence."""
        candidates = [
            SubdomainCandidate(name="A", round_number=1),
            SubdomainCandidate(name="A", round_number=1),
            SubdomainCandidate(name="A", round_number=2),
        ]
        s, d = _count_frequency_classes_by_round(candidates)
        assert s == 0
        assert d == 1  # A in 2 distinct rounds

    def test_case_insensitive(self):
        candidates = [
            SubdomainCandidate(name="Expense Mgmt", round_number=1),
            SubdomainCandidate(name="expense mgmt", round_number=2),
        ]
        s, d = _count_frequency_classes_by_round(candidates)
        assert s == 0
        assert d == 1

    def test_empty(self):
        s, d = _count_frequency_classes_by_round([])
        assert s == 0
        assert d == 0


class TestCountTotalRoundObservations:
    """Test the denominator N for Good-Turing: total (name, round) incidences."""

    def test_basic(self):
        candidates = [
            SubdomainCandidate(name="A", round_number=1),
            SubdomainCandidate(name="A", round_number=2),
            SubdomainCandidate(name="B", round_number=1),
        ]
        # A in 2 rounds + B in 1 round = 3
        assert _count_total_round_observations(candidates) == 3

    def test_duplicate_same_round_counted_once(self):
        candidates = [
            SubdomainCandidate(name="A", round_number=1),
            SubdomainCandidate(name="A", round_number=1),  # same round
            SubdomainCandidate(name="A", round_number=2),
        ]
        # A in rounds {1, 2} = 2 observations
        assert _count_total_round_observations(candidates) == 2

    def test_empty(self):
        assert _count_total_round_observations([]) == 0


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
    async def test_malformed_json_graceful_recovery(self, mock_litellm):
        """M2: Malformed JSON is handled gracefully — no error, 0 candidates."""
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_mock_response("NOT JSON")
        )
        result = await run_source_a_company_brainstorm(
            "context", max_rounds=1, timeout_s=10.0
        )
        assert result.error is None
        assert len(result.candidates) == 0

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

    @pytest.mark.asyncio
    async def test_empty_sitemap_skips_llm_call(self, mock_litellm):
        """H5: Empty sitemap data should skip LLM call entirely."""
        mock_litellm.acompletion = AsyncMock()
        result = await run_source_c_competitor_sitemaps("", "ramp.com", timeout_s=10.0)
        assert result.source == TDSource.source_c
        assert len(result.candidates) == 0
        assert result.total_rounds == 0
        assert result.error is None
        mock_litellm.acompletion.assert_not_called()

    @pytest.mark.asyncio
    async def test_whitespace_sitemap_skips_llm_call(self, mock_litellm):
        """H5: Whitespace-only sitemap data should skip LLM call."""
        mock_litellm.acompletion = AsyncMock()
        result = await run_source_c_competitor_sitemaps("  \n  ", "ramp.com", timeout_s=10.0)
        assert result.source == TDSource.source_c
        assert len(result.candidates) == 0
        assert result.total_rounds == 0
        mock_litellm.acompletion.assert_not_called()


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


# ── H4: revision_note threading tests ─────────────────────────────────


class TestPromptBuilderRevisionNote:
    """H4: Verify prompt builders accept and render revision_note."""

    def test_source_a_revision_note(self):
        from core.topic_discovery.prompts.source_a_company import build_source_a_user_prompt
        prompt = build_source_a_user_prompt("company ctx", revision_note="add compliance topics")
        assert "## Reviewer Feedback" in prompt
        assert "add compliance topics" in prompt

    def test_source_b_revision_note(self):
        from core.topic_discovery.prompts.source_b_persona import build_source_b_user_prompt
        prompt = build_source_b_user_prompt("personas", "company ctx", revision_note="more fintech")
        assert "## Reviewer Feedback" in prompt
        assert "more fintech" in prompt

    def test_source_c_revision_note(self):
        from core.topic_discovery.prompts.source_c_sitemap import build_source_c_user_prompt
        prompt = build_source_c_user_prompt("sitemap data", "ramp.com", revision_note="missing security")
        assert "## Reviewer Feedback" in prompt
        assert "missing security" in prompt

    def test_source_d_revision_note(self):
        from core.topic_discovery.prompts.source_d_adversarial import build_source_d_user_prompt
        prompt = build_source_d_user_prompt("company ctx", "regulatory expert", revision_note="add GDPR")
        assert "## Reviewer Feedback" in prompt
        assert "add GDPR" in prompt

    def test_no_revision_note_omits_section(self):
        from core.topic_discovery.prompts.source_a_company import build_source_a_user_prompt
        prompt = build_source_a_user_prompt("company ctx")
        assert "## Reviewer Feedback" not in prompt

    def test_none_revision_note_omits_section(self):
        from core.topic_discovery.prompts.source_a_company import build_source_a_user_prompt
        prompt = build_source_a_user_prompt("company ctx", revision_note=None)
        assert "## Reviewer Feedback" not in prompt


class TestRevisionNoteInAgents:
    """H4: Verify agent functions thread revision_note to LLM messages."""

    @pytest.mark.asyncio
    async def test_source_a_revision_note_in_llm_messages(self, mock_litellm):
        response_json = json.dumps({"subdomains": []})
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_mock_response(response_json)
        )
        await run_source_a_company_brainstorm(
            "context", max_rounds=1, timeout_s=10.0,
            revision_note="add compliance topics",
        )
        call_args = mock_litellm.acompletion.call_args
        user_msg = call_args.kwargs["messages"][1]["content"]
        assert "## Reviewer Feedback" in user_msg
        assert "add compliance topics" in user_msg

    @pytest.mark.asyncio
    async def test_source_b_revision_note_in_llm_messages(self, mock_litellm):
        response_json = json.dumps({"subdomains": []})
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_mock_response(response_json)
        )
        await run_source_b_persona_brainstorm(
            "personas", "company ctx", max_rounds=1, timeout_s=10.0,
            revision_note="focus on procurement",
        )
        call_args = mock_litellm.acompletion.call_args
        user_msg = call_args.kwargs["messages"][1]["content"]
        assert "## Reviewer Feedback" in user_msg
        assert "focus on procurement" in user_msg

    @pytest.mark.asyncio
    async def test_source_d_revision_note_in_llm_messages(self, mock_litellm):
        response_json = json.dumps({"subdomains": []})
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_mock_response(response_json)
        )
        await run_source_d_adversarial(
            "context", ["existing"],
            specialist_lenses=["regulatory expert"],
            max_rounds=1, timeout_s=10.0,
            revision_note="explore tax implications",
        )
        call_args = mock_litellm.acompletion.call_args
        user_msg = call_args.kwargs["messages"][1]["content"]
        assert "## Reviewer Feedback" in user_msg
        assert "explore tax implications" in user_msg


# ── M1: Round accounting tests ─────────────────────────────────────────


class TestM1RoundAccounting:
    """M1: Source agents must report actual rounds executed, not max_rounds."""

    @pytest.mark.asyncio
    async def test_source_a_early_break_reports_actual_rounds(self, mock_litellm):
        """Round 1 returns candidates, round 2 returns empty → breaks.
        total_rounds should be 2 (both rounds executed), not max_rounds=4."""
        r1 = json.dumps({"subdomains": [
            {"name": "expense mgmt", "description": "d", "confidence": 0.9},
        ]})
        r2 = json.dumps({"subdomains": []})
        mock_litellm.acompletion = AsyncMock(
            side_effect=[_make_mock_response(r1), _make_mock_response(r2)]
        )
        result = await run_source_a_company_brainstorm(
            "context", max_rounds=4, timeout_s=10.0
        )
        assert result.total_rounds == 2
        assert len(result.candidates) == 1
        assert result.error is None

    @pytest.mark.asyncio
    async def test_source_a_full_rounds_reports_max(self, mock_litellm):
        """All 3 rounds produce candidates → total_rounds == 3."""
        resp = json.dumps({"subdomains": [
            {"name": "topic", "description": "d", "confidence": 0.8},
        ]})
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_mock_response(resp)
        )
        result = await run_source_a_company_brainstorm(
            "context", max_rounds=3, timeout_s=10.0
        )
        assert result.total_rounds == 3
        assert mock_litellm.acompletion.call_count == 3

    @pytest.mark.asyncio
    async def test_source_a_exception_mid_round_reports_actual(self, mock_litellm):
        """Round 1 succeeds, round 2 throws → total_rounds == 2
        (round 2 was attempted even though it failed)."""
        r1 = json.dumps({"subdomains": [
            {"name": "expense mgmt", "description": "d", "confidence": 0.9},
        ]})
        mock_litellm.acompletion = AsyncMock(
            side_effect=[_make_mock_response(r1), asyncio.TimeoutError()]
        )
        result = await run_source_a_company_brainstorm(
            "context", max_rounds=4, timeout_s=10.0
        )
        assert result.total_rounds == 2  # round 2 attempted (counter incremented)
        assert result.error is not None
        assert len(result.candidates) == 1

    @pytest.mark.asyncio
    async def test_source_b_early_break_reports_actual_rounds(self, mock_litellm):
        """Source B: early break → total_rounds reflects actual execution."""
        r1 = json.dumps({"subdomains": [
            {"name": "budgeting", "description": "d", "confidence": 0.7},
        ]})
        r2 = json.dumps({"subdomains": []})
        mock_litellm.acompletion = AsyncMock(
            side_effect=[_make_mock_response(r1), _make_mock_response(r2)]
        )
        result = await run_source_b_persona_brainstorm(
            "personas", "company", max_rounds=4, timeout_s=10.0
        )
        assert result.total_rounds == 2
        assert len(result.candidates) == 1

    @pytest.mark.asyncio
    async def test_source_d_rounds_capped_by_max_rounds(self, mock_litellm):
        """5 specialist lenses but max_rounds=2 → total_rounds == 2 (not 5)."""
        resp = json.dumps({"subdomains": [
            {"name": "compliance", "description": "d", "confidence": 0.6},
        ]})
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_mock_response(resp)
        )
        result = await run_source_d_adversarial(
            "context", ["existing"],
            specialist_lenses=["a", "b", "c", "d", "e"],
            max_rounds=2, timeout_s=10.0,
        )
        assert result.total_rounds == 2
        assert mock_litellm.acompletion.call_count == 2


# ── M2: Safe JSON parsing tests ────────────────────────────────────────


class TestParseJsonResponse:
    """M2: _parse_json_response must return None on malformed JSON, not raise."""

    def test_valid_json(self):
        result = _parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_malformed_json_returns_none(self):
        result = _parse_json_response("NOT JSON AT ALL")
        assert result is None

    def test_empty_string_returns_none(self):
        result = _parse_json_response("")
        assert result is None

    def test_code_fences_stripped(self):
        result = _parse_json_response('```json\n{"ok": true}\n```')
        assert result == {"ok": True}


class TestSafeFloat:
    """M2: _safe_float coerces values safely with a fallback default."""

    def test_valid_float(self):
        assert _safe_float(0.9, 0.5) == 0.9

    def test_valid_int(self):
        assert _safe_float(1, 0.5) == 1.0

    def test_valid_string_number(self):
        assert _safe_float("0.75", 0.5) == 0.75

    def test_invalid_string_returns_default(self):
        assert _safe_float("not a number", 0.5) == 0.5

    def test_none_returns_default(self):
        assert _safe_float(None, 0.5) == 0.5

    def test_empty_string_returns_default(self):
        assert _safe_float("", 0.5) == 0.5


class TestM2MalformedJsonRecovery:
    """M2: Malformed JSON mid-round should not lose prior candidates."""

    @pytest.mark.asyncio
    async def test_source_a_malformed_json_mid_round_keeps_prior(self, mock_litellm):
        """R1 returns valid JSON with 2 candidates, R2 returns garbage.
        Should keep R1 candidates and not error."""
        r1 = json.dumps({"subdomains": [
            {"name": "expense mgmt", "description": "d", "confidence": 0.9},
            {"name": "cards", "description": "d", "confidence": 0.8},
        ]})
        r2_bad = "NOT VALID JSON {{{}"
        mock_litellm.acompletion = AsyncMock(
            side_effect=[_make_mock_response(r1), _make_mock_response(r2_bad)]
        )
        result = await run_source_a_company_brainstorm(
            "context", max_rounds=4, timeout_s=10.0
        )
        assert result.error is None
        assert len(result.candidates) == 2
        assert result.candidates[0].name == "expense mgmt"

    @pytest.mark.asyncio
    async def test_source_d_malformed_json_one_lens_continues(self, mock_litellm):
        """Lens 1 returns valid, lens 2 returns garbage → keeps lens 1 candidates."""
        r1 = json.dumps({"subdomains": [
            {"name": "SOC2", "description": "d", "confidence": 0.6},
        ]})
        r2_bad = "<<<GARBAGE>>>"
        mock_litellm.acompletion = AsyncMock(
            side_effect=[_make_mock_response(r1), _make_mock_response(r2_bad)]
        )
        result = await run_source_d_adversarial(
            "context", ["existing"],
            specialist_lenses=["regulatory", "accessibility"],
            max_rounds=2, timeout_s=10.0,
        )
        assert result.error is None
        assert len(result.candidates) == 1
        assert result.candidates[0].name == "SOC2"

    @pytest.mark.asyncio
    async def test_hierarchy_malformed_json_returns_empty_tree(self, mock_litellm):
        """Hierarchy construction with garbage JSON → empty tree."""
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_mock_response("NOT JSON")
        )
        tree = await run_hierarchy_construction(
            ["sub1", "sub2"], "fintech", timeout_s=10.0
        )
        assert tree.domain_name == "fintech"
        assert tree.total_subdomains == 0
        assert len(tree.root_nodes) == 0

    @pytest.mark.asyncio
    async def test_relevance_malformed_json_returns_empty(self, mock_litellm):
        """Relevance filtering with garbage JSON → empty list."""
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_mock_response("BAD JSON")
        )
        result = await run_relevance_filtering(
            "sub1", [{"buyer_stage": "tofu"}], "context", timeout_s=10.0
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_topic_gen_malformed_json_returns_empty(self, mock_litellm):
        """Topic generation with garbage JSON → empty list."""
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_mock_response("BAD JSON")
        )
        result = await run_topic_generation(
            "sub1", "tofu", "informational", "CFO", "context", timeout_s=10.0
        )
        assert result == []
