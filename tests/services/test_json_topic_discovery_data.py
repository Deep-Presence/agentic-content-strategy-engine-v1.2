"""Tests for JsonTopicDiscoveryDataService — filesystem-backed TD read service."""
from __future__ import annotations

from pathlib import Path

import pytest

from core.services.json_topic_discovery_data import JsonTopicDiscoveryDataService
from core.services.topic_discovery_data import TopicDiscoveryDataServiceProtocol


@pytest.fixture
def td_root(tmp_path: Path) -> Path:
    """Create a minimal TD fixture using actual storage class."""
    from core.models.topic_discovery import (
        SubdomainNode,
        TaxonomyTree,
        TopicAssignment,
        TopicAssignmentMatrix,
        TopicDiscoveryManifest,
    )
    from core.topic_discovery.storage import TopicDiscoveryStorage

    storage = TopicDiscoveryStorage(tmp_path, "test-co")

    # Set company_name in manifest so get_discovery_summary doesn't return None
    manifest = storage.read_manifest()
    manifest.company_name = "Test Co"
    storage.write_manifest(manifest)

    # Write taxonomy v1
    tree = TaxonomyTree(
        domain_name="test-co.com",
        root_nodes=[
            SubdomainNode(name="Expense Management", children=[
                SubdomainNode(name="Corporate Cards", depth=1),
            ]),
        ],
        total_subdomains=2,
        max_depth=1,
    )
    storage.write_taxonomy(tree)

    # Write matrix v1
    matrix = TopicAssignmentMatrix(
        assignments=[
            TopicAssignment(
                subdomain_name="Corporate Cards",
                topic_text="Best corporate cards",
            ),
        ],
        total_assignments=1,
        buyer_stage_distribution={"tofu": 1},
        intent_distribution={"informational": 1},
        audience_distribution={},
    )
    storage.write_matrix(matrix)

    return tmp_path


class TestJsonTopicDiscoveryDataService:
    async def test_protocol_conformance(self, tmp_path):
        svc = JsonTopicDiscoveryDataService(tmp_path)
        assert isinstance(svc, TopicDiscoveryDataServiceProtocol)

    async def test_get_discovery_summary(self, td_root):
        svc = JsonTopicDiscoveryDataService(td_root)
        result = await svc.get_discovery_summary("test-co")
        assert result is not None
        assert result["slug"] == "test-co"
        assert result["has_taxonomy"] is True

    async def test_get_discovery_summary_missing(self, tmp_path):
        svc = JsonTopicDiscoveryDataService(tmp_path)
        result = await svc.get_discovery_summary("nonexistent")
        assert result is None

    async def test_get_taxonomy(self, td_root):
        svc = JsonTopicDiscoveryDataService(td_root)
        result = await svc.get_taxonomy("test-co")
        assert result is not None
        assert "root_nodes" in result

    async def test_get_taxonomy_missing(self, tmp_path):
        svc = JsonTopicDiscoveryDataService(tmp_path)
        result = await svc.get_taxonomy("nonexistent")
        assert result is None

    async def test_get_matrix(self, td_root):
        svc = JsonTopicDiscoveryDataService(td_root)
        result = await svc.get_matrix("test-co")
        assert result is not None
        assert "assignments" in result

    async def test_list_assignments(self, td_root):
        svc = JsonTopicDiscoveryDataService(td_root)
        result = await svc.list_assignments("test-co")
        assert result["total"] >= 1
        assert len(result["items"]) >= 1

    async def test_list_assignments_empty(self, tmp_path):
        svc = JsonTopicDiscoveryDataService(tmp_path)
        result = await svc.list_assignments("nonexistent")
        assert result["total"] == 0
        assert result["items"] == []
