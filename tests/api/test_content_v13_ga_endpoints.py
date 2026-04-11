"""Tests for the two-phase TD → GA → CE API endpoints.

POST /api/v1/content/v13/from-topics/gap-analysis   (Phase 1)
POST /api/v1/content/v13/from-topics/start-production  (Phase 2)

Follows the same patterns as test_content_v13_from_topics.py.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace
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


def _capture_background_task(coro):
    """Close dispatched coroutine in tests so patched asyncio.create_task doesn't leak it."""
    try:
        coro.close()
    except Exception:
        pass
    return MagicMock()


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
            "core.redis.get_redis_or_none",
            return_value=None,
        ), patch(
            "core.redis.get_sync_redis_or_none",
            return_value=None,
        ), patch(
            "api.routers.content_v13.dispatch_queued_td_content_runs",
            new_callable=AsyncMock,
            return_value=[{
                "topic_run_id": "run-1",
                "topic_assignment_id": _TA_1,
                "task_id": "task-123",
            }],
        ), patch(
            "core.services.content_engine_topic_runs.ContentEngineTopicRunService",
        ) as mock_topic_run_service_cls:
            mock_storage = MagicMock()
            mock_storage.exists.return_value = True
            mock_gsb.return_value = mock_storage
            topic_run_service = MagicMock()
            topic_run_service.queue_topic_runs_for_dispatch = AsyncMock(
                return_value=[
                    SimpleNamespace(
                        topic_run_id="run-1",
                        batch_run_id="batch-1",
                        topic_assignment_id=_TA_1,
                        display_id="WE-001",
                        topic_text="Topic 1",
                        brief_id="WE-001",
                        ga_run_id=_GA_RUN_ID,
                        pipeline_task_id=None,
                        status="content_queued",
                        stage="content_queued",
                        seq=2,
                        content_piece_id=None,
                        created_at="2026-04-10T00:00:00+00:00",
                        updated_at="2026-04-10T00:00:01+00:00",
                    )
                ]
            )
            topic_run_service.list_topic_runs_by_assignment_ids = AsyncMock(
                return_value=[
                    SimpleNamespace(
                        topic_run_id="run-1",
                        batch_run_id="batch-1",
                        topic_assignment_id=_TA_1,
                        display_id="WE-001",
                        topic_text="Topic 1",
                        brief_id="WE-001",
                        ga_run_id=_GA_RUN_ID,
                        pipeline_task_id="task-123",
                        status="content_queued",
                        stage="content_queued",
                        seq=2,
                        content_piece_id=None,
                        created_at="2026-04-10T00:00:00+00:00",
                        updated_at="2026-04-10T00:00:01+00:00",
                    )
                ]
            )
            mock_topic_run_service_cls.return_value = topic_run_service
            client.app.state.db_session_factory = MagicMock()

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
        assert data["run_id"] == "task-123"
        assert data["topic_runs"][0]["pipeline_task_id"] == "task-123"
        assert data["topic_runs"][0]["topic_assignment_id"] == _TA_1

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

    def test_returns_503_when_durable_queueing_fails(self, client: TestClient):
        with patch(
            "core.storage.get_storage_backend",
        ) as mock_gsb, patch(
            "core.redis.get_redis_or_none",
            return_value=None,
        ), patch(
            "core.redis.get_sync_redis_or_none",
            return_value=None,
        ), patch(
            "core.services.content_engine_topic_runs.ContentEngineTopicRunService",
        ) as mock_topic_run_service_cls, patch(
            "core.orchestration.td_content_orchestrator._update_ga_phase_status",
        ) as update_ga_status:
            mock_storage = MagicMock()
            mock_storage.exists.return_value = True
            mock_gsb.return_value = mock_storage
            topic_run_service = MagicMock()
            topic_run_service.queue_topic_runs_for_dispatch = AsyncMock(
                side_effect=RuntimeError("db down")
            )
            mock_topic_run_service_cls.return_value = topic_run_service
            client.app.state.db_session_factory = MagicMock()

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

        assert resp.status_code == 503
        update_ga_status.assert_not_called()

    def test_returns_409_when_no_topic_runs_were_queued(self, client: TestClient):
        with patch(
            "core.storage.get_storage_backend",
        ) as mock_gsb, patch(
            "core.redis.get_redis_or_none",
            return_value=None,
        ), patch(
            "core.redis.get_sync_redis_or_none",
            return_value=None,
        ), patch(
            "core.services.content_engine_topic_runs.ContentEngineTopicRunService",
        ) as mock_topic_run_service_cls, patch(
            "core.orchestration.td_content_orchestrator._update_ga_phase_status",
        ) as update_ga_status:
            mock_storage = MagicMock()
            mock_storage.exists.return_value = True
            mock_gsb.return_value = mock_storage
            topic_run_service = MagicMock()
            topic_run_service.queue_topic_runs_for_dispatch = AsyncMock(return_value=[])
            mock_topic_run_service_cls.return_value = topic_run_service
            client.app.state.db_session_factory = MagicMock()

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
        update_ga_status.assert_not_called()


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

    @pytest.mark.asyncio
    async def test_pause_marks_topic_run_waiting_human_without_failure(self):
        from api.tasks.runner import run_td_content_production_task
        from core.content_engine.graph_v13 import ApprovalPauseRequested

        task_store = _make_task_store_stub()
        event_bus = _make_event_bus_stub()
        topic_run_service = MagicMock()
        topic_run_service.advance_topic_runs = AsyncMock(return_value=[])
        topic_run_service.mark_topic_run_waiting_human = AsyncMock(return_value=[])

        with patch(
            "api.tasks.runner._resolve_db_context",
            new_callable=AsyncMock,
            return_value=(MagicMock(), _RUN_ID, _COMPANY_ID),
        ), patch(
            "api.tasks.runner._create_pipeline_run",
            new_callable=AsyncMock,
        ), patch(
            "core.services.content_engine_topic_runs.ContentEngineTopicRunService",
            return_value=topic_run_service,
        ), patch(
            "core.orchestration.td_content_orchestrator.run_td_content_production_only",
            new_callable=AsyncMock,
            side_effect=ApprovalPauseRequested(
                {
                    "stage": "brief_approval",
                    "status": "pending_brief_approval",
                    "continuation": {
                        "resume_stage": "brief_approval",
                        "topic_assignment_id": _TA_1,
                        "brief_id": "WE-177",
                        "thread_id": "thread-1",
                    },
                }
            ),
        ):
            await run_td_content_production_task(
                task_id="task-1",
                effective_slug="test-co",
                topic_assignment_ids=[_TA_1],
                company_name="Test Co",
                domain="testco.com",
                ga_run_id=_GA_RUN_ID,
                task_store=task_store,
                event_bus=event_bus,
            )

        topic_run_service.mark_topic_run_waiting_human.assert_awaited_once()
        failure_calls = [
            c for c in task_store.update_task.call_args_list
            if c.kwargs.get("status") == "failed"
        ]
        assert failure_calls == []


class TestDispatchQueuedTdContentRuns:
    @pytest.mark.asyncio
    async def test_pending_approval_tasks_do_not_consume_company_capacity(self):
        from api.tasks.runner import dispatch_queued_td_content_runs
        from api.tasks.models import PipelineTask, TaskStatus

        task_store = MagicMock()
        task_store.list_tasks.return_value = [
            PipelineTask(
                task_id="waiting-human",
                pipeline="td_content",
                company_slug="test-co",
                status=TaskStatus.PENDING_APPROVAL,
            )
        ]
        task_store.create_task.return_value = PipelineTask(
            task_id="new-task",
            pipeline="td_content",
            company_slug="test-co",
        )
        task_store.ensure_created = AsyncMock(return_value=None)
        task_store.register_task_handle = MagicMock()

        event_bus = _make_event_bus_stub()
        topic_run_service = MagicMock()
        topic_run_service.claim_queued_topic_runs = AsyncMock(
            return_value=[
                SimpleNamespace(
                    topic_run_id="run-1",
                    topic_assignment_id=_TA_1,
                    display_id="WE-001",
                    effective_slug="test-co",
                    ga_run_id=_GA_RUN_ID,
                    scheduler_state="queued",
                    pipeline_task_id=None,
                    continuation_payload={},
                    launch_context={
                        "company_name": "Test Co",
                        "domain": "testco.com",
                        "product_slug": None,
                        "product_name": None,
                        "product_description": None,
                        "auto_approve": False,
                    },
                )
            ]
        )
        topic_run_service.mark_claimed_topic_runs_dispatched = AsyncMock(return_value=[])
        topic_run_service.release_topic_run_claims = AsyncMock(return_value=None)

        with patch(
            "api.tasks.runner.api_settings.max_concurrent_content_engine_per_company",
            1,
        ), patch(
            "core.services.content_engine_topic_runs.ContentEngineTopicRunService",
            return_value=topic_run_service,
        ), patch(
            "api.tasks.runner.asyncio.create_task",
            side_effect=_capture_background_task,
        ), patch(
            "api.tasks.runner.run_td_content_production_task",
            new_callable=AsyncMock,
        ):
            results = await dispatch_queued_td_content_runs(
                company_slug="test-co",
                task_store=task_store,
                event_bus=event_bus,
                session_factory=MagicMock(),
            )

        topic_run_service.claim_queued_topic_runs.assert_awaited_once_with(
            company_slug="test-co",
            limit=1,
        )
        assert results == [{
            "topic_run_id": "run-1",
            "topic_assignment_id": _TA_1,
            "task_id": "new-task",
        }]

    @pytest.mark.asyncio
    async def test_claims_only_up_to_available_company_capacity(self):
        from api.tasks.runner import dispatch_queued_td_content_runs
        from api.tasks.models import PipelineTask, TaskStatus

        task_store = MagicMock()
        task_store.list_tasks.return_value = [
            PipelineTask(
                task_id="active-task",
                pipeline="td_content",
                company_slug="test-co",
                status=TaskStatus.RUNNING,
            )
        ]
        task_store.create_task.return_value = PipelineTask(
            task_id="new-task",
            pipeline="td_content",
            company_slug="test-co",
        )
        task_store.ensure_created = AsyncMock(return_value=None)
        task_store.register_task_handle = MagicMock()

        event_bus = _make_event_bus_stub()
        topic_run_service = MagicMock()
        topic_run_service.claim_queued_topic_runs = AsyncMock(
            return_value=[
                SimpleNamespace(
                    topic_run_id="run-1",
                    topic_assignment_id=_TA_1,
                    display_id="WE-001",
                    effective_slug="test-co",
                    ga_run_id=_GA_RUN_ID,
                    scheduler_state="queued",
                    pipeline_task_id=None,
                    continuation_payload={},
                    launch_context={
                        "company_name": "Test Co",
                        "domain": "testco.com",
                        "product_slug": None,
                        "product_name": None,
                        "product_description": None,
                        "auto_approve": False,
                    },
                )
            ]
        )
        topic_run_service.mark_claimed_topic_runs_dispatched = AsyncMock(return_value=[])
        topic_run_service.release_topic_run_claims = AsyncMock(return_value=None)

        with patch(
            "api.tasks.runner.api_settings.max_concurrent_content_engine_per_company",
            2,
        ), patch(
            "core.services.content_engine_topic_runs.ContentEngineTopicRunService",
            return_value=topic_run_service,
        ), patch(
            "api.tasks.runner.asyncio.create_task",
            side_effect=_capture_background_task,
        ), patch(
            "api.tasks.runner.run_td_content_production_task",
            new_callable=AsyncMock,
        ):
            results = await dispatch_queued_td_content_runs(
                company_slug="test-co",
                task_store=task_store,
                event_bus=event_bus,
                session_factory=MagicMock(),
            )

        topic_run_service.claim_queued_topic_runs.assert_awaited_once_with(
            company_slug="test-co",
            limit=1,
        )
        task_store.create_task.assert_called_once()
        task_store.register_task_handle.assert_called_once()
        assert results == [{
            "topic_run_id": "run-1",
            "topic_assignment_id": _TA_1,
            "task_id": "new-task",
        }]

    @pytest.mark.asyncio
    async def test_resume_claim_reuses_existing_task_id(self):
        from api.tasks.runner import dispatch_queued_td_content_runs
        from api.tasks.models import PipelineTask, TaskStatus

        task_store = MagicMock()
        existing_task = PipelineTask(
            task_id="existing-task",
            pipeline="td_content",
            company_slug="test-co",
            status=TaskStatus.PENDING_APPROVAL,
        )
        task_store.list_tasks.return_value = []
        task_store.get_task.return_value = existing_task
        task_store.register_task_handle = MagicMock()

        event_bus = _make_event_bus_stub()
        topic_run_service = MagicMock()
        topic_run_service.claim_queued_topic_runs = AsyncMock(
            return_value=[
                SimpleNamespace(
                    topic_run_id="run-1",
                    topic_assignment_id=_TA_1,
                    display_id="WE-177",
                    effective_slug="test-co",
                    ga_run_id=_GA_RUN_ID,
                    # Real claim snapshots are emitted after the repo flips
                    # scheduler_state to "claimed". The dispatcher must still
                    # detect the resume via the preserved continuation payload.
                    scheduler_state="claimed",
                    pipeline_task_id="existing-task",
                    continuation_payload={
                        "resume_stage": "brief_approval",
                        "brief_id": "WE-177",
                        "approval_data": {"brief_decision": "approve"},
                    },
                    launch_context={
                        "company_name": "Test Co",
                        "domain": "testco.com",
                        "product_slug": None,
                        "product_name": None,
                        "product_description": None,
                        "auto_approve": False,
                    },
                )
            ]
        )
        topic_run_service.mark_claimed_topic_runs_dispatched = AsyncMock(return_value=[])
        topic_run_service.release_topic_run_claims = AsyncMock(return_value=None)

        with patch(
            "api.tasks.runner.api_settings.max_concurrent_content_engine_per_company",
            1,
        ), patch(
            "core.services.content_engine_topic_runs.ContentEngineTopicRunService",
            return_value=topic_run_service,
        ), patch(
            "api.tasks.runner.asyncio.create_task",
            side_effect=_capture_background_task,
        ), patch(
            "api.tasks.runner.run_td_content_production_task",
            new_callable=AsyncMock,
        ) as runner_mock:
            results = await dispatch_queued_td_content_runs(
                company_slug="test-co",
                task_store=task_store,
                event_bus=event_bus,
                session_factory=MagicMock(),
            )

        task_store.create_task.assert_not_called()
        task_store.update_task.assert_called_once_with(
            "existing-task",
            status=TaskStatus.RUNNING,
            error=None,
            approval_payload=None,
        )
        runner_mock.assert_called_once()
        assert runner_mock.call_args.kwargs["td_resume_payload"] == {
            "resume_stage": "brief_approval",
            "brief_id": "WE-177",
            "approval_data": {"brief_decision": "approve"},
        }
        assert runner_mock.call_args.kwargs["td_resume_approval"] == {
            "brief_decision": "approve",
        }
        assert results == [{
            "topic_run_id": "run-1",
            "topic_assignment_id": _TA_1,
            "task_id": "existing-task",
        }]
