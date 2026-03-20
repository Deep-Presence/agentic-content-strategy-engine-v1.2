"""Tests for core.gap_analysis.topic_cluster_map — cluster mapping module.

Covers:
  - All 6 valid buyer_stage × intent_type cells
  - All 6 excluded combinations
  - Case/whitespace normalization
  - Cluster metadata helpers
  - Backward compat: models deserialize without new fields
"""
from __future__ import annotations

import json

import pytest

from core.gap_analysis.topic_cluster_map import (
    CLUSTER_BRAND_POLICY,
    CLUSTER_NAMES,
    ClusterMapping,
    get_all_excluded_cells,
    get_all_valid_cells,
    get_cluster_brand_policy,
    get_cluster_mapping,
    get_cluster_name,
    get_exclusion_reason,
    is_excluded_combo,
)
from core.models.content_generation import ContentPiece
from core.models.content_generation_v13 import (
    ContentGenerationInputV13,
    EntryMode,
)
from core.models.gap_analysis import (
    AnalysisResult,
    GeneratedQuery,
    QueryGap,
)


# ---------------------------------------------------------------------------
# Valid Cells (6)
# ---------------------------------------------------------------------------


class TestValidCells:
    """Test all 6 valid buyer_stage × intent_type mappings."""

    def test_tofu_informational(self):
        m = get_cluster_mapping("tofu", "informational")
        assert m is not None
        assert "C5" in m.primary
        assert "C6" in m.primary
        assert "C1" in m.secondary
        assert m.queries_range == (5, 8)
        assert m.brand_rule == "no_brand_names"

    def test_tofu_commercial(self):
        m = get_cluster_mapping("tofu", "commercial")
        assert m is not None
        assert "C7" in m.primary
        assert "C6" in m.secondary
        assert m.queries_range == (3, 5)

    def test_mofu_informational(self):
        m = get_cluster_mapping("mofu", "informational")
        assert m is not None
        assert "C1" in m.primary
        assert "C2" in m.primary
        assert "C4" in m.secondary
        assert m.queries_range == (5, 8)

    def test_mofu_commercial(self):
        m = get_cluster_mapping("mofu", "commercial")
        assert m is not None
        assert "C3" in m.primary
        assert "C7" in m.primary
        assert "C4" in m.secondary
        assert m.queries_range == (4, 7)

    def test_bofu_commercial(self):
        m = get_cluster_mapping("bofu", "commercial")
        assert m is not None
        assert "C8" in m.primary
        assert "C4" in m.primary
        assert "C3" in m.secondary
        assert m.queries_range == (4, 6)
        assert "brand" in m.brand_rule

    def test_bofu_transactional(self):
        m = get_cluster_mapping("bofu", "transactional")
        assert m is not None
        assert "C9" in m.primary
        assert "C8" in m.primary
        assert len(m.secondary) == 0
        assert m.queries_range == (3, 5)

    def test_all_valid_cells_count(self):
        cells = get_all_valid_cells()
        assert len(cells) == 6

    def test_all_valid_cells_return_mappings(self):
        for stage, intent in get_all_valid_cells():
            m = get_cluster_mapping(stage, intent)
            assert m is not None, f"({stage}, {intent}) should be valid"
            assert len(m.primary) >= 1


# ---------------------------------------------------------------------------
# Excluded Cells (6)
# ---------------------------------------------------------------------------


class TestExcludedCells:
    """Test all 6 excluded buyer_stage × intent_type combinations."""

    @pytest.mark.parametrize(
        "stage,intent",
        [
            ("tofu", "transactional"),
            ("tofu", "navigational"),
            ("mofu", "navigational"),
            ("mofu", "transactional"),
            ("bofu", "informational"),
            ("bofu", "navigational"),
        ],
    )
    def test_excluded_returns_none(self, stage, intent):
        assert get_cluster_mapping(stage, intent) is None

    @pytest.mark.parametrize(
        "stage,intent",
        [
            ("tofu", "transactional"),
            ("tofu", "navigational"),
            ("mofu", "navigational"),
            ("mofu", "transactional"),
            ("bofu", "informational"),
            ("bofu", "navigational"),
        ],
    )
    def test_is_excluded_combo(self, stage, intent):
        assert is_excluded_combo(stage, intent) is True

    @pytest.mark.parametrize(
        "stage,intent",
        [
            ("tofu", "transactional"),
            ("tofu", "navigational"),
            ("mofu", "navigational"),
            ("mofu", "transactional"),
            ("bofu", "informational"),
            ("bofu", "navigational"),
        ],
    )
    def test_exclusion_reason_not_empty(self, stage, intent):
        reason = get_exclusion_reason(stage, intent)
        assert reason is not None
        assert len(reason) > 10

    def test_all_excluded_cells_count(self):
        cells = get_all_excluded_cells()
        assert len(cells) == 6

    def test_valid_combos_not_excluded(self):
        for stage, intent in get_all_valid_cells():
            assert is_excluded_combo(stage, intent) is False


# ---------------------------------------------------------------------------
# Case & Whitespace Normalization
# ---------------------------------------------------------------------------


class TestNormalization:
    """Inputs should be normalized to lowercase with stripped whitespace."""

    def test_uppercase_input(self):
        m = get_cluster_mapping("TOFU", "INFORMATIONAL")
        assert m is not None
        assert "C5" in m.primary

    def test_mixed_case(self):
        m = get_cluster_mapping("Mofu", "Commercial")
        assert m is not None

    def test_whitespace_padding(self):
        m = get_cluster_mapping("  bofu  ", "  transactional  ")
        assert m is not None

    def test_excluded_uppercase(self):
        assert is_excluded_combo("TOFU", "TRANSACTIONAL") is True

    def test_unknown_combo_returns_none(self):
        assert get_cluster_mapping("unknown", "stage") is None
        assert is_excluded_combo("unknown", "stage") is False


# ---------------------------------------------------------------------------
# Cluster Metadata Helpers
# ---------------------------------------------------------------------------


class TestClusterMetadata:
    """Test cluster name and brand policy helpers."""

    def test_all_9_clusters_have_names(self):
        for i in range(1, 10):
            cid = f"C{i}"
            name = get_cluster_name(cid)
            assert name != cid  # Should return a human-readable name
            assert len(name) > 0

    def test_cluster_brand_policies(self):
        # C8 requires brands
        assert "required" in get_cluster_brand_policy("C8")
        # Others generally don't
        assert "no_brand" in get_cluster_brand_policy("C1")
        assert "no_brand" in get_cluster_brand_policy("C5")

    def test_unknown_cluster_fallback(self):
        assert get_cluster_name("C99") == "C99"
        assert get_cluster_brand_policy("C99") == "no_brand_names"

    def test_cluster_names_dict_complete(self):
        assert len(CLUSTER_NAMES) == 9

    def test_cluster_brand_policy_dict_complete(self):
        assert len(CLUSTER_BRAND_POLICY) == 9


# ---------------------------------------------------------------------------
# ClusterMapping Immutability
# ---------------------------------------------------------------------------


class TestClusterMappingDataclass:
    """ClusterMapping is frozen — verify immutability."""

    def test_frozen(self):
        m = ClusterMapping(primary=("C1",), secondary=("C2",))
        with pytest.raises(AttributeError):
            m.primary = ("C3",)  # type: ignore[misc]

    def test_defaults(self):
        m = ClusterMapping()
        assert m.primary == ()
        assert m.secondary == ()
        assert m.queries_range == (3, 5)
        assert m.brand_rule == "no_brand_names"


# ---------------------------------------------------------------------------
# Model Backward Compatibility
# ---------------------------------------------------------------------------


class TestModelBackwardCompat:
    """New fields must deserialize from old JSON (without the field)."""

    def test_generated_query_without_source_topic_ids(self):
        old_json = {
            "query_id": "q1",
            "cluster_id": "C5",
            "cluster_name": "Definition",
            "query_text": "What is AP automation?",
        }
        q = GeneratedQuery(**old_json)
        assert q.source_topic_ids == []

    def test_generated_query_with_source_topic_ids(self):
        data = {
            "query_id": "q1",
            "cluster_id": "C5",
            "cluster_name": "Definition",
            "query_text": "What is AP automation?",
            "source_topic_ids": ["t1", "t2"],
        }
        q = GeneratedQuery(**data)
        assert q.source_topic_ids == ["t1", "t2"]

    def test_query_gap_without_source_topic_ids(self):
        old_json = {
            "query_id": "q1",
            "query_text": "What is AP automation?",
        }
        g = QueryGap(**old_json)
        assert g.source_topic_ids == []

    def test_query_gap_with_source_topic_ids(self):
        data = {
            "query_id": "q1",
            "query_text": "test",
            "source_topic_ids": ["t1"],
        }
        g = QueryGap(**data)
        assert g.source_topic_ids == ["t1"]

    def test_analysis_result_without_topic_query_map(self):
        old_json: dict = {}
        r = AnalysisResult(**old_json)
        assert r.topic_query_map == {}

    def test_analysis_result_with_topic_query_map(self):
        data = {"topic_query_map": {"t1": ["q1", "q2"], "t2": ["q3"]}}
        r = AnalysisResult(**data)
        assert r.topic_query_map == {"t1": ["q1", "q2"], "t2": ["q3"]}

    def test_content_piece_without_topic_assignment_id(self):
        old_json = {"brief_id": "b1", "title": "Test"}
        p = ContentPiece(**old_json)
        assert p.topic_assignment_id is None

    def test_content_piece_with_topic_assignment_id(self):
        data = {"brief_id": "b1", "title": "Test", "topic_assignment_id": "ta-123"}
        p = ContentPiece(**data)
        assert p.topic_assignment_id == "ta-123"

    def test_entry_mode_topic_discovery(self):
        assert EntryMode.TOPIC_DISCOVERY.value == "topic_discovery"

    def test_input_v13_without_td_fields(self):
        old_json = {
            "company_name": "Test Co",
            "domain": "test.co",
        }
        inp = ContentGenerationInputV13(**old_json)
        assert inp.topic_assignment_ids == []
        assert inp.td_effective_slug is None
        assert inp.td_ga_run_id is None

    def test_input_v13_with_td_fields(self):
        data = {
            "company_name": "Test Co",
            "domain": "test.co",
            "entry_mode": "topic_discovery",
            "topic_assignment_ids": ["ta-1", "ta-2"],
            "td_effective_slug": "test-co",
            "td_ga_run_id": "run-abc",
        }
        inp = ContentGenerationInputV13(**data)
        assert inp.entry_mode == EntryMode.TOPIC_DISCOVERY
        assert inp.topic_assignment_ids == ["ta-1", "ta-2"]
        assert inp.td_effective_slug == "test-co"
        assert inp.td_ga_run_id == "run-abc"

    def test_roundtrip_serialization(self):
        """Ensure new fields survive JSON roundtrip."""
        q = GeneratedQuery(
            query_id="q1",
            cluster_id="C5",
            cluster_name="Definition",
            query_text="What is X?",
            source_topic_ids=["t1", "t2"],
        )
        json_str = q.model_dump_json()
        q2 = GeneratedQuery.model_validate_json(json_str)
        assert q2.source_topic_ids == ["t1", "t2"]

    def test_analysis_result_roundtrip(self):
        r = AnalysisResult(topic_query_map={"t1": ["q1"]})
        data = json.loads(r.model_dump_json())
        r2 = AnalysisResult(**data)
        assert r2.topic_query_map == {"t1": ["q1"]}
