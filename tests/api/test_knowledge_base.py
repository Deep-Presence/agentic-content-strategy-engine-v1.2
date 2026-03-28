"""Tests for Knowledge Base pipeline API endpoints."""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.tasks.models import TaskStatus
from core.services.task_store import ApprovalWindowError


# ── Minimal valid payload ─────────────────────────────────────────────

MINIMAL_PAYLOAD = {
    "company_name": "Test Co",
    "domain": "testco.com",
}


@pytest.fixture
def mock_kb_runner():
    """Mock the KB runner to complete instantly."""
    with patch(
        "api.routers.knowledge_base.run_kb_pipeline_task",
        new_callable=AsyncMock,
    ) as mock_fn:

        async def _complete_task(task_id, **kwargs):
            task_store = kwargs["task_store"]
            event_bus = kwargs["event_bus"]
            event_bus.publish(task_id, "pipeline_start", {"pipeline": "knowledge_base"})
            task_store.update_task(
                task_id, status=TaskStatus.COMPLETED, result={"stage": "complete"}
            )
            event_bus.publish(task_id, "completed", {"pipeline": "knowledge_base"})

        mock_fn.side_effect = _complete_task
        yield mock_fn


def _write_manifest(
    artifacts_root: Path,
    slug: str,
    synthesis_version: int = 1,
) -> Path:
    """Write a manifest file for guard tests."""
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


# ── TestStartKB ───────────────────────────────────────────────────────


class TestStartKB:
    def test_returns_202_with_run_id(
        self, client: TestClient, mock_kb_runner
    ) -> None:
        resp = client.post("/api/v1/knowledge-base/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 202
        data = resp.json()
        assert "run_id" in data
        assert data["pipeline"] == "knowledge_base"
        assert data["company_slug"] == "test-co"
        assert data["status"] == "running"

    def test_minimal_payload(self, client: TestClient, mock_kb_runner) -> None:
        """Only company_name + domain required."""
        resp = client.post(
            "/api/v1/knowledge-base/start",
            json={"company_name": "Test Co", "domain": "testco.com"},
        )
        assert resp.status_code == 202

    def test_mode_refresh_with_docs(
        self, client: TestClient, mock_kb_runner
    ) -> None:
        resp = client.post(
            "/api/v1/knowledge-base/start",
            json={
                **MINIMAL_PAYLOAD,
                "mode": "refresh",
                "refresh_docs": ["company_overview", "customer_reviews"],
            },
        )
        assert resp.status_code == 202

    def test_mode_single_with_doc(
        self, client: TestClient, mock_kb_runner
    ) -> None:
        resp = client.post(
            "/api/v1/knowledge-base/start",
            json={
                **MINIMAL_PAYLOAD,
                "mode": "single",
                "single_doc": "brand_perception",
            },
        )
        assert resp.status_code == 202

    def test_auto_approve_forwarded(
        self, client: TestClient, mock_kb_runner
    ) -> None:
        resp = client.post(
            "/api/v1/knowledge-base/start",
            json={**MINIMAL_PAYLOAD, "auto_approve_checkpoints": [1, 2, 3]},
        )
        assert resp.status_code == 202
        time.sleep(0.1)
        call_kwargs = mock_kb_runner.call_args
        assert call_kwargs is not None

    def test_slug_conflict_409(
        self, client: TestClient, task_store, mock_kb_runner
    ) -> None:
        task_store.create_task("knowledge_base", "test-co")
        resp = client.post("/api/v1/knowledge-base/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 409

    def test_tenant_isolation_403(
        self, client: TestClient, mock_kb_runner
    ) -> None:
        resp = client.post(
            "/api/v1/knowledge-base/start",
            json={"company_name": "Other Corp", "domain": "othercorp.com"},
        )
        assert resp.status_code == 403

    def test_validation_error_missing_domain(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/knowledge-base/start",
            json={"company_name": "Test Co"},
        )
        assert resp.status_code == 422

    def test_validation_error_missing_company_name(
        self, client: TestClient
    ) -> None:
        resp = client.post(
            "/api/v1/knowledge-base/start",
            json={"domain": "testco.com"},
        )
        assert resp.status_code == 422

    def test_optional_fields_accepted(
        self, client: TestClient, mock_kb_runner
    ) -> None:
        resp = client.post(
            "/api/v1/knowledge-base/start",
            json={
                **MINIMAL_PAYLOAD,
                "language": "en",
                "region": "us",
                "internal_sources": ["/path/to/notes.md"],
                "additional_constraints": "Focus on enterprise segment",
                "staleness_threshold_days": 60,
            },
        )
        assert resp.status_code == 202

    def test_product_slug_effective_slug(
        self, client: TestClient, mock_kb_runner
    ) -> None:
        resp = client.post(
            "/api/v1/knowledge-base/start",
            json={**MINIMAL_PAYLOAD, "product_slug": "corporate-card"},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["effective_slug"] == "test-co__corporate-card"


# ── TestStartKBGuard ──────────────────────────────────────────────────


class TestStartKBGuard:
    def test_returns_200_when_manifest_and_synthesis_exist(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        _write_manifest(artifacts_root, "test-co", synthesis_version=1)
        resp = client.post("/api/v1/knowledge-base/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()
        assert data["already_exists"] is True
        assert data["status"] == "already_exists"
        assert "force_rerun" in data["message"].lower()

    def test_no_guard_when_manifest_missing(
        self, client: TestClient, artifacts_root: Path, mock_kb_runner
    ) -> None:
        # No manifest at all → proceed
        resp = client.post("/api/v1/knowledge-base/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 202

    def test_force_rerun_bypasses_guard(
        self, client: TestClient, artifacts_root: Path, mock_kb_runner
    ) -> None:
        _write_manifest(artifacts_root, "test-co", synthesis_version=1)
        resp = client.post(
            "/api/v1/knowledge-base/start",
            json={**MINIMAL_PAYLOAD, "force_rerun": True},
        )
        assert resp.status_code == 202
        assert resp.json()["already_exists"] is False

    def test_no_guard_when_synthesis_version_zero(
        self, client: TestClient, artifacts_root: Path, mock_kb_runner
    ) -> None:
        """Partial run (manifest exists but synthesis never completed) → proceed."""
        _write_manifest(artifacts_root, "test-co", synthesis_version=0)
        resp = client.post("/api/v1/knowledge-base/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 202


# ── TestKBStatus ──────────────────────────────────────────────────────


class TestKBStatus:
    def test_status_running(
        self, client: TestClient, task_store
    ) -> None:
        task = task_store.create_task("knowledge_base", "test-co")
        resp = client.get(f"/api/v1/knowledge-base/{task.task_id}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["company_slug"] == "test-co"

    def test_status_completed(
        self, client: TestClient, mock_kb_runner
    ) -> None:
        resp = client.post("/api/v1/knowledge-base/start", json=MINIMAL_PAYLOAD)
        run_id = resp.json()["run_id"]
        time.sleep(0.3)
        status_resp = client.get(f"/api/v1/knowledge-base/{run_id}/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "completed"

    def test_not_found_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/knowledge-base/nonexistent-id/status")
        assert resp.status_code == 404


# ── TestKBApprove ─────────────────────────────────────────────────────


class TestKBApprove:
    def test_approve_success(
        self, client: TestClient, task_store, event_bus
    ) -> None:
        task = task_store.create_task("knowledge_base", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "kb_checkpoint_1", "status": "pending_approval"},
        )
        resp = client.post(
            f"/api/v1/knowledge-base/{task.task_id}/approve",
            json={"decision": "approve"},
        )
        assert resp.status_code == 200
        assert resp.json()["decision"] == "approve"

    def test_revise_with_note(
        self, client: TestClient, task_store, event_bus
    ) -> None:
        task = task_store.create_task("knowledge_base", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "kb_checkpoint_1", "status": "pending_approval"},
        )
        resp = client.post(
            f"/api/v1/knowledge-base/{task.task_id}/approve",
            json={"decision": "revise", "revision_note": "Add more detail"},
        )
        assert resp.status_code == 200
        assert resp.json()["decision"] == "revise"
        assert resp.json()["revision_note"] == "Add more detail"

    def test_revise_constructs_revision_notes_dict(
        self, client: TestClient, task_store, event_bus
    ) -> None:
        """CX-3: Verify that revise decisions construct revision_notes dict keyed by doc types."""
        task = task_store.create_task("knowledge_base", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "kb_checkpoint_1", "status": "pending_approval"},
        )
        with patch.object(task_store, "submit_approval", wraps=task_store.submit_approval) as spy:
            client.post(
                f"/api/v1/knowledge-base/{task.task_id}/approve",
                json={"decision": "revise", "revision_note": "Needs more depth"},
            )
            spy.assert_called_once()
            call_kwargs = spy.call_args
            approval_data = call_kwargs.kwargs.get("approval_data") or (
                call_kwargs[1].get("approval_data") if len(call_kwargs) > 1 else None
            )
            assert approval_data is not None
            assert "revision_notes" in approval_data
            assert approval_data["revision_notes"] == {
                "company_overview": "Needs more depth",
                "customer_reviews": "Needs more depth",
                "competitor_registry": "Needs more depth",
            }

    def test_revise_checkpoint_2_maps_correct_doc_types(
        self, client: TestClient, task_store, event_bus
    ) -> None:
        """CX-3: checkpoint 2 maps to weakness_analysis + brand_perception."""
        task = task_store.create_task("knowledge_base", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "kb_checkpoint_2", "status": "pending_approval"},
        )
        with patch.object(task_store, "submit_approval", wraps=task_store.submit_approval) as spy:
            client.post(
                f"/api/v1/knowledge-base/{task.task_id}/approve",
                json={"decision": "revise", "revision_note": "Fix weaknesses"},
            )
            spy.assert_called_once()
            call_kwargs = spy.call_args
            approval_data = call_kwargs.kwargs.get("approval_data") or (
                call_kwargs[1].get("approval_data") if len(call_kwargs) > 1 else None
            )
            assert approval_data is not None
            assert set(approval_data["revision_notes"].keys()) == {
                "weakness_analysis",
                "brand_perception",
            }

    def test_reject(
        self, client: TestClient, task_store, event_bus
    ) -> None:
        task = task_store.create_task("knowledge_base", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "kb_checkpoint_3", "status": "pending_approval"},
        )
        resp = client.post(
            f"/api/v1/knowledge-base/{task.task_id}/approve",
            json={"decision": "reject"},
        )
        assert resp.status_code == 200
        assert resp.json()["decision"] == "reject"

    def test_not_pending_409(
        self, client: TestClient, task_store
    ) -> None:
        task = task_store.create_task("knowledge_base", "test-co")
        resp = client.post(
            f"/api/v1/knowledge-base/{task.task_id}/approve",
            json={"decision": "approve"},
        )
        assert resp.status_code == 409

    def test_tenant_isolation_403(
        self, client: TestClient, task_store
    ) -> None:
        task = task_store.create_task("knowledge_base", "other-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "kb_checkpoint_1"},
        )
        resp = client.post(
            f"/api/v1/knowledge-base/{task.task_id}/approve",
            json={"decision": "approve"},
        )
        assert resp.status_code == 403

    def test_duplicate_approval_returns_409(
        self, client: TestClient, task_store, event_bus
    ) -> None:
        """Second approval with stale nonce returns 409."""
        task = task_store.create_task("knowledge_base", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={
                "stage": "kb_checkpoint_1",
                "checkpoint_nonce": "nonce-abc",
            },
        )
        # First approval succeeds
        resp1 = client.post(
            f"/api/v1/knowledge-base/{task.task_id}/approve",
            json={"decision": "approve"},
        )
        assert resp1.status_code == 200

        # Put task back into pending with a NEW nonce (simulates pipeline resuming
        # and hitting the next checkpoint)
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={
                "stage": "kb_checkpoint_2",
                "checkpoint_nonce": "nonce-def",
            },
        )

        # Replay old nonce → 409
        with patch.object(
            task_store,
            "submit_approval",
            side_effect=ApprovalWindowError("stale nonce"),
        ):
            resp2 = client.post(
                f"/api/v1/knowledge-base/{task.task_id}/approve",
                json={"decision": "approve"},
            )
            assert resp2.status_code == 409


# ── TestKBValidation ──────────────────────────────────────────────────


class TestKBValidation:
    def test_mode_single_without_single_doc_422(
        self, client: TestClient
    ) -> None:
        resp = client.post(
            "/api/v1/knowledge-base/start",
            json={**MINIMAL_PAYLOAD, "mode": "single"},
        )
        assert resp.status_code == 422

    def test_mode_refresh_without_refresh_docs_422(
        self, client: TestClient
    ) -> None:
        resp = client.post(
            "/api/v1/knowledge-base/start",
            json={**MINIMAL_PAYLOAD, "mode": "refresh"},
        )
        assert resp.status_code == 422

    def test_mode_refresh_with_empty_refresh_docs_422(
        self, client: TestClient
    ) -> None:
        resp = client.post(
            "/api/v1/knowledge-base/start",
            json={**MINIMAL_PAYLOAD, "mode": "refresh", "refresh_docs": []},
        )
        assert resp.status_code == 422

    def test_auto_approve_invalid_values_422(
        self, client: TestClient
    ) -> None:
        resp = client.post(
            "/api/v1/knowledge-base/start",
            json={**MINIMAL_PAYLOAD, "auto_approve_checkpoints": [0, 4, 99]},
        )
        assert resp.status_code == 422

    def test_auto_approve_valid_values_accepted(
        self, client: TestClient, mock_kb_runner
    ) -> None:
        resp = client.post(
            "/api/v1/knowledge-base/start",
            json={**MINIMAL_PAYLOAD, "auto_approve_checkpoints": [1, 3]},
        )
        assert resp.status_code == 202

    def test_auto_approve_partial_invalid_422(
        self, client: TestClient
    ) -> None:
        resp = client.post(
            "/api/v1/knowledge-base/start",
            json={**MINIMAL_PAYLOAD, "auto_approve_checkpoints": [1, 5]},
        )
        assert resp.status_code == 422


# ── TestKBAuth ────────────────────────────────────────────────────────


class TestKBAuth:
    def test_unauthenticated_401(self, public_client: TestClient) -> None:
        resp = public_client.post(
            "/api/v1/knowledge-base/start", json=MINIMAL_PAYLOAD
        )
        assert resp.status_code == 401

    def test_viewer_forbidden_start_403(
        self, viewer_client: TestClient
    ) -> None:
        resp = viewer_client.post(
            "/api/v1/knowledge-base/start", json=MINIMAL_PAYLOAD
        )
        assert resp.status_code == 403

    def test_viewer_can_read_status(
        self, viewer_client: TestClient, task_store
    ) -> None:
        task = task_store.create_task("knowledge_base", "test-co")
        resp = viewer_client.get(
            f"/api/v1/knowledge-base/{task.task_id}/status"
        )
        assert resp.status_code == 200


# ── TestKBHealth ─────────────────────────────────────────────────────


class TestKBHealth:
    """GET /{slug}/health endpoint tests."""

    def test_empty_kb_all_missing_score_zero(
        self, client: TestClient, artifacts_root: Path,
    ) -> None:
        resp = client.get("/api/v1/knowledge-base/test-co/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_score"] == 0.0
        assert len(data["missing_docs"]) == 5

    def test_kb_with_fresh_docs(
        self, client: TestClient, artifacts_root: Path,
    ) -> None:
        from core.research.knowledge_base.storage import KBStorage

        storage = KBStorage(artifacts_root, "test-co")
        for dt_val in ["company_overview", "customer_reviews", "competitor_registry",
                        "weakness_analysis", "brand_perception"]:
            from core.models.knowledge_base import KBDocType
            storage.write_version(KBDocType(dt_val), f"# {dt_val}\n\nContent.")

        resp = client.get("/api/v1/knowledge-base/test-co/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_score"] > 0
        assert len(data["missing_docs"]) == 0
        assert len(data["stale_docs"]) == 0

    def test_tenant_isolation_403(
        self, client: TestClient, artifacts_root: Path,
    ) -> None:
        resp = client.get("/api/v1/knowledge-base/other-co/health")
        assert resp.status_code == 403

    def test_threshold_override_via_query(
        self, client: TestClient, artifacts_root: Path,
    ) -> None:
        from core.models.knowledge_base import KBDocType
        from core.research.knowledge_base.storage import KBStorage

        storage = KBStorage(artifacts_root, "test-co")
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "# Overview")

        resp = client.get(
            "/api/v1/knowledge-base/test-co/health?threshold_override=1",
        )
        assert resp.status_code == 200

    def test_unauthenticated_401(
        self, public_client: TestClient,
    ) -> None:
        resp = public_client.get("/api/v1/knowledge-base/test-co/health")
        assert resp.status_code == 401


# ── TestRefreshStale ─────────────────────────────────────────────────


class TestRefreshStale:
    """POST /{slug}/refresh-stale endpoint tests."""

    def test_stale_docs_return_202(
        self, client: TestClient, artifacts_root: Path, mock_kb_runner,
    ) -> None:
        """Empty KB has all docs missing → 202 with run_id."""
        resp = client.post(
            "/api/v1/knowledge-base/test-co/refresh-stale",
            json={"domain": "testco.com"},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert "run_id" in data
        assert data["pipeline"] == "knowledge_base"

    def test_all_fresh_returns_200(
        self, client: TestClient, artifacts_root: Path,
    ) -> None:
        from core.models.knowledge_base import KBDocType
        from core.research.knowledge_base.storage import KBStorage

        storage = KBStorage(artifacts_root, "test-co")
        for dt_val in ["company_overview", "customer_reviews", "competitor_registry",
                        "weakness_analysis", "brand_perception"]:
            storage.write_version(KBDocType(dt_val), f"# {dt_val}\n\nContent.")

        resp = client.post(
            "/api/v1/knowledge-base/test-co/refresh-stale",
            json={"domain": "testco.com"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["already_exists"] is True
        assert "fresh" in data["message"].lower()

    def test_tenant_isolation_403(
        self, client: TestClient,
    ) -> None:
        resp = client.post(
            "/api/v1/knowledge-base/other-co/refresh-stale",
            json={"domain": "other.com"},
        )
        assert resp.status_code == 403

    def test_viewer_role_403(
        self, viewer_client: TestClient,
    ) -> None:
        resp = viewer_client.post(
            "/api/v1/knowledge-base/test-co/refresh-stale",
            json={"domain": "testco.com"},
        )
        assert resp.status_code == 403

    def test_unauthenticated_401(
        self, public_client: TestClient,
    ) -> None:
        resp = public_client.post(
            "/api/v1/knowledge-base/test-co/refresh-stale",
            json={"domain": "testco.com"},
        )
        assert resp.status_code == 401

    def test_stale_docs_topologically_sorted(self) -> None:
        """_topological_sort_stale respects DAG order."""
        from api.routers.knowledge_base import _topological_sort_stale

        # weakness_analysis depends on company_overview + competitor_registry
        stale = ["weakness_analysis", "company_overview", "competitor_registry"]
        sorted_docs = _topological_sort_stale(stale)
        co_idx = sorted_docs.index("company_overview")
        cr_idx = sorted_docs.index("competitor_registry")
        wa_idx = sorted_docs.index("weakness_analysis")
        assert co_idx < wa_idx
        assert cr_idx < wa_idx
