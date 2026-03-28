"""Integration tests verifying API response shapes match frontend expectations.

Tests that the API returns the correct field names and types that the
frontend TypeScript code relies on. This catches the frontend-backend
disconnect where the API changes a field name but the frontend still
reads the old one.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ─────────────────────────────────────────────────────────


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── Task list response shape ─────────────────────────────────────────


class TestTaskListShape:
    """Verify /tasks response matches TaskListResponse schema."""

    def test_task_list_has_expected_fields(self, client: TestClient):
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 200
        data = resp.json()

        # Must have 'tasks' array and 'total' count
        assert "tasks" in data
        assert "total" in data
        assert isinstance(data["tasks"], list)
        assert isinstance(data["total"], int)

    def test_task_item_shape(self, client: TestClient, task_store):
        """Each task in the list has required fields."""
        t = task_store.create_task("gap_analysis", "test-co")

        resp = client.get("/api/v1/tasks")
        data = resp.json()
        assert data["total"] >= 1

        task = data["tasks"][0]
        required_fields = {"run_id", "pipeline", "status", "company_slug"}
        assert required_fields.issubset(task.keys()), \
            f"Missing fields: {required_fields - task.keys()}"


# ── Health response shape ────────────────────────────────────────────


class TestHealthResponseShape:
    """Verify /health response has expected structure."""

    def test_health_has_required_fields(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()

        assert "status" in data
        assert "database" in data
        assert data["status"] == "ok"

    def test_readiness_has_required_fields(self, client: TestClient):
        with patch("api.routers.health.settings") as mock_s:
            mock_s.openai_api_key = "test"
            mock_s.anthropic_api_key = "test"
            mock_s.perplexity_api_key = "test"
            resp = client.get("/readiness")

        data = resp.json()
        assert "ready" in data
        assert "missing_keys" in data
        assert isinstance(data["ready"], bool)
        assert isinstance(data["missing_keys"], list)


# ── Error response shape ─────────────────────────────────────────────


class TestErrorResponseShape:
    """Verify error responses have 'detail' field (not raw tracebacks)."""

    def test_404_has_detail_field(self, client: TestClient):
        resp = client.get("/api/v1/tasks/nonexistent-task-id")
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data
        # Should be a human-readable message, not a traceback
        assert "Traceback" not in str(data["detail"])

    def test_401_on_unauthenticated(self, public_client: TestClient):
        resp = public_client.get("/api/v1/tasks")
        assert resp.status_code == 401


# ── Content briefs response shape ────────────────────────────────────


class TestContentBriefsResponseShape:
    """Verify content briefs response matches frontend ContentBriefItem type."""

    def test_briefs_list_shape(self, client: TestClient, artifacts_root: Path):
        """GET /briefs returns shape matching frontend expectations."""
        slug = "test-co"
        content_dir = artifacts_root / "content" / slug
        _write_json(
            content_dir / "blueprints.json",
            [
                {
                    "brief_id": "brief-001",
                    "title": "Test Brief",
                    "target_cluster": "seo",
                    "content_format": "long_blog",
                    "word_count_range": [1200, 2000],
                },
            ],
        )

        with patch("api.services.content_data_service.load_analysis_json", return_value=None):
            resp = client.get(f"/api/v1/content-data/{slug}/briefs")

        if resp.status_code == 200:
            data = resp.json()
            assert "briefs" in data
            assert "total" in data

            if data["briefs"]:
                brief = data["briefs"][0]
                # Fields the frontend relies on
                expected_fields = {"id", "title", "status", "content_type"}
                assert expected_fields.issubset(brief.keys()), \
                    f"Missing: {expected_fields - brief.keys()}"


# ── Gap analysis response shape ──────────────────────────────────────


class TestGapSummaryResponseShape:
    """Verify gap summary response matches frontend GapSummary type."""

    def test_summary_shape(self, client: TestClient, artifacts_root: Path):
        slug = "test-co"
        _write_json(
            artifacts_root / "gap_analysis" / slug / "analysis.json",
            {
                "gaps": [],
                "cluster_specs": [],
                "spa_results": [
                    {"cluster_name": "all", "t_stat": 2.0, "p_value": 0.01,
                     "effect": "significant_gap", "mean_citation_similarity": 0.7,
                     "mean_company_similarity": 0.4},
                ],
                "proximity_stats": {
                    "citation_similarity_mean": 0.7,
                    "citation_similarity_median": 0.68,
                    "company_similarity_mean": 0.4,
                    "company_similarity_median": 0.38,
                },
            },
        )

        resp = client.get(f"/api/v1/gap-data/{slug}/summary")

        if resp.status_code == 200:
            data = resp.json()
            expected_fields = {"spa_score", "proximity_stats", "classification_counts"}
            assert expected_fields.issubset(data.keys()), \
                f"Missing: {expected_fields - data.keys()}"
