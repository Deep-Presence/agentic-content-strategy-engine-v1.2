"""Tests for TopicDiscoveryRepository and related repositories.

Unit tests using mocked AsyncSession for new persistence methods.
Existing import/binding tests preserved.
"""
from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL", ""),
    reason="DATABASE_URL not set — skipping DB tests",
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _mock_session() -> AsyncMock:
    """Create a mock AsyncSession with execute chaining."""
    session = AsyncMock()
    session.flush = AsyncMock()
    return session


def _mock_execute_result(rows=None, scalar_value=None):
    """Create a mock execute result."""
    result = MagicMock()
    scalars = MagicMock()
    scalars.first.return_value = rows[0] if rows else None
    scalars.all.return_value = rows or []
    result.scalars.return_value = scalars
    result.scalar.return_value = scalar_value
    result.scalar_one.return_value = scalar_value if scalar_value is not None else 0
    result.rowcount = len(rows) if rows else 0
    return result


def _make_discovery(**overrides):
    """Create a mock TopicDiscoveryModel."""
    disc = MagicMock()
    disc.id = overrides.get("id", uuid.uuid4())
    disc.company_id = overrides.get("company_id", uuid.uuid4())
    disc.effective_slug = overrides.get("effective_slug", "test-co")
    disc.domain_name = overrides.get("domain_name", "example.com")
    disc.status = overrides.get("status", MagicMock(value="draft"))
    disc.taxonomy_version = overrides.get("taxonomy_version", 0)
    disc.matrix_version = overrides.get("matrix_version", 0)
    return disc


def _make_taxonomy(**overrides):
    """Create a mock TaxonomyTreeModel."""
    tax = MagicMock()
    tax.id = overrides.get("id", uuid.uuid4())
    tax.discovery_id = overrides.get("discovery_id", uuid.uuid4())
    tax.version = overrides.get("version", 1)
    tax.tree_json = overrides.get("tree_json", {"root_nodes": []})
    tax.status = overrides.get("status", MagicMock(value="draft"))
    return tax


# ── TopicDiscoveryRepository Tests ───────────────────────────────────────


class TestTopicDiscoveryRepositoryUpsert:
    """Tests for TopicDiscoveryRepository.upsert_discovery."""

    async def test_upsert_creates_new_when_not_exists(self):
        from core.topic_discovery.repository import TopicDiscoveryRepository

        session = _mock_session()
        session.execute.return_value = _mock_execute_result([])
        repo = TopicDiscoveryRepository(session)

        company_id = uuid.uuid4()
        result = await repo.upsert_discovery(
            company_id=company_id,
            effective_slug="test-co",
            domain_name="example.com",
        )

        session.add.assert_called_once()
        session.flush.assert_called_once()
        assert result is not None

    async def test_upsert_updates_existing(self):
        from core.db.enums import TDStatus
        from core.topic_discovery.repository import TopicDiscoveryRepository

        session = _mock_session()
        existing = _make_discovery()
        session.execute.return_value = _mock_execute_result([existing])
        repo = TopicDiscoveryRepository(session)

        run_id = uuid.uuid4()
        result = await repo.upsert_discovery(
            company_id=existing.company_id,
            effective_slug="test-co",
            pipeline_run_id=run_id,
            status=TDStatus.draft,
        )

        session.add.assert_not_called()
        session.flush.assert_called_once()
        assert result is existing


# ── TaxonomyTreeRepository Tests ────────────────────────────────────────


class TestTaxonomyTreeRepositoryUpsert:
    """Tests for TaxonomyTreeRepository.upsert_taxonomy."""

    async def test_upsert_creates_new_taxonomy(self):
        from core.topic_discovery.repository import TaxonomyTreeRepository

        session = _mock_session()
        session.execute.return_value = _mock_execute_result([])
        repo = TaxonomyTreeRepository(session)

        discovery_id = uuid.uuid4()
        tree_json = {"root_nodes": [{"name": "Cloud"}]}
        result = await repo.upsert_taxonomy(
            discovery_id=discovery_id,
            version=1,
            tree_json=tree_json,
            total_subdomains=5,
            max_depth=2,
        )

        session.add.assert_called_once()
        session.flush.assert_called_once()
        assert result is not None

    async def test_upsert_updates_existing_taxonomy(self):
        from core.topic_discovery.repository import TaxonomyTreeRepository

        session = _mock_session()
        existing = _make_taxonomy()
        session.execute.return_value = _mock_execute_result([existing])
        repo = TaxonomyTreeRepository(session)

        new_tree_json = {"root_nodes": [{"name": "Updated"}]}
        result = await repo.upsert_taxonomy(
            discovery_id=existing.discovery_id,
            version=existing.version,
            tree_json=new_tree_json,
            total_subdomains=10,
        )

        session.add.assert_not_called()
        session.flush.assert_called_once()
        assert result is existing
        assert existing.tree_json == new_tree_json
        assert existing.total_subdomains == 10


# ── SubdomainNodeRepository Tests ───────────────────────────────────────


class TestSubdomainNodeRepositoryDelete:
    """Tests for SubdomainNodeRepository.delete_by_taxonomy."""

    async def test_delete_by_taxonomy_returns_count(self):
        from core.topic_discovery.repository import SubdomainNodeRepository

        session = _mock_session()
        result = MagicMock()
        result.rowcount = 5
        session.execute.return_value = result
        repo = SubdomainNodeRepository(session)

        count = await repo.delete_by_taxonomy(uuid.uuid4())

        session.execute.assert_called_once()
        session.flush.assert_called_once()
        assert count == 5

    async def test_delete_by_taxonomy_returns_zero_when_empty(self):
        from core.topic_discovery.repository import SubdomainNodeRepository

        session = _mock_session()
        result = MagicMock()
        result.rowcount = 0
        session.execute.return_value = result
        repo = SubdomainNodeRepository(session)

        count = await repo.delete_by_taxonomy(uuid.uuid4())
        assert count == 0


# ── TopicAssignmentRepository Tests ──────────────────────────────────────


class TestTopicAssignmentRepositoryExtensions:
    """Tests for new TopicAssignmentRepository methods."""

    async def test_delete_by_discovery_returns_count(self):
        from core.topic_discovery.repository import TopicAssignmentRepository

        session = _mock_session()
        result = MagicMock()
        result.rowcount = 10
        session.execute.return_value = result
        repo = TopicAssignmentRepository(session)

        count = await repo.delete_by_discovery(uuid.uuid4())
        assert count == 10

    async def test_delete_by_discovery_scoped_to_version(self):
        from core.topic_discovery.repository import TopicAssignmentRepository

        session = _mock_session()
        result = MagicMock()
        result.rowcount = 3
        session.execute.return_value = result
        repo = TopicAssignmentRepository(session)

        count = await repo.delete_by_discovery(uuid.uuid4(), matrix_version=2)
        assert count == 3

    async def test_list_paginated_returns_items_and_total(self):
        from core.topic_discovery.repository import TopicAssignmentRepository

        session = _mock_session()
        assignment = MagicMock()
        assignment.topic_text = "Best corporate cards"

        count_result = MagicMock()
        count_result.scalar.return_value = 1
        items_result = _mock_execute_result([assignment])

        session.execute.side_effect = [count_result, items_result]
        repo = TopicAssignmentRepository(session)

        items, total = await repo.list_paginated(uuid.uuid4())
        assert total == 1
        assert len(items) == 1

    async def test_list_paginated_with_filters(self):
        from core.db.enums import BuyerStage, IntentType
        from core.topic_discovery.repository import TopicAssignmentRepository

        session = _mock_session()
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        items_result = _mock_execute_result([])

        session.execute.side_effect = [count_result, items_result]
        repo = TopicAssignmentRepository(session)

        items, total = await repo.list_paginated(
            uuid.uuid4(),
            buyer_stage=BuyerStage.tofu,
            intent_type=IntentType.informational,
            page=2,
            page_size=25,
        )
        assert total == 0
        assert len(items) == 0

    async def test_get_stats_returns_aggregates(self):
        from core.topic_discovery.repository import TopicAssignmentRepository

        session = _mock_session()
        bs_result = MagicMock()
        bs_result.all.return_value = [("tofu", 5), ("mofu", 3)]
        it_result = MagicMock()
        it_result.all.return_value = [("informational", 6), ("commercial", 2)]
        rel_result = MagicMock()
        rel_result.all.return_value = [("relevant", 7), ("marginal", 1)]
        st_result = MagicMock()
        st_result.all.return_value = [("not_started", 8)]
        total_result = MagicMock()
        total_result.scalar.return_value = 8

        session.execute.side_effect = [
            total_result, bs_result, it_result, rel_result, st_result,
        ]
        repo = TopicAssignmentRepository(session)

        stats = await repo.get_stats(uuid.uuid4())
        assert stats["total"] == 8
        assert stats["by_buyer_stage"]["tofu"] == 5
        assert stats["by_intent_type"]["informational"] == 6
        assert stats["by_relevance"]["relevant"] == 7
        assert stats["by_status"]["not_started"] == 8


# ── Import/Binding Tests (preserved) ────────────────────────────────────


def test_repository_imports():
    """Verify all repository classes can be imported."""
    from core.topic_discovery.repository import (
        TopicDiscoveryRepository,
        TaxonomyTreeRepository,
        SubdomainNodeRepository,
        TopicAssignmentRepository,
    )
    assert TopicDiscoveryRepository.model_class is not None
    assert TaxonomyTreeRepository.model_class is not None
    assert SubdomainNodeRepository.model_class is not None
    assert TopicAssignmentRepository.model_class is not None


def test_repository_model_class_binding():
    """Each repo must bind to the correct ORM model."""
    from core.db.models.topic_discovery import (
        TopicDiscoveryModel,
        TaxonomyTreeModel,
        SubdomainNodeModel,
        TopicAssignmentModel,
    )
    from core.topic_discovery.repository import (
        TopicDiscoveryRepository,
        TaxonomyTreeRepository,
        SubdomainNodeRepository,
        TopicAssignmentRepository,
    )
    assert TopicDiscoveryRepository.model_class is TopicDiscoveryModel
    assert TaxonomyTreeRepository.model_class is TaxonomyTreeModel
    assert SubdomainNodeRepository.model_class is SubdomainNodeModel
    assert TopicAssignmentRepository.model_class is TopicAssignmentModel
