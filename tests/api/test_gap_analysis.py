"""Tests for gap analysis API endpoints."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.tasks.models import TaskStatus
from api.tasks.store import TaskStore


# ── Minimal valid payload (simplified schema) ──────────────────────

MINIMAL_PAYLOAD = {
    "company_name": "Ramp",
    "domain": "ramp.com",
}


@pytest.fixture
def mock_gap_pipeline():
    """Mock run_gap_analysis to return instantly."""
    from core.models.gap_analysis import GapReport

    mock_report = GapReport(
        report_md="# Test Report",
        report_json={"executive_summary": "test"},
        generation_spec_md="# Spec",
        generation_spec_json={},
        visualization_paths=[],
    )
    with patch(
        "api.tasks.runner.run_gap_analysis",
        new_callable=AsyncMock,
        return_value=mock_report,
    ) as mock_fn:
        yield mock_fn


class TestStartGapAnalysis:
    def test_returns_run_id(self, client: TestClient, mock_gap_pipeline) -> None:
        resp = client.post("/api/v1/gap-analysis/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 202
        data = resp.json()
        assert "run_id" in data
        assert data["pipeline"] == "gap_analysis"
        assert data["company_slug"] == "ramp"
        assert data["status"] == "running"

    def test_minimal_payload_only_requires_name_and_domain(
        self, client: TestClient, mock_gap_pipeline
    ) -> None:
        resp = client.post(
            "/api/v1/gap-analysis/start",
            json={"company_name": "Webflow", "domain": "webflow.com"},
        )
        assert resp.status_code == 202

    def test_validation_error_missing_company_name(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/gap-analysis/start",
            json={"domain": "ramp.com"},
        )
        assert resp.status_code == 422

    def test_validation_error_missing_domain(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/gap-analysis/start",
            json={"company_name": "Ramp"},
        )
        assert resp.status_code == 422

    def test_slug_conflict(
        self, client: TestClient, task_store: TaskStore, mock_gap_pipeline
    ) -> None:
        task_store.create_task("gap_analysis", "ramp")
        resp = client.post("/api/v1/gap-analysis/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 409

    def test_skip_steps_forwarded(self, client: TestClient, mock_gap_pipeline) -> None:
        resp = client.post(
            "/api/v1/gap-analysis/start",
            json={**MINIMAL_PAYLOAD, "skip_steps": [1, 2]},
        )
        assert resp.status_code == 202
        time.sleep(0.2)
        call_kwargs = mock_gap_pipeline.call_args
        assert call_kwargs is not None
        assert call_kwargs.kwargs.get("skip_steps") == [1, 2]

    def test_concurrent_different_slugs_ok(
        self, client: TestClient, mock_gap_pipeline
    ) -> None:
        resp1 = client.post(
            "/api/v1/gap-analysis/start",
            json={"company_name": "Ramp", "domain": "ramp.com"},
        )
        time.sleep(0.2)
        resp2 = client.post(
            "/api/v1/gap-analysis/start",
            json={"company_name": "Carta", "domain": "carta.com"},
        )
        assert resp1.status_code == 202
        assert resp2.status_code == 202

    def test_optional_fields_accepted(self, client: TestClient, mock_gap_pipeline) -> None:
        resp = client.post(
            "/api/v1/gap-analysis/start",
            json={
                "company_name": "Ramp",
                "domain": "ramp.com",
                "seed_urls": ["https://ramp.com/blog"],
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


class TestGetGapAnalysisStatus:
    def test_status_after_start(
        self, client: TestClient, task_store: TaskStore
    ) -> None:
        task = task_store.create_task("gap_analysis", "ramp")
        status_resp = client.get(f"/api/v1/gap-analysis/{task.task_id}/status")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["status"] == "running"
        assert data["company_slug"] == "ramp"

    def test_completed_status(self, client: TestClient, mock_gap_pipeline) -> None:
        resp = client.post("/api/v1/gap-analysis/start", json=MINIMAL_PAYLOAD)
        run_id = resp.json()["run_id"]
        time.sleep(0.3)

        status_resp = client.get(f"/api/v1/gap-analysis/{run_id}/status")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["status"] == "completed"
        assert data["company_slug"] == "ramp"
        assert data["result"] is not None
        assert data["result"]["produced_artifacts"] == [
            {"type": "gap_analysis", "slug": "ramp"},
        ]

    def test_failed_status(self, client: TestClient, mock_gap_pipeline) -> None:
        mock_gap_pipeline.side_effect = RuntimeError("Pipeline failed")
        resp = client.post("/api/v1/gap-analysis/start", json=MINIMAL_PAYLOAD)
        run_id = resp.json()["run_id"]
        time.sleep(0.3)

        status_resp = client.get(f"/api/v1/gap-analysis/{run_id}/status")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["status"] == "failed"
        assert "Pipeline failed" in data["error"]

    def test_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/gap-analysis/nonexistent-id/status")
        assert resp.status_code == 404
