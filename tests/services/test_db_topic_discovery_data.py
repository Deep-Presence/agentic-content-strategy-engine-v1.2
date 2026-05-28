"""Tests for DbTopicDiscoveryDataService — Postgres-backed TD read service."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.services.db_topic_discovery_data import DbTopicDiscoveryDataService
from core.services.topic_discovery_data import TopicDiscoveryDataServiceProtocol


def _mock_repos():
    """Create mock TD repositories (all 6)."""
    td_repo = AsyncMock()
    taxonomy_repo = AsyncMock()
    assignment_repo = AsyncMock()
    node_repo = AsyncMock()
    source_result_repo = AsyncMock()
    persona_affinity_repo = AsyncMock()
    return td_repo, taxonomy_repo, assignment_repo, node_repo, source_result_repo, persona_affinity_repo


@pytest.fixture
def svc(tmp_path: Path) -> DbTopicDiscoveryDataService:
    td_repo, taxonomy_repo, assignment_repo, node_repo, sr_repo, pa_repo = _mock_repos()
    svc = DbTopicDiscoveryDataService(
        td_repo=td_repo,
        taxonomy_repo=taxonomy_repo,
        assignment_repo=assignment_repo,
        node_repo=node_repo,
        source_result_repo=sr_repo,
        persona_affinity_repo=pa_repo,
    )
    return svc


class TestDbTopicDiscoveryDataService:
    async def test_protocol_conformance(self, tmp_path):
        td_repo, taxonomy_repo, assignment_repo, node_repo, sr_repo, pa_repo = _mock_repos()
        svc = DbTopicDiscoveryDataService(
            td_repo=td_repo,
            taxonomy_repo=taxonomy_repo,
            assignment_repo=assignment_repo,
            node_repo=node_repo,
            source_result_repo=sr_repo,
            persona_affinity_repo=pa_repo,
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

    async def test_get_taxonomy_returns_none_when_no_discovery(self, svc, tmp_path):
        """get_taxonomy returns None when discovery not found."""
        svc._td_repo.get_by_effective_slug = AsyncMock(return_value=None)
        result = await svc.get_taxonomy("nonexistent")
        assert result is None

    async def test_get_matrix_returns_none_when_no_discovery(self, svc, tmp_path):
        """get_matrix returns None when discovery not found."""
        svc._td_repo.get_by_effective_slug = AsyncMock(return_value=None)
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
        expected = {
            "get_discovery_summary", "get_taxonomy", "get_matrix",
            "list_assignments", "get_scored_subdomains", "get_persona_affinity",
        }
        for method in expected:
            assert hasattr(DbTopicDiscoveryDataService, method)

    async def test_get_discovery_summary_includes_scoring_version(self, svc):
        from datetime import datetime, timezone

        row = MagicMock()
        row.taxonomy_version = 2
        row.matrix_version = 1
        row.scoring_version = 3
        row.persona_affinity_version = 2
        row.status = MagicMock(value="approved")
        row.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

        svc._td_repo.get_by_effective_slug = AsyncMock(return_value=row)

        result = await svc.get_discovery_summary("test-co")

        assert result["scoring_version"] == 3
        assert result["persona_affinity_version"] == 2
        assert result["status"] == "approved"

    async def test_get_taxonomy_from_db(self, svc):
        import uuid

        discovery = MagicMock()
        discovery.id = uuid.uuid4()
        svc._td_repo.get_by_effective_slug = AsyncMock(return_value=discovery)

        tax = MagicMock()
        tax.tree_json = {"root_nodes": [{"name": "Cloud"}]}
        svc._taxonomy_repo.get_by_discovery = AsyncMock(return_value=tax)

        result = await svc.get_taxonomy("test-co")

        assert result == {"root_nodes": [{"name": "Cloud"}]}

    async def test_get_taxonomy_fallback_to_json(self, svc):
        import uuid

        discovery = MagicMock()
        discovery.id = uuid.uuid4()
        svc._td_repo.get_by_effective_slug = AsyncMock(return_value=discovery)

        tax = MagicMock()
        tax.tree_json = None
        svc._taxonomy_repo.get_by_discovery = AsyncMock(return_value=tax)

        # No JSON file either → should return None
        result = await svc.get_taxonomy("test-co")
        assert result is None

    async def test_get_matrix_from_db(self, svc):
        import uuid

        discovery = MagicMock()
        discovery.id = uuid.uuid4()
        discovery.matrix_version = 1
        svc._td_repo.get_by_effective_slug = AsyncMock(return_value=discovery)

        assignment = MagicMock()
        assignment.id = uuid.uuid4()
        assignment.subdomain_id_text = "sub-123"
        assignment.subdomain_name = "Cloud"
        assignment.topic_text = "Best corporate cards"
        assignment.buyer_stage = MagicMock(value="tofu")
        assignment.intent_type = MagicMock(value="informational")
        assignment.audience_segment = "CFO"
        assignment.audience_segment_type = MagicMock(value="individual_persona")
        assignment.relevance = MagicMock(value="relevant")
        assignment.priority_score = 0.85
        assignment.priority_factors = {"factor": 0.5}
        assignment.status = MagicMock(value="not_started")
        assignment.is_manually_added = False
        assignment.metadata_json = {}
        assignment.persona_id = "persona-cfo"
        assignment.persona_name = "CFO"

        svc._assignment_repo.get_by_discovery = AsyncMock(return_value=[assignment])

        result = await svc.get_matrix("test-co")

        assert result is not None
        assert result["total_assignments"] == 1
        assert result["assignments"][0]["persona_id"] == "persona-cfo"
        assert result["assignments"][0]["subdomain_name"] == "Cloud"

    async def test_list_assignments_includes_persona_fields(self, svc):
        import uuid

        discovery = MagicMock()
        discovery.id = uuid.uuid4()
        svc._td_repo.get_by_effective_slug = AsyncMock(return_value=discovery)

        assignment = MagicMock()
        assignment.id = uuid.uuid4()
        assignment.topic_text = "Best corporate cards"
        assignment.buyer_stage = MagicMock(value="tofu")
        assignment.intent_type = MagicMock(value="informational")
        assignment.audience_segment = "CFO"
        assignment.relevance = MagicMock(value="relevant")
        assignment.priority_score = 0.85
        assignment.status = MagicMock(value="not_started")
        assignment.persona_id = "persona-cfo"
        assignment.persona_name = "CFO"
        assignment.subdomain_id_text = "sub-123"
        assignment.subdomain_name = "Cloud"

        svc._assignment_repo.list_paginated = AsyncMock(
            return_value=([assignment], 1)
        )

        result = await svc.list_assignments("test-co")

        item = result["items"][0]
        assert item["persona_id"] == "persona-cfo"
        assert item["persona_name"] == "CFO"
        assert item["subdomain_id"] == "sub-123"
        assert item["subdomain_name"] == "Cloud"

    async def test_list_assignments_persona_filter_via_db(self, svc):
        import uuid

        discovery = MagicMock()
        discovery.id = uuid.uuid4()
        svc._td_repo.get_by_effective_slug = AsyncMock(return_value=discovery)
        svc._assignment_repo.list_paginated = AsyncMock(return_value=([], 0))

        await svc.list_assignments("test-co", persona_id="persona-cfo")

        call_kwargs = svc._assignment_repo.list_paginated.call_args
        assert call_kwargs.kwargs.get("persona_id") == "persona-cfo"

    async def test_get_scored_subdomains_from_db(self, svc):
        import uuid

        discovery = MagicMock()
        discovery.id = uuid.uuid4()
        discovery.scoring_version = 2
        svc._td_repo.get_by_effective_slug = AsyncMock(return_value=discovery)

        tax = MagicMock()
        tax.id = uuid.uuid4()
        svc._taxonomy_repo.get_by_discovery = AsyncMock(return_value=tax)

        node = MagicMock()
        node.id = uuid.uuid4()
        node.name = "Cloud"
        node.priority_score = 0.92
        node.priority_factors = {"strategic_centrality": 0.8}
        node.persona_affinity_json = {"cfo": 0.9}
        node.metadata_json = {"key": "val"}
        svc._node_repo.get_by_taxonomy = AsyncMock(return_value=[node])

        result = await svc.get_scored_subdomains("test-co")

        assert result is not None
        assert result["total_scored"] == 1
        assert result["version"] == 2
        assert result["scores"][0]["composite_score"] == 0.92
        assert result["scores"][0]["signal_scores"]["strategic_centrality"] == 0.8
        assert result["scores"][0]["persona_affinity"]["cfo"] == 0.9

    async def test_get_persona_affinity_from_db(self, svc):
        import uuid

        discovery = MagicMock()
        discovery.id = uuid.uuid4()
        discovery.persona_affinity_version = 1
        svc._td_repo.get_by_effective_slug = AsyncMock(return_value=discovery)

        row1 = MagicMock()
        row1.persona_id = "persona-cfo"
        row1.subdomain_id_str = "sub-1"
        row1.subdomain_node_id = uuid.uuid4()
        row1.subdomain_name = "Cloud"
        row1.affinity_score = 0.9
        row1.provenance = "llm"
        row1.pain_points = ["budget"]

        row2 = MagicMock()
        row2.persona_id = "persona-cfo"
        row2.subdomain_id_str = "sub-2"
        row2.subdomain_node_id = uuid.uuid4()
        row2.subdomain_name = "Security"
        row2.affinity_score = 0.7
        row2.provenance = "heuristic"
        row2.pain_points = []

        svc._persona_affinity_repo.get_by_discovery = AsyncMock(
            return_value=[row1, row2]
        )

        result = await svc.get_persona_affinity("test-co")

        assert result is not None
        assert result["total_personas"] == 1
        assert result["version"] == 1
        assert len(result["persona_entries"]["persona-cfo"]) == 2

    async def test_get_persona_affinity_filtered(self, svc):
        import uuid

        discovery = MagicMock()
        discovery.id = uuid.uuid4()
        discovery.persona_affinity_version = 1
        svc._td_repo.get_by_effective_slug = AsyncMock(return_value=discovery)

        row = MagicMock()
        row.persona_id = "persona-cto"
        row.subdomain_id_str = "sub-1"
        row.subdomain_node_id = uuid.uuid4()
        row.subdomain_name = "Cloud"
        row.affinity_score = 0.95
        row.provenance = "llm"
        row.pain_points = []

        svc._persona_affinity_repo.get_by_persona = AsyncMock(return_value=[row])

        result = await svc.get_persona_affinity("test-co", persona_id="persona-cto")

        assert result is not None
        assert result["total_personas"] == 1
        svc._persona_affinity_repo.get_by_persona.assert_called_once()
