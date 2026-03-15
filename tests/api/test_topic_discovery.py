"""Tests for Topic Discovery pipeline API endpoints.

Covers: start, status, approve/taxonomy, approve/matrix, taxonomy read, matrix read,
auth, guard, schema validation.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.tasks.event_bus import EventBus
from api.tasks.models import TaskStatus
from api.tasks.store import TaskStore


# ── Constants ─────────────────────────────────────────────────────────

MINIMAL_PAYLOAD = {
    "company_name": "Test Co",
    "domain": "testco.com",
}

PREFIX = "/api/v1/topic-discovery"


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_td_runner():
    """Mock the TD pipeline runner to complete instantly."""
    with patch(
        "api.routers.topic_discovery.run_topic_discovery_pipeline_task",
        new_callable=AsyncMock,
    ) as mock_fn:

        async def _complete_task(task_id, **kwargs):
            task_store = kwargs["task_store"]
            event_bus = kwargs["event_bus"]
            event_bus.publish(task_id, "pipeline_start", {"pipeline": "topic_discovery"})
            task_store.update_task(
                task_id, status=TaskStatus.COMPLETED, result={"stage": "complete"}
            )
            event_bus.publish(task_id, "completed", {"pipeline": "topic_discovery"})

        mock_fn.side_effect = _complete_task
        yield mock_fn


def _write_td_manifest(
    artifacts_root: Path,
    slug: str,
    taxonomy_version: int = 0,
    matrix_version: int = 0,
    status: str = "draft",
) -> Path:
    """Write a TD manifest for guard tests."""
    td_dir = artifacts_root / "topic_discovery" / slug
    td_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "slug": slug,
        "taxonomy_version": taxonomy_version,
        "matrix_version": matrix_version,
        "status": status,
    }
    manifest_path = td_dir / "_manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    return manifest_path


# ═══════════════════════════════════════════════════════════════════════
# POST /start
# ═══════════════════════════════════════════════════════════════════════


class TestStartTopicDiscovery:
    """Tests for POST /topic-discovery/start."""

    def test_start_success(self, client, mock_td_runner):
        resp = client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 202
        data = resp.json()
        assert data["pipeline"] == "topic_discovery"
        assert data["status"] == "started"
        assert "run_id" in data

    def test_start_returns_run_id(self, client, mock_td_runner):
        resp = client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.json()["run_id"]

    def test_start_requires_auth(self, public_client):
        resp = public_client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code in (401, 403)

    def test_start_viewer_rejected(self, viewer_client):
        resp = viewer_client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 403

    def test_start_tenant_isolation(self, client):
        """Cannot start pipeline for a different company."""
        resp = client.post(
            f"{PREFIX}/start",
            json={"company_name": "Other Corp", "domain": "other.com"},
        )
        assert resp.status_code == 403

    def test_start_auto_approve_valid(self, client, mock_td_runner):
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "auto_approve_checkpoints": [1, 2]},
        )
        assert resp.status_code == 202

    def test_start_auto_approve_checkpoint_3_valid(self, client, mock_td_runner):
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "auto_approve_checkpoints": [3]},
        )
        assert resp.status_code == 202

    def test_start_auto_approve_invalid_checkpoint(self, client):
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "auto_approve_checkpoints": [4]},
        )
        assert resp.status_code == 422

    def test_start_with_product_slug(self, client, mock_td_runner):
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "product_slug": "expense-mgmt"},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["effective_slug"] == "test-co__expense-mgmt"
        assert data["product_slug"] == "expense-mgmt"

    def test_start_max_expansion_rounds_validation(self, client):
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "max_expansion_rounds": 0},
        )
        assert resp.status_code == 422

    def test_start_dedup_threshold_validation(self, client):
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "dedup_threshold": 0.3},
        )
        assert resp.status_code == 422


class TestStartTDGuard:
    """Tests for the guard that blocks re-runs when discovery is complete."""

    def test_guard_blocks_when_approved(self, client, artifacts_root):
        _write_td_manifest(
            artifacts_root, "test-co",
            taxonomy_version=1, matrix_version=1, status="approved",
        )
        resp = client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "already_exists"
        assert data["already_exists"] is True

    def test_guard_allows_with_force_rerun(self, client, mock_td_runner, artifacts_root):
        _write_td_manifest(
            artifacts_root, "test-co",
            taxonomy_version=1, matrix_version=1, status="approved",
        )
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "force_rerun": True},
        )
        assert resp.status_code == 202

    def test_guard_allows_when_no_manifest(self, client, mock_td_runner):
        resp = client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 202

    def test_guard_allows_when_draft(self, client, mock_td_runner, artifacts_root):
        _write_td_manifest(
            artifacts_root, "test-co",
            taxonomy_version=1, matrix_version=0, status="draft",
        )
        resp = client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 202


# ═══════════════════════════════════════════════════════════════════════
# GET /{run_id}/status
# ═══════════════════════════════════════════════════════════════════════


class TestGetTDStatus:
    """Tests for GET /topic-discovery/{run_id}/status."""

    def test_status_returns_task(self, client, mock_td_runner):
        resp = client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        run_id = resp.json()["run_id"]
        status_resp = client.get(f"{PREFIX}/{run_id}/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["run_id"] == run_id

    def test_status_not_found(self, client):
        resp = client.get(f"{PREFIX}/nonexistent-123/status")
        assert resp.status_code == 404

    def test_status_tenant_isolation_403(self, client, task_store):
        """Cannot view status of another company's task."""
        task = task_store.create_task("topic_discovery", "other-co")
        resp = client.get(f"{PREFIX}/{task.task_id}/status")
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# POST /{run_id}/approve/taxonomy
# ═══════════════════════════════════════════════════════════════════════


class TestApproveTaxonomy:
    """Tests for POST /topic-discovery/{run_id}/approve/taxonomy."""

    def test_approve_taxonomy(self, client, task_store):
        task = task_store.create_task("topic_discovery", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={
                "stage": "td_taxonomy_review",
                "checkpoint_nonce": "test-nonce",
                "taxonomy": {"root_nodes": []},
            },
        )

        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/taxonomy",
            json={"batch_decision": "approve"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["stage"] == "td_taxonomy_review"

    def test_approve_taxonomy_with_edits(self, client, task_store):
        task = task_store.create_task("topic_discovery", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "td_taxonomy_review", "checkpoint_nonce": "test-nonce"},
        )

        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/taxonomy",
            json={
                "batch_decision": "modify",
                "user_edits": [
                    {"op": "add", "name": "New Topic", "description": "A new topic"},
                    {"op": "rename", "node_id": "abc", "new_name": "Renamed"},
                ],
            },
        )
        assert resp.status_code == 200

    def test_approve_taxonomy_retry(self, client, task_store):
        task = task_store.create_task("topic_discovery", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "td_taxonomy_review", "checkpoint_nonce": "test-nonce"},
        )

        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/taxonomy",
            json={
                "batch_decision": "retry",
                "user_feedback": "Add more subdomains for security",
            },
        )
        assert resp.status_code == 200

    def test_approve_taxonomy_wrong_stage(self, client, task_store):
        task = task_store.create_task("topic_discovery", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "td_matrix_review"},
        )

        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/taxonomy",
            json={"batch_decision": "approve"},
        )
        assert resp.status_code == 409

    def test_approve_taxonomy_not_pending(self, client, task_store):
        task = task_store.create_task("topic_discovery", "test-co")
        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/taxonomy",
            json={"batch_decision": "approve"},
        )
        assert resp.status_code == 409

    def test_approve_taxonomy_not_found(self, client):
        resp = client.post(
            f"{PREFIX}/nonexistent/approve/taxonomy",
            json={"batch_decision": "approve"},
        )
        assert resp.status_code == 404

    def test_approve_taxonomy_tenant_isolation_403(self, client, task_store):
        """Cannot approve taxonomy of another company's task."""
        task = task_store.create_task("topic_discovery", "other-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={
                "stage": "td_taxonomy_review",
                "checkpoint_nonce": "n1",
            },
        )
        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/taxonomy",
            json={"batch_decision": "approve"},
        )
        assert resp.status_code == 403

    def test_approve_taxonomy_missing_nonce_409(self, client, task_store):
        """Approval fails if no checkpoint_nonce in approval_payload."""
        task = task_store.create_task("topic_discovery", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "td_taxonomy_review"},
        )
        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/taxonomy",
            json={"batch_decision": "approve"},
        )
        assert resp.status_code == 409
        assert "No active approval checkpoint" in resp.json()["detail"]


# ═══════════════════════════════════════════════════════════════════════
# POST /{run_id}/approve/matrix
# ═══════════════════════════════════════════════════════════════════════


class TestApproveMatrix:
    """Tests for POST /topic-discovery/{run_id}/approve/matrix."""

    def test_approve_matrix(self, client, task_store):
        task = task_store.create_task("topic_discovery", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "td_matrix_review", "checkpoint_nonce": "test-nonce"},
        )

        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/matrix",
            json={"batch_decision": "approve"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["stage"] == "td_matrix_review"

    def test_approve_matrix_with_edits(self, client, task_store):
        task = task_store.create_task("topic_discovery", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "td_matrix_review", "checkpoint_nonce": "test-nonce"},
        )

        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/matrix",
            json={
                "batch_decision": "modify",
                "user_edits": [
                    {"op": "remove", "assignment_id": "a1"},
                    {"op": "adjust_priority", "assignment_id": "a2", "new_priority": 0.9},
                ],
            },
        )
        assert resp.status_code == 200

    def test_approve_matrix_wrong_stage(self, client, task_store):
        task = task_store.create_task("topic_discovery", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "td_taxonomy_review"},
        )

        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/matrix",
            json={"batch_decision": "approve"},
        )
        assert resp.status_code == 409

    def test_approve_matrix_not_found(self, client):
        resp = client.post(
            f"{PREFIX}/nonexistent/approve/matrix",
            json={"batch_decision": "approve"},
        )
        assert resp.status_code == 404

    def test_approve_matrix_tenant_isolation_403(self, client, task_store):
        """Cannot approve matrix of another company's task."""
        task = task_store.create_task("topic_discovery", "other-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={
                "stage": "td_matrix_review",
                "checkpoint_nonce": "n1",
            },
        )
        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/matrix",
            json={"batch_decision": "approve"},
        )
        assert resp.status_code == 403

    def test_approve_matrix_missing_nonce_409(self, client, task_store):
        """Approval fails if no checkpoint_nonce in approval_payload."""
        task = task_store.create_task("topic_discovery", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "td_matrix_review"},
        )
        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/matrix",
            json={"batch_decision": "approve"},
        )
        assert resp.status_code == 409
        assert "No active approval checkpoint" in resp.json()["detail"]


# ═══════════════════════════════════════════════════════════════════════
# GET /{slug}/taxonomy
# ═══════════════════════════════════════════════════════════════════════


class TestGetLatestTaxonomy:
    """Tests for GET /topic-discovery/{slug}/taxonomy."""

    def test_taxonomy_found(self, client, artifacts_root):
        from core.models.topic_discovery import (
            SubdomainNode,
            TaxonomyTree,
            TopicDiscoveryManifest,
        )
        from core.topic_discovery.storage import TopicDiscoveryStorage

        storage = TopicDiscoveryStorage(artifacts_root, "test-co")
        tree = TaxonomyTree(
            root_nodes=[
                SubdomainNode(name="Finance", description="Finance topics"),
                SubdomainNode(name="HR", description="HR topics"),
            ],
            total_subdomains=2,
            coverage_score=0.85,
        )
        ver = storage.write_taxonomy(tree)
        # Update manifest so the router can read the version
        manifest = storage.read_manifest()
        manifest.taxonomy_version = ver
        storage.write_manifest(manifest)

        resp = client.get(f"{PREFIX}/test-co/taxonomy")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "test-co"
        assert data["version"] == 1
        assert data["total_subdomains"] == 2
        assert data["coverage_score"] == 0.85

    def test_taxonomy_not_found(self, client):
        resp = client.get(f"{PREFIX}/test-co/taxonomy")
        assert resp.status_code == 404

    def test_taxonomy_tenant_isolation_403(self, client):
        """Cannot read taxonomy of another company."""
        resp = client.get(f"{PREFIX}/other-co/taxonomy")
        assert resp.status_code == 403

    def test_taxonomy_effective_slug_other_company_blocked(self, client):
        """Cannot read taxonomy using effective slug of another company."""
        resp = client.get(f"{PREFIX}/other-co__product/taxonomy")
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# GET /{slug}/matrix
# ═══════════════════════════════════════════════════════════════════════


class TestGetLatestMatrix:
    """Tests for GET /topic-discovery/{slug}/matrix."""

    def test_matrix_found(self, client, artifacts_root):
        from core.models.topic_discovery import TopicAssignment, TopicAssignmentMatrix
        from core.topic_discovery.storage import TopicDiscoveryStorage

        storage = TopicDiscoveryStorage(artifacts_root, "test-co")
        matrix = TopicAssignmentMatrix(
            assignments=[
                TopicAssignment(
                    topic_text="How to manage expenses",
                    subdomain_name="Finance",
                    buyer_stage="tofu",
                    intent_type="informational",
                ),
            ],
            total_assignments=1,
        )
        ver = storage.write_matrix(matrix)
        # Update manifest so the router can read the version
        manifest = storage.read_manifest()
        manifest.matrix_version = ver
        storage.write_manifest(manifest)

        resp = client.get(f"{PREFIX}/test-co/matrix")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "test-co"
        assert data["version"] == 1
        assert data["total_assignments"] == 1

    def test_matrix_not_found(self, client):
        resp = client.get(f"{PREFIX}/test-co/matrix")
        assert resp.status_code == 404

    def test_matrix_tenant_isolation_403(self, client):
        """Cannot read matrix of another company."""
        resp = client.get(f"{PREFIX}/other-co/matrix")
        assert resp.status_code == 403

    def test_matrix_effective_slug_other_company_blocked(self, client):
        """Cannot read matrix using effective slug of another company."""
        resp = client.get(f"{PREFIX}/other-co__product/matrix")
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# Schema Validation
# ═══════════════════════════════════════════════════════════════════════


class TestSchemaValidation:
    """Tests for request schema validation."""

    def test_taxonomy_approval_invalid_decision(self, client):
        resp = client.post(
            f"{PREFIX}/some-task/approve/taxonomy",
            json={"batch_decision": "invalid"},
        )
        assert resp.status_code == 422

    def test_matrix_approval_invalid_decision(self, client):
        resp = client.post(
            f"{PREFIX}/some-task/approve/matrix",
            json={"batch_decision": "retry"},  # matrix doesn't support retry
        )
        assert resp.status_code == 422

    def test_taxonomy_edit_invalid_op(self, client):
        resp = client.post(
            f"{PREFIX}/some-task/approve/taxonomy",
            json={
                "batch_decision": "modify",
                "user_edits": [{"op": "invalid_op"}],
            },
        )
        assert resp.status_code == 422

    def test_start_missing_required_fields(self, client):
        resp = client.post(f"{PREFIX}/start", json={})
        assert resp.status_code == 422

    # ── M9: Invalid enum values rejected ─────────────────────────────

    def test_matrix_edit_invalid_buyer_stage_422(self, client):
        """M9: buyer_stage must be a valid BuyerStage enum value."""
        resp = client.post(
            f"{PREFIX}/some-task/approve/matrix",
            json={
                "batch_decision": "modify",
                "user_edits": [
                    {"op": "add", "buyer_stage": "invalid_stage", "topic_text": "x"},
                ],
            },
        )
        assert resp.status_code == 422

    def test_matrix_edit_invalid_intent_type_422(self, client):
        """M9: intent_type must be a valid IntentType enum value."""
        resp = client.post(
            f"{PREFIX}/some-task/approve/matrix",
            json={
                "batch_decision": "modify",
                "user_edits": [
                    {"op": "add", "intent_type": "garbage", "topic_text": "x"},
                ],
            },
        )
        assert resp.status_code == 422

    def test_matrix_edit_valid_enums_accepted(self, client):
        """M9: Valid enum values pass schema validation (may fail downstream)."""
        resp = client.post(
            f"{PREFIX}/some-task/approve/matrix",
            json={
                "batch_decision": "modify",
                "user_edits": [
                    {"op": "add", "buyer_stage": "tofu", "intent_type": "informational"},
                ],
            },
        )
        # Not 422 — schema accepted. Downstream may give 404/409.
        assert resp.status_code != 422

    # ── L2: Extra fields rejected ────────────────────────────────────

    def test_start_extra_fields_rejected_422(self, client, mock_td_runner):
        """L2: Extra fields on start request must be rejected."""
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "bogus_field": True},
        )
        assert resp.status_code == 422

    def test_taxonomy_approval_extra_fields_rejected_422(self, client):
        """L2: Extra fields on taxonomy approval must be rejected."""
        resp = client.post(
            f"{PREFIX}/some-task/approve/taxonomy",
            json={
                "batch_decision": "approve",
                "extra_field": "should_fail",
            },
        )
        assert resp.status_code == 422

    def test_matrix_approval_extra_fields_rejected_422(self, client):
        """L2: Extra fields on matrix approval must be rejected."""
        resp = client.post(
            f"{PREFIX}/some-task/approve/matrix",
            json={
                "batch_decision": "approve",
                "extra_field": "should_fail",
            },
        )
        assert resp.status_code == 422

    # ── L4: Typed response models ────────────────────────────────────

    def test_taxonomy_response_has_typed_fields(self, client, artifacts_root):
        """L4: Taxonomy response validates against TaxonomyReadResponse."""
        from api.schemas.topic_discovery import TaxonomyReadResponse
        from core.topic_discovery.storage import TopicDiscoveryStorage
        from core.models.topic_discovery import TaxonomyTree, SubdomainNode

        storage = TopicDiscoveryStorage(artifacts_root, "test-co")
        tree = TaxonomyTree(
            domain_name="test",
            root_nodes=[SubdomainNode(name="A")],
            total_subdomains=1,
            coverage_score=0.9,
        )
        ver = storage.write_taxonomy(tree)
        manifest = storage.read_manifest()
        manifest.taxonomy_version = ver
        storage.write_manifest(manifest)

        resp = client.get(f"{PREFIX}/test-co/taxonomy")
        assert resp.status_code == 200
        data = TaxonomyReadResponse(**resp.json())
        assert data.slug == "test-co"
        assert data.total_subdomains == 1
        assert data.coverage_score == 0.9

    def test_matrix_response_has_typed_fields(self, client, artifacts_root):
        """L4: Matrix response validates against MatrixReadResponse."""
        from api.schemas.topic_discovery import MatrixReadResponse
        from core.topic_discovery.storage import TopicDiscoveryStorage
        from core.models.topic_discovery import TopicAssignmentMatrix, TopicAssignment

        storage = TopicDiscoveryStorage(artifacts_root, "test-co")
        matrix = TopicAssignmentMatrix(
            assignments=[TopicAssignment(topic_text="test")],
            total_assignments=1,
        )
        ver = storage.write_matrix(matrix)
        manifest = storage.read_manifest()
        manifest.matrix_version = ver
        storage.write_manifest(manifest)

        resp = client.get(f"{PREFIX}/test-co/matrix")
        assert resp.status_code == 200
        data = MatrixReadResponse(**resp.json())
        assert data.slug == "test-co"
        assert data.total_assignments == 1


# ═══════════════════════════════════════════════════════════════════════
# POST /{run_id}/approve/subdomains (HITL-1.5)
# ═══════════════════════════════════════════════════════════════════════


class TestApproveSubdomains:
    """Tests for POST /topic-discovery/{run_id}/approve/subdomains."""

    def test_approve_subdomains_select(self, client, task_store):
        task = task_store.create_task("topic_discovery", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={
                "stage": "td_subdomain_selection",
                "checkpoint_nonce": "test-nonce",
            },
        )

        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/subdomains",
            json={
                "batch_decision": "select",
                "selected_subdomain_ids": ["sd-1", "sd-2"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["stage"] == "td_subdomain_selection"

    def test_approve_subdomains_top_n(self, client, task_store):
        task = task_store.create_task("topic_discovery", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={
                "stage": "td_subdomain_selection",
                "checkpoint_nonce": "test-nonce",
            },
        )

        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/subdomains",
            json={"batch_decision": "select_top_n", "top_n": 5},
        )
        assert resp.status_code == 200

    def test_approve_subdomains_wrong_stage(self, client, task_store):
        task = task_store.create_task("topic_discovery", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "td_taxonomy_review"},
        )

        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/subdomains",
            json={"batch_decision": "select", "selected_subdomain_ids": ["sd-1"]},
        )
        assert resp.status_code == 409

    def test_approve_subdomains_not_pending(self, client, task_store):
        task = task_store.create_task("topic_discovery", "test-co")
        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/subdomains",
            json={"batch_decision": "select", "selected_subdomain_ids": ["sd-1"]},
        )
        assert resp.status_code == 409

    def test_approve_subdomains_tenant_isolation_403(self, client, task_store):
        task = task_store.create_task("topic_discovery", "other-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={
                "stage": "td_subdomain_selection",
                "checkpoint_nonce": "n1",
            },
        )
        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/subdomains",
            json={"batch_decision": "select", "selected_subdomain_ids": ["sd-1"]},
        )
        assert resp.status_code == 403

    def test_approve_subdomains_missing_nonce_409(self, client, task_store):
        task = task_store.create_task("topic_discovery", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "td_subdomain_selection"},
        )
        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/subdomains",
            json={"batch_decision": "select", "selected_subdomain_ids": ["sd-1"]},
        )
        assert resp.status_code == 409
        assert "No active approval checkpoint" in resp.json()["detail"]

    def test_approve_subdomains_extra_fields_rejected(self, client):
        resp = client.post(
            f"{PREFIX}/some-task/approve/subdomains",
            json={
                "batch_decision": "select",
                "selected_subdomain_ids": ["sd-1"],
                "extra_field": "bad",
            },
        )
        assert resp.status_code == 422

    def test_approve_subdomains_invalid_decision_422(self, client):
        resp = client.post(
            f"{PREFIX}/some-task/approve/subdomains",
            json={"batch_decision": "approve"},
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# GET /{slug}/scored-subdomains
# ═══════════════════════════════════════════════════════════════════════


class TestGetScoredSubdomains:
    """Tests for GET /topic-discovery/{slug}/scored-subdomains."""

    def test_scored_subdomains_found(self, client, artifacts_root):
        from core.models.topic_discovery import ScoredSubdomainList, SubdomainScore
        from core.topic_discovery.storage import TopicDiscoveryStorage

        storage = TopicDiscoveryStorage(artifacts_root, "test-co")
        scored = ScoredSubdomainList(
            scores=[
                SubdomainScore(
                    subdomain_id="sd-1",
                    subdomain_name="Finance",
                    composite_score=0.85,
                    rank=1,
                ),
            ],
            total_scored=1,
            signals_used=["source_confidence", "persona_breadth"],
        )
        storage.write_scoring(scored)

        resp = client.get(f"{PREFIX}/test-co/scored-subdomains")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "test-co"
        assert data["total_scored"] == 1
        assert "source_confidence" in data["signals_used"]

    def test_scored_subdomains_not_found(self, client):
        resp = client.get(f"{PREFIX}/test-co/scored-subdomains")
        assert resp.status_code == 404

    def test_scored_subdomains_tenant_isolation_403(self, client):
        resp = client.get(f"{PREFIX}/other-co/scored-subdomains")
        assert resp.status_code == 403

    def test_scored_subdomains_effective_slug_other_company_blocked(self, client):
        resp = client.get(f"{PREFIX}/other-co__product/scored-subdomains")
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# GET /{slug}/personas
# ═══════════════════════════════════════════════════════════════════════


class TestGetPersonaAffinity:
    """Tests for GET /topic-discovery/{slug}/personas."""

    def test_personas_found(self, client, artifacts_root):
        from core.models.topic_discovery import (
            PersonaAffinityIndex,
            PersonaSubdomainEntry,
        )
        from core.topic_discovery.storage import TopicDiscoveryStorage

        storage = TopicDiscoveryStorage(artifacts_root, "test-co")
        index = PersonaAffinityIndex(
            persona_entries={
                "david": [
                    PersonaSubdomainEntry(
                        subdomain_id="sd-1",
                        subdomain_name="Finance",
                        affinity_score=0.75,
                        provenance="source_b",
                    ),
                ],
            },
            total_personas=1,
            total_subdomains=1,
        )
        storage.write_persona_affinity(index)

        resp = client.get(f"{PREFIX}/test-co/personas")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "test-co"
        assert data["total_personas"] == 1
        assert "david" in data["persona_entries"]

    def test_personas_not_found(self, client):
        resp = client.get(f"{PREFIX}/test-co/personas")
        assert resp.status_code == 404

    def test_personas_tenant_isolation_403(self, client):
        resp = client.get(f"{PREFIX}/other-co/personas")
        assert resp.status_code == 403

    def test_personas_with_persona_id_filter(self, client, artifacts_root):
        from core.models.topic_discovery import (
            PersonaAffinityIndex,
            PersonaSubdomainEntry,
        )
        from core.topic_discovery.storage import TopicDiscoveryStorage

        storage = TopicDiscoveryStorage(artifacts_root, "test-co")
        index = PersonaAffinityIndex(
            persona_entries={
                "david": [
                    PersonaSubdomainEntry(
                        subdomain_id="sd-1",
                        subdomain_name="Finance",
                        affinity_score=0.75,
                    ),
                ],
                "marcus": [
                    PersonaSubdomainEntry(
                        subdomain_id="sd-2",
                        subdomain_name="HR",
                        affinity_score=0.6,
                    ),
                ],
            },
            total_personas=2,
            total_subdomains=2,
        )
        storage.write_persona_affinity(index)

        resp = client.get(f"{PREFIX}/test-co/personas?persona_id=david")
        assert resp.status_code == 200
        data = resp.json()
        assert "david" in data["persona_entries"]
        assert "marcus" not in data["persona_entries"]


# ═══════════════════════════════════════════════════════════════════════
# Start Request — new fields
# ═══════════════════════════════════════════════════════════════════════


class TestStartNewFields:
    """Tests for new top_n_expand and persona_filter fields."""

    def test_start_with_top_n_expand(self, client, mock_td_runner):
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "top_n_expand": 5},
        )
        assert resp.status_code == 202

    def test_start_top_n_expand_too_high(self, client):
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "top_n_expand": 100},
        )
        assert resp.status_code == 422

    def test_start_top_n_expand_too_low(self, client):
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "top_n_expand": 0},
        )
        assert resp.status_code == 422

    def test_start_with_persona_filter(self, client, mock_td_runner):
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "persona_filter": "david"},
        )
        assert resp.status_code == 202

    def test_start_all_checkpoints_valid(self, client, mock_td_runner):
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "auto_approve_checkpoints": [1, 2, 3]},
        )
        assert resp.status_code == 202


# ═══════════════════════════════════════════════════════════════════════
# POST /expand (Pipeline B)
# ═══════════════════════════════════════════════════════════════════════


class TestStartTopicExpansion:
    """Tests for POST /topic-discovery/expand."""

    @pytest.fixture
    def mock_expansion_runner(self):
        """Mock the expansion pipeline runner to complete instantly."""
        with patch(
            "api.routers.topic_discovery.run_topic_expansion_pipeline_task",
            new_callable=AsyncMock,
        ) as mock_fn:

            async def _complete_task(task_id, **kwargs):
                task_store = kwargs["task_store"]
                event_bus = kwargs["event_bus"]
                event_bus.publish(task_id, "pipeline_start", {"pipeline": "topic_expansion"})
                task_store.update_task(
                    task_id, status=TaskStatus.COMPLETED, result={"stage": "complete"}
                )
                event_bus.publish(task_id, "completed", {"pipeline": "topic_expansion"})

            mock_fn.side_effect = _complete_task
            yield mock_fn

    def test_expand_success(self, client, mock_expansion_runner, artifacts_root):
        """POST /expand succeeds when Pipeline A has completed."""
        _write_td_manifest(
            artifacts_root, "test-co",
            taxonomy_version=1, status="discovery_complete",
        )
        resp = client.post(
            f"{PREFIX}/expand",
            json={
                **MINIMAL_PAYLOAD,
                "subdomain_ids": ["sd-1", "sd-2"],
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["pipeline"] == "topic_expansion"
        assert data["status"] == "started"
        assert "run_id" in data

    def test_expand_missing_discovery_409(self, client, artifacts_root):
        """POST /expand returns 409 when Pipeline A hasn't run."""
        resp = client.post(
            f"{PREFIX}/expand",
            json={
                **MINIMAL_PAYLOAD,
                "subdomain_ids": ["sd-1"],
            },
        )
        assert resp.status_code == 409
        assert "not been completed" in resp.json()["detail"]

    def test_expand_empty_subdomain_ids_422(self, client):
        """POST /expand with empty subdomain_ids is rejected by schema."""
        resp = client.post(
            f"{PREFIX}/expand",
            json={**MINIMAL_PAYLOAD, "subdomain_ids": []},
        )
        assert resp.status_code == 422

    def test_expand_requires_auth(self, public_client):
        resp = public_client.post(
            f"{PREFIX}/expand",
            json={**MINIMAL_PAYLOAD, "subdomain_ids": ["sd-1"]},
        )
        assert resp.status_code in (401, 403)

    def test_expand_viewer_rejected(self, viewer_client):
        resp = viewer_client.post(
            f"{PREFIX}/expand",
            json={**MINIMAL_PAYLOAD, "subdomain_ids": ["sd-1"]},
        )
        assert resp.status_code == 403

    def test_expand_tenant_isolation(self, client):
        """Cannot expand for a different company."""
        resp = client.post(
            f"{PREFIX}/expand",
            json={
                "company_name": "Other Corp",
                "domain": "other.com",
                "subdomain_ids": ["sd-1"],
            },
        )
        assert resp.status_code == 403

    def test_expand_auto_approve_only_2_valid(self, client, mock_expansion_runner, artifacts_root):
        """Pipeline B only supports checkpoint 2 for auto-approve."""
        _write_td_manifest(
            artifacts_root, "test-co",
            taxonomy_version=1, status="discovery_complete",
        )
        resp = client.post(
            f"{PREFIX}/expand",
            json={
                **MINIMAL_PAYLOAD,
                "subdomain_ids": ["sd-1"],
                "auto_approve_checkpoints": [2],
            },
        )
        assert resp.status_code == 202

    def test_expand_auto_approve_invalid_checkpoint_422(self, client):
        """Pipeline B rejects checkpoint values other than 2."""
        resp = client.post(
            f"{PREFIX}/expand",
            json={
                **MINIMAL_PAYLOAD,
                "subdomain_ids": ["sd-1"],
                "auto_approve_checkpoints": [1],
            },
        )
        assert resp.status_code == 422

    def test_expand_extra_fields_rejected_422(self, client):
        """Extra fields on expand request must be rejected."""
        resp = client.post(
            f"{PREFIX}/expand",
            json={
                **MINIMAL_PAYLOAD,
                "subdomain_ids": ["sd-1"],
                "bogus_field": True,
            },
        )
        assert resp.status_code == 422

    def test_expand_with_product_slug(self, client, mock_expansion_runner, artifacts_root):
        """Expansion with product_slug uses effective_slug."""
        _write_td_manifest(
            artifacts_root, "test-co__cards",
            taxonomy_version=1, status="discovery_complete",
        )
        resp = client.post(
            f"{PREFIX}/expand",
            json={
                **MINIMAL_PAYLOAD,
                "product_slug": "cards",
                "subdomain_ids": ["sd-1"],
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["effective_slug"] == "test-co__cards"


# ═══════════════════════════════════════════════════════════════════════
# GET /{slug}/expansion-status
# ═══════════════════════════════════════════════════════════════════════


class TestGetExpansionStatus:
    """Tests for GET /topic-discovery/{slug}/expansion-status."""

    def test_expansion_status_found(self, client, artifacts_root):
        from core.models.topic_discovery import SubdomainNode, TaxonomyTree
        from core.topic_discovery.storage import TopicDiscoveryStorage

        storage = TopicDiscoveryStorage(artifacts_root, "test-co")
        tree = TaxonomyTree(
            domain_name="test.com",
            root_nodes=[
                SubdomainNode(
                    id="sd-1", name="Finance", priority_score=0.9,
                    expansion_status="expanded",
                ),
                SubdomainNode(
                    id="sd-2", name="HR", priority_score=0.7,
                    expansion_status="not_expanded",
                ),
                SubdomainNode(
                    id="sd-3", name="Legal", priority_score=0.5,
                    expansion_status="failed",
                ),
            ],
            total_subdomains=3,
        )
        storage.write_taxonomy(tree)

        resp = client.get(f"{PREFIX}/test-co/expansion-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "test-co"
        assert data["total_subdomains"] == 3
        assert data["expanded"] == 1
        assert data["not_expanded"] == 2  # not_expanded + failed
        assert data["expanded_ids"] == ["sd-1"]
        assert len(data["available_for_expansion"]) == 2
        # Sorted by priority descending
        assert data["available_for_expansion"][0]["id"] == "sd-2"
        assert data["available_for_expansion"][1]["id"] == "sd-3"

    def test_expansion_status_not_found(self, client):
        resp = client.get(f"{PREFIX}/test-co/expansion-status")
        assert resp.status_code == 404

    def test_expansion_status_tenant_isolation_403(self, client):
        resp = client.get(f"{PREFIX}/other-co/expansion-status")
        assert resp.status_code == 403

    def test_expansion_status_effective_slug_other_company_blocked(self, client):
        resp = client.get(f"{PREFIX}/other-co__product/expansion-status")
        assert resp.status_code == 403
