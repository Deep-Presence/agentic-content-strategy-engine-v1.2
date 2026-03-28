"""Tests for SSE endpoint context binding (PB-83).

The SSE ``/events`` path bypasses ``RequestLoggingMiddleware``, so context
must be bound explicitly inside the endpoint handler.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient



class TestSSEContextBinding:
    """Verify that SSE endpoint binds structured logging context."""

    def test_sse_binds_task_id(
        self, client: TestClient, task_store, event_bus
    ) -> None:
        task = task_store.create_task("gap_analysis", "test-co")
        event_bus.publish(task.task_id, "completed", {})

        with patch("api.routers.events.bind_context") as mock_bind:
            with client.stream("GET", f"/api/v1/tasks/{task.task_id}/events") as resp:
                list(resp.iter_lines())

        # At least one call should include task_id
        all_kwargs = {}
        for call in mock_bind.call_args_list:
            all_kwargs.update(call.kwargs)
        assert all_kwargs.get("task_id") == task.task_id

    def test_sse_binds_company_slug(
        self, client: TestClient, task_store, event_bus
    ) -> None:
        task = task_store.create_task("gap_analysis", "test-co")
        event_bus.publish(task.task_id, "completed", {})

        with patch("api.routers.events.bind_context") as mock_bind:
            with client.stream("GET", f"/api/v1/tasks/{task.task_id}/events") as resp:
                list(resp.iter_lines())

        all_kwargs = {}
        for call in mock_bind.call_args_list:
            all_kwargs.update(call.kwargs)
        assert all_kwargs.get("company_slug") == "test-co"

    def test_sse_binds_pipeline_name(
        self, client: TestClient, task_store, event_bus
    ) -> None:
        task = task_store.create_task("gap_analysis", "test-co")
        event_bus.publish(task.task_id, "completed", {})

        with patch("api.routers.events.bind_context") as mock_bind:
            with client.stream("GET", f"/api/v1/tasks/{task.task_id}/events") as resp:
                list(resp.iter_lines())

        all_kwargs = {}
        for call in mock_bind.call_args_list:
            all_kwargs.update(call.kwargs)
        assert all_kwargs.get("pipeline_name") == "gap_analysis"

    def test_sse_generates_correlation_id(
        self, client: TestClient, task_store, event_bus
    ) -> None:
        task = task_store.create_task("gap_analysis", "test-co")
        event_bus.publish(task.task_id, "completed", {})

        with patch("api.routers.events.bind_context") as mock_bind:
            with client.stream("GET", f"/api/v1/tasks/{task.task_id}/events") as resp:
                list(resp.iter_lines())

        all_kwargs = {}
        for call in mock_bind.call_args_list:
            all_kwargs.update(call.kwargs)
        assert "correlation_id" in all_kwargs
        # Should be a UUID-like string (36 chars)
        assert len(all_kwargs["correlation_id"]) == 36

    def test_sse_forwards_correlation_id(
        self, client: TestClient, task_store, event_bus
    ) -> None:
        task = task_store.create_task("gap_analysis", "test-co")
        event_bus.publish(task.task_id, "completed", {})

        with patch("api.routers.events.bind_context") as mock_bind:
            with client.stream(
                "GET",
                f"/api/v1/tasks/{task.task_id}/events",
                headers={"X-Correlation-ID": "upstream-abc"},
            ) as resp:
                list(resp.iter_lines())

        all_kwargs = {}
        for call in mock_bind.call_args_list:
            all_kwargs.update(call.kwargs)
        assert all_kwargs.get("correlation_id") == "upstream-abc"

    def test_sse_clears_context_after_stream(
        self, client: TestClient, task_store, event_bus
    ) -> None:
        task = task_store.create_task("gap_analysis", "test-co")
        event_bus.publish(task.task_id, "completed", {})

        with patch("api.routers.events.clear_context") as mock_clear:
            with client.stream("GET", f"/api/v1/tasks/{task.task_id}/events") as resp:
                list(resp.iter_lines())

        mock_clear.assert_called()
