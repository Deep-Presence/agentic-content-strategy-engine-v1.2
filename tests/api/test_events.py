"""Tests for SSE events endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient



class TestSSEEvents:
    def test_unknown_task_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/tasks/nonexistent/events")
        assert resp.status_code == 404

    def test_sse_content_type(
        self, client: TestClient, task_store, event_bus
    ) -> None:
        task = task_store.create_task("gap_analysis", "test-co")
        event_bus.publish(task.task_id, "pipeline_start", {"pipeline": "gap_analysis"})
        event_bus.publish(task.task_id, "completed", {})

        with client.stream("GET", f"/api/v1/tasks/{task.task_id}/events") as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]

    def test_sse_replays_existing_events(
        self, client: TestClient, task_store, event_bus
    ) -> None:
        task = task_store.create_task("gap_analysis", "test-co")
        event_bus.publish(task.task_id, "step_start", {"step": 1})
        event_bus.publish(task.task_id, "step_complete", {"step": 1})
        event_bus.publish(task.task_id, "completed", {})

        with client.stream("GET", f"/api/v1/tasks/{task.task_id}/events") as resp:
            chunks = []
            for line in resp.iter_lines():
                chunks.append(line)

            combined = "\n".join(chunks)
            assert "event: step_start" in combined
            assert "event: step_complete" in combined
            assert "event: completed" in combined

    def test_sse_stream_terminates_on_completed(
        self, client: TestClient, task_store, event_bus
    ) -> None:
        """Stream should terminate after a completed event is replayed."""
        task = task_store.create_task("gap_analysis", "test-co")
        event_bus.publish(task.task_id, "pipeline_start", {"pipeline": "gap_analysis"})
        event_bus.publish(task.task_id, "completed", {"result": "done"})

        with client.stream("GET", f"/api/v1/tasks/{task.task_id}/events") as resp:
            lines = list(resp.iter_lines())

        # Should have lines for both events — stream closed after completed
        combined = "\n".join(lines)
        assert "event: pipeline_start" in combined
        assert "event: completed" in combined

    def test_sse_stream_terminates_on_failed(
        self, client: TestClient, task_store, event_bus
    ) -> None:
        """Stream should terminate after a failed event is replayed."""
        task = task_store.create_task("gap_analysis", "test-co")
        event_bus.publish(task.task_id, "step_start", {"step": 1})
        event_bus.publish(task.task_id, "failed", {"error": "boom"})

        with client.stream("GET", f"/api/v1/tasks/{task.task_id}/events") as resp:
            lines = list(resp.iter_lines())

        combined = "\n".join(lines)
        assert "event: step_start" in combined
        assert "event: failed" in combined
