"""Tests for request logging middleware."""
from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient


class TestRequestLogging:
    def test_logs_request_completed(self, client: TestClient, caplog) -> None:
        with caplog.at_level(logging.INFO, logger="api.middleware"):
            client.get("/health")

        records = [r for r in caplog.records if "api.middleware" in r.name]
        assert any(r.message == "request_completed" for r in records), (
            f"Expected 'request_completed' log, got: {[r.message for r in records]}"
        )

    def test_logs_status_code(self, client: TestClient, caplog) -> None:
        with caplog.at_level(logging.INFO, logger="api.middleware"):
            client.get("/health")

        records = [r for r in caplog.records if "api.middleware" in r.name]
        completed = [r for r in records if r.message == "request_completed"]
        assert completed, "No request_completed log found"
        assert completed[0].status_code == 200  # type: ignore[attr-defined]

    def test_logs_duration(self, client: TestClient, caplog) -> None:
        with caplog.at_level(logging.INFO, logger="api.middleware"):
            client.get("/health")

        records = [r for r in caplog.records if "api.middleware" in r.name]
        completed = [r for r in records if r.message == "request_completed"]
        assert completed, "No request_completed log found"
        assert hasattr(completed[0], "duration_ms")
        assert completed[0].duration_ms >= 0  # type: ignore[attr-defined]

    def test_correlation_id_in_response(self, client: TestClient) -> None:
        response = client.get("/health")
        assert "X-Correlation-ID" in response.headers
        # Should be a valid UUID-like string
        assert len(response.headers["X-Correlation-ID"]) > 0

    def test_forwarded_correlation_id(self, client: TestClient) -> None:
        response = client.get(
            "/health", headers={"X-Correlation-ID": "test-corr-123"},
        )
        assert response.headers["X-Correlation-ID"] == "test-corr-123"


class TestRequestIdHeader:
    """Layer 2 — X-Request-ID header (always server-generated UUID4)."""

    def test_request_id_in_response(self, client: TestClient) -> None:
        response = client.get("/health")
        assert "X-Request-ID" in response.headers
        # Must be a UUID-like string (36 chars with dashes)
        rid = response.headers["X-Request-ID"]
        assert len(rid) == 36
        assert rid.count("-") == 4

    def test_request_id_always_unique(self, client: TestClient) -> None:
        r1 = client.get("/health")
        r2 = client.get("/health")
        assert r1.headers["X-Request-ID"] != r2.headers["X-Request-ID"]

    def test_request_id_independent_of_correlation_id(self, client: TestClient) -> None:
        response = client.get(
            "/health", headers={"X-Correlation-ID": "upstream-corr-abc"},
        )
        # Correlation ID is forwarded
        assert response.headers["X-Correlation-ID"] == "upstream-corr-abc"
        # Request ID is server-generated, NOT the forwarded value
        assert response.headers["X-Request-ID"] != "upstream-corr-abc"

    def test_correlation_id_defaults_to_request_id(self, client: TestClient) -> None:
        """When no X-Correlation-ID is sent, it defaults to request_id."""
        response = client.get("/health")
        assert response.headers["X-Correlation-ID"] == response.headers["X-Request-ID"]

    def test_long_correlation_id_truncated(self, client: TestClient) -> None:
        long_corr = "x" * 256
        response = client.get(
            "/health", headers={"X-Correlation-ID": long_corr},
        )
        assert len(response.headers["X-Correlation-ID"]) == 128
