"""Tests for the two-phase TD → GA → CE API endpoints.

POST /api/v1/content/v13/from-topics/gap-analysis   (Phase 1)
POST /api/v1/content/v13/from-topics/start-production  (Phase 2)

Follows the same patterns as test_content_v13_from_topics.py.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# Fixed UUIDs for test fixtures
_TA_1 = str(uuid.uuid5(uuid.NAMESPACE_DNS, "ta-1"))
_TA_2 = str(uuid.uuid5(uuid.NAMESPACE_DNS, "ta-2"))
_GA_RUN_ID = str(uuid.uuid4())


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
