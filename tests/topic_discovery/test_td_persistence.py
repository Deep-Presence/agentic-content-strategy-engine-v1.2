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
