"""Tests for the CPS scoring API endpoint.

Covers:
  - POST /api/v1/cps/score  (standalone CPS scoring)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_PAYLOAD = {
    "content_markdown": "# Best CRM Software\n\nThis comprehensive guide covers the top CRM platforms for B2B companies.",
    "target_queries": ["best CRM software", "top CRM platforms"],
    "content_url": "https://example.com/crm-guide",
}

MOCK_CPS_RESULT = {
    "cps_score": 0.72,
    "per_engine": {
        "chatgpt_search": 0.75,
        "claude_search": 0.68,
        "gemini_search": 0.71,
        "perplexity": 0.74,
    },
    "per_query": [
        {"query": "best CRM software", "cps_score": 0.73},
        {"query": "top CRM platforms", "cps_score": 0.71},
    ],
    "model_version": "v1",
    "feature_config": "option_b_full31",
    "target_weight": 0.5,
}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestCPSScoreEndpoint:
    """POST /api/v1/cps/score — success cases."""

    @patch("api.routers.cps.get_cps_scorer")
    def test_score_success(
        self, mock_get_scorer: MagicMock, client: TestClient
    ) -> None:
        """200 — valid payload returns CPS scores."""
        scorer = MagicMock()
        scorer.score_async = AsyncMock(return_value=MOCK_CPS_RESULT)
        mock_get_scorer.return_value = scorer

        resp = client.post("/api/v1/cps/score", json=VALID_PAYLOAD)

        assert resp.status_code == 200
        data = resp.json()
        assert data["cps_score"] == 0.72
        assert "per_engine" in data
        assert "per_query" in data
        assert data["model_version"] == "v1"
        assert data["feature_config"] == "option_b_full31"
        assert data["target_weight"] == 0.5

    @patch("api.routers.cps.get_cps_scorer")
    def test_content_url_passed_through(
        self, mock_get_scorer: MagicMock, client: TestClient
    ) -> None:
        """Verify content_url reaches scorer.score_async."""
        scorer = MagicMock()
        scorer.score_async = AsyncMock(return_value=MOCK_CPS_RESULT)
        mock_get_scorer.return_value = scorer

        client.post("/api/v1/cps/score", json=VALID_PAYLOAD)

        call_kwargs = scorer.score_async.call_args[1]
        assert call_kwargs["content_url"] == "https://example.com/crm-guide"

    @patch("api.routers.cps.get_cps_scorer")
    def test_default_content_url(
        self, mock_get_scorer: MagicMock, client: TestClient
    ) -> None:
        """Omitting content_url uses default."""
        scorer = MagicMock()
        scorer.score_async = AsyncMock(return_value=MOCK_CPS_RESULT)
        mock_get_scorer.return_value = scorer

        payload = {
            "content_markdown": "# Good content\n\n" + "x " * 30,
            "target_queries": ["test query"],
        }
        resp = client.post("/api/v1/cps/score", json=payload)

        assert resp.status_code == 200
        call_kwargs = scorer.score_async.call_args[1]
        assert call_kwargs["content_url"] == "https://example.com"

    @patch("api.routers.cps.get_cps_scorer")
    def test_multiple_queries_per_query_count(
        self, mock_get_scorer: MagicMock, client: TestClient
    ) -> None:
        """per_query list has same length as target_queries."""
        scorer = MagicMock()
        scorer.score_async = AsyncMock(return_value=MOCK_CPS_RESULT)
        mock_get_scorer.return_value = scorer

        resp = client.post("/api/v1/cps/score", json=VALID_PAYLOAD)

        data = resp.json()
        assert len(data["per_query"]) == 2

    @patch("api.routers.cps.get_cps_scorer")
    def test_response_schema_complete(
        self, mock_get_scorer: MagicMock, client: TestClient
    ) -> None:
        """All expected fields are present and correctly typed."""
        scorer = MagicMock()
        scorer.score_async = AsyncMock(return_value=MOCK_CPS_RESULT)
        mock_get_scorer.return_value = scorer

        resp = client.post("/api/v1/cps/score", json=VALID_PAYLOAD)
        data = resp.json()

        assert isinstance(data["cps_score"], float)
        assert isinstance(data["per_engine"], dict)
        assert len(data["per_engine"]) == 4
        assert isinstance(data["per_query"], list)
        assert isinstance(data["model_version"], str)
        assert isinstance(data["feature_config"], str)
        assert isinstance(data["target_weight"], float)


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestCPSScoreErrors:
    """POST /api/v1/cps/score — error and edge cases."""

    @patch("api.routers.cps.get_cps_scorer")
    def test_scorer_unavailable_503(
        self, mock_get_scorer: MagicMock, client: TestClient
    ) -> None:
        """503 when get_cps_scorer() returns None (torch/model absent)."""
        mock_get_scorer.return_value = None

        resp = client.post("/api/v1/cps/score", json=VALID_PAYLOAD)

        assert resp.status_code == 503
        assert "unavailable" in resp.json()["detail"].lower()

    def test_content_too_short_422(self, client: TestClient) -> None:
        """422 when content_markdown is too short (<50 chars)."""
        payload = {
            "content_markdown": "Short",
            "target_queries": ["test query"],
        }
        resp = client.post("/api/v1/cps/score", json=payload)
        assert resp.status_code == 422

    def test_empty_queries_422(self, client: TestClient) -> None:
        """422 when target_queries is empty."""
        payload = {
            "content_markdown": "# Good content\n\n" + "x " * 30,
            "target_queries": [],
        }
        resp = client.post("/api/v1/cps/score", json=payload)
        assert resp.status_code == 422

    def test_too_many_queries_422(self, client: TestClient) -> None:
        """422 when target_queries exceeds 10."""
        payload = {
            "content_markdown": "# Good content\n\n" + "x " * 30,
            "target_queries": [f"query {i}" for i in range(11)],
        }
        resp = client.post("/api/v1/cps/score", json=payload)
        assert resp.status_code == 422

    @patch("api.routers.cps.get_cps_scorer")
    def test_scorer_raises_500(
        self, mock_get_scorer: MagicMock, client: TestClient
    ) -> None:
        """500 when scorer.score_async raises an unexpected error."""
        scorer = MagicMock()
        scorer.score_async = AsyncMock(side_effect=RuntimeError("inference failed"))
        mock_get_scorer.return_value = scorer

        resp = client.post("/api/v1/cps/score", json=VALID_PAYLOAD)

        assert resp.status_code == 500
        assert "scoring failed" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Auth enforcement
# ---------------------------------------------------------------------------


class TestCPSScoreAuth:
    """Auth and RBAC tests for the CPS endpoint."""

    def test_unauthenticated_401(self, public_client: TestClient) -> None:
        """401 when no auth token is provided."""
        resp = public_client.post("/api/v1/cps/score", json=VALID_PAYLOAD)
        assert resp.status_code == 401

    @patch("api.routers.cps.get_cps_scorer")
    def test_viewer_allowed(
        self, mock_get_scorer: MagicMock, viewer_client: TestClient
    ) -> None:
        """Viewers can score content (read-only operation)."""
        scorer = MagicMock()
        scorer.score_async = AsyncMock(return_value=MOCK_CPS_RESULT)
        mock_get_scorer.return_value = scorer

        resp = viewer_client.post("/api/v1/cps/score", json=VALID_PAYLOAD)
        assert resp.status_code == 200
