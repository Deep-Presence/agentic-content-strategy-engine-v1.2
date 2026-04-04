"""Tests for JsonTopicDiscoveryDataService planner methods.

Covers the write methods added for Content Planner:
- update_assignment_status(effective_slug, assignment_id, status)
- create_assignment(effective_slug, assignment_data)
- list_assignments with status filter
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.services.json_topic_discovery_data import JsonTopicDiscoveryDataService


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def td_root(tmp_path: Path) -> Path:
    """Create a minimal TD fixture using actual storage class."""
    from core.models.topic_discovery import (
        BuyerStage,
        IntentType,
        SubdomainNode,
        TaxonomyTree,
        TopicAssignment,
        TopicAssignmentMatrix,
        TopicAssignmentStatus,
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
            SubdomainNode(
                name="Expense Management",
                children=[SubdomainNode(name="Corporate Cards", depth=1)],
            ),
        ],
        total_subdomains=2,
        max_depth=1,
    )
    storage.write_taxonomy(tree)

    # Write matrix v1 with two assignments (known IDs for update tests)
    a1 = TopicAssignment(
        id="aaaa-1111-2222-3333-444444444444",
        subdomain_name="Corporate Cards",
        topic_text="Best corporate cards",
        buyer_stage=BuyerStage.TOFU,
        intent_type=IntentType.informational,
        priority_score=0.8,
        status=TopicAssignmentStatus.not_started,
    )
    a2 = TopicAssignment(
        id="bbbb-1111-2222-3333-444444444444",
        subdomain_name="Corporate Cards",
        topic_text="Corporate card comparison",
        buyer_stage=BuyerStage.MOFU,
        intent_type=IntentType.commercial,
        priority_score=0.6,
        status=TopicAssignmentStatus.approved,
    )
    matrix = TopicAssignmentMatrix(
        assignments=[a1, a2],
        total_assignments=2,
        buyer_stage_distribution={"tofu": 1, "mofu": 1},
        intent_distribution={"informational": 1, "commercial": 1},
        audience_distribution={},
    )
    storage.write_matrix(matrix)

    return tmp_path


# ═══════════════════════════════════════════════════════════════════════
# update_assignment_status
# ═══════════════════════════════════════════════════════════════════════


class TestUpdateAssignmentStatus:
    """Tests for JsonTopicDiscoveryDataService.update_assignment_status."""

    async def test_update_existing_assignment(self, td_root: Path):
        svc = JsonTopicDiscoveryDataService(td_root)
        result = await svc.update_assignment_status(
            "test-co", "aaaa-1111-2222-3333-444444444444", "approved"
        )
        assert result is not None
        assert result["id"] == "aaaa-1111-2222-3333-444444444444"
        assert result["status"] == "approved"

    async def test_update_persists_to_disk(self, td_root: Path):
        """Verify the status change survives a re-read from storage."""
        svc = JsonTopicDiscoveryDataService(td_root)
        await svc.update_assignment_status(
            "test-co", "aaaa-1111-2222-3333-444444444444", "rejected"
        )

        # Re-read via a fresh service instance
        svc2 = JsonTopicDiscoveryDataService(td_root)
        result = await svc2.list_assignments(
            "test-co", status="rejected"
        )
        assert result["total"] == 1
        assert result["items"][0]["id"] == "aaaa-1111-2222-3333-444444444444"
        assert result["items"][0]["status"] == "rejected"

    async def test_update_missing_assignment_returns_none(self, td_root: Path):
        svc = JsonTopicDiscoveryDataService(td_root)
        result = await svc.update_assignment_status(
            "test-co", "nonexistent-id-0000-0000-000000000000", "approved"
        )
        assert result is None

    async def test_update_missing_matrix_returns_none(self, tmp_path: Path):
        """No matrix at all for the slug -> None."""
        svc = JsonTopicDiscoveryDataService(tmp_path)
        result = await svc.update_assignment_status(
            "nonexistent", "some-id", "approved"
        )
        assert result is None

    async def test_restore_to_not_started(self, td_root: Path):
        """Restore a previously approved assignment back to not_started."""
        svc = JsonTopicDiscoveryDataService(td_root)
        # Assignment bbbb is already approved
        result = await svc.update_assignment_status(
            "test-co", "bbbb-1111-2222-3333-444444444444", "not_started"
        )
        assert result is not None
        assert result["status"] == "not_started"


# ═══════════════════════════════════════════════════════════════════════
# create_assignment
# ═══════════════════════════════════════════════════════════════════════


class TestCreateAssignment:
    """Tests for JsonTopicDiscoveryDataService.create_assignment."""

    async def test_create_basic(self, td_root: Path):
        svc = JsonTopicDiscoveryDataService(td_root)
        result = await svc.create_assignment(
            "test-co",
            assignment_data={
                "topic_text": "New custom topic",
                "buyer_stage": "tofu",
                "intent_type": "informational",
            },
        )
        assert result is not None
        assert result["topic_text"] == "New custom topic"
        assert result["is_manually_added"] is True
        # Auto-generated UUID
        assert result["id"]

    async def test_create_increments_total(self, td_root: Path):
        svc = JsonTopicDiscoveryDataService(td_root)
        await svc.create_assignment(
            "test-co",
            assignment_data={
                "topic_text": "Additional topic",
                "buyer_stage": "bofu",
                "intent_type": "transactional",
            },
        )

        # Matrix should now have 3 assignments (2 original + 1 new)
        result = await svc.list_assignments("test-co")
        assert result["total"] == 3

    async def test_create_persists_to_disk(self, td_root: Path):
        """Verify the new assignment survives a re-read from storage."""
        svc = JsonTopicDiscoveryDataService(td_root)
        created = await svc.create_assignment(
            "test-co",
            assignment_data={
                "topic_text": "Persisted topic",
                "buyer_stage": "mofu",
                "intent_type": "commercial",
            },
        )

        # Re-read via a fresh service instance
        svc2 = JsonTopicDiscoveryDataService(td_root)
        result = await svc2.list_assignments("test-co")
        ids = [item["id"] for item in result["items"]]
        assert created["id"] in ids

    async def test_create_with_full_data(self, td_root: Path):
        svc = JsonTopicDiscoveryDataService(td_root)
        result = await svc.create_assignment(
            "test-co",
            assignment_data={
                "topic_text": "Full data topic",
                "subdomain_id": "sd-99",
                "subdomain_name": "Enterprise",
                "buyer_stage": "bofu",
                "intent_type": "transactional",
                "persona_id": "cto",
                "persona_name": "CTO",
                "priority_score": 0.95,
            },
        )
        assert result["subdomain_id"] == "sd-99"
        assert result["persona_id"] == "cto"
        assert result["priority_score"] == 0.95
        assert result["is_manually_added"] is True

    async def test_create_raises_for_missing_matrix(self, tmp_path: Path):
        """Cannot create assignment when no matrix exists."""
        svc = JsonTopicDiscoveryDataService(tmp_path)
        with pytest.raises(ValueError, match="No matrix found"):
            await svc.create_assignment(
                "nonexistent",
                assignment_data={
                    "topic_text": "Should fail",
                    "buyer_stage": "tofu",
                    "intent_type": "informational",
                },
            )


# ═══════════════════════════════════════════════════════════════════════
# list_assignments with status filter
# ═══════════════════════════════════════════════════════════════════════


class TestListAssignmentsFiltered:
    """Tests for list_assignments with filters — verifying service-level logic."""

    async def test_filter_by_status_not_started(self, td_root: Path):
        svc = JsonTopicDiscoveryDataService(td_root)
        result = await svc.list_assignments("test-co", status="not_started")
        assert result["total"] == 1
        assert all(
            item["status"] == "not_started" for item in result["items"]
        )

    async def test_filter_by_status_approved(self, td_root: Path):
        svc = JsonTopicDiscoveryDataService(td_root)
        result = await svc.list_assignments("test-co", status="approved")
        assert result["total"] == 1
        assert result["items"][0]["status"] == "approved"

    async def test_filter_by_buyer_stage(self, td_root: Path):
        svc = JsonTopicDiscoveryDataService(td_root)
        result = await svc.list_assignments("test-co", buyer_stage="tofu")
        assert result["total"] == 1
        assert result["items"][0]["buyer_stage"] == "tofu"

    async def test_filter_by_intent_type(self, td_root: Path):
        svc = JsonTopicDiscoveryDataService(td_root)
        result = await svc.list_assignments("test-co", intent_type="commercial")
        assert result["total"] == 1
        assert result["items"][0]["intent_type"] == "commercial"

    async def test_filter_returns_empty_when_no_match(self, td_root: Path):
        svc = JsonTopicDiscoveryDataService(td_root)
        result = await svc.list_assignments("test-co", status="rejected")
        assert result["total"] == 0
        assert result["items"] == []

    async def test_combined_filters(self, td_root: Path):
        svc = JsonTopicDiscoveryDataService(td_root)
        result = await svc.list_assignments(
            "test-co", buyer_stage="tofu", status="not_started"
        )
        assert result["total"] == 1
        item = result["items"][0]
        assert item["buyer_stage"] == "tofu"
        assert item["status"] == "not_started"

    async def test_combined_filters_no_match(self, td_root: Path):
        svc = JsonTopicDiscoveryDataService(td_root)
        result = await svc.list_assignments(
            "test-co", buyer_stage="bofu", status="not_started"
        )
        assert result["total"] == 0
