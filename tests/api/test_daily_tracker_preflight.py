"""BYOK preflight tests for Daily Tracker launch routes."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from tests._support.model_config_service import FailingModelConfigService


def test_missing_byok_config_blocks_daily_run_before_task_creation(
    client: TestClient,
) -> None:
    service = FailingModelConfigService()
    client.app.state.model_config_service = service

    with patch(
        "api.routers._helpers.create_task_durable",
        new_callable=AsyncMock,
    ) as create_task:
        resp = client.post(
            "/api/v1/daily-tracker/runs",
            json={"workspace_slug": "test-co"},
        )

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["code"] == "byok_model_config_required"
    assert detail["missing_credential"] is True
    assert detail["reason"] == "model_config_required"
    assert detail["required_agent_keys"] == ["daily_tracker.platform.perplexity"]
    assert service.preflight_calls[0][0]
    assert service.preflight_calls[0][1] == ["daily_tracker.platform.perplexity"]
    create_task.assert_not_awaited()
