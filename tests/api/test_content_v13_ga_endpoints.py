"""Tests for the two-phase TD → GA → CE API endpoints.

POST /api/v1/content/v13/from-topics/gap-analysis   (Phase 1)
POST /api/v1/content/v13/from-topics/start-production  (Phase 2)

Follows the same patterns as test_content_v13_from_topics.py.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# Fixed UUIDs for test fixtures
_TA_1 = str(uuid.uuid5(uuid.NAMESPACE_DNS, "ta-1"))
_TA_2 = str(uuid.uuid5(uuid.NAMESPACE_DNS, "ta-2"))
_GA_RUN_ID = str(uuid.uuid4())
_RUN_ID = uuid.uuid4()
_COMPANY_ID = uuid.uuid4()


class _NoopAsyncContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _make_task_store_stub():
    task_store = MagicMock()
    task_store.pipeline_semaphore.return_value = _NoopAsyncContext()
    task_store.update_task = MagicMock()
    task_store.remove_task_handle = MagicMock()
    task_store.flush_terminal = AsyncMock()
    return task_store


def _make_event_bus_stub():
    event_bus = MagicMock()
    event_bus.publish = MagicMock()
    return event_bus


# ---------------------------------------------------------------------------
# Schema Tests
# ---------------------------------------------------------------------------


class TestTopicContentProductionRequestSchema:
    """Validates TopicContentProductionRequest Pydantic model."""

    def test_valid_minimal(self):
        from api.schemas.content_v13 import TopicContentProductionRequest

        req = TopicContentProductionRequest(
            company_name="Test Co",
            domain="test.co",
            effective_slug="test-co",
            topic_assignment_ids=[_TA_1],
            ga_run_id=_GA_RUN_ID,
        )
        assert req.auto_approve is False
        assert req.ga_run_id == _GA_RUN_ID

    def test_invalid_ga_run_id_rejected(self):
        from api.schemas.content_v13 import TopicContentProductionRequest

        with pytest.raises(Exception):
            TopicContentProductionRequest(
                company_name="Test Co",
                domain="test.co",
                effective_slug="test-co",
                topic_assignment_ids=[_TA_1],
                ga_run_id="not-a-uuid",
            )

    def test_non_uuid_topic_ids_rejected(self):
        from api.schemas.content_v13 import TopicContentProductionRequest

        with pytest.raises(Exception):
            TopicContentProductionRequest(
                company_name="Test Co",
                domain="test.co",
                effective_slug="test-co",
                topic_assignment_ids=["not-a-uuid"],
                ga_run_id=_GA_RUN_ID,
            )

    def test_empty_topic_ids_rejected(self):
        from api.schemas.content_v13 import TopicContentProductionRequest

        with pytest.raises(Exception):
            TopicContentProductionRequest(
                company_name="Test Co",
                domain="test.co",
                effective_slug="test-co",
                topic_assignment_ids=[],
                ga_run_id=_GA_RUN_ID,
            )


# ---------------------------------------------------------------------------
# PipelineTask td_gap_analysis literal
# ---------------------------------------------------------------------------


class TestPipelineTaskTdGapAnalysis:
    """PipelineTask should accept 'td_gap_analysis' as a pipeline type."""

    def test_td_gap_analysis_accepted(self):
        from api.tasks.models import PipelineTask

        task = PipelineTask(
            task_id="test-123",
            pipeline="td_gap_analysis",
            company_slug="test-co",
        )
        assert task.pipeline == "td_gap_analysis"


# ---------------------------------------------------------------------------
# POST /from-topics/gap-analysis — Phase 1
# ---------------------------------------------------------------------------


class TestStartFromTopicsGapAnalysis:
    """Tests for POST /api/v1/content/v13/from-topics/gap-analysis."""

    def test_returns_202(self, client: TestClient):
        with patch(
            "api.routers.content_v13.asyncio.create_task",
            return_value=MagicMock(),
        ):
            resp = client.post(
                "/api/v1/content/v13/from-topics/gap-analysis",
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
        assert data["entry_mode"] == "topic_discovery_ga"
        assert "run_id" in data

    def test_unauthenticated_401(self, public_client: TestClient):
        resp = public_client.post(
            "/api/v1/content/v13/from-topics/gap-analysis",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "effective_slug": "test-co",
                "topic_assignment_ids": [_TA_1],
            },
        )
        assert resp.status_code == 401

    def test_invalid_slug_400(self, client: TestClient):
        resp = client.post(
            "/api/v1/content/v13/from-topics/gap-analysis",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "effective_slug": "../malicious",
                "topic_assignment_ids": [_TA_1],
            },
        )
        assert resp.status_code == 400

    def test_tenant_isolation_403(self, client: TestClient):
        resp = client.post(
            "/api/v1/content/v13/from-topics/gap-analysis",
            json={
                "company_name": "Other Corp",
                "domain": "othercorp.com",
                "effective_slug": "other-corp",
                "topic_assignment_ids": [_TA_1],
            },
        )
        assert resp.status_code == 403

    def test_viewer_role_403(self, viewer_client: TestClient):
        resp = viewer_client.post(
            "/api/v1/content/v13/from-topics/gap-analysis",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "effective_slug": "test-co",
                "topic_assignment_ids": [_TA_1],
            },
        )
        assert resp.status_code == 403

    def test_empty_topic_ids_422(self, client: TestClient):
        resp = client.post(
            "/api/v1/content/v13/from-topics/gap-analysis",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "effective_slug": "test-co",
                "topic_assignment_ids": [],
            },
        )
        assert resp.status_code == 422

    def test_non_uuid_topic_ids_422(self, client: TestClient):
        resp = client.post(
            "/api/v1/content/v13/from-topics/gap-analysis",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "effective_slug": "test-co",
                "topic_assignment_ids": ["not-a-uuid"],
            },
        )
        assert resp.status_code == 422

    def test_product_slug_passed(self, client: TestClient):
        with patch(
            "api.routers.content_v13.asyncio.create_task",
            return_value=MagicMock(),
        ):
            resp = client.post(
                "/api/v1/content/v13/from-topics/gap-analysis",
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
# POST /from-topics/start-production — Phase 2
# ---------------------------------------------------------------------------


class TestStartFromTopicsProduction:
    """Tests for POST /api/v1/content/v13/from-topics/start-production."""

    def test_returns_202(self, client: TestClient, artifacts_root):
        """Happy path: storage.exists returns True → 202."""
        with patch(
            "core.storage.get_storage_backend",
        ) as mock_gsb, patch(
            "api.routers.content_v13.asyncio.create_task",
            return_value=MagicMock(),
        ):
            mock_storage = MagicMock()
            mock_storage.exists.return_value = True
            mock_gsb.return_value = mock_storage

            resp = client.post(
                "/api/v1/content/v13/from-topics/start-production",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                    "effective_slug": "test-co",
                    "topic_assignment_ids": [_TA_1],
                    "ga_run_id": _GA_RUN_ID,
                },
            )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "started"
        assert "run_id" in data

    def test_missing_analysis_404(self, client: TestClient):
        """Missing analysis.json → 404."""
        with patch(
            "core.storage.get_storage_backend",
        ) as mock_gsb:
            mock_storage = MagicMock()
            mock_storage.exists.return_value = False
            mock_gsb.return_value = mock_storage

            resp = client.post(
                "/api/v1/content/v13/from-topics/start-production",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                    "effective_slug": "test-co",
                    "topic_assignment_ids": [_TA_1],
                    "ga_run_id": _GA_RUN_ID,
                },
            )
        assert resp.status_code == 404
        assert "analysis not found" in resp.json()["detail"]

    def test_invalid_ga_run_id_422(self, client: TestClient):
        """Non-UUID ga_run_id → 422."""
        resp = client.post(
            "/api/v1/content/v13/from-topics/start-production",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "effective_slug": "test-co",
                "topic_assignment_ids": [_TA_1],
                "ga_run_id": "not-a-uuid",
            },
        )
        assert resp.status_code == 422

    def test_unauthenticated_401(self, public_client: TestClient):
        resp = public_client.post(
            "/api/v1/content/v13/from-topics/start-production",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "effective_slug": "test-co",
                "topic_assignment_ids": [_TA_1],
                "ga_run_id": _GA_RUN_ID,
            },
        )
        assert resp.status_code == 401

    def test_tenant_isolation_403(self, client: TestClient):
        resp = client.post(
            "/api/v1/content/v13/from-topics/start-production",
            json={
                "company_name": "Other Corp",
                "domain": "othercorp.com",
                "effective_slug": "other-corp",
                "topic_assignment_ids": [_TA_1],
                "ga_run_id": _GA_RUN_ID,
            },
        )
        assert resp.status_code == 403

    def test_invalid_slug_400(self, client: TestClient):
        resp = client.post(
            "/api/v1/content/v13/from-topics/start-production",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "effective_slug": "../malicious",
                "topic_assignment_ids": [_TA_1],
                "ga_run_id": _GA_RUN_ID,
            },
        )
        assert resp.status_code == 400

    def test_viewer_role_403(self, viewer_client: TestClient):
        resp = viewer_client.post(
            "/api/v1/content/v13/from-topics/start-production",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "effective_slug": "test-co",
                "topic_assignment_ids": [_TA_1],
                "ga_run_id": _GA_RUN_ID,
            },
        )
        assert resp.status_code == 403

    def test_conflict_when_topic_already_queued_for_production(self, client: TestClient):
        with patch(
            "core.storage.get_storage_backend",
        ) as mock_gsb, patch(
            "core.redis.get_redis_or_none",
            return_value=object(),
        ), patch(
            "core.content_engine.state_redis.read_ga_phase_cards_async",
            new_callable=AsyncMock,
            return_value=[{
                "topic_assignment_id": _TA_1,
                "status": "content_queued",
                "ga_run_id": _GA_RUN_ID,
            }],
        ):
            mock_storage = MagicMock()
            mock_storage.exists.return_value = True
            mock_gsb.return_value = mock_storage

            resp = client.post(
                "/api/v1/content/v13/from-topics/start-production",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                    "effective_slug": "test-co",
                    "topic_assignment_ids": [_TA_1],
                    "ga_run_id": _GA_RUN_ID,
                },
            )

        assert resp.status_code == 409
        assert "already queued" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Task Runner function signatures
# ---------------------------------------------------------------------------


class TestRunTdGapAnalysisTask:
    """Tests for run_td_gap_analysis_task function signature."""

    def test_function_exists(self):
        from api.tasks.runner import run_td_gap_analysis_task

        import inspect

        assert inspect.iscoroutinefunction(run_td_gap_analysis_task)

    def test_function_signature(self):
        from api.tasks.runner import run_td_gap_analysis_task

        import inspect

        sig = inspect.signature(run_td_gap_analysis_task)
        params = list(sig.parameters.keys())
        assert "task_id" in params
        assert "effective_slug" in params
        assert "topic_assignment_ids" in params
        assert "company_name" in params
        assert "domain" in params
        assert "task_store" in params
        assert "event_bus" in params


class TestRunTdContentProductionTask:
    """Tests for run_td_content_production_task function signature."""

    def test_function_exists(self):
        from api.tasks.runner import run_td_content_production_task

        import inspect

        assert inspect.iscoroutinefunction(run_td_content_production_task)

    def test_function_signature(self):
        from api.tasks.runner import run_td_content_production_task

        import inspect

        sig = inspect.signature(run_td_content_production_task)
        params = list(sig.parameters.keys())
        assert "task_id" in params
        assert "effective_slug" in params
        assert "topic_assignment_ids" in params
        assert "company_name" in params
        assert "domain" in params
        assert "ga_run_id" in params
        assert "task_store" in params
        assert "event_bus" in params

    @pytest.mark.asyncio
    async def test_preserves_per_topic_terminal_states(self):
        from api.tasks.runner import run_td_content_production_task
        from core.models.content_generation import (
            ContentGenerationOutput,
            ContentPiece,
            ContentStatus,
        )

        task_store = _make_task_store_stub()
        event_bus = _make_event_bus_stub()
        topic_run_service = MagicMock()
        topic_run_service.advance_topic_runs = AsyncMock(return_value=[])

        output = ContentGenerationOutput(
            company_slug="test-co",
            total_briefs=2,
            total_approved=1,
            total_rejected=1,
            pieces=[
                ContentPiece(
                    brief_id="WE-001",
                    title="Completed",
                    status=ContentStatus.APPROVED,
                    topic_assignment_id=_TA_1,
                ),
                ContentPiece(
                    brief_id="WE-002",
                    title="Rejected",
                    status=ContentStatus.REJECTED,
                    topic_assignment_id=_TA_2,
                ),
            ],
        )

        with patch(
            "api.tasks.runner._resolve_db_context",
            new_callable=AsyncMock,
            return_value=(MagicMock(), _RUN_ID, _COMPANY_ID),
        ), patch(
            "api.tasks.runner._create_pipeline_run",
            new_callable=AsyncMock,
        ), patch(
            "api.tasks.runner._mark_pipeline_run_failed",
            new_callable=AsyncMock,
        ), patch(
            "core.services.content_engine_topic_runs.ContentEngineTopicRunService",
            return_value=topic_run_service,
        ), patch(
            "core.orchestration.td_content_orchestrator.run_td_content_production_only",
            new_callable=AsyncMock,
            return_value=output,
        ):
            await run_td_content_production_task(
                task_id="task-1",
                effective_slug="test-co",
                topic_assignment_ids=[_TA_1, _TA_2],
                company_name="Test Co",
                domain="testco.com",
                ga_run_id=_GA_RUN_ID,
                task_store=task_store,
                event_bus=event_bus,
            )

        calls = topic_run_service.advance_topic_runs.await_args_list
        assert any(
            call.kwargs.get("topic_assignment_ids") == [_TA_1]
            and call.kwargs.get("status") == "content_produced"
            and call.kwargs.get("stage") == "completed"
            and call.kwargs.get("payload_json", {}).get("note") == "Content production completed"
            and call.kwargs.get("payload_json", {}).get("content_piece_status") == "approved"
            for call in calls
        )
        assert any(
            call.kwargs.get("topic_assignment_ids") == [_TA_2]
            and call.kwargs.get("status") == "rejected"
            and call.kwargs.get("stage") == "rejected"
            and call.kwargs.get("payload_json", {}).get("note") == "Content was rejected"
            and call.kwargs.get("payload_json", {}).get("content_piece_status") == "rejected"
            for call in calls
        )
        assert not any(
            call.kwargs.get("topic_assignment_ids") == [_TA_1, _TA_2]
            and call.kwargs.get("status") == "content_produced"
            and call.kwargs.get("stage") == "completed"
            for call in calls
        )

    @pytest.mark.asyncio
    async def test_failure_rolls_durable_topic_runs_back_to_retryable_state(self):
        from api.tasks.runner import run_td_content_production_task

        task_store = _make_task_store_stub()
        event_bus = _make_event_bus_stub()
        topic_run_service = MagicMock()
        topic_run_service.advance_topic_runs = AsyncMock(return_value=[])

        with patch(
            "api.tasks.runner._resolve_db_context",
            new_callable=AsyncMock,
            return_value=(MagicMock(), _RUN_ID, _COMPANY_ID),
        ), patch(
            "api.tasks.runner._create_pipeline_run",
            new_callable=AsyncMock,
        ), patch(
            "api.tasks.runner._mark_pipeline_run_failed",
            new_callable=AsyncMock,
        ), patch(
            "api.tasks.runner._cleanup_stale_pipeline_state",
        ), patch(
            "core.services.content_engine_topic_runs.ContentEngineTopicRunService",
            return_value=topic_run_service,
        ), patch(
            "core.orchestration.td_content_orchestrator.run_td_content_production_only",
            new_callable=AsyncMock,
            side_effect=RuntimeError("ce boom"),
        ), patch(
            "core.orchestration.td_content_orchestrator._update_ga_phase_status",
        ), patch(
            "core.orchestration.td_content_orchestrator._update_assignment_statuses_db",
            new_callable=AsyncMock,
        ), patch(
            "core.orchestration.td_content_orchestrator._emit_company_event",
        ):
            await run_td_content_production_task(
                task_id="task-1",
                effective_slug="test-co",
                topic_assignment_ids=[_TA_1, _TA_2],
                company_name="Test Co",
                domain="testco.com",
                ga_run_id=_GA_RUN_ID,
                task_store=task_store,
                event_bus=event_bus,
            )

        calls = topic_run_service.advance_topic_runs.await_args_list
        assert any(
            call.kwargs.get("status") == "gap_analysis_complete"
            and call.kwargs.get("stage") == "gap_analysis_complete"
            and call.kwargs.get("last_error") == "ce boom"
            and call.kwargs.get("payload_json", {}).get("note") == "Content production failed; card returned to gap analysis complete"
            and call.kwargs.get("payload_json", {}).get("rollback_target") == "gap_analysis_complete"
            for call in calls
        )
        assert not any(call.kwargs.get("status") == "failed" for call in calls)
