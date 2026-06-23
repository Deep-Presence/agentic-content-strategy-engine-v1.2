"""Tests for gap analysis API endpoints."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.tasks.models import TaskStatus
from tests._support.model_config_service import FailingModelConfigService


# ── Minimal valid payload (simplified schema) ──────────────────────

MINIMAL_PAYLOAD = {
    "company_name": "Test Co",
    "domain": "testco.com",
}


@pytest.fixture
def mock_gap_pipeline():
    """Mock run_gap_pipeline_task to complete instantly."""
    with patch(
        "api.routers.gap_analysis.run_gap_pipeline_task",
        new_callable=AsyncMock,
    ) as mock_fn:

        async def _complete_task(task_id, **kwargs):
            task_store = kwargs["task_store"]
            event_bus = kwargs["event_bus"]
            request = kwargs["request"]
            event_bus.publish(task_id, "pipeline_start", {"pipeline": "gap_analysis"})
            task_store.update_task(
                task_id,
                status=TaskStatus.COMPLETED,
                result={
                    "produced_artifacts": [
                        {"type": "gap_analysis", "slug": task_store.get_task(task_id).effective_slug},
                    ],
                },
            )
            event_bus.publish(task_id, "completed", {"pipeline": "gap_analysis"})

        mock_fn.side_effect = _complete_task
        yield mock_fn


class TestStartGapAnalysis:
    def test_returns_run_id(self, client: TestClient, mock_gap_pipeline) -> None:
        resp = client.post("/api/v1/gap-analysis/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 202
        data = resp.json()
        assert "run_id" in data
        assert data["pipeline"] == "gap_analysis"
        assert data["company_slug"] == "test-co"
        assert data["status"] == "running"

    def test_minimal_payload_only_requires_name_and_domain(
        self, client: TestClient, mock_gap_pipeline
    ) -> None:
        resp = client.post(
            "/api/v1/gap-analysis/start",
            json={"company_name": "Test Co", "domain": "testco.com"},
        )
        assert resp.status_code == 202

    def test_validation_error_missing_company_name(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/gap-analysis/start",
            json={"domain": "testco.com"},
        )
        assert resp.status_code == 422

    def test_validation_error_missing_domain(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/gap-analysis/start",
            json={"company_name": "Test Co"},
        )
        assert resp.status_code == 422

    def test_slug_conflict(
        self, client: TestClient, task_store, mock_gap_pipeline
    ) -> None:
        task_store.create_task("gap_analysis", "test-co")
        resp = client.post("/api/v1/gap-analysis/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 409

    def test_skip_steps_forwarded(self, client: TestClient, mock_gap_pipeline) -> None:
        resp = client.post(
            "/api/v1/gap-analysis/start",
            json={**MINIMAL_PAYLOAD, "skip_steps": [1, 2]},
        )
        assert resp.status_code == 202
        call_kwargs = mock_gap_pipeline.call_args
        assert call_kwargs is not None
        request_obj = call_kwargs.kwargs.get("request")
        assert request_obj is not None
        assert request_obj.skip_steps == [1, 2]

    def test_concurrent_company_and_product_ok(
        self, client: TestClient, mock_gap_pipeline
    ) -> None:
        """Company-level and product-level runs for same tenant coexist."""
        resp1 = client.post(
            "/api/v1/gap-analysis/start",
            json={"company_name": "Test Co", "domain": "testco.com"},
        )
        time.sleep(0.2)
        resp2 = client.post(
            "/api/v1/gap-analysis/start",
            json={"company_name": "Test Co", "domain": "testco.com", "product_slug": "analytics"},
        )
        assert resp1.status_code == 202
        assert resp2.status_code == 202

    def test_optional_fields_accepted(self, client: TestClient, mock_gap_pipeline) -> None:
        resp = client.post(
            "/api/v1/gap-analysis/start",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "seed_urls": ["https://testco.com/blog"],
                "max_queries": 200,
                "platforms": ["perplexity", "openai"],
                "language": "en",
                "region": "us",
                "additional_constraints": "Focus on expense management",
                "max_crawl_pages": 50,
                "max_crawl_depth": 3,
            },
        )
        assert resp.status_code == 202

    def test_missing_byok_config_blocks_start_before_task_creation(
        self, client: TestClient
    ) -> None:
        service = FailingModelConfigService()
        client.app.state.model_config_service = service

        with patch(
            "api.routers.gap_analysis.create_task_durable",
            new_callable=AsyncMock,
        ) as create_task:
            resp = client.post(
                "/api/v1/gap-analysis/start",
                json={**MINIMAL_PAYLOAD, "force_rerun": True},
            )

        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert detail["code"] == "byok_model_config_required"
        assert detail["missing_credential"] is True
        assert detail["reason"] == "model_config_required"
        assert "gap.query_generation" in detail["required_agent_keys"]
        assert "gap.report_generation" in detail["required_agent_keys"]
        assert "gap.search.perplexity" in detail["required_agent_keys"]
        assert "gap.query_generation" in service.preflight_calls[0][1]
        create_task.assert_not_awaited()


class TestStartGapAnalysisGuard:
    """Guard: return 200 already_exists when artifacts exist instead of launching a new run."""

    def _make_sentinel(
        self,
        artifacts_root: Path,
        effective_slug: str,
        filename: str = "gap_analysis_complete.json",
    ) -> None:
        d = artifacts_root / "gap_analysis" / effective_slug
        d.mkdir(parents=True, exist_ok=True)
        (d / filename).touch()

    def test_start_returns_already_exists_when_complete_json_present(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        self._make_sentinel(artifacts_root, "test-co")
        resp = client.post("/api/v1/gap-analysis/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()
        assert data["already_exists"] is True
        assert data["status"] == "already_exists"
        assert "force_rerun" in data["message"].lower()

    def test_start_returns_already_exists_when_only_analysis_json_present(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        """Fallback sentinel (s6 output) also triggers the guard."""
        self._make_sentinel(artifacts_root, "test-co", "analysis.json")
        resp = client.post("/api/v1/gap-analysis/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 200
        assert resp.json()["already_exists"] is True

    def test_start_force_rerun_bypasses_guard(
        self, client: TestClient, artifacts_root: Path, mock_gap_pipeline
    ) -> None:
        self._make_sentinel(artifacts_root, "test-co")
        resp = client.post(
            "/api/v1/gap-analysis/start",
            json={**MINIMAL_PAYLOAD, "force_rerun": True},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["already_exists"] is False

    def test_start_already_exists_includes_last_task_run_id(
        self, client: TestClient, artifacts_root: Path, task_store
    ) -> None:
        self._make_sentinel(artifacts_root, "test-co")
        task = task_store.create_task("gap_analysis", "test-co")
        task_store.update_task(task.task_id, status=TaskStatus.COMPLETED)
        resp = client.post("/api/v1/gap-analysis/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 200
        assert resp.json()["run_id"] == task.task_id

    def test_start_already_exists_uses_existing_prefix_when_no_task_record(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        self._make_sentinel(artifacts_root, "test-co", "analysis.json")
        resp = client.post("/api/v1/gap-analysis/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"].startswith("existing-")
        assert "test-co" in data["run_id"]

    def test_start_new_company_no_artifacts_proceeds_normally(
        self, client: TestClient, artifacts_root: Path, mock_gap_pipeline
    ) -> None:
        """No artifacts for test-co yet — should proceed normally."""
        resp = client.post(
            "/api/v1/gap-analysis/start",
            json={"company_name": "Test Co", "domain": "testco.com"},
        )
        assert resp.status_code == 202
        assert resp.json()["already_exists"] is False

    def test_product_level_checks_effective_slug_dir(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        """Product run must check the effective_slug dir, not the bare company slug."""
        self._make_sentinel(artifacts_root, "test-co__corp-card", "analysis.json")
        resp = client.post(
            "/api/v1/gap-analysis/start",
            json={**MINIMAL_PAYLOAD, "product_slug": "corp-card"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["already_exists"] is True
        assert data["product_slug"] == "corp-card"


class TestGetGapAnalysisStatus:
    def test_status_after_start(
        self, client: TestClient, task_store
    ) -> None:
        task = task_store.create_task("gap_analysis", "test-co")
        status_resp = client.get(f"/api/v1/gap-analysis/{task.task_id}/status")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["status"] == "running"
        assert data["company_slug"] == "test-co"

    def test_completed_status(
        self, client: TestClient, task_store, mock_gap_pipeline
    ) -> None:
        resp = client.post("/api/v1/gap-analysis/start", json=MINIMAL_PAYLOAD)
        run_id = resp.json()["run_id"]

        # Simulate background task completion by updating task store directly
        task_store.update_task(
            run_id,
            status=TaskStatus.COMPLETED,
            result={
                "produced_artifacts": [
                    {"type": "gap_analysis", "slug": "test-co"},
                ],
            },
        )

        status_resp = client.get(f"/api/v1/gap-analysis/{run_id}/status")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["status"] == "completed"
        assert data["company_slug"] == "test-co"
        assert data["result"] is not None
        assert data["result"]["produced_artifacts"] == [
            {"type": "gap_analysis", "slug": "test-co"},
        ]

    def test_failed_status(
        self, client: TestClient, task_store, mock_gap_pipeline
    ) -> None:
        resp = client.post("/api/v1/gap-analysis/start", json=MINIMAL_PAYLOAD)
        run_id = resp.json()["run_id"]

        # Simulate background task failure by updating task store directly
        task_store.update_task(
            run_id, status=TaskStatus.FAILED, error="Pipeline failed"
        )

        status_resp = client.get(f"/api/v1/gap-analysis/{run_id}/status")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["status"] == "failed"
        assert "Pipeline failed" in data["error"]

    def test_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/gap-analysis/nonexistent-id/status")
        assert resp.status_code == 404
