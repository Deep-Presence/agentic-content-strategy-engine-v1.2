"""Tests for Topic Discovery persistence hooks.

Unit tests with mocked session factories, matching the pattern
in ``tests/research/test_persistence.py``.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.topic_discovery.persistence import (
    _flatten_taxonomy_tree,
    _should_persist,
    persist_td_assignments,
    persist_td_discovery,
    persist_td_persona_affinity,
    persist_td_scoring_metadata,
    persist_td_source_results,
    persist_td_status_update,
    persist_td_taxonomy,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_session_factory():
    """Create a mock async_sessionmaker that yields a mock session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()

    # Make session work as async context manager
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock()
    factory.return_value = ctx
    return factory, session


def _make_subdomain_node(
    name: str,
    node_id: str | None = None,
    children: list | None = None,
    depth: int = 0,
):
    """Create a mock SubdomainNode (Pydantic model)."""
    return SimpleNamespace(
        id=node_id or str(uuid.uuid4()),
        name=name,
        description=f"Desc for {name}",
        depth=depth,
        source_provenance={"source_a": True},
        confidence=0.8,
        is_manually_added=False,
        sort_order=0,
        children=children or [],
        metadata={"key": "val"},
    )


def _make_taxonomy(root_nodes=None, version=1):
    """Create a mock TaxonomyTree (Pydantic model)."""
    return SimpleNamespace(
        id=str(uuid.uuid4()),
        root_nodes=root_nodes or [],
        total_subdomains=len(root_nodes) if root_nodes else 0,
        max_depth=1,
        coverage_score=0.85,
        chao1_estimate=10.0,
        capture_recapture_est={"median": 12},
        version=version,
        model_dump=MagicMock(return_value={"root_nodes": []}),
    )


def _make_assignment(topic_text="Best corporate cards"):
    """Create a mock TopicAssignment (Pydantic model)."""
    return SimpleNamespace(
        id=str(uuid.uuid4()),
        subdomain_id=str(uuid.uuid4()),
        subdomain_name="Cloud",
        topic_text=topic_text,
        buyer_stage=SimpleNamespace(value="tofu"),
        intent_type=SimpleNamespace(value="informational"),
        audience_segment="CFO",
        audience_segment_type=SimpleNamespace(value="individual_persona"),
        relevance=SimpleNamespace(value="relevant"),
        priority_score=0.85,
        priority_factors={"factor_a": 0.5},
        status=SimpleNamespace(value="not_started"),
        is_manually_added=False,
        metadata={"key": "val"},
    )


def _make_matrix(assignments=None, version=1):
    """Create a mock TopicAssignmentMatrix (Pydantic model)."""
    return SimpleNamespace(
        id=str(uuid.uuid4()),
        version=version,
        assignments=assignments or [],
        total_assignments=len(assignments) if assignments else 0,
    )


# ── Guard Tests ──────────────────────────────────────────────────────────


class TestShouldPersist:
    def test_returns_true_when_all_present(self):
        assert _should_persist(MagicMock(), uuid.uuid4(), uuid.uuid4()) is True

    def test_returns_false_when_session_factory_none(self):
        assert _should_persist(None, uuid.uuid4(), uuid.uuid4()) is False

    def test_returns_false_when_run_id_none(self):
        assert _should_persist(MagicMock(), None, uuid.uuid4()) is False

    def test_returns_false_when_company_id_none(self):
        assert _should_persist(MagicMock(), uuid.uuid4(), None) is False


# ── Flatten Taxonomy Tree Tests ──────────────────────────────────────────


class TestFlattenTaxonomyTree:
    def test_empty_tree(self):
        result = _flatten_taxonomy_tree([], uuid.uuid4())
        assert result == []

    def test_single_root_node(self):
        node = _make_subdomain_node("Cloud")
        tax_id = uuid.uuid4()
        result = _flatten_taxonomy_tree([node], tax_id)

        assert len(result) == 1
        assert result[0]["name"] == "Cloud"
        assert result[0]["taxonomy_id"] == tax_id
        assert result[0]["parent_id"] is None
        assert result[0]["id"] == uuid.UUID(node.id)

    def test_nested_tree_parent_before_child(self):
        child = _make_subdomain_node("Sub-Cloud", depth=1)
        parent = _make_subdomain_node("Cloud", children=[child], depth=0)
        tax_id = uuid.uuid4()

        result = _flatten_taxonomy_tree([parent], tax_id)

        assert len(result) == 2
        # Parent comes first
        assert result[0]["name"] == "Cloud"
        assert result[0]["parent_id"] is None
        # Child comes second with correct parent_id
        assert result[1]["name"] == "Sub-Cloud"
        assert result[1]["parent_id"] == uuid.UUID(parent.id)

    def test_preserves_existing_uuids(self):
        known_id = str(uuid.uuid4())
        node = _make_subdomain_node("Cloud", node_id=known_id)
        result = _flatten_taxonomy_tree([node], uuid.uuid4())

        assert result[0]["id"] == uuid.UUID(known_id)

    def test_handles_invalid_uuid_gracefully(self):
        node = _make_subdomain_node("Cloud", node_id="not-a-uuid")
        result = _flatten_taxonomy_tree([node], uuid.uuid4())

        # Should get a valid uuid4 fallback
        assert isinstance(result[0]["id"], uuid.UUID)

    def test_deep_nesting(self):
        leaf = _make_subdomain_node("Leaf", depth=2)
        mid = _make_subdomain_node("Mid", children=[leaf], depth=1)
        root = _make_subdomain_node("Root", children=[mid], depth=0)

        result = _flatten_taxonomy_tree([root], uuid.uuid4())
        assert len(result) == 3
        assert [r["name"] for r in result] == ["Root", "Mid", "Leaf"]
        assert result[2]["parent_id"] == uuid.UUID(mid.id)


# ── Persist TD Discovery Tests ───────────────────────────────────────────


class TestPersistTDDiscovery:
    async def test_happy_path_returns_uuid(self):
        sf, session = _make_session_factory()
        disc_id = uuid.uuid4()

        mock_disc = MagicMock()
        mock_disc.id = disc_id

        with patch(
            "core.db.repositories.topic_discovery_repo.TopicDiscoveryRepository"
        ) as MockRepo:
            MockRepo.return_value.upsert_discovery = AsyncMock(
                return_value=mock_disc
            )
            result = await persist_td_discovery(
                sf, uuid.uuid4(), uuid.uuid4(),
                "test-co", "example.com",
            )

        assert result == disc_id
        session.commit.assert_called_once()

    async def test_noop_when_session_factory_none(self):
        result = await persist_td_discovery(
            None, uuid.uuid4(), uuid.uuid4(),
            "test-co", "example.com",
        )
        assert result is None

    async def test_exception_returns_none(self):
        sf, session = _make_session_factory()

        with patch(
            "core.db.repositories.topic_discovery_repo.TopicDiscoveryRepository"
        ) as MockRepo:
            MockRepo.return_value.upsert_discovery = AsyncMock(
                side_effect=RuntimeError("DB down")
            )
            result = await persist_td_discovery(
                sf, uuid.uuid4(), uuid.uuid4(),
                "test-co", "example.com",
            )

        assert result is None


# ── Persist TD Taxonomy Tests ────────────────────────────────────────────


class TestPersistTDTaxonomy:
    async def test_happy_path_returns_taxonomy_id(self):
        sf, session = _make_session_factory()
        disc_id = uuid.uuid4()
        tax_id = uuid.uuid4()

        mock_tax = MagicMock()
        mock_tax.id = tax_id

        taxonomy = _make_taxonomy(
            root_nodes=[_make_subdomain_node("Cloud")],
        )

        with patch(
            "core.db.repositories.topic_discovery_repo.TaxonomyTreeRepository"
        ) as MockTaxRepo, patch(
            "core.db.repositories.topic_discovery_repo.SubdomainNodeRepository"
        ) as MockNodeRepo, patch(
            "core.db.repositories.topic_discovery_repo.TopicDiscoveryRepository"
        ) as MockDiscRepo:
            MockTaxRepo.return_value.upsert_taxonomy = AsyncMock(
                return_value=mock_tax
            )
            MockNodeRepo.return_value.delete_by_taxonomy = AsyncMock(return_value=0)
            MockNodeRepo.return_value.bulk_create = AsyncMock(return_value=[])
            MockDiscRepo.return_value.update_versions = AsyncMock(return_value=None)

            result = await persist_td_taxonomy(
                sf, uuid.uuid4(), uuid.uuid4(),
                disc_id, taxonomy, 1,
            )

        assert result == tax_id
        session.commit.assert_called_once()

    async def test_noop_when_discovery_id_none(self):
        sf, _ = _make_session_factory()
        result = await persist_td_taxonomy(
            sf, uuid.uuid4(), uuid.uuid4(),
            None, _make_taxonomy(), 1,
        )
        assert result is None

    async def test_exception_returns_none(self):
        sf, session = _make_session_factory()

        with patch(
            "core.db.repositories.topic_discovery_repo.TaxonomyTreeRepository"
        ) as MockTaxRepo:
            MockTaxRepo.return_value.upsert_taxonomy = AsyncMock(
                side_effect=RuntimeError("DB down")
            )
            result = await persist_td_taxonomy(
                sf, uuid.uuid4(), uuid.uuid4(),
                uuid.uuid4(), _make_taxonomy(), 1,
            )
        assert result is None


# ── Persist TD Assignments Tests ─────────────────────────────────────────


class TestPersistTDAssignments:
    async def test_happy_path(self):
        sf, session = _make_session_factory()

        matrix = _make_matrix(
            assignments=[_make_assignment(), _make_assignment("Topic 2")],
        )

        with patch(
            "core.db.repositories.topic_discovery_repo.TopicAssignmentRepository"
        ) as MockAssignRepo, patch(
            "core.db.repositories.topic_discovery_repo.TopicDiscoveryRepository"
        ) as MockDiscRepo:
            MockAssignRepo.return_value.delete_by_discovery = AsyncMock(return_value=0)
            MockAssignRepo.return_value.bulk_create = AsyncMock(return_value=[])
            MockDiscRepo.return_value.update_versions = AsyncMock(return_value=None)

            await persist_td_assignments(
                sf, uuid.uuid4(), uuid.uuid4(),
                uuid.uuid4(), matrix, 1,
            )

        session.commit.assert_called_once()

    async def test_noop_when_discovery_id_none(self):
        sf, session = _make_session_factory()
        await persist_td_assignments(
            sf, uuid.uuid4(), uuid.uuid4(),
            None, _make_matrix(), 1,
        )
        session.commit.assert_not_called()

    async def test_exception_does_not_crash(self):
        sf, session = _make_session_factory()

        with patch(
            "core.db.repositories.topic_discovery_repo.TopicAssignmentRepository"
        ) as MockAssignRepo:
            MockAssignRepo.return_value.delete_by_discovery = AsyncMock(
                side_effect=RuntimeError("DB down")
            )
            # Should NOT raise
            await persist_td_assignments(
                sf, uuid.uuid4(), uuid.uuid4(),
                uuid.uuid4(), _make_matrix(assignments=[_make_assignment()]), 1,
            )


# ── Persist TD Status Update Tests ───────────────────────────────────────


class TestPersistTDStatusUpdate:
    async def test_happy_path(self):
        sf, session = _make_session_factory()

        with patch(
            "core.db.repositories.topic_discovery_repo.TopicDiscoveryRepository"
        ) as MockRepo:
            MockRepo.return_value.update_status = AsyncMock(return_value=None)

            await persist_td_status_update(
                sf, uuid.uuid4(), "approved",
            )

        session.commit.assert_called_once()

    async def test_noop_when_discovery_id_none(self):
        sf, session = _make_session_factory()
        await persist_td_status_update(sf, None, "approved")
        session.commit.assert_not_called()

    async def test_exception_does_not_crash(self):
        sf, session = _make_session_factory()

        with patch(
            "core.db.repositories.topic_discovery_repo.TopicDiscoveryRepository"
        ) as MockRepo:
            MockRepo.return_value.update_status = AsyncMock(
                side_effect=RuntimeError("DB down")
            )
            await persist_td_status_update(sf, uuid.uuid4(), "approved")


# ── Enum Mapping Tests ───────────────────────────────────────────────────


class TestEnumMapping:
    """Verify Pydantic enum .value strings match DB enum members."""

    def test_buyer_stage_values_match(self):
        from core.db.enums import BuyerStage as DBBuyerStage
        from core.models.topic_discovery import BuyerStage as PydanticBuyerStage

        for member in PydanticBuyerStage:
            assert DBBuyerStage(member.value), f"No DB match for {member}"

    def test_intent_type_values_match(self):
        from core.db.enums import IntentType as DBIntentType
        from core.models.topic_discovery import IntentType as PydanticIntentType

        for member in PydanticIntentType:
            assert DBIntentType(member.value), f"No DB match for {member}"

    def test_relevance_cell_values_match(self):
        from core.db.enums import RelevanceCell as DBRelevanceCell
        from core.models.topic_discovery import RelevanceCell as PydanticRelevanceCell

        for member in PydanticRelevanceCell:
            assert DBRelevanceCell(member.value), f"No DB match for {member}"

    def test_assignment_status_values_match(self):
        from core.db.enums import TopicAssignmentStatus as DBStatus
        from core.models.topic_discovery import TopicAssignmentStatus as PydanticStatus

        for member in PydanticStatus:
            assert DBStatus(member.value), f"No DB match for {member}"

    def test_audience_segment_type_values_match(self):
        from core.db.enums import AudienceSegmentType as DBType
        from core.models.topic_discovery import AudienceSegmentType as PydanticType

        for member in PydanticType:
            assert DBType(member.value), f"No DB match for {member}"

    def test_td_status_discovery_complete_exists(self):
        from core.db.enums import TDStatus

        assert TDStatus("discovery_complete"), "discovery_complete missing from TDStatus"


# ── Flatten Taxonomy Tree New Fields Tests ─────────────────────────────


class TestFlattenTaxonomyTreeNewFields:
    """Verify _flatten_taxonomy_tree includes priority_score, priority_factors,
    persona_affinity_json, expansion_status."""

    def test_includes_priority_score(self):
        node = _make_subdomain_node("Cloud")
        node.priority_score = 0.92
        result = _flatten_taxonomy_tree([node], uuid.uuid4())

        assert result[0]["priority_score"] == 0.92

    def test_includes_priority_factors(self):
        node = _make_subdomain_node("Cloud")
        node.priority_factors = {"strategic_centrality": 0.8, "citation_opp": 0.7}
        result = _flatten_taxonomy_tree([node], uuid.uuid4())

        assert result[0]["priority_factors"] == {
            "strategic_centrality": 0.8,
            "citation_opp": 0.7,
        }

    def test_includes_persona_affinity_json(self):
        node = _make_subdomain_node("Cloud")
        node.persona_affinity = {"cfo": 0.9, "cto": 0.6}
        result = _flatten_taxonomy_tree([node], uuid.uuid4())

        assert result[0]["persona_affinity_json"] == {"cfo": 0.9, "cto": 0.6}

    def test_persona_affinity_none_when_not_dict(self):
        node = _make_subdomain_node("Cloud")
        node.persona_affinity = "not-a-dict"
        result = _flatten_taxonomy_tree([node], uuid.uuid4())

        assert result[0]["persona_affinity_json"] is None

    def test_includes_expansion_status(self):
        node = _make_subdomain_node("Cloud")
        node.expansion_status = "expanded"
        result = _flatten_taxonomy_tree([node], uuid.uuid4())

        assert result[0]["expansion_status"] == "expanded"

    def test_defaults_when_attrs_missing(self):
        """Nodes without the new attrs should get safe defaults."""
        node = SimpleNamespace(
            id=str(uuid.uuid4()),
            name="Bare",
            children=[],
        )
        result = _flatten_taxonomy_tree([node], uuid.uuid4())

        assert result[0]["priority_score"] == 0.0
        assert result[0]["priority_factors"] is None
        assert result[0]["persona_affinity_json"] is None
        assert result[0]["expansion_status"] == "not_expanded"

    def test_nested_nodes_carry_new_fields(self):
        child = _make_subdomain_node("Sub", depth=1)
        child.priority_score = 0.5
        child.expansion_status = "pending"
        parent = _make_subdomain_node("Root", children=[child], depth=0)
        parent.priority_score = 0.9

        result = _flatten_taxonomy_tree([parent], uuid.uuid4())

        assert result[0]["priority_score"] == 0.9
        assert result[1]["priority_score"] == 0.5
        assert result[1]["expansion_status"] == "pending"


# ── Persist TD Source Results Tests ─────────────────────────────────────


def _make_source_result(source="source_a", num_candidates=3):
    """Create a mock SourceResult (Pydantic model)."""
    candidates = [
        SimpleNamespace(
            model_dump=MagicMock(return_value={"text": f"candidate_{i}"}),
        )
        for i in range(num_candidates)
    ]
    return SimpleNamespace(
        source=SimpleNamespace(value=source),
        candidates=candidates,
        total_rounds=2,
        singletons=1,
        doubletons=0,
        chao1_estimate=5.0,
        source_sample_coverage=0.8,
        execution_time_s=1.5,
        error=None,
    )


class TestPersistTDSourceResults:
    async def test_happy_path(self):
        sf, session = _make_session_factory()

        source_results = [
            _make_source_result("source_a", 3),
            _make_source_result("source_b", 2),
        ]

        with patch(
            "core.db.repositories.topic_discovery_repo.SourceResultRepository"
        ) as MockRepo:
            MockRepo.return_value.delete_by_discovery = AsyncMock(return_value=0)
            MockRepo.return_value.bulk_create = AsyncMock(return_value=[])

            await persist_td_source_results(
                sf, uuid.uuid4(), uuid.uuid4(),
                uuid.uuid4(), source_results, 1,
            )

        session.commit.assert_called_once()

    async def test_noop_when_session_factory_none(self):
        await persist_td_source_results(
            None, uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), [_make_source_result()], 1,
        )

    async def test_noop_when_discovery_id_none(self):
        sf, session = _make_session_factory()
        await persist_td_source_results(
            sf, uuid.uuid4(), uuid.uuid4(),
            None, [_make_source_result()], 1,
        )
        session.commit.assert_not_called()

    async def test_noop_when_empty_results(self):
        sf, session = _make_session_factory()
        await persist_td_source_results(
            sf, uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), [], 1,
        )
        session.commit.assert_not_called()

    async def test_exception_does_not_crash(self):
        sf, session = _make_session_factory()

        with patch(
            "core.db.repositories.topic_discovery_repo.SourceResultRepository"
        ) as MockRepo:
            MockRepo.return_value.delete_by_discovery = AsyncMock(
                side_effect=RuntimeError("DB down")
            )
            await persist_td_source_results(
                sf, uuid.uuid4(), uuid.uuid4(),
                uuid.uuid4(), [_make_source_result()], 1,
            )


# ── Persist TD Persona Affinity Tests ──────────────────────────────────


def _make_persona_affinity_index():
    """Create a mock PersonaAffinityIndex (Pydantic model)."""
    sub_id = str(uuid.uuid4())
    return SimpleNamespace(
        persona_entries={
            "persona-cfo": [
                SimpleNamespace(
                    subdomain_id=sub_id,
                    subdomain_name="Cloud",
                    affinity_score=0.9,
                    provenance="llm",
                    pain_points=["budget constraints"],
                ),
                SimpleNamespace(
                    subdomain_id=str(uuid.uuid4()),
                    subdomain_name="Security",
                    affinity_score=0.7,
                    provenance="heuristic",
                    pain_points=None,
                ),
            ],
            "persona-cto": [
                SimpleNamespace(
                    subdomain_id=sub_id,
                    subdomain_name="Cloud",
                    affinity_score=0.95,
                    provenance="llm",
                    pain_points=["scalability"],
                ),
            ],
        }
    )


class TestPersistTDPersonaAffinity:
    async def test_happy_path(self):
        sf, session = _make_session_factory()

        with patch(
            "core.db.repositories.topic_discovery_repo.PersonaAffinityRepository"
        ) as MockRepo:
            MockRepo.return_value.delete_by_discovery = AsyncMock(return_value=0)
            MockRepo.return_value.bulk_create = AsyncMock(return_value=[])

            await persist_td_persona_affinity(
                sf, uuid.uuid4(), uuid.uuid4(),
                uuid.uuid4(), _make_persona_affinity_index(), 1,
            )

        session.commit.assert_called_once()

    async def test_noop_when_session_factory_none(self):
        await persist_td_persona_affinity(
            None, uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), _make_persona_affinity_index(), 1,
        )

    async def test_noop_when_discovery_id_none(self):
        sf, session = _make_session_factory()
        await persist_td_persona_affinity(
            sf, uuid.uuid4(), uuid.uuid4(),
            None, _make_persona_affinity_index(), 1,
        )
        session.commit.assert_not_called()

    async def test_noop_when_affinity_index_none(self):
        sf, session = _make_session_factory()
        await persist_td_persona_affinity(
            sf, uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), None, 1,
        )
        session.commit.assert_not_called()

    async def test_exception_does_not_crash(self):
        sf, session = _make_session_factory()

        with patch(
            "core.db.repositories.topic_discovery_repo.PersonaAffinityRepository"
        ) as MockRepo:
            MockRepo.return_value.delete_by_discovery = AsyncMock(
                side_effect=RuntimeError("DB down")
            )
            await persist_td_persona_affinity(
                sf, uuid.uuid4(), uuid.uuid4(),
                uuid.uuid4(), _make_persona_affinity_index(), 1,
            )


# ── Persist TD Scoring Metadata Tests ──────────────────────────────────


class TestPersistTDScoringMetadata:
    async def test_happy_path(self):
        sf, session = _make_session_factory()

        with patch(
            "core.db.repositories.topic_discovery_repo.TopicDiscoveryRepository"
        ) as MockRepo:
            MockRepo.return_value.update_versions = AsyncMock(return_value=None)

            await persist_td_scoring_metadata(
                sf, uuid.uuid4(), 2, 1,
            )

        session.commit.assert_called_once()

    async def test_noop_when_session_factory_none(self):
        await persist_td_scoring_metadata(None, uuid.uuid4(), 1, 1)

    async def test_noop_when_discovery_id_none(self):
        sf, session = _make_session_factory()
        await persist_td_scoring_metadata(sf, None, 1, 1)
        session.commit.assert_not_called()

    async def test_exception_does_not_crash(self):
        sf, session = _make_session_factory()

        with patch(
            "core.db.repositories.topic_discovery_repo.TopicDiscoveryRepository"
        ) as MockRepo:
            MockRepo.return_value.update_versions = AsyncMock(
                side_effect=RuntimeError("DB down")
            )
            await persist_td_scoring_metadata(
                sf, uuid.uuid4(), 1, 1,
            )


# ── Persist TD Assignments New Fields Tests ────────────────────────────


class TestPersistTDAssignmentsNewFields:
    """Verify persist_td_assignments maps persona/subdomain fields and FK."""

    async def test_subdomain_node_id_linked_via_uuid(self):
        sf, session = _make_session_factory()
        sub_uuid = str(uuid.uuid4())

        assignment = _make_assignment()
        assignment.subdomain_id = sub_uuid
        matrix = _make_matrix(assignments=[assignment])

        created_models = []

        with patch(
            "core.db.repositories.topic_discovery_repo.TopicAssignmentRepository"
        ) as MockAssignRepo, patch(
            "core.db.repositories.topic_discovery_repo.TopicDiscoveryRepository"
        ) as MockDiscRepo:
            MockAssignRepo.return_value.delete_by_discovery = AsyncMock(return_value=0)
            MockAssignRepo.return_value.bulk_create = AsyncMock(
                side_effect=lambda models: created_models.extend(models) or models
            )
            MockDiscRepo.return_value.update_versions = AsyncMock(return_value=None)

            await persist_td_assignments(
                sf, uuid.uuid4(), uuid.uuid4(),
                uuid.uuid4(), matrix, 1,
            )

        assert len(created_models) == 1
        assert created_models[0].subdomain_node_id == uuid.UUID(sub_uuid)

    async def test_persona_fields_mapped(self):
        sf, session = _make_session_factory()

        assignment = _make_assignment()
        assignment.persona_id = "persona-cfo"
        assignment.persona_name = "Chief Financial Officer"
        matrix = _make_matrix(assignments=[assignment])

        created_models = []

        with patch(
            "core.db.repositories.topic_discovery_repo.TopicAssignmentRepository"
        ) as MockAssignRepo, patch(
            "core.db.repositories.topic_discovery_repo.TopicDiscoveryRepository"
        ) as MockDiscRepo:
            MockAssignRepo.return_value.delete_by_discovery = AsyncMock(return_value=0)
            MockAssignRepo.return_value.bulk_create = AsyncMock(
                side_effect=lambda models: created_models.extend(models) or models
            )
            MockDiscRepo.return_value.update_versions = AsyncMock(return_value=None)

            await persist_td_assignments(
                sf, uuid.uuid4(), uuid.uuid4(),
                uuid.uuid4(), matrix, 1,
            )

        assert created_models[0].persona_id == "persona-cfo"
        assert created_models[0].persona_name == "Chief Financial Officer"

    async def test_subdomain_display_fields_mapped(self):
        sf, session = _make_session_factory()

        assignment = _make_assignment()
        assignment.subdomain_name = "Cloud Infrastructure"
        raw_sub_id = str(uuid.uuid4())
        assignment.subdomain_id = raw_sub_id
        matrix = _make_matrix(assignments=[assignment])

        created_models = []

        with patch(
            "core.db.repositories.topic_discovery_repo.TopicAssignmentRepository"
        ) as MockAssignRepo, patch(
            "core.db.repositories.topic_discovery_repo.TopicDiscoveryRepository"
        ) as MockDiscRepo:
            MockAssignRepo.return_value.delete_by_discovery = AsyncMock(return_value=0)
            MockAssignRepo.return_value.bulk_create = AsyncMock(
                side_effect=lambda models: created_models.extend(models) or models
            )
            MockDiscRepo.return_value.update_versions = AsyncMock(return_value=None)

            await persist_td_assignments(
                sf, uuid.uuid4(), uuid.uuid4(),
                uuid.uuid4(), matrix, 1,
            )

        assert created_models[0].subdomain_id_text == raw_sub_id
        assert created_models[0].subdomain_name == "Cloud Infrastructure"

    async def test_invalid_subdomain_id_falls_back_to_none(self):
        sf, session = _make_session_factory()

        assignment = _make_assignment()
        assignment.subdomain_id = "not-a-uuid"
        matrix = _make_matrix(assignments=[assignment])

        created_models = []

        with patch(
            "core.db.repositories.topic_discovery_repo.TopicAssignmentRepository"
        ) as MockAssignRepo, patch(
            "core.db.repositories.topic_discovery_repo.TopicDiscoveryRepository"
        ) as MockDiscRepo:
            MockAssignRepo.return_value.delete_by_discovery = AsyncMock(return_value=0)
            MockAssignRepo.return_value.bulk_create = AsyncMock(
                side_effect=lambda models: created_models.extend(models) or models
            )
            MockDiscRepo.return_value.update_versions = AsyncMock(return_value=None)

            await persist_td_assignments(
                sf, uuid.uuid4(), uuid.uuid4(),
                uuid.uuid4(), matrix, 1,
            )

        assert created_models[0].subdomain_node_id is None
        assert created_models[0].subdomain_id_text == "not-a-uuid"


# ── Persist TD Discovery Manifest Tests ────────────────────────────────


class TestPersistTDDiscoveryManifest:
    async def test_manifest_json_stored(self):
        sf, session = _make_session_factory()
        disc_id = uuid.uuid4()

        mock_disc = MagicMock()
        mock_disc.id = disc_id
        mock_disc.manifest_json = None

        with patch(
            "core.db.repositories.topic_discovery_repo.TopicDiscoveryRepository"
        ) as MockRepo:
            MockRepo.return_value.upsert_discovery = AsyncMock(
                return_value=mock_disc
            )
            result = await persist_td_discovery(
                sf, uuid.uuid4(), uuid.uuid4(),
                "test-co", "example.com",
                manifest_json={"expanded_subdomain_ids": ["abc"]},
            )

        assert result == disc_id
        assert mock_disc.manifest_json == {"expanded_subdomain_ids": ["abc"]}
        session.flush.assert_called_once()
        session.commit.assert_called_once()
