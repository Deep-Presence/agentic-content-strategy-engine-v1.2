"""Tests for request logging middleware."""
from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient


class TestRequestLogging:
    def test_logs_request(self, client: TestClient, caplog) -> None:
        with caplog.at_level(logging.INFO, logger="api.middleware"):
            client.get("/health")

        # Check that a log entry was created for the request
        log_messages = [r.message for r in caplog.records if "api.middleware" in r.name]
        assert any("GET" in msg and "/health" in msg for msg in log_messages)

    def test_logs_status_code(self, client: TestClient, caplog) -> None:
        with caplog.at_level(logging.INFO, logger="api.middleware"):
            client.get("/health")

        log_messages = [r.message for r in caplog.records if "api.middleware" in r.name]
        assert any("200" in msg for msg in log_messages)

    def test_logs_duration(self, client: TestClient, caplog) -> None:
        with caplog.at_level(logging.INFO, logger="api.middleware"):
            client.get("/health")

        log_messages = [r.message for r in caplog.records if "api.middleware" in r.name]
        assert any("ms" in msg for msg in log_messages)
