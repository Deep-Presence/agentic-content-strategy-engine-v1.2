"""Tests for DbTopicDiscoveryDataService — Postgres-backed TD read service."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.services.db_topic_discovery_data import DbTopicDiscoveryDataService
from core.services.topic_discovery_data import TopicDiscoveryDataServiceProtocol


def _mock_repos():
    """Create mock TD repositories."""
    td_repo = AsyncMock()
    taxonomy_repo = AsyncMock()
    assignment_repo = AsyncMock()
    return td_repo, taxonomy_repo, assignment_repo


@pytest.fixture
def svc(tmp_path: Path) -> DbTopicDiscoveryDataService:
    td_repo, taxonomy_repo, assignment_repo = _mock_repos()
    svc = DbTopicDiscoveryDataService(
        td_repo=td_repo,
        taxonomy_repo=taxonomy_repo,
        assignment_repo=assignment_repo,
        artifacts_root=tmp_path,
    )
    return svc


class TestDbTopicDiscoveryDataService:
    async def test_protocol_conformance(self, tmp_path):
        td_repo, taxonomy_repo, assignment_repo = _mock_repos()
        svc = DbTopicDiscoveryDataService(
            td_repo=td_repo,
            taxonomy_repo=taxonomy_repo,
            assignment_repo=assignment_repo,
            artifacts_root=tmp_path,
        )
        assert isinstance(svc, TopicDiscoveryDataServiceProtocol)

    async def test_get_discovery_summary(self, svc):
        from datetime import datetime, timezone

        row = MagicMock()
        row.taxonomy_version = 2
        row.matrix_version = 1
        row.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

        svc._td_repo.get_by_effective_slug = AsyncMock(return_value=row)

        result = await svc.get_discovery_summary("test-co")

        assert result is not None
        assert result["slug"] == "test-co"
        assert result["has_taxonomy"] is True
        assert result["taxonomy_version"] == 2
        assert result["has_matrix"] is True
        assert result["matrix_version"] == 1
        svc._td_repo.get_by_effective_slug.assert_called_once_with("test-co")

    async def test_get_discovery_summary_missing(self, svc):
        svc._td_repo.get_by_effective_slug = AsyncMock(return_value=None)

        result = await svc.get_discovery_summary("nonexistent")
        assert result is None

    async def test_get_taxonomy_delegates_to_json(self, svc, tmp_path):
        """get_taxonomy delegates to JSON service — verify no crash when missing."""
        result = await svc.get_taxonomy("nonexistent")
        assert result is None

    async def test_get_matrix_delegates_to_json(self, svc, tmp_path):
        """get_matrix delegates to JSON service — verify no crash when missing."""
        result = await svc.get_matrix("nonexistent")
        assert result is None

    async def test_list_assignments_empty(self, svc):
        svc._td_repo.get_by_effective_slug = AsyncMock(return_value=None)

        result = await svc.list_assignments("nonexistent")

        assert result["total"] == 0
        assert result["items"] == []

    async def test_list_assignments_with_data(self, svc):
        import uuid

        discovery = MagicMock()
        discovery.id = uuid.uuid4()
        svc._td_repo.get_by_effective_slug = AsyncMock(return_value=discovery)

        assignment = MagicMock()
        assignment.topic_text = "Best corporate cards"
        assignment.buyer_stage = MagicMock(value="tofu")
        assignment.intent_type = MagicMock(value="informational")
        assignment.audience_segment = "CFO"
        assignment.relevance = MagicMock(value="relevant")
        assignment.priority_score = 0.85
        assignment.status = MagicMock(value="not_started")

        svc._assignment_repo.list_paginated = AsyncMock(
            return_value=([assignment], 1)
        )

        result = await svc.list_assignments("test-co")

        assert result["total"] == 1
        assert len(result["items"]) == 1
        assert result["items"][0]["topic_text"] == "Best corporate cards"
        assert result["items"][0]["buyer_stage"] == "tofu"
        svc._assignment_repo.list_paginated.assert_called_once()

    async def test_list_assignments_with_filters(self, svc):
        import uuid

        discovery = MagicMock()
        discovery.id = uuid.uuid4()
        svc._td_repo.get_by_effective_slug = AsyncMock(return_value=discovery)
        svc._assignment_repo.list_paginated = AsyncMock(return_value=([], 0))

        result = await svc.list_assignments(
            "test-co", buyer_stage="tofu", intent_type="informational",
            page=2, page_size=25,
        )

        assert result["total"] == 0
        assert result["page"] == 2
        assert result["page_size"] == 25
        # Verify enum mapping was attempted
        svc._assignment_repo.list_paginated.assert_called_once()

    async def test_has_all_protocol_methods(self):
        expected = {"get_discovery_summary", "get_taxonomy", "get_matrix", "list_assignments"}
        for method in expected:
            assert hasattr(DbTopicDiscoveryDataService, method)
