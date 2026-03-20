"""Tests for core.topic_discovery.scoring — algorithmic subdomain scoring."""
from __future__ import annotations

import json

import pytest

from core.models.topic_discovery import (
    PersonaAffinityIndex,
    ScoredSubdomainList,
    SubdomainCandidate,
    SubdomainNode,
    SubdomainScore,
    TaxonomyTree,
    TopicAssignment,
)
from core.topic_discovery.scoring import (
    _flatten_nodes,
    _normalize_and_combine,
    _score_competitive_density,
    _score_content_coverage,
    _score_gap_severity,
    _score_persona_breadth,
    _score_source_confidence,
    compute_persona_affinity_index,
    compute_subdomain_scores,
    compute_topic_priority,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node(
    name: str = "test",
    *,
    node_id: str = "",
    source_provenance: dict | None = None,
    children: list | None = None,
    is_manually_added: bool = False,
) -> SubdomainNode:
    """Build a SubdomainNode with sensible defaults."""
    return SubdomainNode(
        id=node_id or name,
        name=name,
        description=f"Description of {name}",
        source_provenance=source_provenance or {},
        children=children or [],
        is_manually_added=is_manually_added,
    )


def _taxonomy(*nodes: SubdomainNode) -> TaxonomyTree:
    return TaxonomyTree(
        root_nodes=list(nodes),
        total_subdomains=len(nodes),
    )


# ---------------------------------------------------------------------------
# Signal 1: Source Confidence
# ---------------------------------------------------------------------------


class TestSourceConfidence:
    def test_all_four_sources(self):
        n = _node(source_provenance={
            "source_a": True, "source_b": True,
            "source_c": True, "source_d": True,
        })
        assert _score_source_confidence(n) == pytest.approx(1.0)

    def test_single_source(self):
        n = _node(source_provenance={"source_a": True})
        assert _score_source_confidence(n) == pytest.approx(0.25)

    def test_two_sources(self):
        n = _node(source_provenance={"source_a": True, "source_b": True})
        assert _score_source_confidence(n) == pytest.approx(0.5)

    def test_false_entries_excluded(self):
        n = _node(source_provenance={
            "source_a": True, "source_b": False,
            "source_c": True, "source_d": False,
        })
        assert _score_source_confidence(n) == pytest.approx(0.5)

    def test_manually_added_empty_provenance_neutral(self):
        """CODEX: manually-added nodes with empty provenance → 0.5 neutral."""
        n = _node(source_provenance={}, is_manually_added=True)
        assert _score_source_confidence(n) == pytest.approx(0.5)

    def test_empty_provenance_neutral(self):
        n = _node(source_provenance={})
        assert _score_source_confidence(n) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Signal 2: Content Coverage
# ---------------------------------------------------------------------------


class TestContentCoverage:
    def test_no_site_audit_data(self):
        assert _score_content_coverage([0.1, 0.2], [], 0.6) is None

    def test_no_embedding(self):
        assert _score_content_coverage([], [[0.1, 0.2]], 0.6) is None

    def test_greenfield_no_matches(self):
        """No similar pages → 1.0 (high opportunity)."""
        sd_emb = [1.0, 0.0, 0.0]
        page_embs = [[0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        score = _score_content_coverage(sd_emb, page_embs, 0.6)
        assert score == pytest.approx(1.0)

    def test_saturated_many_matches(self):
        """10+ matching pages → 0.0 (fully covered)."""
        sd_emb = [1.0, 0.0, 0.0]
        page_embs = [[0.95, 0.1, 0.0]] * 15  # all very similar
        score = _score_content_coverage(sd_emb, page_embs, 0.6)
        assert score is not None
        assert score <= 0.0 + 0.01  # near zero or clamped to 0


# ---------------------------------------------------------------------------
# Signal 3: Gap Severity
# ---------------------------------------------------------------------------


class TestGapSeverity:
    def test_no_gap_data(self):
        assert _score_gap_severity([0.1], [], [], 0.6) is None

    def test_no_aligned_queries(self):
        """No queries above similarity threshold → None."""
        sd_emb = [1.0, 0.0]
        gap_embs = [[0.0, 1.0]]
        gap_scores = [0.8]
        assert _score_gap_severity(sd_emb, gap_embs, gap_scores, 0.99) is None

    def test_high_gap(self):
        """Aligned queries with high gap scores → high score."""
        sd_emb = [1.0, 0.0]
        gap_embs = [[0.95, 0.1], [0.9, 0.2]]
        gap_scores = [0.8, 0.6]
        result = _score_gap_severity(sd_emb, gap_embs, gap_scores, 0.6)
        assert result is not None
        assert result > 0.5


# ---------------------------------------------------------------------------
# Signal 4: Competitive Density
# ---------------------------------------------------------------------------


class TestCompetitiveDensity:
    def test_no_competitor_data(self):
        assert _score_competitive_density([0.1], [], 0.6) is None

    def test_no_matches(self):
        sd_emb = [1.0, 0.0]
        comp_embs = [[0.0, 1.0]]
        assert _score_competitive_density(sd_emb, comp_embs, 0.99) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Signal 5: Persona Breadth
# ---------------------------------------------------------------------------


class TestPersonaBreadth:
    def test_multi_source_with_persona(self):
        n = _node(source_provenance={
            "source_a": True, "source_b": True, "source_c": False, "source_d": True,
        })
        score = _score_persona_breadth(n)
        # 3/4 = 0.75 + 0.15 (source_b bonus) = 0.90
        assert score == pytest.approx(0.90)

    def test_no_persona_source(self):
        n = _node(source_provenance={"source_a": True, "source_d": True})
        score = _score_persona_breadth(n)
        # 2/4 = 0.5, no bonus
        assert score == pytest.approx(0.5)

    def test_empty_provenance_neutral(self):
        n = _node(source_provenance={})
        assert _score_persona_breadth(n) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


class TestNormalizeAndCombine:
    def test_excludes_unavailable_signals(self):
        raw = {"a": 0.8, "b": None, "c": 0.6}
        weights = {"a": 0.5, "b": 0.3, "c": 0.2}
        composite, used, norm_w, avail = _normalize_and_combine(raw, weights)
        assert "b" not in used
        assert set(avail) == {"a", "c"}
        # weights renormalised: a=0.5/(0.5+0.2)=0.714, c=0.2/0.7=0.286
        assert composite == pytest.approx(0.8 * (0.5 / 0.7) + 0.6 * (0.2 / 0.7), rel=1e-3)

    def test_all_none_returns_zero(self):
        raw = {"a": None, "b": None}
        composite, _, _, _ = _normalize_and_combine(raw, {"a": 0.5, "b": 0.5})
        assert composite == 0.0

    def test_single_signal(self):
        raw = {"a": 0.7}
        composite, _, _, _ = _normalize_and_combine(raw, {"a": 1.0})
        assert composite == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# compute_subdomain_scores (integration)
# ---------------------------------------------------------------------------


class TestComputeSubdomainScores:
    @pytest.mark.asyncio
    async def test_minimal_signals(self):
        """Only always-available signals (source_confidence + persona_breadth)."""
        tax = _taxonomy(
            _node("alpha", node_id="a1", source_provenance={
                "source_a": True, "source_b": True,
            }),
            _node("beta", node_id="b1", source_provenance={
                "source_a": True,
            }),
        )
        result = await compute_subdomain_scores(tax)
        assert isinstance(result, ScoredSubdomainList)
        assert result.total_scored == 2
        # alpha has more sources → higher score
        assert result.scores[0].subdomain_name == "alpha"
        assert result.scores[0].rank == 1
        assert result.scores[1].rank == 2

    @pytest.mark.asyncio
    async def test_ranked_output_sorted_descending(self):
        tax = _taxonomy(
            _node("low", node_id="lo", source_provenance={"source_a": True}),
            _node("high", node_id="hi", source_provenance={
                "source_a": True, "source_b": True,
                "source_c": True, "source_d": True,
            }),
        )
        result = await compute_subdomain_scores(tax)
        assert result.scores[0].subdomain_name == "high"
        assert result.scores[0].composite_score >= result.scores[1].composite_score

    @pytest.mark.asyncio
    async def test_tie_breaking_alphabetical(self):
        """CODEX: equal scores → alphabetical by name."""
        tax = _taxonomy(
            _node("zebra", node_id="z1", source_provenance={"source_a": True}),
            _node("alpha", node_id="a1", source_provenance={"source_a": True}),
        )
        result = await compute_subdomain_scores(tax)
        assert result.scores[0].subdomain_name == "alpha"
        assert result.scores[1].subdomain_name == "zebra"

    @pytest.mark.asyncio
    async def test_custom_weights(self):
        tax = _taxonomy(
            _node("x", node_id="x1", source_provenance={"source_a": True}),
        )
        custom = {"source_confidence": 1.0, "persona_breadth": 0.0}
        result = await compute_subdomain_scores(tax, weights_config=custom)
        assert result.weights_config == custom

    @pytest.mark.asyncio
    async def test_nested_children_flattened(self):
        child = _node("child", node_id="c1", source_provenance={"source_a": True})
        parent = _node("parent", node_id="p1", source_provenance={
            "source_a": True, "source_b": True,
        }, children=[child])
        tax = _taxonomy(parent)
        result = await compute_subdomain_scores(tax)
        assert result.total_scored == 2
        names = {s.subdomain_name for s in result.scores}
        assert names == {"parent", "child"}


# ---------------------------------------------------------------------------
# Persona Affinity Index
# ---------------------------------------------------------------------------


class TestPersonaAffinityIndex:
    @pytest.mark.asyncio
    async def test_source_b_provenance(self):
        tax = _taxonomy(
            _node("topic-a", node_id="a1"),
            _node("topic-b", node_id="b1"),
        )
        persona_mds = {"david": "David is a founder"}
        persona_embs = {"david": [0.0] * 10}  # dummy
        sd_embs = {"a1": [0.0] * 10, "b1": [0.0] * 10}
        sb_map = {"topic-a": ["david"]}  # only topic-a via Source B

        result = await compute_persona_affinity_index(
            tax, sd_embs, persona_mds, persona_embs, sb_map,
        )
        assert isinstance(result, PersonaAffinityIndex)
        assert result.total_personas == 1
        entries = result.persona_entries["david"]
        # topic-a should have higher affinity than topic-b
        a_entry = next(e for e in entries if e.subdomain_name == "topic-a")
        b_entry = next(e for e in entries if e.subdomain_name == "topic-b")
        assert a_entry.affinity_score > b_entry.affinity_score

    @pytest.mark.asyncio
    async def test_embedding_similarity(self):
        tax = _taxonomy(
            _node("fintech", node_id="f1"),
            _node("devops", node_id="d1"),
        )
        persona_mds = {"cfo": "CFO managing finances"}
        # fintech embedding close to CFO, devops far
        persona_embs = {"cfo": [1.0, 0.0]}
        sd_embs = {"f1": [0.9, 0.1], "d1": [0.0, 1.0]}
        sb_map: dict = {}

        result = await compute_persona_affinity_index(
            tax, sd_embs, persona_mds, persona_embs, sb_map,
        )
        entries = result.persona_entries["cfo"]
        f_entry = next(e for e in entries if e.subdomain_name == "fintech")
        d_entry = next(e for e in entries if e.subdomain_name == "devops")
        assert f_entry.affinity_score > d_entry.affinity_score

    @pytest.mark.asyncio
    async def test_no_personas_empty_index(self):
        tax = _taxonomy(_node("x", node_id="x1"))
        result = await compute_persona_affinity_index(
            tax, {}, {}, {}, {},
        )
        assert result.total_personas == 0
        assert result.persona_entries == {}

    @pytest.mark.asyncio
    async def test_both_signals(self):
        tax = _taxonomy(_node("topic-a", node_id="a1"))
        persona_embs = {"p1": [1.0, 0.0]}
        sd_embs = {"a1": [0.9, 0.1]}
        sb_map = {"topic-a": ["p1"]}

        result = await compute_persona_affinity_index(
            tax, sd_embs, {"p1": "Persona 1"}, persona_embs, sb_map,
        )
        entry = result.persona_entries["p1"][0]
        assert entry.provenance == "both"
        # 0.6 * 1.0 + 0.4 * cosim(~0.99) ≈ ~0.99+
        assert entry.affinity_score > 0.9


# ---------------------------------------------------------------------------
# Topic Priority Scoring
# ---------------------------------------------------------------------------


class TestTopicPriority:
    def test_bofu_transactional_highest(self):
        score, factors = compute_topic_priority("bofu", "transactional", 1.0)
        # (1.0 + 1.0) / 2 * 1.0 = 1.0
        assert score == pytest.approx(1.0)
        assert factors["buyer_weight"] == pytest.approx(1.0)
        assert factors["intent_weight"] == pytest.approx(1.0)

    def test_tofu_navigational_lowest(self):
        score, _ = compute_topic_priority("tofu", "navigational", 1.0)
        # (0.6 + 0.2) / 2 = 0.4
        assert score == pytest.approx(0.4)

    def test_subdomain_multiplier(self):
        score_high, _ = compute_topic_priority("mofu", "commercial", 1.0)
        score_low, _ = compute_topic_priority("mofu", "commercial", 0.5)
        assert score_high > score_low

    def test_priority_factors_populated(self):
        _, factors = compute_topic_priority("mofu", "informational", 0.8)
        assert "buyer_weight" in factors
        assert "intent_weight" in factors
        assert "subdomain_score" in factors
        assert "base_weight" in factors

    def test_unknown_stage_defaults(self):
        """Unknown buyer_stage/intent → default 0.5."""
        score, _ = compute_topic_priority("unknown", "unknown", 1.0)
        assert score == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Backward Compatibility (CODEX)
# ---------------------------------------------------------------------------


class TestBackwardCompat:
    def test_subdomain_node_missing_new_fields(self):
        """Old JSON without priority_score/persona_affinity/expansion_status."""
        old_json = {
            "id": "abc",
            "name": "old node",
            "depth": 1,
            "source_provenance": {"source_a": True},
            "children": [],
        }
        node = SubdomainNode.model_validate(old_json)
        assert node.priority_score == 0.0
        assert node.priority_factors == {}
        assert node.persona_affinity == {}
        assert node.expansion_status == "not_expanded"

    def test_topic_assignment_missing_new_fields(self):
        """Old JSON without persona_id/persona_name."""
        old_json = {
            "id": "ta1",
            "subdomain_name": "test",
            "topic_text": "old topic",
            "buyer_stage": "tofu",
            "intent_type": "informational",
            "audience_segment": "Persona 1",
        }
        ta = TopicAssignment.model_validate(old_json)
        assert ta.persona_id == ""
        assert ta.persona_name == ""

    def test_subdomain_candidate_missing_new_fields(self):
        """Old JSON without persona_ids/pain_points."""
        old_json = {
            "name": "old candidate",
            "source": "source_a",
            "confidence": 0.5,
        }
        c = SubdomainCandidate.model_validate(old_json)
        assert c.persona_ids == []
        assert c.pain_points == []
