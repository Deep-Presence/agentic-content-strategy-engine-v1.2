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
from core.model_config.schemas import ResolvedModelConfig
from core.topic_discovery.agents import (
    DeduplicationResult,
    _build_taxonomy_tree,
    _cosine_similarity,
    _count_frequency_classes,
    _count_frequency_classes_by_round,
    _count_total_round_observations,
    _count_tree_stats,
    _extract_taxonomy_nodes,
    _parse_hierarchy_nodes,
    _parse_json_response,
    _safe_float,
    _strip_code_fences,
    compute_all_coverage_metrics,
    compute_capture_recapture,
    compute_chao1_lower_bound,
    compute_cluster_based_overlap,
    compute_sample_coverage,
    compute_semantic_frequency_classes,
    deduplicate_subdomains,
    deduplicate_subdomains_with_clusters,
    run_hierarchy_construction,
    run_relevance_filtering,
    run_source_a_company_brainstorm,
    run_source_b_persona_brainstorm,
    run_source_c_deep_research,
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

    def test_preamble_before_fence(self):
        """Preamble text before code fence should still extract JSON."""
        text = 'Here is the JSON:\n```json\n{"key": "value"}\n```'
        assert _strip_code_fences(text) == '{"key": "value"}'

    def test_bare_json_with_preamble(self):
        """If no code fences, extract JSON between first { and last }."""
        text = 'Some preamble\n{"key": "value"}\nmore text'
        result = _strip_code_fences(text)
        assert '{"key": "value"}' in result
        assert "preamble" not in result

    def test_bare_json_array_with_preamble(self):
        """Extract JSON array between first [ and last ]."""
        text = 'text [1, 2, 3] more text'
        result = _strip_code_fences(text)
        assert "[1, 2, 3]" in result
        assert "text" not in result.replace("[1, 2, 3]", "").strip()

    def test_no_json_at_all_passthrough(self):
        """Plain text with no JSON structure passes through unchanged."""
        text = "just plain text"
        assert _strip_code_fences(text) == "just plain text"


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

    def test_prompt_schema_pillar_keys(self):
        """Parser should accept the prompt's pillar_name/subdomains/sub_subdomains keys."""
        data = [
            {
                "pillar_name": "Financial Operations",
                "pillar_description": "Everything finance",
                "subdomains": [
                    {
                        "name": "Expense Management",
                        "description": "expense desc",
                        "sources": ["source_a", "source_b"],
                        "sub_subdomains": [
                            {"name": "Invoice Processing", "description": "invoice desc"},
                        ],
                    },
                ],
            },
        ]
        nodes = _parse_hierarchy_nodes(data)
        assert len(nodes) == 1
        assert nodes[0].name == "Financial Operations"
        assert nodes[0].description == "Everything finance"
        # Level 2 children from "subdomains" key
        assert len(nodes[0].children) == 1
        assert nodes[0].children[0].name == "Expense Management"
        # Level 3 children from "sub_subdomains" key
        assert len(nodes[0].children[0].children) == 1
        assert nodes[0].children[0].children[0].name == "Invoice Processing"

    def test_legacy_schema_still_works(self):
        """Backward-compat: name/description/children keys must still parse."""
        data = [
            {
                "name": "Finance",
                "description": "Financial tools",
                "children": [
                    {"name": "Budgeting", "description": "desc"},
                ],
            },
        ]
        nodes = _parse_hierarchy_nodes(data)
        assert len(nodes) == 1
        assert nodes[0].name == "Finance"
        assert len(nodes[0].children) == 1
        assert nodes[0].children[0].name == "Budgeting"

    def test_source_provenance_from_sources_list(self):
        """'sources' list from prompt schema should convert to dict for source_provenance."""
        data = [{"name": "Topic", "sources": ["source_a", "source_b"]}]
        nodes = _parse_hierarchy_nodes(data)
        assert nodes[0].source_provenance == {"source_a": True, "source_b": True}


class TestExtractTaxonomyNodes:
    """Tests for _extract_taxonomy_nodes — top-level key tolerance."""

    def test_hierarchy_key(self):
        parsed = {"hierarchy": [{"name": "A"}]}
        result = _extract_taxonomy_nodes(parsed)
        assert result == [{"name": "A"}]

    def test_taxonomy_key(self):
        parsed = {"taxonomy": [{"name": "A"}]}
        result = _extract_taxonomy_nodes(parsed)
        assert result == [{"name": "A"}]

    def test_hierarchy_preferred_over_taxonomy(self):
        parsed = {"hierarchy": [{"name": "H"}], "taxonomy": [{"name": "T"}]}
        result = _extract_taxonomy_nodes(parsed)
        assert result == [{"name": "H"}]

    def test_none_input(self):
        assert _extract_taxonomy_nodes(None) is None

    def test_empty_hierarchy(self):
        assert _extract_taxonomy_nodes({"hierarchy": []}) is None

    def test_no_known_key(self):
        assert _extract_taxonomy_nodes({"other": [1, 2]}) is None

    def test_bare_list_fallback(self):
        """If parsed is itself a list, treat it as nodes."""
        result = _extract_taxonomy_nodes([{"name": "A"}])
        assert result == [{"name": "A"}]

    def test_empty_list_fallback(self):
        assert _extract_taxonomy_nodes([]) is None


class TestBuildTaxonomyTree:
    """Tests for _build_taxonomy_tree helper."""

    def test_basic(self):
        nodes_data = [
            {"name": "Parent", "description": "p", "children": [
                {"name": "Child", "description": "c"},
            ]},
        ]
        tree = _build_taxonomy_tree(nodes_data, "test.com")
        assert tree.domain_name == "test.com"
        assert tree.total_subdomains == 2
        assert tree.max_depth == 1
        assert len(tree.root_nodes) == 1

    def test_empty_nodes(self):
        tree = _build_taxonomy_tree([], "test.com")
        assert tree.total_subdomains == 0
        assert tree.max_depth == 0


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
    """Create a mock OpenAI chat completion response."""
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_choice.finish_reason = "stop"
    mock_response.choices = [mock_choice]
    return mock_response


class _LiteLLMCompat:
    """Shim so existing tests can keep using ``mock_litellm.acompletion = AsyncMock(...)``."""

    def __init__(self, mock_client: MagicMock):
        self._client = mock_client

    @property
    def acompletion(self):
        return self._client.chat.completions.create

    @acompletion.setter
    def acompletion(self, value):
        self._client.chat.completions.create = value


@pytest.fixture
def mock_litellm():
    """Patch OpenRouter async client so tests control LLM responses.

    Yields a shim with ``.acompletion`` property that maps to
    ``client.chat.completions.create`` — backward-compatible with all
    existing test code that does ``mock_litellm.acompletion = AsyncMock(...)``.
    """
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock()
    with patch("core.shared_tools.openrouter_client.get_async_client", return_value=mock_client):
        yield _LiteLLMCompat(mock_client)


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


class TestSourceCDeepResearch:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        response_json = json.dumps({
            "subdomains": [
                {
                    "name": "Expense Management",
                    "description": "Corporate expense tracking and policy enforcement",
                    "competitive_density": "high",
                    "source_type": "established",
                    "confidence": 0.85,
                },
            ],
            "metadata": {
                "publishers_identified": ["Ramp Blog"],
                "top_gaps": ["AI expense categorization"],
                "emerging_trends": ["Real-time spend controls"],
            },
        })
        with patch(
            "core.research.tools.perplexity_client"
        ) as mock_pplx:
            mock_pplx.research = MagicMock(return_value=(response_json, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}))
            result = await run_source_c_deep_research(
                "Ramp is a fintech company", "Competitor data", "fintech",
                timeout_s=10.0,
            )
        assert result.source == TDSource.source_c
        assert len(result.candidates) == 1
        assert result.candidates[0].name == "Expense Management"
        assert result.candidates[0].confidence == 0.85
        assert result.total_rounds == 1
        assert result.error is None

    @pytest.mark.asyncio
    async def test_byok_resolves_model_config_for_source_c(self):
        response_json = json.dumps({
            "subdomains": [
                {"name": "API Security", "description": "desc", "confidence": 0.7},
            ],
        })
        resolved = ResolvedModelConfig(
            workspace_id="ws-123",
            workspace_slug="acme",
            agent_key="topic_discovery.source_c_deep_research",
            model="perplexity/sonar-deep-research",
            base_url="https://openrouter.workspace/api/v1",
            api_key="sk-workspace",
            credential_id="cred-123",
            model_config_id="cfg-123",
            timeout_s=77.0,
        )
        with (
            patch("core.research.tools.perplexity_client") as mock_pplx,
            patch(
                "core.topic_discovery.agents._resolve_model_config_for_agent",
                new_callable=AsyncMock,
                return_value=resolved,
            ) as mock_resolve,
        ):
            mock_pplx.research = MagicMock(
                return_value=(response_json, {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3})
            )
            result = await run_source_c_deep_research(
                "Company context",
                "Competitor data",
                "cybersecurity",
                timeout_s=10.0,
                company_slug="acme",
                workspace_id="ws-123",
                workspace_slug="acme",
            )

        assert len(result.candidates) == 1
        mock_resolve.assert_awaited_once_with(
            workspace_id="ws-123",
            workspace_slug="acme",
            agent_key="topic_discovery.source_c_deep_research",
        )
        call_kwargs = mock_pplx.research.call_args.kwargs
        assert call_kwargs["model"] == "perplexity/sonar-deep-research"
        assert call_kwargs["timeout_s"] == 77.0
        assert call_kwargs["api_key"] == "sk-workspace"
        assert call_kwargs["base_url"] == "https://openrouter.workspace/api/v1"
        assert call_kwargs["workspace_id"] == "ws-123"
        assert call_kwargs["agent_key"] == "topic_discovery.source_c_deep_research"
        assert call_kwargs["credential_id"] == "cred-123"
        assert call_kwargs["model_config_id"] == "cfg-123"
        assert call_kwargs["workspace_billed"] is True

    @pytest.mark.asyncio
    async def test_empty_context_skips_api_call(self):
        """Skip API call when both company_context and competitor_landscape are empty."""
        with patch(
            "core.research.tools.perplexity_client"
        ) as mock_pplx:
            mock_pplx.research = MagicMock()
            result = await run_source_c_deep_research(
                "", "", "fintech", timeout_s=10.0,
            )
        assert result.source == TDSource.source_c
        assert len(result.candidates) == 0
        assert result.total_rounds == 0
        assert result.error is None
        mock_pplx.research.assert_not_called()

    @pytest.mark.asyncio
    async def test_whitespace_context_skips_api_call(self):
        """Whitespace-only context should skip API call."""
        with patch(
            "core.research.tools.perplexity_client"
        ) as mock_pplx:
            mock_pplx.research = MagicMock()
            result = await run_source_c_deep_research(
                "  \n  ", "  ", "fintech", timeout_s=10.0,
            )
        assert result.source == TDSource.source_c
        assert len(result.candidates) == 0
        assert result.total_rounds == 0
        mock_pplx.research.assert_not_called()

    @pytest.mark.asyncio
    async def test_citations_stripped_before_json_parse(self):
        """Perplexity citations section should be stripped before JSON parsing."""
        response_json = json.dumps({
            "subdomains": [
                {"name": "API Security", "description": "desc", "confidence": 0.7},
            ],
        })
        raw_with_citations = (
            response_json + "\n\nSources:\n[1] https://example.com\n[2] https://other.com"
        )
        with patch(
            "core.research.tools.perplexity_client"
        ) as mock_pplx:
            mock_pplx.research = MagicMock(return_value=(raw_with_citations, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}))
            result = await run_source_c_deep_research(
                "Company context", "", "cybersecurity", timeout_s=10.0,
            )
        assert len(result.candidates) == 1
        assert result.candidates[0].name == "API Security"

    @pytest.mark.asyncio
    async def test_timeout_returns_error(self):
        """Timeout should be handled gracefully."""
        with patch(
            "core.research.tools.perplexity_client"
        ) as mock_pplx:
            mock_pplx.research = MagicMock(
                side_effect=asyncio.TimeoutError()
            )
            result = await run_source_c_deep_research(
                "Company context", "", "fintech", timeout_s=0.001,
            )
        assert result.source == TDSource.source_c
        assert result.error is not None
        assert len(result.candidates) == 0


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


class TestRunCompletionResponseFormat:
    """Verify _run_completion passes response_format to litellm."""

    @pytest.mark.asyncio
    async def test_response_format_passed_through(self, mock_litellm):
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_mock_response('{"ok": true}')
        )
        from core.topic_discovery.agents import _run_completion
        await _run_completion(
            model="test-model",
            messages=[{"role": "user", "content": "hi"}],
            response_format={"type": "json_object"},
            timeout_s=10.0,
        )
        call_kwargs = mock_litellm.acompletion.call_args.kwargs
        assert call_kwargs.get("response_format") == {"type": "json_object"}

    @pytest.mark.asyncio
    async def test_response_format_omitted_when_none(self, mock_litellm):
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_mock_response('{"ok": true}')
        )
        from core.topic_discovery.agents import _run_completion
        await _run_completion(
            model="test-model",
            messages=[{"role": "user", "content": "hi"}],
            timeout_s=10.0,
        )
        call_kwargs = mock_litellm.acompletion.call_args.kwargs
        assert "response_format" not in call_kwargs


class TestHierarchyConstruction:
    @pytest.mark.asyncio
    async def test_happy_path_legacy_keys(self, mock_litellm):
        """Legacy 'taxonomy'/'name'/'children' keys still produce a valid tree."""
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

    @pytest.mark.asyncio
    async def test_happy_path_prompt_schema(self, mock_litellm):
        """Prompt's 'hierarchy'/'pillar_name'/'subdomains' keys produce a valid tree."""
        response_json = json.dumps({
            "hierarchy": [
                {
                    "pillar_name": "Finance",
                    "pillar_description": "Financial tools",
                    "subdomains": [
                        {"name": "Expense Management", "description": "desc"},
                        {"name": "Budgeting", "description": "desc"},
                    ],
                },
            ],
            "merge_log": [],
            "orphans": [],
            "metadata": {},
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
        assert tree.root_nodes[0].name == "Finance"
        assert len(tree.root_nodes[0].children) == 2

    @pytest.mark.asyncio
    async def test_uses_response_format_json_object(self, mock_litellm):
        """Hierarchy construction should request json_object mode."""
        response_json = json.dumps({"hierarchy": [{"pillar_name": "A", "pillar_description": "d"}]})
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_mock_response(response_json)
        )
        await run_hierarchy_construction(["A"], "test.com", timeout_s=10.0)
        first_call_kwargs = mock_litellm.acompletion.call_args_list[0].kwargs
        rf = first_call_kwargs.get("response_format")
        assert rf is not None
        assert rf["type"] == "json_object"

    @pytest.mark.asyncio
    async def test_retry_on_first_failure(self, mock_litellm):
        """First attempt fails parsing → retry with repair prompt → succeeds."""
        good_json = json.dumps({"hierarchy": [{"pillar_name": "A", "pillar_description": "d"}]})
        mock_litellm.acompletion = AsyncMock(side_effect=[
            _make_mock_response("NOT JSON"),       # first attempt fails
            _make_mock_response(good_json),         # retry succeeds
        ])
        tree = await run_hierarchy_construction(["A"], "test.com", timeout_s=10.0)
        assert tree.total_subdomains == 1
        assert mock_litellm.acompletion.call_count == 2
        # Retry should include the failed response as assistant message
        retry_messages = mock_litellm.acompletion.call_args_list[1].kwargs["messages"]
        assert any("NOT JSON" in str(m.get("content", "")) for m in retry_messages)

    @pytest.mark.asyncio
    async def test_both_attempts_fail_raises_runtime_error(self, mock_litellm):
        """Both attempts return garbage → RuntimeError raised."""
        mock_litellm.acompletion = AsyncMock(side_effect=[
            _make_mock_response("GARBAGE 1"),
            _make_mock_response("GARBAGE 2"),
        ])
        with pytest.raises(RuntimeError, match="Hierarchy construction failed"):
            await run_hierarchy_construction(["A"], "test.com", timeout_s=10.0)

    @pytest.mark.asyncio
    async def test_first_attempt_succeeds_no_retry(self, mock_litellm):
        """Valid JSON on first attempt → no retry, single LLM call."""
        response_json = json.dumps({"hierarchy": [{"pillar_name": "A", "pillar_description": "d"}]})
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_mock_response(response_json)
        )
        tree = await run_hierarchy_construction(["A"], "test.com", timeout_s=10.0)
        assert tree.total_subdomains == 1
        assert mock_litellm.acompletion.call_count == 1


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
        from core.topic_discovery.prompts.source_c_deep_research import build_source_c_user_prompt
        prompt = build_source_c_user_prompt("company ctx", "competitors", "fintech", revision_note="missing security")
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
    async def test_hierarchy_malformed_json_raises_after_retry(self, mock_litellm):
        """Hierarchy construction with garbage JSON on both attempts → RuntimeError."""
        mock_litellm.acompletion = AsyncMock(side_effect=[
            _make_mock_response("NOT JSON"),  # first attempt
            _make_mock_response("STILL NOT JSON"),  # retry
        ])
        with pytest.raises(RuntimeError, match="Hierarchy construction failed"):
            await run_hierarchy_construction(
                ["sub1", "sub2"], "fintech", timeout_s=10.0
            )

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


# ── Part B: Semantic Coverage Statistics ──────────────────────────────


def _embed_vec(value: float) -> List[float]:
    """Create a simple 3-dim embedding vector for testing."""
    return [value, 1.0 - value, 0.5]


class TestSemanticFrequencyClasses:
    """Tests for compute_semantic_frequency_classes — embedding-based round overlap."""

    def test_identical_embeddings_different_rounds_are_doubletons(self):
        """Two candidates with identical embeddings in rounds 1 and 2 → doubleton."""
        candidates = [
            SubdomainCandidate(name="A", source=TDSource.source_a, round_number=1),
            SubdomainCandidate(name="B", source=TDSource.source_a, round_number=2),
        ]
        # Identical embeddings → cosine sim = 1.0
        embeddings = [[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
        s, d = compute_semantic_frequency_classes(candidates, embeddings, similarity_threshold=0.70)
        assert s == 0
        assert d == 1

    def test_similar_embeddings_above_threshold_are_doubletons(self):
        """Two candidates with cosine sim > threshold in different rounds → doubleton."""
        candidates = [
            SubdomainCandidate(name="Expense Management", source=TDSource.source_a, round_number=1),
            SubdomainCandidate(name="Expense Tracking", source=TDSource.source_a, round_number=2),
        ]
        # Cosine sim of [0.9, 0.1, 0.0] and [0.85, 0.15, 0.0] ≈ 0.9997 > 0.70
        embeddings = [[0.9, 0.1, 0.0], [0.85, 0.15, 0.0]]
        s, d = compute_semantic_frequency_classes(candidates, embeddings, similarity_threshold=0.70)
        assert s == 0
        assert d == 1

    def test_dissimilar_embeddings_are_singletons(self):
        """Two candidates with low cosine sim in different rounds → singletons."""
        candidates = [
            SubdomainCandidate(name="A", source=TDSource.source_a, round_number=1),
            SubdomainCandidate(name="B", source=TDSource.source_a, round_number=2),
        ]
        # Orthogonal → cosine sim = 0.0
        embeddings = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        s, d = compute_semantic_frequency_classes(candidates, embeddings, similarity_threshold=0.70)
        assert s == 2
        assert d == 0

    def test_three_rounds_same_concept(self):
        """Same concept in 3 rounds → neither singleton nor doubleton (appears in 3 rounds)."""
        candidates = [
            SubdomainCandidate(name="A", source=TDSource.source_a, round_number=1),
            SubdomainCandidate(name="B", source=TDSource.source_a, round_number=2),
            SubdomainCandidate(name="C", source=TDSource.source_a, round_number=3),
        ]
        # All identical embeddings
        embeddings = [[1.0, 0.0, 0.0]] * 3
        s, d = compute_semantic_frequency_classes(candidates, embeddings, similarity_threshold=0.70)
        assert s == 0
        assert d == 0  # in 3 rounds, not a doubleton

    def test_single_round_all_singletons(self):
        """All candidates in round 1 only → all singletons."""
        candidates = [
            SubdomainCandidate(name="A", source=TDSource.source_a, round_number=1),
            SubdomainCandidate(name="B", source=TDSource.source_a, round_number=1),
        ]
        embeddings = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        s, d = compute_semantic_frequency_classes(candidates, embeddings, similarity_threshold=0.70)
        assert s == 2
        assert d == 0

    def test_same_round_similar_not_counted(self):
        """Similar candidates in the SAME round don't create a doubleton."""
        candidates = [
            SubdomainCandidate(name="A", source=TDSource.source_a, round_number=1),
            SubdomainCandidate(name="B", source=TDSource.source_a, round_number=1),
        ]
        # Identical embeddings but same round
        embeddings = [[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
        s, d = compute_semantic_frequency_classes(candidates, embeddings, similarity_threshold=0.70)
        # Same round: merged into one component spanning 1 round → singleton
        assert d == 0

    def test_empty_candidates(self):
        s, d = compute_semantic_frequency_classes([], [], similarity_threshold=0.70)
        assert s == 0
        assert d == 0

    def test_threshold_sensitivity(self):
        """Same data, different thresholds → different results."""
        candidates = [
            SubdomainCandidate(name="A", source=TDSource.source_a, round_number=1),
            SubdomainCandidate(name="B", source=TDSource.source_a, round_number=2),
        ]
        # Cosine sim ≈ 0.75
        embeddings = [[0.9, 0.4, 0.0], [0.6, 0.8, 0.0]]
        from core.topic_discovery.agents import _cosine_similarity
        sim = _cosine_similarity(embeddings[0], embeddings[1])
        # With threshold below sim → doubleton
        s1, d1 = compute_semantic_frequency_classes(candidates, embeddings, similarity_threshold=sim - 0.05)
        assert d1 == 1
        # With threshold above sim → singletons
        s2, d2 = compute_semantic_frequency_classes(candidates, embeddings, similarity_threshold=sim + 0.05)
        assert d2 == 0
        assert s2 == 2


class TestClusterBasedOverlap:
    """Tests for compute_cluster_based_overlap — between-source overlap from dedup clusters."""

    def test_two_sources_one_shared_cluster(self):
        """Cluster contains candidates from source_a and source_b → 1 overlap."""
        clusters = [[0, 1], [2]]  # cluster 0 has indices 0+1, cluster 1 has index 2
        source_of = [TDSource.source_a, TDSource.source_b, TDSource.source_a]
        result = compute_cluster_based_overlap(clusters, source_of)
        assert result["source_a_source_b"] == 1

    def test_no_shared_clusters(self):
        """Each cluster has candidates from only one source → empty overlap."""
        clusters = [[0], [1]]
        source_of = [TDSource.source_a, TDSource.source_b]
        result = compute_cluster_based_overlap(clusters, source_of)
        assert len(result) == 0

    def test_three_sources_multiple_overlaps(self):
        """Clusters spanning 3 sources → all 3 pairs have counts."""
        # Cluster 0: source_a + source_b, Cluster 1: source_b + source_d
        clusters = [[0, 1], [2, 3]]
        source_of = [TDSource.source_a, TDSource.source_b, TDSource.source_b, TDSource.source_d]
        result = compute_cluster_based_overlap(clusters, source_of)
        assert result.get("source_a_source_b", 0) == 1
        assert result.get("source_b_source_d", 0) == 1
        assert result.get("source_a_source_d", 0) == 0  # no shared cluster

    def test_multiple_clusters_same_pair(self):
        """3 clusters each containing source_a + source_b → overlap = 3."""
        clusters = [[0, 1], [2, 3], [4, 5]]
        source_of = [
            TDSource.source_a, TDSource.source_b,
            TDSource.source_a, TDSource.source_b,
            TDSource.source_a, TDSource.source_b,
        ]
        result = compute_cluster_based_overlap(clusters, source_of)
        assert result["source_a_source_b"] == 3


class TestDeduplicateSubdomainsWithClusters:
    """Tests for deduplicate_subdomains_with_clusters."""

    @pytest.mark.asyncio
    async def test_clusters_track_merged_indices(self):
        """Two similar candidates → one cluster with both indices."""
        candidates = [
            SubdomainCandidate(name="expense management", source=TDSource.source_a, round_number=1),
            SubdomainCandidate(name="expense tracking", source=TDSource.source_b, round_number=1),
            SubdomainCandidate(name="corporate cards", source=TDSource.source_a, round_number=1),
        ]

        def mock_embed(texts):
            vectors = []
            for t in texts:
                if "expense" in t.lower():
                    vectors.append([0.9, 0.1, 0.0])
                else:
                    vectors.append([0.1, 0.9, 0.0])
            return vectors

        with patch("core.shared_tools.embedding_client.embed_texts", side_effect=mock_embed):
            result = await deduplicate_subdomains_with_clusters(candidates, threshold=0.5)

        assert isinstance(result, DeduplicationResult)
        assert len(result.kept) == 2
        assert len(result.embeddings) == 3
        assert len(result.source_of) == 3
        # One cluster should contain indices 0 and 1 (both "expense" variants)
        merged_cluster = [c for c in result.clusters if len(c) > 1]
        assert len(merged_cluster) == 1
        assert set(merged_cluster[0]) == {0, 1}

    @pytest.mark.asyncio
    async def test_source_of_populated(self):
        candidates = [
            SubdomainCandidate(name="A", source=TDSource.source_a, round_number=1),
            SubdomainCandidate(name="B", source=TDSource.source_b, round_number=1),
        ]

        def mock_embed(texts):
            return [[1.0, 0.0], [0.0, 1.0]]

        with patch("core.shared_tools.embedding_client.embed_texts", side_effect=mock_embed):
            result = await deduplicate_subdomains_with_clusters(candidates, threshold=0.85)

        assert result.source_of == [TDSource.source_a, TDSource.source_b]

    @pytest.mark.asyncio
    async def test_backward_compat_wrapper(self):
        """Old deduplicate_subdomains still returns List[SubdomainCandidate]."""
        candidates = [
            SubdomainCandidate(name="A", source=TDSource.source_a, round_number=1),
            SubdomainCandidate(name="B", source=TDSource.source_b, round_number=1),
        ]

        def mock_embed(texts):
            return [[1.0, 0.0], [0.0, 1.0]]

        with patch("core.shared_tools.embedding_client.embed_texts", side_effect=mock_embed):
            result = await deduplicate_subdomains(candidates, threshold=0.85)

        assert isinstance(result, list)
        assert all(isinstance(c, SubdomainCandidate) for c in result)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_empty_candidates(self):
        result = await deduplicate_subdomains_with_clusters([])
        assert result.kept == []
        assert result.clusters == []
        assert result.embeddings == []
        assert result.source_of == []

    @pytest.mark.asyncio
    async def test_workspace_context_routes_embeddings_through_byok_config(self):
        candidates = [
            SubdomainCandidate(name="A", source=TDSource.source_a, round_number=1),
            SubdomainCandidate(name="B", source=TDSource.source_b, round_number=1),
        ]
        resolved = ResolvedModelConfig(
            agent_key="shared.embeddings.default",
            model="openai/text-embedding-3-large",
            api_key="sk-workspace",
            base_url="https://openrouter.workspace/api/v1",
            timeout_s=12.0,
            credential_id="cred-123",
            model_config_id="cfg-123",
        )

        with (
            patch(
                "core.topic_discovery.agents._resolve_model_config_for_agent",
                new_callable=AsyncMock,
                return_value=resolved,
            ) as mock_resolve,
            patch(
                "core.shared_tools.embedding_client.embed_texts",
                return_value=[[1.0, 0.0], [0.0, 1.0]],
            ) as mock_embed,
        ):
            result = await deduplicate_subdomains_with_clusters(
                candidates,
                threshold=0.85,
                company_slug="acme",
                workspace_id="ws-123",
                workspace_slug="acme",
            )

        assert len(result.kept) == 2
        mock_resolve.assert_awaited_once_with(
            workspace_id="ws-123",
            workspace_slug="acme",
            agent_key="shared.embeddings.default",
        )
        assert mock_embed.call_args.args == (["A", "B"],)
        assert mock_embed.call_args.kwargs == {
            "model": "openai/text-embedding-3-large",
            "api_key": "sk-workspace",
            "base_url": "https://openrouter.workspace/api/v1",
            "timeout_s": 12.0,
            "pipeline": "topic_discovery",
            "pipeline_step": "dedup_embedding",
            "company_slug": "acme",
            "workspace_id": "ws-123",
            "agent_key": "shared.embeddings.default",
            "credential_id": "cred-123",
            "model_config_id": "cfg-123",
            "actual_provider": "openai",
            "workspace_billed": True,
        }


class TestComputeAllCoverageMetricsWithClusters:
    """Tests for compute_all_coverage_metrics with dedup_result (new path)."""

    def test_without_dedup_result_backward_compat(self):
        """Without dedup_result → uses legacy exact-name path."""
        sr_a = SourceResult(
            source=TDSource.source_a,
            candidates=[SubdomainCandidate(name="A", source=TDSource.source_a, round_number=1)],
            total_rounds=1, singletons=1, doubletons=0,
            chao1_estimate=1.0, source_sample_coverage=0.0,
        )
        result = compute_all_coverage_metrics([sr_a])
        assert result.cluster_based_overlap is False

    def test_with_dedup_result_uses_cluster_overlap(self):
        """With dedup_result → cluster-based overlap instead of exact name matching."""
        sr_a = SourceResult(
            source=TDSource.source_a,
            candidates=[
                SubdomainCandidate(name="expense mgmt", source=TDSource.source_a, round_number=1),
            ],
            total_rounds=1, singletons=1, doubletons=0,
            chao1_estimate=1.0, source_sample_coverage=0.0,
        )
        sr_b = SourceResult(
            source=TDSource.source_b,
            candidates=[
                SubdomainCandidate(name="expense tracking", source=TDSource.source_b, round_number=1),
            ],
            total_rounds=1, singletons=1, doubletons=0,
            chao1_estimate=1.0, source_sample_coverage=0.0,
        )
        # Dedup merged "expense mgmt" and "expense tracking" into same cluster
        dedup = DeduplicationResult(
            kept=[SubdomainCandidate(name="expense mgmt", source=TDSource.source_a, round_number=1)],
            clusters=[[0, 1]],  # indices 0 (src_a) and 1 (src_b) merged
            embeddings=[[0.9, 0.1, 0.0], [0.85, 0.15, 0.0]],
            source_of=[TDSource.source_a, TDSource.source_b],
        )
        result = compute_all_coverage_metrics([sr_a, sr_b], dedup_result=dedup)
        assert result.cluster_based_overlap is True
        # With cluster overlap = 1, pairwise should now be populated
        assert len(result.pairwise_estimates) >= 1

    def test_with_dedup_result_uses_semantic_frequency(self):
        """With dedup_result → per-source coverage uses semantic singletons/doubletons."""
        sr_a = SourceResult(
            source=TDSource.source_a,
            candidates=[
                SubdomainCandidate(name="expense mgmt", source=TDSource.source_a, round_number=1),
                SubdomainCandidate(name="expense tracking", source=TDSource.source_a, round_number=2),
            ],
            total_rounds=2, singletons=2, doubletons=0,
            chao1_estimate=3.0, source_sample_coverage=0.0,
        )
        # Embeddings are very similar → semantic doubleton
        dedup = DeduplicationResult(
            kept=[SubdomainCandidate(name="expense mgmt", source=TDSource.source_a, round_number=1)],
            clusters=[[0, 1]],
            embeddings=[[0.9, 0.1, 0.0], [0.85, 0.15, 0.0]],
            source_of=[TDSource.source_a, TDSource.source_a],
        )
        result = compute_all_coverage_metrics(
            [sr_a], dedup_result=dedup, semantic_sim_threshold=0.70,
        )
        psc = result.per_source_coverage.get("source_a")
        assert psc is not None
        assert psc.semantic_doubletons >= 1
        assert psc.semantic_sim_threshold == 0.70

    def test_cluster_based_overlap_flag_set(self):
        """cluster_based_overlap flag should be True when dedup_result provided."""
        sr_a = SourceResult(
            source=TDSource.source_a,
            candidates=[SubdomainCandidate(name="A", source=TDSource.source_a, round_number=1)],
            total_rounds=1, singletons=1, doubletons=0,
            chao1_estimate=1.0, source_sample_coverage=0.0,
        )
        dedup = DeduplicationResult(
            kept=[SubdomainCandidate(name="A", source=TDSource.source_a, round_number=1)],
            clusters=[[0]],
            embeddings=[[1.0, 0.0, 0.0]],
            source_of=[TDSource.source_a],
        )
        result = compute_all_coverage_metrics([sr_a], dedup_result=dedup)
        assert result.cluster_based_overlap is True


# ── Phase 3: Persona Metadata Tests ──────────────────────────────────────


class TestResolvePersonaIds:
    """Tests for _resolve_persona_ids helper."""

    def test_exact_match(self):
        from core.topic_discovery.agents import _resolve_persona_ids

        name_to_id = {"David Chen": "david", "Marcus Lee": "marcus"}
        result = _resolve_persona_ids(["David Chen"], name_to_id)
        assert result == ["david"]

    def test_case_insensitive_match(self):
        from core.topic_discovery.agents import _resolve_persona_ids

        name_to_id = {"David Chen": "david"}
        result = _resolve_persona_ids(["david chen"], name_to_id)
        assert result == ["david"]

    def test_substring_match(self):
        from core.topic_discovery.agents import _resolve_persona_ids

        name_to_id = {"David Chen — First-time Founder": "david"}
        result = _resolve_persona_ids(["David Chen"], name_to_id)
        assert result == ["david"]

    def test_empty_input(self):
        from core.topic_discovery.agents import _resolve_persona_ids

        assert _resolve_persona_ids([], {"a": "b"}) == []
        assert _resolve_persona_ids(["x"], {}) == []

    def test_deduplication(self):
        from core.topic_discovery.agents import _resolve_persona_ids

        name_to_id = {"David": "david"}
        result = _resolve_persona_ids(["David", "david", "DAVID"], name_to_id)
        assert result == ["david"]

    def test_non_string_ignored(self):
        from core.topic_discovery.agents import _resolve_persona_ids

        name_to_id = {"David": "david"}
        result = _resolve_persona_ids([None, "", 123, "David"], name_to_id)  # type: ignore[list-item]
        assert result == ["david"]


class TestSourceBPersonaCapture:
    """Tests for persona metadata captured in Source B agent."""

    @pytest.mark.asyncio
    async def test_source_b_captures_persona_ids(self):
        """Source B should populate persona_ids on SubdomainCandidate."""
        llm_response = json.dumps({
            "subdomains": [
                {
                    "name": "Cap Table Accuracy",
                    "description": "Ensuring cap table data is correct",
                    "source_personas": ["David Chen"],
                    "pain_points_addressed": ["inaccurate cap tables", "equity confusion"],
                    "confidence": 0.8,
                }
            ],
            "metadata": {"round_number": 1, "subdomains_generated": 1},
        })

        with patch("core.topic_discovery.agents._run_completion") as mock_comp:
            mock_comp.return_value = (None, llm_response)
            result = await run_source_b_persona_brainstorm(
                "persona profiles text",
                "company context",
                max_rounds=1,
                persona_name_to_id={"David Chen": "david"},
            )
        assert len(result.candidates) == 1
        c = result.candidates[0]
        assert c.persona_ids == ["david"]
        assert "inaccurate cap tables" in c.pain_points
        assert "equity confusion" in c.pain_points

    @pytest.mark.asyncio
    async def test_source_b_without_persona_mapping(self):
        """Without persona_name_to_id, persona_ids should be empty."""
        llm_response = json.dumps({
            "subdomains": [
                {
                    "name": "Test Topic",
                    "description": "desc",
                    "source_personas": ["SomeName"],
                    "confidence": 0.5,
                }
            ],
            "metadata": {"round_number": 1, "subdomains_generated": 1},
        })

        with patch("core.topic_discovery.agents._run_completion") as mock_comp:
            mock_comp.return_value = (None, llm_response)
            result = await run_source_b_persona_brainstorm(
                "profiles", "context", max_rounds=1,
            )
        assert len(result.candidates) == 1
        assert result.candidates[0].persona_ids == []


class TestDedupMergesPersonaIds:
    """Tests for persona_id merging through dedup clusters."""

    @pytest.mark.asyncio
    async def test_dedup_merges_persona_ids(self):
        """When two candidates merge, their persona_ids are combined."""
        from core.topic_discovery.agents import deduplicate_subdomains_with_clusters

        c1 = SubdomainCandidate(
            name="expense mgmt",
            source=TDSource.source_b,
            persona_ids=["david"],
            pain_points=["slow reports"],
        )
        c2 = SubdomainCandidate(
            name="expense management",
            source=TDSource.source_b,
            persona_ids=["marcus"],
            pain_points=["audit failures"],
        )

        with patch("core.shared_tools.embedding_client.embed_texts") as mock_embed:
            # Very similar embeddings → will merge
            mock_embed.return_value = [[0.9, 0.1, 0.0], [0.88, 0.12, 0.0]]
            result = await deduplicate_subdomains_with_clusters(
                [c1, c2], threshold=0.85,
            )

        assert len(result.kept) == 1
        kept = result.kept[0]
        assert sorted(kept.persona_ids) == ["david", "marcus"]
        assert "slow reports" in kept.pain_points
        assert "audit failures" in kept.pain_points

    @pytest.mark.asyncio
    async def test_dedup_no_merge_preserves_persona_ids(self):
        """Dissimilar candidates keep their own persona_ids."""
        from core.topic_discovery.agents import deduplicate_subdomains_with_clusters

        c1 = SubdomainCandidate(
            name="billing", source=TDSource.source_b, persona_ids=["david"],
        )
        c2 = SubdomainCandidate(
            name="devops", source=TDSource.source_b, persona_ids=["marcus"],
        )

        with patch("core.shared_tools.embedding_client.embed_texts") as mock_embed:
            # Very different embeddings → no merge
            mock_embed.return_value = [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
            result = await deduplicate_subdomains_with_clusters(
                [c1, c2], threshold=0.85,
            )

        assert len(result.kept) == 2
        assert result.kept[0].persona_ids == ["david"]
        assert result.kept[1].persona_ids == ["marcus"]


# ── _run_completion cost tracking ───────────────────────────────────────


def _make_mock_response_with_usage(content: str, prompt_tokens: int = 50, completion_tokens: int = 100):
    """Create a mock OpenAI response with usage data for cost tracking tests."""
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_choice.finish_reason = "stop"
    mock_response.choices = [mock_choice]
    mock_response.usage = MagicMock(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    return mock_response


class TestRunCompletionCostTracking:
    """Verify track_llm_cost() is called inside _run_completion()."""

    @pytest.mark.asyncio
    async def test_cost_tracked_on_success(self):
        from core.topic_discovery.agents import _run_completion

        mock_resp = _make_mock_response_with_usage('{"ok": true}', 50, 100)
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        meta = {
            "pipeline": "topic_discovery",
            "pipeline_step": "source_a",
            "company_slug": "test-co",
        }

        with patch("core.shared_tools.openrouter_client.get_async_client", return_value=mock_client), \
             patch("core.shared_tools.cost_tracker.track_llm_cost") as mock_track:
            await _run_completion(
                model="anthropic/claude-sonnet-4-6",
                messages=[{"role": "user", "content": "hi"}],
                timeout_s=10.0,
                metadata=meta,
            )
        mock_track.assert_called_once()
        kw = mock_track.call_args[1]
        assert kw["model"] == "anthropic/claude-sonnet-4-6"
        assert kw["provider"] == "openrouter"
        assert kw["pipeline"] == "topic_discovery"
        assert kw["pipeline_step"] == "source_a"
        assert kw["prompt_tokens"] == 50
        assert kw["completion_tokens"] == 100
        assert kw["company_slug"] == "test-co"
        assert kw["source"] == "openrouter"

    @pytest.mark.asyncio
    async def test_cost_tracked_with_no_metadata(self):
        from core.topic_discovery.agents import _run_completion

        mock_resp = _make_mock_response_with_usage('{"ok": true}')
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        with patch("core.shared_tools.openrouter_client.get_async_client", return_value=mock_client), \
             patch("core.shared_tools.cost_tracker.track_llm_cost") as mock_track:
            await _run_completion(
                model="test-model",
                messages=[{"role": "user", "content": "hi"}],
                timeout_s=10.0,
            )
        kw = mock_track.call_args[1]
        assert kw["pipeline"] == ""
        assert kw["pipeline_step"] == ""
        assert kw["company_slug"] == ""

    @pytest.mark.asyncio
    async def test_cost_tracked_with_missing_usage(self):
        from core.topic_discovery.agents import _run_completion

        mock_resp = _make_mock_response('{"ok": true}')
        mock_resp.usage = None  # explicitly no usage
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        with patch("core.shared_tools.openrouter_client.get_async_client", return_value=mock_client), \
             patch("core.shared_tools.cost_tracker.track_llm_cost") as mock_track:
            await _run_completion(
                model="test-model",
                messages=[{"role": "user", "content": "hi"}],
                timeout_s=10.0,
            )
        kw = mock_track.call_args[1]
        assert kw["prompt_tokens"] == 0
        assert kw["completion_tokens"] == 0

    @pytest.mark.asyncio
    async def test_byok_resolution_uses_workspace_client_and_tracks_metadata(self):
        from core.topic_discovery.agents import _run_completion

        resolved = ResolvedModelConfig(
            workspace_id="ws-123",
            workspace_slug="acme",
            agent_key="topic_discovery.source_a_company",
            model="anthropic/claude-haiku-4-5",
            base_url="https://openrouter.test/api/v1",
            api_key="sk-workspace",
            credential_id="cred-123",
            model_config_id="cfg-123",
            temperature=0.2,
            max_tokens=1234,
            timeout_s=42.0,
            extra_body={"route": "fallback"},
        )
        mock_resp = _make_mock_response_with_usage(
            '{"ok": true}',
            prompt_tokens=12,
            completion_tokens=34,
        )
        mock_resp.model = "anthropic/claude-haiku-4-5"
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        meta = {
            "pipeline": "topic_discovery",
            "pipeline_step": "source_a",
            "company_slug": "acme",
            "run_id": "run-123",
        }

        with (
            patch(
                "core.topic_discovery.agents._resolve_model_config_for_agent",
                new_callable=AsyncMock,
                return_value=resolved,
            ) as mock_resolve,
            patch(
                "core.shared_tools.openrouter_client.build_async_client_for_key",
                return_value=mock_client,
            ) as mock_build,
            patch("core.shared_tools.openrouter_client.get_async_client") as mock_platform_client,
            patch("core.shared_tools.cost_tracker.track_llm_cost") as mock_track,
        ):
            await _run_completion(
                model="anthropic/platform-default",
                messages=[{"role": "user", "content": "hi"}],
                metadata=meta,
                workspace_id="ws-123",
                workspace_slug="acme",
                agent_key="topic_discovery.source_a_company",
            )

        mock_resolve.assert_awaited_once_with(
            workspace_id="ws-123",
            workspace_slug="acme",
            agent_key="topic_discovery.source_a_company",
        )
        mock_build.assert_called_once_with(
            "sk-workspace",
            base_url="https://openrouter.test/api/v1",
            timeout_s=42.0,
        )
        mock_platform_client.assert_not_called()
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "anthropic/claude-haiku-4-5"
        assert call_kwargs["temperature"] == 0.2
        assert call_kwargs["max_tokens"] == 1234
        assert call_kwargs["extra_body"] == {
            "route": "fallback",
            "metadata": meta,
        }
        kw = mock_track.call_args.kwargs
        assert kw["workspace_id"] == "ws-123"
        assert kw["agent_key"] == "topic_discovery.source_a_company"
        assert kw["credential_id"] == "cred-123"
        assert kw["model_config_id"] == "cfg-123"
        assert kw["actual_provider"] == "anthropic"
        assert kw["workspace_billed"] is True
        assert kw["run_id"] == "run-123"
