"""Tests for auth failure structured logging (PB-84).

401 responses bypass ``RequestLoggingMiddleware`` because the ASGI
``AuthMiddleware`` short-circuits before the Starlette dispatch layer.
These tests verify that structured warning logs are emitted on auth failures.
"""
from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient


class TestAuthFailureLogging:
    """Structured logging on 401 auth failures."""

    def test_missing_token_logs_auth_failure(
        self, public_client: TestClient, caplog
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="api.auth.middleware"):
            public_client.get("/api/v1/tasks")

        records = [r for r in caplog.records if r.name == "api.auth.middleware"]
        auth_failures = [r for r in records if r.message == "auth_failure"]
        assert auth_failures, f"Expected auth_failure log, got: {[r.message for r in records]}"
        assert auth_failures[0].error_code == "missing_token"  # type: ignore[attr-defined]

    def test_invalid_token_logs_auth_failure(
        self, public_client: TestClient, caplog
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="api.auth.middleware"):
            public_client.get(
                "/api/v1/tasks", headers={"Authorization": "Bearer bad-token"}
            )

        records = [r for r in caplog.records if r.name == "api.auth.middleware"]
        auth_failures = [r for r in records if r.message == "auth_failure"]
        assert auth_failures, f"Expected auth_failure log, got: {[r.message for r in records]}"
        assert auth_failures[0].error_code == "invalid_token"  # type: ignore[attr-defined]

    def test_auth_failure_includes_path(
        self, public_client: TestClient, caplog
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="api.auth.middleware"):
            public_client.get("/api/v1/tasks")

        records = [r for r in caplog.records if r.name == "api.auth.middleware"]
        auth_failures = [r for r in records if r.message == "auth_failure"]
        assert auth_failures
        assert auth_failures[0].path == "/api/v1/tasks"  # type: ignore[attr-defined]

    def test_auth_failure_includes_method(
        self, public_client: TestClient, caplog
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="api.auth.middleware"):
            public_client.post("/api/v1/gap-analysis/start", json={})

        records = [r for r in caplog.records if r.name == "api.auth.middleware"]
        auth_failures = [r for r in records if r.message == "auth_failure"]
        assert auth_failures
        assert auth_failures[0].method == "POST"  # type: ignore[attr-defined]

    def test_stream_token_misuse_logs_auth_failure(
        self, app, auth_store, test_user, test_company, public_client: TestClient, caplog
    ) -> None:
        """Stream token used on non-SSE path should log auth_failure."""
        stream_token = auth_store.create_stream_token(
            test_user.id, test_company.slug
        )
        with caplog.at_level(logging.WARNING, logger="api.auth.middleware"):
            public_client.get(
                "/api/v1/tasks",
                headers={"Authorization": f"Bearer {stream_token}"},
            )

        records = [r for r in caplog.records if r.name == "api.auth.middleware"]
        auth_failures = [r for r in records if r.message == "auth_failure"]
        assert auth_failures
        assert auth_failures[0].error_code == "invalid_token"  # type: ignore[attr-defined]
