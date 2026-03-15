"""Tests for Topic Discovery Pydantic models.

Covers: enum values, model instantiation, field defaults, serialization
round-trips, recursive SubdomainNode, and forward-ref resolution.
"""
from __future__ import annotations

import json

import pytest

from core.models.topic_discovery import (
    AudienceSegmentType,
    BuyerStage,
    CaptureRecaptureResult,
    IntentType,
    PerSourceCoverage,
    RelevanceCell,
    SourceResult,
    SubdomainCandidate,
    SubdomainNode,
    TaxonomyTree,
    TDSource,
    TopicAssignment,
    TopicAssignmentMatrix,
    TopicAssignmentStatus,
    TopicDiscoveryInput,
    TopicDiscoveryManifest,
    TopicDiscoveryOutput,
    TopicDiscoveryStatus,
)


# ── Enum Tests ────────────────────────────────────────────────────────────


class TestEnums:
    """Verify all enums have the expected values."""

    def test_buyer_stage_values(self):
        assert set(BuyerStage) == {BuyerStage.TOFU, BuyerStage.MOFU, BuyerStage.BOFU}
        assert BuyerStage.TOFU.value == "tofu"

    def test_intent_type_values(self):
        assert len(IntentType) == 4
        assert IntentType.informational.value == "informational"
        assert IntentType.commercial.value == "commercial"
        assert IntentType.navigational.value == "navigational"
        assert IntentType.transactional.value == "transactional"

    def test_audience_segment_type_values(self):
        assert len(AudienceSegmentType) == 2
        assert AudienceSegmentType.individual_persona.value == "individual_persona"
        assert AudienceSegmentType.team_group.value == "team_group"

    def test_topic_discovery_status_values(self):
        assert len(TopicDiscoveryStatus) == 5
        expected = {"draft", "hitl_pending", "discovery_complete", "approved", "archived"}
        assert {s.value for s in TopicDiscoveryStatus} == expected

    def test_td_source_values(self):
        assert len(TDSource) == 4
        expected = {"source_a", "source_b", "source_c", "source_d"}
        assert {s.value for s in TDSource} == expected

    def test_relevance_cell_values(self):
        assert len(RelevanceCell) == 3
        assert RelevanceCell.relevant.value == "relevant"
        assert RelevanceCell.marginal.value == "marginal"
        assert RelevanceCell.irrelevant.value == "irrelevant"

    def test_topic_assignment_status_values(self):
        assert len(TopicAssignmentStatus) == 4
        expected = {"not_started", "in_gap_analysis", "content_produced", "published"}
        assert {s.value for s in TopicAssignmentStatus} == expected


# ── TopicDiscoveryInput ───────────────────────────────────────────────────


class TestTopicDiscoveryInput:
    def test_minimal_construction(self):
        inp = TopicDiscoveryInput(company_name="Acme")
        assert inp.company_name == "Acme"
        assert inp.domain is None
        assert inp.language == "en"
        assert inp.max_expansion_rounds == 4
        assert inp.dedup_threshold == 0.85
        assert inp.auto_approve_checkpoints == []

    def test_full_construction(self):
        inp = TopicDiscoveryInput(
            company_name="Ramp",
            domain="ramp.com",
            company_slug="ramp",
            product_slug="expense",
            product_name="Expense Management",
            seed_urls=["https://ramp.com/sitemap.xml"],
            language="en",
            region="US",
            max_expansion_rounds=6,
            dedup_threshold=0.9,
            auto_approve_checkpoints=[1, 2],
        )
        assert inp.product_slug == "expense"
        assert len(inp.seed_urls) == 1

    def test_roundtrip_serialization(self):
        inp = TopicDiscoveryInput(company_name="Test Co", domain="test.com")
        data = json.loads(inp.model_dump_json())
        restored = TopicDiscoveryInput(**data)
        assert restored.company_name == inp.company_name
        assert restored.domain == inp.domain

    def test_topic_discovery_input_default_company_name(self):
        """M8: company_name defaults to '' for backward compat."""
        inp = TopicDiscoveryInput()
        assert inp.company_name == ""


# ── SubdomainCandidate ────────────────────────────────────────────────────


class TestSubdomainCandidate:
    def test_defaults(self):
        c = SubdomainCandidate()
        assert c.name == ""
        assert c.source == TDSource.source_a
        assert c.round_number == 1
        assert c.specialist_lens is None
        assert c.confidence == 0.0
        assert c.id  # UUID auto-generated

    def test_unique_ids(self):
        c1 = SubdomainCandidate()
        c2 = SubdomainCandidate()
        assert c1.id != c2.id

    def test_roundtrip(self):
        c = SubdomainCandidate(
            name="fintech",
            source=TDSource.source_d,
            specialist_lens="regulatory",
            confidence=0.7,
        )
        data = json.loads(c.model_dump_json())
        restored = SubdomainCandidate(**data)
        assert restored.name == "fintech"
        assert restored.source == TDSource.source_d
        assert restored.specialist_lens == "regulatory"


# ── SourceResult ──────────────────────────────────────────────────────────


class TestSourceResult:
    def test_defaults(self):
        sr = SourceResult()
        assert sr.source == TDSource.source_a
        assert sr.candidates == []
        assert sr.total_rounds == 0
        assert sr.chao1_estimate == 0.0
        assert sr.source_sample_coverage == 0.0
        assert sr.error is None

    def test_with_candidates(self, sample_source_result):
        assert len(sample_source_result.candidates) == 5
        assert sample_source_result.total_rounds == 3
        assert sample_source_result.singletons == 2

    def test_roundtrip(self, sample_source_result):
        data = json.loads(sample_source_result.model_dump_json())
        restored = SourceResult(**data)
        assert len(restored.candidates) == 5
        assert restored.source == TDSource.source_a

    def test_error_field(self):
        sr = SourceResult(error="Timeout after 120s")
        assert sr.error == "Timeout after 120s"

    def test_new_coverage_fields(self):
        sr = SourceResult(
            source=TDSource.source_b,
            chao1_estimate=12.5,
            source_sample_coverage=0.85,
        )
        assert sr.chao1_estimate == 12.5
        assert sr.source_sample_coverage == 0.85

    def test_backward_compat_old_json(self):
        """Old JSON without new fields deserializes with defaults."""
        old = {"source": "source_a", "candidates": [], "total_rounds": 2,
               "singletons": 1, "doubletons": 0, "execution_time_s": 5.0}
        sr = SourceResult(**old)
        assert sr.chao1_estimate == 0.0
        assert sr.source_sample_coverage == 0.0


# ── PerSourceCoverage ────────────────────────────────────────────────────


class TestPerSourceCoverage:
    def test_defaults(self):
        psc = PerSourceCoverage()
        assert psc.source == TDSource.source_a
        assert psc.singletons == 0
        assert psc.doubletons == 0
        assert psc.observed == 0
        assert psc.total_observations == 0
        assert psc.chao1_estimate == 0.0
        assert psc.sample_coverage == 0.0

    def test_roundtrip(self):
        psc = PerSourceCoverage(
            source=TDSource.source_d,
            singletons=3,
            doubletons=1,
            observed=10,
            total_observations=14,
            chao1_estimate=14.5,
            sample_coverage=0.79,
        )
        data = json.loads(psc.model_dump_json())
        restored = PerSourceCoverage(**data)
        assert restored.source == TDSource.source_d
        assert restored.chao1_estimate == 14.5
        assert restored.sample_coverage == 0.79


# ── CaptureRecaptureResult ───────────────────────────────────────────────


class TestCaptureRecaptureResult:
    def test_defaults(self):
        cr = CaptureRecaptureResult()
        assert cr.median_estimate == 0.0
        assert cr.meets_target is False
        assert cr.coverage_target == 0.95
        assert cr.per_source_coverage == {}
        assert cr.aggregate_sample_coverage == 0.0
        assert cr.aggregate_chao1_ratio == 0.0

    def test_with_data(self):
        cr = CaptureRecaptureResult(
            pairwise_estimates={"a_b": 112.0, "a_c": 108.0},
            median_estimate=110.0,
            estimate_range=[108.0, 112.0],
            chao1_lower_bound=105.0,
            sample_coverage=0.96,
            observed_count=100,
            total_singletons=4,
            total_doubletons=2,
            meets_target=True,
        )
        assert cr.sample_coverage == 0.96
        assert cr.meets_target is True

    def test_with_per_source_coverage(self):
        psc_a = PerSourceCoverage(
            source=TDSource.source_a, singletons=2, observed=10,
            chao1_estimate=12.0, sample_coverage=0.92,
        )
        cr = CaptureRecaptureResult(
            per_source_coverage={"source_a": psc_a},
            aggregate_sample_coverage=0.92,
            aggregate_chao1_ratio=0.83,
        )
        assert cr.per_source_coverage["source_a"].chao1_estimate == 12.0
        assert cr.aggregate_sample_coverage == 0.92

    def test_roundtrip(self):
        cr = CaptureRecaptureResult(
            pairwise_estimates={"a_b": 112.0},
            median_estimate=112.0,
            sample_coverage=0.94,
            observed_count=100,
        )
        data = json.loads(cr.model_dump_json())
        restored = CaptureRecaptureResult(**data)
        assert restored.median_estimate == 112.0
        assert restored.pairwise_estimates["a_b"] == 112.0

    def test_roundtrip_with_per_source(self):
        psc = PerSourceCoverage(
            source=TDSource.source_b, singletons=3, chao1_estimate=8.0,
        )
        cr = CaptureRecaptureResult(
            per_source_coverage={"source_b": psc},
            aggregate_sample_coverage=0.88,
        )
        data = json.loads(cr.model_dump_json())
        restored = CaptureRecaptureResult(**data)
        assert "source_b" in restored.per_source_coverage
        assert restored.per_source_coverage["source_b"].singletons == 3
        assert restored.aggregate_sample_coverage == 0.88

    def test_backward_compat_old_json(self):
        """Old JSON without new fields deserializes with defaults."""
        old_data = {
            "pairwise_estimates": {"a_b": 100.0},
            "median_estimate": 100.0,
            "estimate_range": [100.0, 100.0],
            "chao1_lower_bound": 95.0,
            "sample_coverage": 0.93,
            "observed_count": 90,
            "total_singletons": 5,
            "total_doubletons": 3,
            "coverage_target": 0.95,
            "meets_target": False,
        }
        cr = CaptureRecaptureResult(**old_data)
        # Old fields preserved
        assert cr.sample_coverage == 0.93
        assert cr.total_singletons == 5
        # New fields get defaults
        assert cr.per_source_coverage == {}
        assert cr.aggregate_sample_coverage == 0.0
        assert cr.aggregate_chao1_ratio == 0.0


# ── SubdomainNode (recursive) ────────────────────────────────────────────


class TestSubdomainNode:
    def test_defaults(self):
        node = SubdomainNode()
        assert node.name == ""
        assert node.children == []
        assert node.depth == 0
        assert node.is_manually_added is False

    def test_nested_children(self):
        child = SubdomainNode(name="Child", depth=1)
        parent = SubdomainNode(name="Parent", depth=0, children=[child])
        assert len(parent.children) == 1
        assert parent.children[0].name == "Child"

    def test_deep_nesting(self):
        """3-level deep nesting should work."""
        leaf = SubdomainNode(name="Leaf", depth=2)
        mid = SubdomainNode(name="Mid", depth=1, children=[leaf])
        root = SubdomainNode(name="Root", depth=0, children=[mid])
        assert root.children[0].children[0].name == "Leaf"

    def test_roundtrip_nested(self):
        child = SubdomainNode(name="Sub", depth=1, confidence=0.8)
        parent = SubdomainNode(
            name="Main",
            depth=0,
            source_provenance={"source_a": True, "source_b": False},
            children=[child],
        )
        data = json.loads(parent.model_dump_json())
        restored = SubdomainNode(**data)
        assert restored.children[0].name == "Sub"
        assert restored.source_provenance["source_a"] is True

    def test_source_provenance_dict(self):
        node = SubdomainNode(
            name="Test",
            source_provenance={
                "source_a": True,
                "source_b": True,
                "source_c": False,
                "source_d": True,
            },
            confidence=0.75,
        )
        assert sum(node.source_provenance.values()) == 3


# ── TaxonomyTree ─────────────────────────────────────────────────────────


class TestTaxonomyTree:
    def test_defaults(self):
        t = TaxonomyTree()
        assert t.version == 1
        assert t.root_nodes == []
        assert t.status == TopicDiscoveryStatus.draft
        assert t.created_at  # auto-filled

    def test_with_nodes(self, sample_taxonomy):
        assert sample_taxonomy.domain_name == "fintech"
        assert len(sample_taxonomy.root_nodes) == 2
        assert sample_taxonomy.total_subdomains == 4
        assert sample_taxonomy.coverage_score == 0.92

    def test_roundtrip(self, sample_taxonomy):
        data = json.loads(sample_taxonomy.model_dump_json())
        restored = TaxonomyTree(**data)
        assert len(restored.root_nodes) == 2
        assert restored.root_nodes[0].children[0].name == "Receipt Scanning"
        assert restored.status == TopicDiscoveryStatus.approved

    def test_nested_nodes_preserved(self, sample_taxonomy):
        """Verify nested children survive serialization."""
        data = sample_taxonomy.model_dump(mode="json")
        restored = TaxonomyTree.model_validate(data)
        expense = restored.root_nodes[0]
        assert len(expense.children) == 2
        assert expense.children[1].name == "Policy Enforcement"


# ── TopicAssignment ──────────────────────────────────────────────────────


class TestTopicAssignment:
    def test_defaults(self):
        ta = TopicAssignment()
        assert ta.buyer_stage == BuyerStage.TOFU
        assert ta.intent_type == IntentType.informational
        assert ta.relevance == RelevanceCell.relevant
        assert ta.status == TopicAssignmentStatus.not_started
        assert ta.priority_score == 0.0
        assert ta.is_manually_added is False

    def test_full_construction(self):
        ta = TopicAssignment(
            subdomain_name="Expense Management",
            topic_text="How to automate expense reports",
            buyer_stage=BuyerStage.MOFU,
            intent_type=IntentType.commercial,
            audience_segment="CFO",
            audience_segment_type=AudienceSegmentType.individual_persona,
            relevance=RelevanceCell.relevant,
            priority_score=0.9,
            priority_factors={"strategic": 0.8, "audience_coverage": 0.7},
        )
        assert ta.priority_score == 0.9
        assert ta.priority_factors["strategic"] == 0.8

    def test_roundtrip(self):
        ta = TopicAssignment(
            topic_text="Test topic",
            buyer_stage=BuyerStage.BOFU,
            intent_type=IntentType.transactional,
        )
        data = json.loads(ta.model_dump_json())
        restored = TopicAssignment(**data)
        assert restored.buyer_stage == BuyerStage.BOFU
        assert restored.intent_type == IntentType.transactional


# ── TopicAssignmentMatrix ────────────────────────────────────────────────


class TestTopicAssignmentMatrix:
    def test_defaults(self):
        m = TopicAssignmentMatrix()
        assert m.version == 1
        assert m.assignments == []
        assert m.total_assignments == 0

    def test_with_assignments(self, sample_matrix):
        assert len(sample_matrix.assignments) == 2
        assert sample_matrix.total_relevant_cells == 2

    def test_roundtrip(self, sample_matrix):
        data = json.loads(sample_matrix.model_dump_json())
        restored = TopicAssignmentMatrix(**data)
        assert len(restored.assignments) == 2
        assert restored.assignments[0].topic_text == "Best expense management tools for startups"
        assert restored.assignments[1].audience_segment_type == AudienceSegmentType.team_group

    def test_distribution_dicts(self):
        m = TopicAssignmentMatrix(
            buyer_stage_distribution={"tofu": 5, "mofu": 3, "bofu": 2},
            intent_distribution={"informational": 6, "commercial": 4},
        )
        assert sum(m.buyer_stage_distribution.values()) == 10


# ── TopicDiscoveryManifest ───────────────────────────────────────────────


class TestTopicDiscoveryManifest:
    def test_defaults(self):
        m = TopicDiscoveryManifest()
        assert m.slug == ""
        assert m.status == TopicDiscoveryStatus.draft
        assert m.taxonomy_version == 0
        assert m.matrix_version == 0
        assert m.created_at  # auto-filled

    def test_roundtrip(self):
        m = TopicDiscoveryManifest(
            slug="test-co",
            effective_slug="test-co__main",
            company_name="Test Co",
            domain_name="test.com",
            taxonomy_version=2,
            matrix_version=1,
            status=TopicDiscoveryStatus.approved,
            source_results_written=["source_a", "source_b"],
        )
        data = json.loads(m.model_dump_json())
        restored = TopicDiscoveryManifest(**data)
        assert restored.effective_slug == "test-co__main"
        assert restored.taxonomy_version == 2
        assert len(restored.source_results_written) == 2


# ── TopicDiscoveryOutput ─────────────────────────────────────────────────


class TestTopicDiscoveryOutput:
    def test_defaults(self):
        o = TopicDiscoveryOutput()
        assert o.slug == ""
        assert o.status == TopicDiscoveryStatus.draft
        assert o.taxonomy is None
        assert o.matrix is None
        assert o.error is None

    def test_with_taxonomy_and_matrix(self, sample_taxonomy, sample_matrix):
        o = TopicDiscoveryOutput(
            slug="test-co",
            company_name="Test Co",
            taxonomy=sample_taxonomy,
            matrix=sample_matrix,
            taxonomy_version=1,
            matrix_version=1,
            status=TopicDiscoveryStatus.approved,
        )
        assert o.taxonomy.domain_name == "fintech"
        assert len(o.matrix.assignments) == 2

    def test_roundtrip(self, sample_taxonomy, sample_matrix):
        o = TopicDiscoveryOutput(
            slug="test-co",
            taxonomy=sample_taxonomy,
            matrix=sample_matrix,
        )
        data = json.loads(o.model_dump_json())
        restored = TopicDiscoveryOutput(**data)
        assert len(restored.taxonomy.root_nodes) == 2
        assert restored.matrix.version == 1

    def test_error_output(self):
        o = TopicDiscoveryOutput(
            slug="test-co",
            error="Missing company context",
            status=TopicDiscoveryStatus.draft,
        )
        assert o.error == "Missing company context"


# ── Cross-Model Integration ──────────────────────────────────────────────


# ── M6: ORM server_default + nullable alignment ────────────────────────


class TestM6OrmServerDefaults:
    """M6: ORM columns that map as non-nullable must have server_default + nullable=False."""

    def _get_column(self, model_cls, col_name):
        """Get the SA Column object from an ORM model."""
        return model_cls.__table__.columns[col_name]

    def test_taxonomy_tree_total_subdomains(self):
        from core.db.models.topic_discovery import TaxonomyTreeModel
        col = self._get_column(TaxonomyTreeModel, "total_subdomains")
        assert col.server_default is not None, "Missing server_default"
        assert col.nullable is False, "Must be non-nullable"

    def test_taxonomy_tree_max_depth(self):
        from core.db.models.topic_discovery import TaxonomyTreeModel
        col = self._get_column(TaxonomyTreeModel, "max_depth")
        assert col.server_default is not None
        assert col.nullable is False

    def test_subdomain_node_depth(self):
        from core.db.models.topic_discovery import SubdomainNodeModel
        col = self._get_column(SubdomainNodeModel, "depth")
        assert col.server_default is not None
        assert col.nullable is False

    def test_subdomain_node_is_manually_added(self):
        from core.db.models.topic_discovery import SubdomainNodeModel
        col = self._get_column(SubdomainNodeModel, "is_manually_added")
        assert col.server_default is not None
        assert col.nullable is False

    def test_subdomain_node_sort_order(self):
        from core.db.models.topic_discovery import SubdomainNodeModel
        col = self._get_column(SubdomainNodeModel, "sort_order")
        assert col.server_default is not None
        assert col.nullable is False

    def test_topic_assignment_matrix_version(self):
        from core.db.models.topic_discovery import TopicAssignmentModel
        col = self._get_column(TopicAssignmentModel, "matrix_version")
        assert col.server_default is not None
        assert col.nullable is False

    def test_topic_assignment_is_manually_added(self):
        from core.db.models.topic_discovery import TopicAssignmentModel
        col = self._get_column(TopicAssignmentModel, "is_manually_added")
        assert col.server_default is not None
        assert col.nullable is False

    def test_topic_discovery_taxonomy_version(self):
        from core.db.models.topic_discovery import TopicDiscoveryModel
        col = self._get_column(TopicDiscoveryModel, "taxonomy_version")
        assert col.server_default is not None
        assert col.nullable is False

    def test_topic_discovery_matrix_version(self):
        from core.db.models.topic_discovery import TopicDiscoveryModel
        col = self._get_column(TopicDiscoveryModel, "matrix_version")
        assert col.server_default is not None
        assert col.nullable is False


# ── Cross-Model Integration ──────────────────────────────────────────────


class TestCrossModelIntegration:
    """Verify models work together as the pipeline expects."""

    def test_source_result_candidates_match_subdomain_candidate(self):
        """SourceResult.candidates should be a list of SubdomainCandidate."""
        sr = SourceResult(
            source=TDSource.source_b,
            candidates=[
                SubdomainCandidate(name="topic1", source=TDSource.source_b),
                SubdomainCandidate(name="topic2", source=TDSource.source_b),
            ],
        )
        assert all(isinstance(c, SubdomainCandidate) for c in sr.candidates)
        assert all(c.source == TDSource.source_b for c in sr.candidates)

    def test_taxonomy_node_ids_are_unique(self, sample_taxonomy):
        """All node IDs in a taxonomy should be unique."""
        ids = set()

        def collect_ids(node: SubdomainNode):
            ids.add(node.id)
            for child in node.children:
                collect_ids(child)

        for root in sample_taxonomy.root_nodes:
            collect_ids(root)
        assert len(ids) == sample_taxonomy.total_subdomains

    def test_full_pipeline_output_serialization(
        self, sample_taxonomy, sample_matrix
    ):
        """Full output with all nested models should serialize cleanly."""
        coverage = CaptureRecaptureResult(
            pairwise_estimates={"a_b": 112.0},
            median_estimate=112.0,
            sample_coverage=0.94,
            observed_count=100,
        )
        manifest = TopicDiscoveryManifest(
            slug="test-co",
            company_name="Test Co",
            taxonomy_version=1,
            matrix_version=1,
        )
        output = TopicDiscoveryOutput(
            slug="test-co",
            company_name="Test Co",
            taxonomy=sample_taxonomy,
            matrix=sample_matrix,
            coverage=coverage,
            manifest=manifest,
            taxonomy_version=1,
            matrix_version=1,
            status=TopicDiscoveryStatus.approved,
            total_execution_time_s=45.2,
        )
        data = json.loads(output.model_dump_json())
        restored = TopicDiscoveryOutput(**data)
        assert restored.coverage.sample_coverage == 0.94
        assert restored.manifest.slug == "test-co"
        assert len(restored.taxonomy.root_nodes) == 2
