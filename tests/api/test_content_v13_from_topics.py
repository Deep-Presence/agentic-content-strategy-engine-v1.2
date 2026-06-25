"""Tests for the TD → Content API endpoints.

POST /api/v1/content/v13/from-topics
GET /api/v1/content/v13/{effective_slug}/topic-content-status

Plus schema validation and task runner integration.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from tests._support.model_config_service import FailingModelConfigService

# Fixed UUIDs for test fixtures (M2 fix requires valid UUIDs)
_TA_1 = str(uuid.uuid5(uuid.NAMESPACE_DNS, "ta-1"))
_TA_2 = str(uuid.uuid5(uuid.NAMESPACE_DNS, "ta-2"))
_TA_3 = str(uuid.uuid5(uuid.NAMESPACE_DNS, "ta-3"))


# ---------------------------------------------------------------------------
# Schema Tests
# ---------------------------------------------------------------------------


class TestTopicContentStartRequestSchema:
    """Validates TopicContentStartRequest Pydantic model."""

    def test_valid_minimal(self):
        from api.schemas.content_v13 import TopicContentStartRequest

        req = TopicContentStartRequest(
            company_name="Test Co",
            domain="test.co",
            effective_slug="test-co",
            topic_assignment_ids=[_TA_1],
        )
        assert req.auto_approve is False
        assert len(req.platforms) == 4

    def test_valid_full(self):
        from api.schemas.content_v13 import TopicContentStartRequest

        req = TopicContentStartRequest(
            company_name="Test Co",
            domain="test.co",
            effective_slug="test-co__product",
            topic_assignment_ids=[_TA_1, _TA_2, _TA_3],
            product_slug="product",
            product_name="Product",
            auto_approve=True,
            platforms=["perplexity", "openai"],
        )
        assert req.product_slug == "product"
        assert len(req.platforms) == 2

    def test_empty_topic_ids_rejected(self):
        from api.schemas.content_v13 import TopicContentStartRequest

        with pytest.raises(Exception):
            TopicContentStartRequest(
                company_name="Test Co",
                domain="test.co",
                effective_slug="test-co",
                topic_assignment_ids=[],
            )

    def test_too_many_topic_ids_rejected(self):
        from api.schemas.content_v13 import TopicContentStartRequest

        with pytest.raises(Exception):
            TopicContentStartRequest(
                company_name="Test Co",
                domain="test.co",
                effective_slug="test-co",
                topic_assignment_ids=[str(uuid.uuid4()) for _ in range(21)],
            )

    def test_non_uuid_topic_ids_rejected(self):
        """M2 fix: non-UUID strings must be rejected."""
        from api.schemas.content_v13 import TopicContentStartRequest

        with pytest.raises(Exception):
            TopicContentStartRequest(
                company_name="Test Co",
                domain="test.co",
                effective_slug="test-co",
                topic_assignment_ids=["not-a-uuid"],
            )

    def test_invalid_platform_rejected(self):
        """M2 fix: unsupported platform names must be rejected."""
        from api.schemas.content_v13 import TopicContentStartRequest

        with pytest.raises(Exception):
            TopicContentStartRequest(
                company_name="Test Co",
                domain="test.co",
                effective_slug="test-co",
                topic_assignment_ids=[_TA_1],
                platforms=["invalid_platform"],
            )


class TestTopicContentStatusResponseSchema:
    """Validates TopicContentStatusResponse."""

    def test_empty_response(self):
        from api.schemas.content_v13 import TopicContentStatusResponse

        resp = TopicContentStatusResponse(effective_slug="test-co")
        assert resp.total_assignments == 0
        assert resp.items == []

    def test_with_items(self):
        from api.schemas.content_v13 import (
            TopicContentStatusItem,
            TopicContentStatusResponse,
        )

        items = [
            TopicContentStatusItem(
                topic_assignment_id="ta-1",
                topic_text="How AP Works",
                status="not_started",
            ),
            TopicContentStatusItem(
                topic_assignment_id="ta-2",
                topic_text="Best Practices",
                status="content_produced",
                content_piece_id="cp-1",
                content_title="AP Best Practices Guide",
            ),
        ]
        resp = TopicContentStatusResponse(
            effective_slug="test-co",
            total_assignments=2,
            items=items,
        )
        assert resp.total_assignments == 2
        assert resp.items[1].content_title == "AP Best Practices Guide"


# ---------------------------------------------------------------------------
# PipelineTask td_content literal
# ---------------------------------------------------------------------------


class TestPipelineTaskTdContent:
    """PipelineTask should accept 'td_content' as a pipeline type."""

    def test_td_content_accepted(self):
        from api.tasks.models import PipelineTask

        task = PipelineTask(
            task_id="test-123",
            pipeline="td_content",
            company_slug="test-co",
        )
        assert task.pipeline == "td_content"

    def test_invalid_pipeline_rejected(self):
        from api.tasks.models import PipelineTask

        with pytest.raises(Exception):
            PipelineTask(
                task_id="test-123",
                pipeline="nonexistent_pipeline",
                company_slug="test-co",
            )


# ---------------------------------------------------------------------------
# POST /from-topics endpoint
# ---------------------------------------------------------------------------


class TestStartFromTopics:
    """Tests for POST /api/v1/content/v13/from-topics."""

    def test_returns_202(self, client: TestClient):
        with patch(
            "api.routers.content_v13.asyncio.create_task",
            return_value=MagicMock(),
        ):
            resp = client.post(
                "/api/v1/content/v13/from-topics",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                    "effective_slug": "test-co",
                    "topic_assignment_ids": [_TA_1, _TA_2],
                },
            )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "started"
        assert data["entry_mode"] == "topic_discovery"
        assert "run_id" in data

    def test_missing_byok_config_blocks_start_before_task_creation(self, client: TestClient):
        service = FailingModelConfigService()
        client.app.state.model_config_service = service

        with patch(
            "api.routers.content_v13.create_task_durable",
            new_callable=AsyncMock,
        ) as create_task:
            resp = client.post(
                "/api/v1/content/v13/from-topics",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                    "effective_slug": "test-co",
                    "topic_assignment_ids": [_TA_1],
                },
            )

        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert detail["code"] == "byok_model_config_required"
        assert detail["missing_credential"] is True
        assert "content.brief_builder" in detail["required_agent_keys"]
        assert "content.brief_builder" in service.preflight_calls[0][1]
        create_task.assert_not_awaited()

    def test_tenant_isolation_403(self, client: TestClient):
        resp = client.post(
            "/api/v1/content/v13/from-topics",
            json={
                "company_name": "Other Corp",
                "domain": "othercorp.com",
                "effective_slug": "other-corp",
                "topic_assignment_ids": [_TA_1],
            },
        )
        assert resp.status_code == 403

    def test_unauthenticated_401(self, public_client: TestClient):
        resp = public_client.post(
            "/api/v1/content/v13/from-topics",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "effective_slug": "test-co",
                "topic_assignment_ids": [_TA_1],
            },
        )
        assert resp.status_code == 401

    def test_viewer_role_403(self, viewer_client: TestClient):
        resp = viewer_client.post(
            "/api/v1/content/v13/from-topics",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "effective_slug": "test-co",
                "topic_assignment_ids": [_TA_1],
            },
        )
        assert resp.status_code == 403

    def test_invalid_slug_400(self, client: TestClient):
        resp = client.post(
            "/api/v1/content/v13/from-topics",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "effective_slug": "../malicious",
                "topic_assignment_ids": [_TA_1],
            },
        )
        assert resp.status_code == 400

    def test_empty_topic_ids_422(self, client: TestClient):
        resp = client.post(
            "/api/v1/content/v13/from-topics",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "effective_slug": "test-co",
                "topic_assignment_ids": [],
            },
        )
        assert resp.status_code == 422

    def test_non_uuid_topic_ids_422(self, client: TestClient):
        """M2 fix: non-UUID topic_assignment_ids should be rejected at API."""
        resp = client.post(
            "/api/v1/content/v13/from-topics",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "effective_slug": "test-co",
                "topic_assignment_ids": ["not-a-uuid"],
            },
        )
        assert resp.status_code == 422

    def test_invalid_platform_422(self, client: TestClient):
        """M2 fix: unsupported platforms should be rejected at API."""
        resp = client.post(
            "/api/v1/content/v13/from-topics",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "effective_slug": "test-co",
                "topic_assignment_ids": [_TA_1],
                "platforms": ["invalid_engine"],
            },
        )
        assert resp.status_code == 422

    def test_product_slug_passed(self, client: TestClient):
        with patch(
            "api.routers.content_v13.asyncio.create_task",
            return_value=MagicMock(),
        ):
            resp = client.post(
                "/api/v1/content/v13/from-topics",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                    "effective_slug": "test-co__product",
                    "topic_assignment_ids": [_TA_1],
                    "product_slug": "product",
                    "product_name": "Product",
                },
            )
        assert resp.status_code == 202


# ---------------------------------------------------------------------------
# GET /topic-content-status endpoint
# ---------------------------------------------------------------------------


class TestGetTopicContentStatus:
    """Tests for GET /api/v1/content/v13/{effective_slug}/topic-content-status."""

    @staticmethod
    def _ensure_session_factory(app):
        """Set a mock db_session_factory on app state if absent."""
        if getattr(app.state, "db_session_factory", None) is None:
            app.state.db_session_factory = MagicMock()

    def test_returns_empty_when_no_matrix(self, client: TestClient):
        self._ensure_session_factory(client.app)
        with patch(
            "core.topic_discovery.db_ops.db_read_latest_matrix",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = client.get(
                "/api/v1/content/v13/test-co/topic-content-status",
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["effective_slug"] == "test-co"
        assert data["total_assignments"] == 0
        assert data["items"] == []

    def test_returns_assignments_from_matrix(self, client: TestClient):
        from core.models.topic_discovery import (
            BuyerStage,
            IntentType,
            TopicAssignment,
            TopicAssignmentMatrix,
            TopicAssignmentStatus,
        )

        matrix = TopicAssignmentMatrix(
            assignments=[
                TopicAssignment(
                    id="ta-1",
                    subdomain_id="sd-1",
                    subdomain_name="AP Automation",
                    topic_text="How AP Works",
                    buyer_stage=BuyerStage.TOFU,
                    intent_type=IntentType.informational,
                    audience_segment="AP Manager",
                    status=TopicAssignmentStatus.not_started,
                ),
                TopicAssignment(
                    id="ta-2",
                    subdomain_id="sd-1",
                    subdomain_name="AP Automation",
                    topic_text="Best Practices",
                    buyer_stage=BuyerStage.MOFU,
                    intent_type=IntentType.commercial,
                    audience_segment="CFO",
                    status=TopicAssignmentStatus.content_produced,
                ),
            ],
            total_assignments=2,
        )

        self._ensure_session_factory(client.app)
        with patch(
            "core.topic_discovery.db_ops.db_read_latest_matrix",
            new_callable=AsyncMock,
            return_value=matrix,
        ):
            resp = client.get(
                "/api/v1/content/v13/test-co/topic-content-status",
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_assignments"] == 2
        assert data["items"][0]["topic_assignment_id"] == "ta-1"
        assert data["items"][0]["status"] == "not_started"
        assert data["items"][1]["status"] == "content_produced"

    def test_invalid_slug_400(self, client: TestClient):
        resp = client.get(
            "/api/v1/content/v13/../evil/topic-content-status",
        )
        # FastAPI may return 400 or 404 depending on path parsing
        assert resp.status_code in (400, 404)

    def test_tenant_isolation_403(self, client: TestClient):
        resp = client.get(
            "/api/v1/content/v13/other-corp/topic-content-status",
        )
        assert resp.status_code == 403

    def test_db_error_returns_empty(self, client: TestClient):
        """DB errors should not 500 — return empty response."""
        self._ensure_session_factory(client.app)
        with patch(
            "core.topic_discovery.db_ops.db_read_latest_matrix",
            new_callable=AsyncMock,
            side_effect=RuntimeError("DB connection failed"),
        ):
            resp = client.get(
                "/api/v1/content/v13/test-co/topic-content-status",
            )
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_no_session_factory_returns_empty(self, client: TestClient):
        """When db_session_factory is None, return empty response."""
        app = client.app
        original = getattr(app.state, "db_session_factory", None)
        app.state.db_session_factory = None
        try:
            resp = client.get(
                "/api/v1/content/v13/test-co/topic-content-status",
            )
        finally:
            app.state.db_session_factory = original
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_unauthenticated_401(self, public_client: TestClient):
        resp = public_client.get(
            "/api/v1/content/v13/test-co/topic-content-status",
        )
        assert resp.status_code == 401


class TestGetTopicRuns:
    """Tests for GET /api/v1/content/v13/{effective_slug}/topic-runs."""

    def test_prefix_slug_tenant_bypass_is_rejected(self, client: TestClient):
        resp = client.get("/api/v1/content/v13/test-co-pro/topic-runs")
        assert resp.status_code == 403


class TestGetTopicRunEvents:
    """Tests for GET /api/v1/content/v13/{effective_slug}/topic-runs/{topic_run_id}/events."""

    @staticmethod
    def _ensure_session_factory(app):
        if getattr(app.state, "db_session_factory", None) is None:
            app.state.db_session_factory = MagicMock()

    def test_returns_durable_topic_events(self, client: TestClient):
        self._ensure_session_factory(client.app)
        topic_run_id = str(uuid.uuid4())
        with patch(
            "core.services.content_engine_topic_runs.ContentEngineTopicRunService.list_topic_run_events",
            new_callable=AsyncMock,
            return_value=(
                MagicMock(
                    topic_run_id=topic_run_id,
                    batch_run_id="batch-1",
                    topic_assignment_id=_TA_1,
                    display_id="WE-003",
                    topic_text="Equity dilution guide",
                    brief_id="WE-003",
                    ga_run_id="ga-1",
                    pipeline_task_id="task-1",
                    status="drafting",
                    stage="drafting",
                    seq=4,
                    content_piece_id=None,
                    created_at="2026-04-10T00:00:00+00:00",
                    updated_at="2026-04-10T00:00:01+00:00",
                ),
                [
                    MagicMock(
                        topic_event_id="evt-1",
                        topic_run_id=topic_run_id,
                        topic_assignment_id=_TA_1,
                        display_id="WE-003",
                        brief_id="WE-003",
                        event_type="topic_run_created",
                        stage="gap_analysis_pending",
                        status="gap_analysis_pending",
                        seq=1,
                        content_piece_id=None,
                        pipeline_task_id="task-1",
                        payload_json={"brief_id": "WE-003"},
                        created_at="2026-04-10T00:00:00+00:00",
                    ),
                    MagicMock(
                        topic_event_id="evt-2",
                        topic_run_id=topic_run_id,
                        topic_assignment_id=_TA_1,
                        display_id="WE-003",
                        brief_id="WE-003",
                        event_type="topic_run_changed",
                        stage="drafting",
                        status="drafting",
                        seq=4,
                        content_piece_id=None,
                        pipeline_task_id="task-1",
                        payload_json={"note": "Worker drafting started"},
                        created_at="2026-04-10T00:00:01+00:00",
                    ),
                ],
            ),
        ):
            resp = client.get(f"/api/v1/content/v13/test-co/topic-runs/{topic_run_id}/events")

        assert resp.status_code == 200
        data = resp.json()
        assert data["effective_slug"] == "test-co"
        assert data["topic_run_id"] == topic_run_id
        assert data["display_id"] == "WE-003"
        assert data["brief_id"] == "WE-003"
        assert data["total"] == 2
        assert data["items"][0]["event_type"] == "topic_run_created"
        assert data["items"][1]["payload_json"] == {"note": "Worker drafting started"}

    def test_prefix_slug_tenant_bypass_is_rejected(self, client: TestClient):
        resp = client.get(
            f"/api/v1/content/v13/test-co-pro/topic-runs/{uuid.uuid4()}/events",
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Task Runner
# ---------------------------------------------------------------------------


class TestRunTdContentPipelineTask:
    """Tests for run_td_content_pipeline_task function signature."""

    def test_function_exists(self):
        from api.tasks.runner import run_td_content_pipeline_task

        import inspect

        assert inspect.iscoroutinefunction(run_td_content_pipeline_task)

    def test_function_signature(self):
        from api.tasks.runner import run_td_content_pipeline_task

        import inspect

        sig = inspect.signature(run_td_content_pipeline_task)
        params = list(sig.parameters.keys())
        assert "task_id" in params
        assert "effective_slug" in params
        assert "topic_assignment_ids" in params
        assert "company_name" in params
        assert "domain" in params
        assert "task_store" in params
        assert "event_bus" in params
