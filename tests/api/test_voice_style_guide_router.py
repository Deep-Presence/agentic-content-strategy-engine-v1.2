"""Tests for Voice Style Guide pipeline API endpoints.

Covers: start, status, approve/authors, guide read, auth, guard.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.tasks.models import TaskStatus
from core.services.task_store import ApprovalWindowError


# ── Constants ─────────────────────────────────────────────────────────

MINIMAL_PAYLOAD = {
    "company_name": "Test Co",
    "domain": "testco.com",
}

PREFIX = "/api/v1/voice-style-guide"


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_vsg_runner():
    """Mock the VSG pipeline runner to complete instantly."""
    with patch(
        "api.routers.voice_style_guide.run_voice_style_guide_pipeline_task",
        new_callable=AsyncMock,
    ) as mock_fn:

        async def _complete_task(task_id, **kwargs):
            task_store = kwargs["task_store"]
            event_bus = kwargs["event_bus"]
            event_bus.publish(task_id, "pipeline_start", {"pipeline": "voice_style_guide"})
            task_store.update_task(
                task_id, status=TaskStatus.COMPLETED, result={"stage": "complete"}
            )
            event_bus.publish(task_id, "completed", {"pipeline": "voice_style_guide"})

        mock_fn.side_effect = _complete_task
        yield mock_fn


def _write_vsg_manifest(
    artifacts_root: Path,
    slug: str,
    guide_version: int = 0,
    guide_status: str = "missing",
) -> Path:
    """Write a VSG manifest for guard tests."""
    vsg_dir = artifacts_root / "voice_style_guide" / slug
    vsg_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "slug": slug,
        "guide": {
            "current_version": guide_version,
            "status": guide_status,
        },
        "authors": {},
    }
    manifest_path = vsg_dir / "_manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    return manifest_path


# ═══════════════════════════════════════════════════════════════════════
# POST /start
# ═══════════════════════════════════════════════════════════════════════


class TestStartVoiceStyleGuide:
    """Tests for POST /voice-style-guide/start."""

    def test_start_success(self, client, mock_vsg_runner):
        resp = client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 202
        data = resp.json()
        assert data["pipeline"] == "voice_style_guide"
        assert data["status"] == "started"
        assert "run_id" in data

    def test_start_returns_run_id(self, client, mock_vsg_runner):
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

    def test_start_custom_max_authors(self, client, mock_vsg_runner):
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "max_authors": 3},
        )
        assert resp.status_code == 202

    def test_start_invalid_max_authors_too_low(self, client):
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "max_authors": 1},
        )
        assert resp.status_code == 422

    def test_start_invalid_max_authors_too_high(self, client):
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "max_authors": 10},
        )
        assert resp.status_code == 422

    def test_start_auto_approve_valid(self, client, mock_vsg_runner):
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "auto_approve_checkpoints": [1]},
        )
        assert resp.status_code == 202

    def test_start_auto_approve_invalid_checkpoint(self, client):
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "auto_approve_checkpoints": [2]},
        )
        assert resp.status_code == 422


class TestStartVSGGuard:
    """Tests for the guard that blocks re-runs when a guide exists."""

    def test_guard_blocks_when_fresh_guide_exists(self, client, artifacts_root):
        _write_vsg_manifest(artifacts_root, "test-co", guide_version=1, guide_status="fresh")
        resp = client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "already_exists"
        assert data["already_exists"] is True

    def test_guard_allows_with_force_rerun(self, client, mock_vsg_runner, artifacts_root):
        _write_vsg_manifest(artifacts_root, "test-co", guide_version=1, guide_status="fresh")
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "force_rerun": True},
        )
        assert resp.status_code == 202

    def test_guard_allows_when_no_guide(self, client, mock_vsg_runner):
        resp = client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 202


# ═══════════════════════════════════════════════════════════════════════
# GET /{run_id}/status
# ═══════════════════════════════════════════════════════════════════════


class TestGetVSGStatus:
    """Tests for GET /voice-style-guide/{run_id}/status."""

    def test_status_returns_task(self, client, mock_vsg_runner):
        resp = client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        run_id = resp.json()["run_id"]
        status_resp = client.get(f"{PREFIX}/{run_id}/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["run_id"] == run_id

    def test_status_not_found(self, client):
        resp = client.get(f"{PREFIX}/nonexistent-123/status")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# POST /{run_id}/approve/authors
# ═══════════════════════════════════════════════════════════════════════


class TestApproveAuthors:
    """Tests for POST /voice-style-guide/{run_id}/approve/authors."""

    def test_approve_all(self, client, task_store):
        # Create a task in pending_approval state
        task = task_store.create_task("voice_style_guide", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={
                "stage": "vsg_author_review",
                "authors": [{"author_id": "a1", "name": "Author 1"}],
            },
        )

        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/authors",
            json={"batch_decision": "approve_all"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["stage"] == "vsg_author_review"

    def test_approve_wrong_stage(self, client, task_store):
        task = task_store.create_task("voice_style_guide", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "some_other_stage"},
        )

        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/authors",
            json={"batch_decision": "approve_all"},
        )
        assert resp.status_code == 409

    def test_approve_not_pending(self, client, task_store):
        task = task_store.create_task("voice_style_guide", "test-co")
        # Task is RUNNING, not PENDING_APPROVAL
        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/authors",
            json={"batch_decision": "approve_all"},
        )
        assert resp.status_code == 409

    def test_approve_partial_requires_reviews(self, client):
        resp = client.post(
            f"{PREFIX}/some-task/approve/authors",
            json={"batch_decision": "partial", "author_reviews": []},
        )
        assert resp.status_code == 422

    def test_approve_not_found(self, client):
        resp = client.post(
            f"{PREFIX}/nonexistent/approve/authors",
            json={"batch_decision": "approve_all"},
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# GET /{slug}/guide
# ═══════════════════════════════════════════════════════════════════════


class TestGetLatestGuide:
    """Tests for GET /voice-style-guide/{slug}/guide."""

    def test_guide_found(self, client, artifacts_root):
        # Write a guide via storage
        from core.research.voice_style_guide.storage import VoiceStyleGuideStorage

        storage = VoiceStyleGuideStorage(artifacts_root, "test-co")
        storage.write_guide("# Test Guide\n\nContent here.", source_authors=["author-1"])

        resp = client.get(f"{PREFIX}/test-co/guide")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "test-co"
        assert "Test Guide" in data["guide_md"]
        assert data["version"] == 1
        assert "author-1" in data["source_authors"]

    def test_guide_not_found(self, client):
        resp = client.get(f"{PREFIX}/nonexistent-slug/guide")
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# Schema Validation
# ═══════════════════════════════════════════════════════════════════════


class TestSchemaValidation:
    """Tests for request schema validation."""

    def test_author_approval_reject_all(self, client, task_store):
        task = task_store.create_task("voice_style_guide", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "vsg_author_review"},
        )

        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/authors",
            json={"batch_decision": "reject_all"},
        )
        assert resp.status_code == 200

    def test_author_approval_partial_with_reviews(self, client, task_store):
        task = task_store.create_task("voice_style_guide", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "vsg_author_review"},
        )

        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/authors",
            json={
                "batch_decision": "partial",
                "author_reviews": [
                    {"author_id": "a1", "decision": "approve"},
                    {"author_id": "a2", "decision": "reject"},
                ],
            },
        )
        assert resp.status_code == 200
