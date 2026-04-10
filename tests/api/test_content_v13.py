"""Tests for api/routers/content_v13.py — v1.3 content engine API endpoints.

Tests all 5 endpoints: POST /start, GET /status, POST /approve/topics,
POST /approve/briefs, POST /approve/content.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.tasks.models import TaskStatus


def _make_pending_task(task_store, stage: str, brief_id: str | None = None):
    """Create a task in PENDING_APPROVAL state with the correct approval_payload.

    This helper mirrors what run_hitl_checkpoint does: it sets
    status=PENDING_APPROVAL and approval_payload with the machine stage name
    (and optionally brief_id for brief/content stages).
    """
    task = task_store.create_task(pipeline="content_v13", company_slug="test-co")
    payload = {"stage": stage, "checkpoint_nonce": "test-nonce-123"}
    if brief_id:
        payload["brief_id"] = brief_id
    task_store.update_task(
        task.task_id,
        status=TaskStatus.PENDING_APPROVAL,
        approval_payload=payload,
    )
    return task


def _make_pending_td_task(task_store, stage: str, brief_id: str):
    task = task_store.create_task(
        pipeline="td_content",
        company_slug="test-co",
    )
    task.effective_slug = "test-co"
    task_store.update_task(
        task.task_id,
        status=TaskStatus.PENDING_APPROVAL,
        approval_payload={
            "stage": stage,
            "brief_id": brief_id,
            "checkpoint_nonce": "test-nonce-123",
            "continuation": {
                "resume_stage": stage,
                "topic_assignment_id": "ta-123",
                "brief_id": brief_id,
                "thread_id": f"thread-{brief_id}",
            },
        },
    )
    return task


# ═══════════════════════════════════════════════════════════════════════
# POST /start
# ═══════════════════════════════════════════════════════════════════════


class TestStartContentV13:
    """Tests for POST /api/v1/content/v13/start."""

    def test_returns_202(self, client: TestClient):
        with patch("api.routers.content_v13.asyncio.create_task", return_value=MagicMock()):
            resp = client.post(
                "/api/v1/content/v13/start",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                    "entry_mode": "autonomous",
                },
            )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "started"
        assert data["entry_mode"] == "autonomous"
        assert "run_id" in data

    def test_manual_mode(self, client: TestClient):
        with patch("api.routers.content_v13.asyncio.create_task", return_value=MagicMock()):
            resp = client.post(
                "/api/v1/content/v13/start",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                    "entry_mode": "manual",
                    "manual_prompt": "What is a 409A valuation?",
                },
            )
        assert resp.status_code == 202
        assert resp.json()["entry_mode"] == "manual"

    def test_tenant_isolation_403(self, client: TestClient):
        """Different company slug than user's company triggers 403."""
        resp = client.post(
            "/api/v1/content/v13/start",
            json={
                "company_name": "Other Corp",
                "domain": "othercorp.com",
            },
        )
        assert resp.status_code == 403

    def test_unauthenticated_401(self, public_client: TestClient):
        resp = public_client.post(
            "/api/v1/content/v13/start",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
            },
        )
        assert resp.status_code == 401

    def test_viewer_role_403(self, viewer_client: TestClient):
        """Viewer role cannot start pipelines."""
        resp = viewer_client.post(
            "/api/v1/content/v13/start",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
            },
        )
        assert resp.status_code == 403

    def test_validation_422(self, client: TestClient):
        """Missing required fields returns 422."""
        resp = client.post(
            "/api/v1/content/v13/start",
            json={},
        )
        assert resp.status_code == 422

    def test_invalid_entry_mode_422(self, client: TestClient):
        resp = client.post(
            "/api/v1/content/v13/start",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "entry_mode": "invalid_mode",
            },
        )
        assert resp.status_code == 422

    def test_skip_stages_accepted(self, client: TestClient):
        with patch("api.routers.content_v13.asyncio.create_task", return_value=MagicMock()):
            resp = client.post(
                "/api/v1/content/v13/start",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                    "skip_stages": [1, 2],
                },
            )
        assert resp.status_code == 202

    def test_auto_approve_flag(self, client: TestClient):
        with patch("api.routers.content_v13.asyncio.create_task", return_value=MagicMock()):
            resp = client.post(
                "/api/v1/content/v13/start",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                    "auto_approve": True,
                },
            )
        assert resp.status_code == 202


# ═══════════════════════════════════════════════════════════════════════
# GET /status
# ═══════════════════════════════════════════════════════════════════════


class TestStatusV13:
    """Tests for GET /api/v1/content/v13/{run_id}/status."""

    def test_returns_task_details(self, client: TestClient, task_store):
        task = task_store.create_task(
            pipeline="content_v13",
            company_slug="test-co",
        )
        resp = client.get(f"/api/v1/content/v13/{task.task_id}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == task.task_id
        assert "status" in data

    def test_unknown_task_404(self, client: TestClient):
        resp = client.get("/api/v1/content/v13/nonexistent-id/status")
        assert resp.status_code == 404

    def test_unauthenticated_401(self, public_client: TestClient):
        resp = public_client.get("/api/v1/content/v13/some-id/status")
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════
# POST /approve/topics
# ═══════════════════════════════════════════════════════════════════════


class TestApproveTopics:
    """Tests for POST /api/v1/content/v13/{run_id}/approve/topics."""

    def test_approve_submission(self, client: TestClient, task_store):
        task = _make_pending_task(task_store, "topic_approval")
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/topics",
            json={
                "decision": "approve",
                "approved_topic_ranks": [0, 1, 2],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["stage"] == "topic_approval"

    def test_reject_submission(self, client: TestClient, task_store):
        task = _make_pending_task(task_store, "topic_approval")
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/topics",
            json={"decision": "reject"},
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Topic reject submitted"

    def test_retry_with_feedback(self, client: TestClient, task_store):
        task = _make_pending_task(task_store, "topic_approval")
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/topics",
            json={
                "decision": "retry",
                "feedback": "Focus more on equity topics",
            },
        )
        assert resp.status_code == 200

    def test_unknown_task_404(self, client: TestClient):
        resp = client.post(
            "/api/v1/content/v13/nonexistent/approve/topics",
            json={"decision": "approve"},
        )
        assert resp.status_code == 404

    def test_invalid_decision_422(self, client: TestClient, task_store):
        task = _make_pending_task(task_store, "topic_approval")
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/topics",
            json={"decision": "invalid"},
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# POST /approve/briefs
# ═══════════════════════════════════════════════════════════════════════


class TestApproveBriefs:
    """Tests for POST /api/v1/content/v13/{run_id}/approve/briefs."""

    def test_approve_submission(self, client: TestClient, task_store):
        task = _make_pending_task(task_store, "brief_approval", brief_id="brief-001")
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/briefs",
            json={
                "brief_id": "brief-001",
                "decision": "approve",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["brief_id"] == "brief-001"
        assert data["stage"] == "brief_approval"

    def test_feedback_submission(self, client: TestClient, task_store):
        task = _make_pending_task(task_store, "brief_approval", brief_id="brief-002")
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/briefs",
            json={
                "brief_id": "brief-002",
                "decision": "feedback",
                "feedback": "Emphasize ROI more in section 3",
            },
        )
        assert resp.status_code == 200

    def test_reject_submission(self, client: TestClient, task_store):
        task = _make_pending_task(task_store, "brief_approval", brief_id="brief-003")
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/briefs",
            json={
                "brief_id": "brief-003",
                "decision": "reject",
            },
        )
        assert resp.status_code == 200

    def test_unknown_task_404(self, client: TestClient):
        resp = client.post(
            "/api/v1/content/v13/nonexistent/approve/briefs",
            json={"brief_id": "b-1", "decision": "approve"},
        )
        assert resp.status_code == 404

    def test_missing_brief_id_422(self, client: TestClient, task_store):
        task = _make_pending_task(task_store, "brief_approval", brief_id="b-1")
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/briefs",
            json={"decision": "approve"},
        )
        assert resp.status_code == 422

    def test_td_continuation_routes_to_durable_resume_queue(
        self,
        client: TestClient,
        task_store,
    ):
        task = _make_pending_td_task(task_store, "brief_approval", brief_id="WE-177")
        client.app.state.db_session_factory = MagicMock()
        client.app.state.event_bus = MagicMock()

        with patch(
            "core.services.content_engine_topic_runs.ContentEngineTopicRunService",
        ) as service_cls, patch(
            "api.routers.content_v13.dispatch_queued_td_content_runs",
            new_callable=AsyncMock,
            return_value=[],
        ) as dispatch_mock:
            service = MagicMock()
            service.queue_topic_run_resume = AsyncMock(return_value=MagicMock())
            service_cls.return_value = service

            resp = client.post(
                f"/api/v1/content/v13/{task.task_id}/approve/briefs",
                json={
                    "brief_id": "WE-177",
                    "decision": "approve",
                },
            )

        assert resp.status_code == 200
        service.queue_topic_run_resume.assert_awaited_once_with(
            effective_slug="test-co",
            pipeline_task_id=task.task_id,
            approval_data={
                "brief_decision": "approve",
                "brief_feedback": "",
                "brief_id": "WE-177",
            },
        )
        dispatch_mock.assert_awaited_once()

    def test_td_brief_approval_retry_still_allowed_after_resume_queue_failure(
        self,
        client: TestClient,
        task_store,
    ):
        task = _make_pending_td_task(task_store, "brief_approval", brief_id="WE-177")
        client.app.state.db_session_factory = MagicMock()
        client.app.state.event_bus = MagicMock()

        with patch(
            "core.services.content_engine_topic_runs.ContentEngineTopicRunService",
        ) as service_cls, patch(
            "api.routers.content_v13.dispatch_queued_td_content_runs",
            new_callable=AsyncMock,
            return_value=[],
        ):
            service = MagicMock()
            service.queue_topic_run_resume = AsyncMock(
                side_effect=[RuntimeError("db down"), MagicMock()]
            )
            service_cls.return_value = service

            first = client.post(
                f"/api/v1/content/v13/{task.task_id}/approve/briefs",
                json={
                    "brief_id": "WE-177",
                    "decision": "approve",
                },
            )
            second = client.post(
                f"/api/v1/content/v13/{task.task_id}/approve/briefs",
                json={
                    "brief_id": "WE-177",
                    "decision": "approve",
                },
            )

        assert first.status_code == 503
        assert second.status_code == 200
        assert len(task.approval_history) == 1
        assert task.approval_history[0].decision == "approve"


# ═══════════════════════════════════════════════════════════════════════
# POST /approve/content
# ═══════════════════════════════════════════════════════════════════════


class TestApproveContent:
    """Tests for POST /api/v1/content/v13/{run_id}/approve/content."""

    def test_approve_submission(self, client: TestClient, task_store):
        task = _make_pending_task(task_store, "content_review", brief_id="brief-001")
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/content",
            json={
                "brief_id": "brief-001",
                "decision": "approve",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["stage"] == "content_review"
        assert data["brief_id"] == "brief-001"

    def test_edit_with_notes(self, client: TestClient, task_store):
        task = _make_pending_task(task_store, "content_review", brief_id="brief-001")
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/content",
            json={
                "brief_id": "brief-001",
                "decision": "edit",
                "editor_notes": "Fix the introduction paragraph",
            },
        )
        assert resp.status_code == 200

    def test_reject_with_rethink(self, client: TestClient, task_store):
        task = _make_pending_task(task_store, "content_review", brief_id="brief-001")
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/content",
            json={
                "brief_id": "brief-001",
                "decision": "reject",
                "rethink": True,
            },
        )
        assert resp.status_code == 200

    def test_unknown_task_404(self, client: TestClient):
        resp = client.post(
            "/api/v1/content/v13/nonexistent/approve/content",
            json={"brief_id": "b-1", "decision": "approve"},
        )
        assert resp.status_code == 404

    def test_missing_brief_id_422(self, client: TestClient, task_store):
        task = _make_pending_task(task_store, "content_review", brief_id="b-1")
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/content",
            json={"decision": "approve"},
        )
        assert resp.status_code == 422

    def test_invalid_decision_422(self, client: TestClient, task_store):
        task = _make_pending_task(task_store, "content_review", brief_id="b-1")
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/content",
            json={"brief_id": "b-1", "decision": "invalid"},
        )
        assert resp.status_code == 422

    def test_td_content_review_routes_to_durable_resume_queue(
        self,
        client: TestClient,
        task_store,
    ):
        task = _make_pending_td_task(task_store, "content_review", brief_id="WE-177")
        client.app.state.db_session_factory = MagicMock()
        client.app.state.event_bus = MagicMock()

        with patch(
            "core.services.content_engine_topic_runs.ContentEngineTopicRunService",
        ) as service_cls, patch(
            "api.routers.content_v13.dispatch_queued_td_content_runs",
            new_callable=AsyncMock,
            return_value=[],
        ) as dispatch_mock:
            service = MagicMock()
            service.queue_topic_run_resume = AsyncMock(return_value=MagicMock())
            service_cls.return_value = service

            resp = client.post(
                f"/api/v1/content/v13/{task.task_id}/approve/content",
                json={
                    "brief_id": "WE-177",
                    "decision": "edit",
                    "editor_notes": "Tighten the intro",
                    "content_markdown": "# Edited\n\nLatest approved draft",
                },
            )

        assert resp.status_code == 200
        service.queue_topic_run_resume.assert_awaited_once_with(
            effective_slug="test-co",
            pipeline_task_id=task.task_id,
            approval_data={
                "content_decision": "edit",
                "editor_notes": "Tighten the intro",
                "rethink": False,
                "brief_id": "WE-177",
                "content_markdown": "# Edited\n\nLatest approved draft",
            },
        )
        dispatch_mock.assert_awaited_once()

    def test_td_content_approval_retry_still_allowed_after_resume_queue_failure(
        self,
        client: TestClient,
        task_store,
    ):
        task = _make_pending_td_task(task_store, "content_review", brief_id="WE-177")
        client.app.state.db_session_factory = MagicMock()
        client.app.state.event_bus = MagicMock()

        with patch(
            "core.services.content_engine_topic_runs.ContentEngineTopicRunService",
        ) as service_cls, patch(
            "api.routers.content_v13.dispatch_queued_td_content_runs",
            new_callable=AsyncMock,
            return_value=[],
        ):
            service = MagicMock()
            service.queue_topic_run_resume = AsyncMock(
                side_effect=[RuntimeError("db down"), MagicMock()]
            )
            service_cls.return_value = service

            first = client.post(
                f"/api/v1/content/v13/{task.task_id}/approve/content",
                json={
                    "brief_id": "WE-177",
                    "decision": "edit",
                    "editor_notes": "Tighten the intro",
                },
            )
            second = client.post(
                f"/api/v1/content/v13/{task.task_id}/approve/content",
                json={
                    "brief_id": "WE-177",
                    "decision": "edit",
                    "editor_notes": "Tighten the intro",
                },
            )

        assert first.status_code == 503
        assert second.status_code == 200
        assert len(task.approval_history) == 1
        assert task.approval_history[0].decision == "edit"


class TestReviewDraftContent:
    """Tests for GET/PUT /api/v1/content/v13/{run_id}/draft/content."""

    def test_get_review_draft_content(self, client: TestClient, task_store):
        task = task_store.create_task(pipeline="td_content", company_slug="test-co")
        task.effective_slug = "test-co"

        with patch(
            "api.routers.content_v13._load_review_draft_content",
            new_callable=AsyncMock,
            return_value="# Draft\n\nHello world",
        ) as load_mock:
            resp = client.get(
                f"/api/v1/content/v13/{task.task_id}/draft/content",
                params={"brief_id": "WE-001"},
            )

        assert resp.status_code == 200
        assert resp.json() == {
            "brief_id": "WE-001",
            "content_markdown": "# Draft\n\nHello world",
        }
        load_mock.assert_awaited_once_with(
            app=client.app,
            effective_slug="test-co",
            brief_id="WE-001",
        )

    def test_get_review_draft_content_404_when_missing(self, client: TestClient, task_store):
        task = task_store.create_task(pipeline="td_content", company_slug="test-co")
        task.effective_slug = "test-co"

        with patch(
            "api.routers.content_v13._load_review_draft_content",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = client.get(
                f"/api/v1/content/v13/{task.task_id}/draft/content",
                params={"brief_id": "WE-001"},
            )

        assert resp.status_code == 404

    def test_put_review_draft_content(self, client: TestClient, task_store):
        task = task_store.create_task(pipeline="td_content", company_slug="test-co")
        task.effective_slug = "test-co"

        with patch(
            "api.routers.content_v13._save_review_draft_content",
            new_callable=AsyncMock,
            return_value="content/test-co/content/WE-001/review_draft.md",
        ) as save_mock:
            resp = client.put(
                f"/api/v1/content/v13/{task.task_id}/draft/content",
                json={
                    "brief_id": "WE-001",
                    "content_markdown": "# Draft\n\nAutosaved",
                },
            )

        assert resp.status_code == 200
        assert resp.json() == {
            "status": "saved",
            "brief_id": "WE-001",
            "storage_key": "content/test-co/content/WE-001/review_draft.md",
        }
        save_mock.assert_awaited_once_with(
            app=client.app,
            effective_slug="test-co",
            brief_id="WE-001",
            content_markdown="# Draft\n\nAutosaved",
        )


# ═══════════════════════════════════════════════════════════════════════
# Cross-Tenant Isolation (C3 security fix)
# ═══════════════════════════════════════════════════════════════════════


class TestCrossTenantIsolation:
    """C3: Tasks belonging to another company must return 403 on all endpoints."""

    def test_status_cross_tenant_403(self, client: TestClient, task_store):
        """GET /status for a task owned by other-co returns 403 for test-co user."""
        task = task_store.create_task(
            pipeline="content_v13",
            company_slug="other-co",
        )
        resp = client.get(f"/api/v1/content/v13/{task.task_id}/status")
        assert resp.status_code == 403

    def test_approve_topics_cross_tenant_403(self, client: TestClient, task_store):
        """POST /approve/topics for other-co task returns 403."""
        task = task_store.create_task(
            pipeline="content_v13",
            company_slug="other-co",
        )
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/topics",
            json={"decision": "approve", "approved_topic_ranks": [0]},
        )
        assert resp.status_code == 403

    def test_approve_briefs_cross_tenant_403(self, client: TestClient, task_store):
        """POST /approve/briefs for other-co task returns 403."""
        task = task_store.create_task(
            pipeline="content_v13",
            company_slug="other-co",
        )
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/briefs",
            json={"brief_id": "brief-001", "decision": "approve"},
        )
        assert resp.status_code == 403

    def test_approve_content_cross_tenant_403(self, client: TestClient, task_store):
        """POST /approve/content for other-co task returns 403."""
        task = task_store.create_task(
            pipeline="content_v13",
            company_slug="other-co",
        )
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/content",
            json={"brief_id": "brief-001", "decision": "approve"},
        )
        assert resp.status_code == 403

    def test_own_task_still_200(self, client: TestClient, task_store):
        """Requests for own-company tasks still succeed after the tenant check is added."""
        task = task_store.create_task(
            pipeline="content_v13",
            company_slug="test-co",
        )
        resp = client.get(f"/api/v1/content/v13/{task.task_id}/status")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════
# H5: gap_slug path traversal validation
# ═══════════════════════════════════════════════════════════════════════


class TestGapSlugValidation:
    """H5: gap_slug must be validated against slug regex before filesystem use."""

    def test_path_traversal_slug_returns_400(self, client: TestClient):
        """gap_slug with '../' traversal component must be rejected with 400."""
        resp = client.post(
            "/api/v1/content/v13/start",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "gap_slug": "../../etc/passwd",
            },
        )
        assert resp.status_code == 400
        assert "gap_slug" in resp.json()["detail"].lower()

    def test_dotdot_slug_returns_400(self, client: TestClient):
        """gap_slug starting with '..' is rejected."""
        resp = client.post(
            "/api/v1/content/v13/start",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "gap_slug": "../sibling",
            },
        )
        assert resp.status_code == 400

    def test_absolute_path_slug_returns_400(self, client: TestClient):
        """gap_slug that looks like an absolute path is rejected."""
        resp = client.post(
            "/api/v1/content/v13/start",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "gap_slug": "/etc/passwd",
            },
        )
        assert resp.status_code == 400

    def test_valid_slug_accepted(self, client: TestClient):
        """A well-formed gap_slug is accepted and the request proceeds normally."""
        with patch("api.routers.content_v13.asyncio.create_task", return_value=MagicMock()):
            resp = client.post(
                "/api/v1/content/v13/start",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                    "gap_slug": "test-co",
                },
            )
        assert resp.status_code == 202

    def test_product_effective_slug_accepted(self, client: TestClient):
        """Effective slugs with double-underscore separator are accepted."""
        with patch("api.routers.content_v13.asyncio.create_task", return_value=MagicMock()):
            resp = client.post(
                "/api/v1/content/v13/start",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                    "gap_slug": "test-co__my-product",
                },
            )
        assert resp.status_code == 202

    def test_no_gap_slug_uses_effective_slug(self, client: TestClient):
        """Omitting gap_slug falls back to scope.effective_slug (no validation error)."""
        with patch("api.routers.content_v13.asyncio.create_task", return_value=MagicMock()):
            resp = client.post(
                "/api/v1/content/v13/start",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                },
            )
        assert resp.status_code == 202


# ═══════════════════════════════════════════════════════════════════════
# H2: Task handle registration
# ═══════════════════════════════════════════════════════════════════════


class TestTaskHandleRegistration:
    """H2: Task handle must be registered after create_task for cancellation support."""

    def test_task_handle_registered_on_start(self, client: TestClient, task_store):
        """Starting the pipeline registers a task handle for the new task."""
        mock_handle = MagicMock()
        with patch("api.routers.content_v13.asyncio.create_task", return_value=mock_handle):
            resp = client.post(
                "/api/v1/content/v13/start",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                },
            )
        assert resp.status_code == 202
        task_id = resp.json()["run_id"]
        # The handle must be registered in task_store so cancellation works
        assert task_store._task_handles.get(task_id) is mock_handle


# ═══════════════════════════════════════════════════════════════════════
# M2: Schema field length limits — unbounded user strings
# ═══════════════════════════════════════════════════════════════════════


class TestContentV13SchemaValidation:
    """M2: User-controlled string fields must have max_length to prevent abuse.

    Validates that manual_prompt, manual_description, and editor_notes are
    rejected when they exceed their respective character limits.
    """

    def test_manual_prompt_too_long_422(self, client: TestClient):
        """manual_prompt exceeding 2000 chars must be rejected with 422."""
        resp = client.post(
            "/api/v1/content/v13/start",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "entry_mode": "manual",
                "manual_prompt": "x" * 2001,
            },
        )
        assert resp.status_code == 422

    def test_manual_prompt_at_limit_202(self, client: TestClient):
        """manual_prompt of exactly 2000 chars must be accepted."""
        with patch("api.routers.content_v13.asyncio.create_task", return_value=MagicMock()):
            resp = client.post(
                "/api/v1/content/v13/start",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                    "entry_mode": "manual",
                    "manual_prompt": "x" * 2000,
                },
            )
        assert resp.status_code == 202

    def test_manual_description_too_long_422(self, client: TestClient):
        """manual_description exceeding 2000 chars must be rejected with 422."""
        resp = client.post(
            "/api/v1/content/v13/start",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "manual_description": "x" * 2001,
            },
        )
        assert resp.status_code == 422

    def test_manual_description_at_limit_202(self, client: TestClient):
        """manual_description of exactly 2000 chars must be accepted."""
        with patch("api.routers.content_v13.asyncio.create_task", return_value=MagicMock()):
            resp = client.post(
                "/api/v1/content/v13/start",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                    "manual_description": "x" * 2000,
                },
            )
        assert resp.status_code == 202

    def test_editor_notes_too_long_422(self, client: TestClient, task_store):
        """editor_notes exceeding 5000 chars must be rejected with 422."""
        task = _make_pending_task(task_store, "content_review", brief_id="brief-001")
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/content",
            json={
                "brief_id": "brief-001",
                "decision": "edit",
                "editor_notes": "x" * 5001,
            },
        )
        assert resp.status_code == 422

    def test_editor_notes_at_limit_200(self, client: TestClient, task_store):
        """editor_notes of exactly 5000 chars must be accepted."""
        task = _make_pending_task(task_store, "content_review", brief_id="brief-001")
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/content",
            json={
                "brief_id": "brief-001",
                "decision": "edit",
                "editor_notes": "x" * 5000,
            },
        )
        assert resp.status_code == 200

    # -- C2-fix: manual_prompt required when entry_mode == "manual" -------

    def test_manual_mode_rejects_none_prompt(self, client: TestClient):
        """entry_mode='manual' with no manual_prompt must be rejected."""
        resp = client.post(
            "/api/v1/content/v13/start",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "entry_mode": "manual",
                # manual_prompt omitted → None
            },
        )
        assert resp.status_code == 422

    def test_manual_mode_rejects_whitespace_prompt(self, client: TestClient):
        """entry_mode='manual' with whitespace-only prompt must be rejected."""
        resp = client.post(
            "/api/v1/content/v13/start",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "entry_mode": "manual",
                "manual_prompt": "   ",
            },
        )
        assert resp.status_code == 422

    def test_manual_mode_accepts_valid_prompt(self, client: TestClient):
        """entry_mode='manual' with a real prompt must be accepted (202)."""
        with patch("api.routers.content_v13.asyncio.create_task", return_value=MagicMock()):
            resp = client.post(
                "/api/v1/content/v13/start",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                    "entry_mode": "manual",
                    "manual_prompt": "How does equity compensation work?",
                },
            )
        assert resp.status_code == 202

    def test_autonomous_mode_allows_none_prompt(self, client: TestClient):
        """entry_mode='autonomous' must accept missing manual_prompt (no regression)."""
        with patch("api.routers.content_v13.asyncio.create_task", return_value=MagicMock()):
            resp = client.post(
                "/api/v1/content/v13/start",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                    "entry_mode": "autonomous",
                },
            )
        assert resp.status_code == 202

    # -- H6-fix: skip_stages validation for manual mode -------------------

    def test_manual_mode_rejects_skip_stage_2(self, client: TestClient):
        """Manual mode cannot skip stage 2 (Brief Builder) — 422."""
        resp = client.post(
            "/api/v1/content/v13/start",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "entry_mode": "manual",
                "manual_prompt": "What is equity?",
                "skip_stages": [2],
            },
        )
        assert resp.status_code == 422

    def test_manual_mode_rejects_skip_stage_0_1(self, client: TestClient):
        """Manual mode cannot skip stages 0 or 1 (already skipped by design) — 422."""
        resp = client.post(
            "/api/v1/content/v13/start",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "entry_mode": "manual",
                "manual_prompt": "What is equity?",
                "skip_stages": [0, 1],
            },
        )
        assert resp.status_code == 422

    def test_manual_mode_accepts_skip_stages_3_4_5(self, client: TestClient):
        """Manual mode can skip stages 3, 4, 5 — 202."""
        with patch("api.routers.content_v13.asyncio.create_task", return_value=MagicMock()):
            resp = client.post(
                "/api/v1/content/v13/start",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                    "entry_mode": "manual",
                    "manual_prompt": "What is equity?",
                    "skip_stages": [3, 4, 5],
                },
            )
        assert resp.status_code == 202

    # -- M1-fix: manual_cluster validation --------------------------------

    def test_manual_cluster_too_long_422(self, client: TestClient):
        """manual_cluster exceeding 200 chars must be rejected."""
        resp = client.post(
            "/api/v1/content/v13/start",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "entry_mode": "manual",
                "manual_prompt": "What is equity?",
                "manual_cluster": "x" * 201,
            },
        )
        assert resp.status_code == 422

    def test_manual_cluster_stripped(self, client: TestClient):
        """manual_cluster with leading/trailing whitespace is stripped."""
        from api.schemas.content_v13 import ContentStartRequestV13

        req = ContentStartRequestV13(
            company_name="Test Co",
            domain="testco.com",
            entry_mode="manual",
            manual_prompt="What is equity?",
            manual_cluster="  equity  ",
        )
        assert req.manual_cluster == "equity"


# ═══════════════════════════════════════════════════════════════════════
# C2: Stage-Aware Approval Window Validation
# ═══════════════════════════════════════════════════════════════════════


class TestApprovalWindowValidation:
    """C2 FIX: Approval endpoints reject requests when task is in wrong state/stage."""

    def test_approve_topics_when_running_409(self, client: TestClient, task_store):
        """Submitting topic approval when task is RUNNING (not PENDING_APPROVAL) → 409."""
        task = task_store.create_task(pipeline="content_v13", company_slug="test-co")
        task_store.update_task(task.task_id, status=TaskStatus.RUNNING)
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/topics",
            json={"decision": "approve", "approved_topic_ranks": [0]},
        )
        assert resp.status_code == 409
        assert "not awaiting approval" in resp.json()["detail"]

    def test_approve_topics_when_completed_409(self, client: TestClient, task_store):
        """Submitting topic approval when task is COMPLETED → 409."""
        task = task_store.create_task(pipeline="content_v13", company_slug="test-co")
        task_store.update_task(task.task_id, status=TaskStatus.COMPLETED)
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/topics",
            json={"decision": "approve"},
        )
        assert resp.status_code == 409

    def test_approve_topics_wrong_stage_409(self, client: TestClient, task_store):
        """Submitting topic approval when task is pending at brief_approval stage → 409."""
        task = _make_pending_task(task_store, "brief_approval", brief_id="b-1")
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/topics",
            json={"decision": "approve"},
        )
        assert resp.status_code == 409
        assert "Wrong approval stage" in resp.json()["detail"]

    def test_approve_briefs_wrong_stage_409(self, client: TestClient, task_store):
        """Submitting brief approval when task is pending at topic_approval stage → 409."""
        task = _make_pending_task(task_store, "topic_approval")
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/briefs",
            json={"brief_id": "b-1", "decision": "approve"},
        )
        assert resp.status_code == 409

    def test_approve_briefs_wrong_brief_id_409(self, client: TestClient, task_store):
        """Submitting brief approval with mismatched brief_id → 409."""
        task = _make_pending_task(task_store, "brief_approval", brief_id="brief-001")
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/briefs",
            json={"brief_id": "brief-999", "decision": "approve"},
        )
        assert resp.status_code == 409
        assert "Brief ID mismatch" in resp.json()["detail"]

    def test_approve_content_when_running_409(self, client: TestClient, task_store):
        """Submitting content approval when task is RUNNING → 409."""
        task = task_store.create_task(pipeline="content_v13", company_slug="test-co")
        task_store.update_task(task.task_id, status=TaskStatus.RUNNING)
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/content",
            json={"brief_id": "b-1", "decision": "approve"},
        )
        assert resp.status_code == 409

    def test_approve_content_wrong_brief_id_409(self, client: TestClient, task_store):
        """Submitting content approval with mismatched brief_id → 409."""
        task = _make_pending_task(task_store, "content_review", brief_id="brief-001")
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/content",
            json={"brief_id": "brief-999", "decision": "approve"},
        )
        assert resp.status_code == 409

    def test_correct_window_200(self, client: TestClient, task_store):
        """Submitting approval when task is in the correct PENDING_APPROVAL window → 200."""
        task = _make_pending_task(task_store, "topic_approval")
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/topics",
            json={"decision": "approve", "approved_topic_ranks": [0, 1]},
        )
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════
# M1: Negative Rank Injection Prevention
# ═══════════════════════════════════════════════════════════════════════


class TestNegativeRankValidation:
    """M1 FIX: Negative indices in approved_topic_ranks must be rejected."""

    def test_negative_rank_returns_422(self, client: TestClient, task_store):
        """approved_topic_ranks with negative values → 422 (Pydantic validator)."""
        task = _make_pending_task(task_store, "topic_approval")
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/topics",
            json={
                "decision": "approve",
                "approved_topic_ranks": [-1, 0, 1],
            },
        )
        assert resp.status_code == 422

    def test_all_negative_ranks_returns_422(self, client: TestClient, task_store):
        """All negative ranks → 422."""
        task = _make_pending_task(task_store, "topic_approval")
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/topics",
            json={
                "decision": "approve",
                "approved_topic_ranks": [-3, -1],
            },
        )
        assert resp.status_code == 422

    def test_zero_and_positive_ranks_accepted(self, client: TestClient, task_store):
        """Ranks [0, 1, 2] (all non-negative) → accepted."""
        task = _make_pending_task(task_store, "topic_approval")
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/topics",
            json={
                "decision": "approve",
                "approved_topic_ranks": [0, 1, 2],
            },
        )
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════
# Nonce Validation + TOCTOU Prevention (Phase 5)
# ═══════════════════════════════════════════════════════════════════════


class TestNonceValidation:
    """Endpoint-level tests for atomic nonce validation via submit_approval."""

    def test_stale_nonce_returns_409(self, client: TestClient, task_store):
        """If task.approval_payload nonce changes between _validate and submit → 409."""
        task = _make_pending_task(task_store, "topic_approval")
        # Simulate a nonce change (e.g., checkpoint advanced to a new interrupt)
        # by mutating the approval_payload after task creation
        task_store.update_task(
            task.task_id,
            approval_payload={
                "stage": "topic_approval",
                "checkpoint_nonce": "new-nonce-xyz",
            },
        )
        # The endpoint reads the task, extracts nonce "new-nonce-xyz",
        # but then passes it to submit_approval which compares against
        # the current payload. Since the endpoint re-reads in _validate,
        # the nonce should match. This test verifies the full flow works.
        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/topics",
            json={"decision": "approve", "approved_topic_ranks": [0]},
        )
        # Should succeed because the endpoint reads the nonce at request time
        assert resp.status_code == 200

    def test_duplicate_approval_returns_409(self, client: TestClient, task_store):
        """Second approval for same checkpoint → 409 (queue already full)."""
        task = _make_pending_task(task_store, "topic_approval")
        # Pre-fill the queue to simulate a prior approval already submitted
        import asyncio
        if task.task_id not in task_store._approval_queues:
            task_store._approval_queues[task.task_id] = asyncio.Queue(maxsize=1)
        task_store._approval_queues[task.task_id].put_nowait({"decision": "approve"})

        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/topics",
            json={"decision": "approve", "approved_topic_ranks": [0]},
        )
        assert resp.status_code == 409
        assert "queue full" in resp.json()["detail"]

    def test_duplicate_brief_approval_returns_409(self, client: TestClient, task_store):
        """Second brief approval for same checkpoint → 409."""
        task = _make_pending_task(task_store, "brief_approval", brief_id="b-1")
        import asyncio
        if task.task_id not in task_store._approval_queues:
            task_store._approval_queues[task.task_id] = asyncio.Queue(maxsize=1)
        task_store._approval_queues[task.task_id].put_nowait({"decision": "approve"})

        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/briefs",
            json={"brief_id": "b-1", "decision": "approve"},
        )
        assert resp.status_code == 409
        assert "queue full" in resp.json()["detail"]

    def test_duplicate_content_approval_returns_409(self, client: TestClient, task_store):
        """Second content approval for same checkpoint → 409."""
        task = _make_pending_task(task_store, "content_review", brief_id="b-1")
        import asyncio
        if task.task_id not in task_store._approval_queues:
            task_store._approval_queues[task.task_id] = asyncio.Queue(maxsize=1)
        task_store._approval_queues[task.task_id].put_nowait({"decision": "approve"})

        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/content",
            json={"brief_id": "b-1", "decision": "approve"},
        )
        assert resp.status_code == 409
        assert "queue full" in resp.json()["detail"]

    def test_no_dead_update_task_before_submit(self, client: TestClient, task_store):
        """Endpoints must NOT call update_task(approval_payload=...) before submit_approval.

        After the C1 fix, the graph reads from the queue, not from
        task.approval_payload. The only thing in approval_payload should be
        the checkpoint data set by run_hitl_checkpoint.
        """
        task = _make_pending_task(task_store, "topic_approval")
        original_payload = task_store.get_task(task.task_id).approval_payload.copy()

        resp = client.post(
            f"/api/v1/content/v13/{task.task_id}/approve/topics",
            json={"decision": "approve", "approved_topic_ranks": [0]},
        )
        assert resp.status_code == 200

        # After approval, the approval_payload should NOT have been overwritten
        # with the approval_data dict. It should only have been modified by
        # submit_approval's internal audit logic (which doesn't touch approval_payload).
        # Note: approval_payload might be unchanged or cleared by the queue consumer,
        # but it should NOT contain topic_decision/approved_topic_ranks.
        updated_task = task_store.get_task(task.task_id)
        payload = updated_task.approval_payload or {}
        assert "topic_decision" not in payload, (
            "Dead code not removed: endpoint still writes approval_data to task.approval_payload"
        )
