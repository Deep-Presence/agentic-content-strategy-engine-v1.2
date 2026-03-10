"""Tests for Audience Persona pipeline API endpoints.

Strict TDD — all tests written before router/runner implementation.
Covers: start, status, approve/briefs, approve/profiles, add-persona,
standalone-approve, list-personas, auth.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.tasks.event_bus import EventBus
from api.tasks.models import TaskStatus
from api.tasks.store import TaskStore
from core.services.task_store import ApprovalWindowError


# ── Minimal valid payload ─────────────────────────────────────────────

MINIMAL_PAYLOAD = {
    "company_name": "Test Co",
    "domain": "testco.com",
}

PREFIX = "/api/v1/audience-persona"


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_ap_runner():
    """Mock the AP pipeline runner to complete instantly."""
    with patch(
        "api.routers.audience_persona.run_audience_persona_pipeline_task",
        new_callable=AsyncMock,
    ) as mock_fn:

        async def _complete_task(task_id, **kwargs):
            task_store = kwargs["task_store"]
            event_bus = kwargs["event_bus"]
            event_bus.publish(task_id, "pipeline_start", {"pipeline": "audience_persona"})
            task_store.update_task(
                task_id, status=TaskStatus.COMPLETED, result={"stage": "complete"}
            )
            event_bus.publish(task_id, "completed", {"pipeline": "audience_persona"})

        mock_fn.side_effect = _complete_task
        yield mock_fn


@pytest.fixture
def mock_standalone_runner():
    """Mock the standalone single-persona generator runner."""
    with patch(
        "api.routers.audience_persona.run_single_persona_generator_task",
        new_callable=AsyncMock,
    ) as mock_fn:

        async def _complete_task(task_id, **kwargs):
            task_store = kwargs["task_store"]
            task_store.update_task(
                task_id, status=TaskStatus.COMPLETED, result={"persona_id": "test-persona"}
            )

        mock_fn.side_effect = _complete_task
        yield mock_fn


def _write_ap_manifest(
    artifacts_root: Path,
    slug: str,
    personas: dict | None = None,
    kb_synthesis_version: int | None = None,
) -> Path:
    """Write an AP manifest for guard tests."""
    ap_dir = artifacts_root / "audience_personas" / slug
    ap_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "slug": slug,
        "personas": personas or {},
        "kb_synthesis_version": kb_synthesis_version,
    }
    manifest_path = ap_dir / "_manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    return manifest_path


def _write_kb_manifest(
    artifacts_root: Path,
    slug: str,
    synthesis_version: int = 1,
) -> Path:
    """Write a KB manifest for staleness tests."""
    kb_dir = artifacts_root / "knowledge_base" / slug
    kb_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "company_slug": slug,
        "synthesis_version": synthesis_version,
        "documents": {},
    }
    manifest_path = kb_dir / "_manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    return manifest_path


# ═══════════════════════════════════════════════════════════════════════
# TestStartAudiencePersona
# ═══════════════════════════════════════════════════════════════════════


class TestStartAudiencePersona:
    def test_returns_202_with_run_id(
        self, client: TestClient, mock_ap_runner
    ) -> None:
        resp = client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 202
        data = resp.json()
        assert "run_id" in data
        assert data["pipeline"] == "audience_persona"
        assert data["company_slug"] == "test-co"
        assert data["status"] == "running"

    def test_guard_200_when_fresh_personas_exist(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        """Guard returns 200 when approved (fresh|stale) personas exist."""
        _write_ap_manifest(
            artifacts_root,
            "test-co",
            personas={
                "cto-persona": {
                    "persona_id": "cto-persona",
                    "persona_name": "CTO",
                    "status": "fresh",
                    "current_version": 1,
                }
            },
        )
        resp = client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()
        assert data["already_exists"] is True

    def test_force_rerun_bypasses_guard(
        self, client: TestClient, artifacts_root: Path, mock_ap_runner
    ) -> None:
        _write_ap_manifest(
            artifacts_root,
            "test-co",
            personas={
                "cto-persona": {
                    "persona_id": "cto-persona",
                    "persona_name": "CTO",
                    "status": "fresh",
                    "current_version": 1,
                }
            },
        )
        resp = client.post(
            f"{PREFIX}/start", json={**MINIMAL_PAYLOAD, "force_rerun": True}
        )
        assert resp.status_code == 202
        assert resp.json()["already_exists"] is False

    def test_kb_staleness_bypasses_guard(
        self, client: TestClient, artifacts_root: Path, mock_ap_runner
    ) -> None:
        """If KB synthesis version > AP manifest's kb_synthesis_version, run."""
        _write_ap_manifest(
            artifacts_root,
            "test-co",
            personas={
                "cto-persona": {
                    "persona_id": "cto-persona",
                    "persona_name": "CTO",
                    "status": "fresh",
                    "current_version": 1,
                }
            },
            kb_synthesis_version=1,
        )
        _write_kb_manifest(artifacts_root, "test-co", synthesis_version=2)
        resp = client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 202

    def test_pending_review_only_does_not_guard(
        self, client: TestClient, artifacts_root: Path, mock_ap_runner
    ) -> None:
        """Only pending_review personas → not counted as active → run."""
        _write_ap_manifest(
            artifacts_root,
            "test-co",
            personas={
                "cto-persona": {
                    "persona_id": "cto-persona",
                    "persona_name": "CTO",
                    "status": "pending_review",
                    "current_version": 1,
                }
            },
        )
        resp = client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 202

    def test_archived_only_does_not_guard(
        self, client: TestClient, artifacts_root: Path, mock_ap_runner
    ) -> None:
        """Only archived personas → not counted as active → run."""
        _write_ap_manifest(
            artifacts_root,
            "test-co",
            personas={
                "cto-persona": {
                    "persona_id": "cto-persona",
                    "persona_name": "CTO",
                    "status": "archived",
                    "current_version": 1,
                }
            },
        )
        resp = client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 202

    def test_no_manifest_proceeds(
        self, client: TestClient, mock_ap_runner
    ) -> None:
        resp = client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 202

    def test_slug_conflict_409(
        self, client: TestClient, task_store: TaskStore, mock_ap_runner
    ) -> None:
        task_store.create_task("audience_persona", "test-co")
        resp = client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 409

    def test_tenant_isolation_403(
        self, client: TestClient, mock_ap_runner
    ) -> None:
        resp = client.post(
            f"{PREFIX}/start",
            json={"company_name": "Other Corp", "domain": "othercorp.com"},
        )
        assert resp.status_code == 403

    def test_validation_missing_domain(self, client: TestClient) -> None:
        resp = client.post(f"{PREFIX}/start", json={"company_name": "Test Co"})
        assert resp.status_code == 422

    def test_validation_max_personas_out_of_range(
        self, client: TestClient
    ) -> None:
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "max_personas": 10},
        )
        assert resp.status_code == 422

    def test_validation_invalid_auto_approve(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "auto_approve_checkpoints": [3]},
        )
        assert resp.status_code == 422

    def test_product_slug_effective_slug(
        self, client: TestClient, mock_ap_runner
    ) -> None:
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "product_slug": "corporate-card"},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["effective_slug"] == "test-co__corporate-card"


# ═══════════════════════════════════════════════════════════════════════
# TestAudiencePersonaStatus
# ═══════════════════════════════════════════════════════════════════════


class TestAudiencePersonaStatus:
    def test_status_running(
        self, client: TestClient, task_store: TaskStore
    ) -> None:
        task = task_store.create_task("audience_persona", "test-co")
        resp = client.get(f"{PREFIX}/{task.task_id}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["company_slug"] == "test-co"

    def test_status_completed(
        self, client: TestClient, mock_ap_runner
    ) -> None:
        resp = client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        run_id = resp.json()["run_id"]
        time.sleep(0.3)
        status_resp = client.get(f"{PREFIX}/{run_id}/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "completed"

    def test_not_found_404(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/nonexistent-id/status")
        assert resp.status_code == 404

    def test_tenant_isolation_403(
        self, client: TestClient, task_store: TaskStore
    ) -> None:
        task = task_store.create_task("audience_persona", "other-co")
        resp = client.get(f"{PREFIX}/{task.task_id}/status")
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# TestApproveBriefs (HITL-1)
# ═══════════════════════════════════════════════════════════════════════


class TestApproveBriefs:
    def _pending_task(
        self, task_store: TaskStore, nonce: str = "nonce-abc"
    ) -> str:
        """Create a task pending at persona_brief_review."""
        task = task_store.create_task("audience_persona", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={
                "stage": "persona_brief_review",
                "status": "pending_persona_brief_approval",
                "checkpoint_nonce": nonce,
            },
        )
        return task.task_id

    def test_approve_all_success(
        self, client: TestClient, task_store: TaskStore, event_bus: EventBus
    ) -> None:
        task_id = self._pending_task(task_store)
        resp = client.post(
            f"{PREFIX}/{task_id}/approve/briefs",
            json={"batch_decision": "approve_all"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["stage"] == "persona_brief_review"

    def test_partial_with_brief_reviews(
        self, client: TestClient, task_store: TaskStore, event_bus: EventBus
    ) -> None:
        task_id = self._pending_task(task_store)
        resp = client.post(
            f"{PREFIX}/{task_id}/approve/briefs",
            json={
                "batch_decision": "partial",
                "brief_reviews": [
                    {"brief_id": "pb-001", "decision": "approve"},
                    {"brief_id": "pb-002", "decision": "reject"},
                ],
            },
        )
        assert resp.status_code == 200

    def test_partial_with_added_briefs(
        self, client: TestClient, task_store: TaskStore, event_bus: EventBus
    ) -> None:
        task_id = self._pending_task(task_store)
        resp = client.post(
            f"{PREFIX}/{task_id}/approve/briefs",
            json={
                "batch_decision": "partial",
                "added_briefs": [
                    {"persona_name": "New Persona", "tagline": "A new one"},
                ],
            },
        )
        assert resp.status_code == 200

    def test_reject_all(
        self, client: TestClient, task_store: TaskStore, event_bus: EventBus
    ) -> None:
        task_id = self._pending_task(task_store)
        resp = client.post(
            f"{PREFIX}/{task_id}/approve/briefs",
            json={"batch_decision": "reject_all"},
        )
        assert resp.status_code == 200

    def test_approval_data_shape(
        self, client: TestClient, task_store: TaskStore, event_bus: EventBus
    ) -> None:
        """Verify approval_data matches _process_brief_resume format."""
        task_id = self._pending_task(task_store)
        with patch.object(
            task_store, "submit_approval", wraps=task_store.submit_approval
        ) as spy:
            client.post(
                f"{PREFIX}/{task_id}/approve/briefs",
                json={
                    "batch_decision": "partial",
                    "brief_reviews": [
                        {"brief_id": "pb-001", "decision": "approve"},
                        {
                            "brief_id": "pb-002",
                            "decision": "modify",
                            "modified_brief": {
                                "persona_name": "Updated CTO",
                                "tagline": "Tech leader",
                            },
                        },
                    ],
                    "added_briefs": [
                        {"persona_name": "Manual Persona"},
                    ],
                },
            )
            spy.assert_called_once()
            call_kwargs = spy.call_args
            approval_data = call_kwargs.kwargs.get("approval_data") or (
                call_kwargs[1].get("approval_data") if len(call_kwargs) > 1 else None
            )
            assert approval_data is not None
            assert "batch_decision" in approval_data
            assert "brief_reviews" in approval_data
            assert "added_briefs" in approval_data
            assert approval_data["batch_decision"] == "partial"
            assert len(approval_data["brief_reviews"]) == 2
            assert len(approval_data["added_briefs"]) == 1

    def test_stage_mismatch_409(
        self, client: TestClient, task_store: TaskStore
    ) -> None:
        """Pending at profile_review but trying to approve briefs → 409."""
        task = task_store.create_task("audience_persona", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={
                "stage": "persona_profile_review",
                "checkpoint_nonce": "nonce-abc",
            },
        )
        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/briefs",
            json={"batch_decision": "approve_all"},
        )
        assert resp.status_code == 409

    def test_not_pending_409(
        self, client: TestClient, task_store: TaskStore
    ) -> None:
        task = task_store.create_task("audience_persona", "test-co")
        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/briefs",
            json={"batch_decision": "approve_all"},
        )
        assert resp.status_code == 409

    def test_tenant_isolation_403(
        self, client: TestClient, task_store: TaskStore
    ) -> None:
        task = task_store.create_task("audience_persona", "other-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "persona_brief_review"},
        )
        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/briefs",
            json={"batch_decision": "approve_all"},
        )
        assert resp.status_code == 403

    def test_stale_nonce_replay_409(
        self, client: TestClient, task_store: TaskStore, event_bus: EventBus
    ) -> None:
        """Replay with old nonce → ApprovalWindowError → 409."""
        task_id = self._pending_task(task_store, nonce="nonce-abc")
        with patch.object(
            task_store,
            "submit_approval",
            side_effect=ApprovalWindowError("stale nonce"),
        ):
            resp = client.post(
                f"{PREFIX}/{task_id}/approve/briefs",
                json={"batch_decision": "approve_all"},
            )
            assert resp.status_code == 409

    def test_partial_empty_reviews_422(self, client: TestClient, task_store: TaskStore) -> None:
        """batch_decision='partial' with no reviews or added_briefs → 422."""
        task_id = self._pending_task(task_store)
        resp = client.post(
            f"{PREFIX}/{task_id}/approve/briefs",
            json={"batch_decision": "partial"},
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# TestApproveProfiles (HITL-2)
# ═══════════════════════════════════════════════════════════════════════


class TestApproveProfiles:
    def _pending_task(
        self, task_store: TaskStore, nonce: str = "nonce-xyz"
    ) -> str:
        """Create a task pending at persona_profile_review."""
        task = task_store.create_task("audience_persona", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={
                "stage": "persona_profile_review",
                "status": "pending_persona_profile_approval",
                "checkpoint_nonce": nonce,
            },
        )
        return task.task_id

    def test_approve_success(
        self, client: TestClient, task_store: TaskStore, event_bus: EventBus
    ) -> None:
        task_id = self._pending_task(task_store)
        resp = client.post(
            f"{PREFIX}/{task_id}/approve/profiles",
            json={
                "profile_reviews": [
                    {"persona_id": "cto-persona", "decision": "approve"},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["stage"] == "persona_profile_review"

    def test_revise_with_note(
        self, client: TestClient, task_store: TaskStore, event_bus: EventBus
    ) -> None:
        task_id = self._pending_task(task_store)
        resp = client.post(
            f"{PREFIX}/{task_id}/approve/profiles",
            json={
                "profile_reviews": [
                    {
                        "persona_id": "cto-persona",
                        "decision": "revise",
                        "revision_note": "Add more technical details",
                    },
                ],
            },
        )
        assert resp.status_code == 200

    def test_reject_profile(
        self, client: TestClient, task_store: TaskStore, event_bus: EventBus
    ) -> None:
        task_id = self._pending_task(task_store)
        resp = client.post(
            f"{PREFIX}/{task_id}/approve/profiles",
            json={
                "profile_reviews": [
                    {"persona_id": "cto-persona", "decision": "reject"},
                ],
            },
        )
        assert resp.status_code == 200

    def test_approval_data_shape(
        self, client: TestClient, task_store: TaskStore, event_bus: EventBus
    ) -> None:
        """Verify approval_data matches _process_profile_resume format."""
        task_id = self._pending_task(task_store)
        with patch.object(
            task_store, "submit_approval", wraps=task_store.submit_approval
        ) as spy:
            client.post(
                f"{PREFIX}/{task_id}/approve/profiles",
                json={
                    "profile_reviews": [
                        {"persona_id": "cto-persona", "decision": "approve"},
                        {
                            "persona_id": "dev-lead",
                            "decision": "revise",
                            "revision_note": "More depth",
                        },
                    ],
                },
            )
            spy.assert_called_once()
            call_kwargs = spy.call_args
            approval_data = call_kwargs.kwargs.get("approval_data") or (
                call_kwargs[1].get("approval_data") if len(call_kwargs) > 1 else None
            )
            assert approval_data is not None
            assert "profile_reviews" in approval_data
            assert len(approval_data["profile_reviews"]) == 2

    def test_stage_mismatch_409(
        self, client: TestClient, task_store: TaskStore
    ) -> None:
        """Pending at brief_review but trying to approve profiles → 409."""
        task = task_store.create_task("audience_persona", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={
                "stage": "persona_brief_review",
                "checkpoint_nonce": "nonce-abc",
            },
        )
        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/profiles",
            json={
                "profile_reviews": [
                    {"persona_id": "cto-persona", "decision": "approve"},
                ],
            },
        )
        assert resp.status_code == 409

    def test_not_pending_409(
        self, client: TestClient, task_store: TaskStore
    ) -> None:
        task = task_store.create_task("audience_persona", "test-co")
        resp = client.post(
            f"{PREFIX}/{task.task_id}/approve/profiles",
            json={
                "profile_reviews": [
                    {"persona_id": "cto-persona", "decision": "approve"},
                ],
            },
        )
        assert resp.status_code == 409

    def test_stale_nonce_replay_409(
        self, client: TestClient, task_store: TaskStore, event_bus: EventBus
    ) -> None:
        task_id = self._pending_task(task_store, nonce="nonce-xyz")
        with patch.object(
            task_store,
            "submit_approval",
            side_effect=ApprovalWindowError("stale nonce"),
        ):
            resp = client.post(
                f"{PREFIX}/{task_id}/approve/profiles",
                json={
                    "profile_reviews": [
                        {"persona_id": "cto-persona", "decision": "approve"},
                    ],
                },
            )
            assert resp.status_code == 409

    def test_empty_reviews_422(self, client: TestClient, task_store: TaskStore) -> None:
        """profile_reviews must have at least 1 item."""
        task_id = self._pending_task(task_store)
        resp = client.post(
            f"{PREFIX}/{task_id}/approve/profiles",
            json={"profile_reviews": []},
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# TestAddPersona (standalone)
# ═══════════════════════════════════════════════════════════════════════


class TestAddPersona:
    def test_success_returns_persona_id_and_task_id(
        self, client: TestClient, mock_standalone_runner
    ) -> None:
        resp = client.post(
            f"{PREFIX}/test-co/add-persona",
            json={
                "persona_name": "Security Engineer",
                "tagline": "Enterprise security buyer",
                "description": "Evaluates security posture",
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert "persona_id" in data
        assert "task_id" in data
        assert "security-engineer" in data["persona_id"]

    def test_tenant_isolation_403(
        self, client: TestClient, mock_standalone_runner
    ) -> None:
        resp = client.post(
            f"{PREFIX}/other-co/add-persona",
            json={"persona_name": "Security Engineer"},
        )
        assert resp.status_code == 403

    def test_validation_empty_name_422(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/test-co/add-persona",
            json={"persona_name": "   "},
        )
        assert resp.status_code == 422

    def test_managed_task_lifecycle(
        self, client: TestClient, task_store: TaskStore, mock_standalone_runner
    ) -> None:
        """Verify that add-persona uses create_task + register_task_handle."""
        resp = client.post(
            f"{PREFIX}/test-co/add-persona",
            json={"persona_name": "DevOps Lead"},
        )
        assert resp.status_code == 202
        task_id = resp.json()["task_id"]
        task = task_store.get_task(task_id)
        assert task.pipeline == "audience_persona"
        assert task.company_slug == "test-co"


# ═══════════════════════════════════════════════════════════════════════
# TestStandaloneApprove
# ═══════════════════════════════════════════════════════════════════════


class TestStandaloneApprove:
    def _setup_persona(
        self, artifacts_root: Path, slug: str, persona_id: str, status: str = "pending_review"
    ) -> None:
        """Write a manifest with one persona at the given status."""
        _write_ap_manifest(
            artifacts_root,
            slug,
            personas={
                persona_id: {
                    "persona_id": persona_id,
                    "persona_name": "CTO Persona",
                    "status": status,
                    "current_version": 1,
                }
            },
        )

    def test_approve_pending_review_to_fresh(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        self._setup_persona(artifacts_root, "test-co", "cto-persona", "pending_review")
        resp = client.post(
            f"{PREFIX}/test-co/personas/cto-persona/approve",
            json={"decision": "approve"},
        )
        assert resp.status_code == 200

    def test_reject_pending_review_to_archived(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        self._setup_persona(artifacts_root, "test-co", "cto-persona", "pending_review")
        resp = client.post(
            f"{PREFIX}/test-co/personas/cto-persona/approve",
            json={"decision": "reject"},
        )
        assert resp.status_code == 200

    def test_persona_not_found_404(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        # No manifest at all
        resp = client.post(
            f"{PREFIX}/test-co/personas/nonexistent/approve",
            json={"decision": "approve"},
        )
        assert resp.status_code == 404

    def test_wrong_status_409(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        """Already fresh → cannot re-approve → 409."""
        self._setup_persona(artifacts_root, "test-co", "cto-persona", "fresh")
        resp = client.post(
            f"{PREFIX}/test-co/personas/cto-persona/approve",
            json={"decision": "approve"},
        )
        assert resp.status_code == 409

    def test_tenant_isolation_403(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        self._setup_persona(artifacts_root, "other-co", "cto-persona", "pending_review")
        resp = client.post(
            f"{PREFIX}/other-co/personas/cto-persona/approve",
            json={"decision": "approve"},
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# TestListPersonas
# ═══════════════════════════════════════════════════════════════════════


class TestListPersonas:
    def test_list_with_metadata(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        _write_ap_manifest(
            artifacts_root,
            "test-co",
            personas={
                "cto-persona": {
                    "persona_id": "cto-persona",
                    "persona_name": "CTO",
                    "tagline": "Tech leader",
                    "status": "fresh",
                    "current_version": 2,
                    "kind": "icp",
                    "word_count": 1500,
                    "created_by": "agent",
                },
                "dev-lead": {
                    "persona_id": "dev-lead",
                    "persona_name": "Dev Lead",
                    "status": "archived",
                    "current_version": 1,
                },
            },
        )
        resp = client.get(f"{PREFIX}/test-co/personas")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "test-co"
        assert data["total"] == 2
        assert len(data["personas"]) == 2
        names = {p["persona_name"] for p in data["personas"]}
        assert names == {"CTO", "Dev Lead"}

    def test_empty_list(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        resp = client.get(f"{PREFIX}/test-co/personas")
        assert resp.status_code == 200
        data = resp.json()
        assert data["personas"] == []
        assert data["total"] == 0

    def test_tenant_isolation_403(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/other-co/personas")
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# TestAudiencePersonaAuth
# ═══════════════════════════════════════════════════════════════════════


class TestAudiencePersonaAuth:
    def test_unauthenticated_401(self, public_client: TestClient) -> None:
        resp = public_client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 401

    def test_viewer_cannot_start_403(
        self, viewer_client: TestClient
    ) -> None:
        resp = viewer_client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 403

    def test_viewer_can_get_status(
        self, viewer_client: TestClient, task_store: TaskStore
    ) -> None:
        task = task_store.create_task("audience_persona", "test-co")
        resp = viewer_client.get(f"{PREFIX}/{task.task_id}/status")
        assert resp.status_code == 200
