"""Tests for company profile endpoint GET /api/v1/companies/{slug}."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.auth.store import AuthStore
from api.tasks.models import TaskStatus
from api.tasks.store import TaskStore


class TestCompanyProfile:
    """Tests for GET /api/v1/companies/{slug}."""

    def test_returns_404_for_unknown_slug(self, client: TestClient) -> None:
        resp = client.get("/api/v1/companies/nonexistent")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_returns_400_for_invalid_slug(self, client: TestClient) -> None:
        resp = client.get("/api/v1/companies/INVALID_SLUG!")
        assert resp.status_code == 400
        assert "Invalid slug" in resp.json()["detail"]

    def test_returns_profile_from_auth_store(
        self, client: TestClient, auth_store: AuthStore
    ) -> None:
        auth_store.create_company(slug="ramp", name="Ramp", domain="ramp.com")

        resp = client.get("/api/v1/companies/ramp")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "ramp"
        assert data["name"] == "Ramp"
        assert data["domain"] == "ramp.com"
        assert data["has_research"] is False
        assert data["has_gap_analysis"] is False
        assert data["has_content"] is False

    def test_returns_profile_from_artifacts_only(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        """Company not in auth store but has artifacts on disk."""
        cc_dir = artifacts_root / "company_context"
        cc_dir.mkdir(parents=True)
        (cc_dir / "carta.md").write_text("# Carta Company Context")

        resp = client.get("/api/v1/companies/carta")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "carta"
        # Name derived from slug when not in auth store
        assert data["name"] == "Carta"
        assert data["domain"] == ""
        assert data["has_research"] is True

    def test_research_summary_includes_artifacts(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        # Create company context (approved)
        cc_dir = artifacts_root / "company_context"
        cc_dir.mkdir(parents=True)
        (cc_dir / "ramp.md").write_text("approved context")

        # Create persona file
        p_dir = artifacts_root / "personas"
        p_dir.mkdir(parents=True)
        (p_dir / "ramp__persona-icp.md").write_text("persona")

        # Create style guide (draft)
        sg_dir = artifacts_root / "style_guides"
        sg_dir.mkdir(parents=True)
        (sg_dir / "ramp.draft.md").write_text("style draft")

        resp = client.get("/api/v1/companies/ramp")
        assert resp.status_code == 200
        data = resp.json()
        rs = data["research_summary"]
        assert rs["company_context"] == "ramp.md"
        assert rs["company_context_status"] == "approved"
        assert "ramp__persona-icp.md" in rs["personas"]
        assert rs["style_guide"] == "ramp.draft.md"
        assert rs["style_guide_status"] == "draft"

    def test_gap_analysis_detection(
        self, client: TestClient, artifacts_root: Path, auth_store: AuthStore
    ) -> None:
        auth_store.create_company(slug="ramp", name="Ramp", domain="ramp.com")

        # Create gap analysis directory with a file
        ga_dir = artifacts_root / "gap_analysis" / "ramp"
        ga_dir.mkdir(parents=True)
        (ga_dir / "gap_analysis_complete.json").write_text("{}")

        resp = client.get("/api/v1/companies/ramp")
        assert resp.status_code == 200
        assert resp.json()["has_gap_analysis"] is True

    def test_content_detection(
        self, client: TestClient, artifacts_root: Path, auth_store: AuthStore
    ) -> None:
        auth_store.create_company(slug="ramp", name="Ramp", domain="ramp.com")

        content_dir = artifacts_root / "content" / "ramp"
        content_dir.mkdir(parents=True)
        (content_dir / "briefs.json").write_text("[]")

        resp = client.get("/api/v1/companies/ramp")
        assert resp.status_code == 200
        assert resp.json()["has_content"] is True

    def test_latest_runs_from_task_store(
        self,
        client: TestClient,
        auth_store: AuthStore,
        task_store: TaskStore,
    ) -> None:
        auth_store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        task = task_store.create_task("gap_analysis", "ramp")
        task_store.update_task(task.task_id, status=TaskStatus.COMPLETED)

        resp = client.get("/api/v1/companies/ramp")
        assert resp.status_code == 200
        runs = resp.json()["latest_runs"]
        assert runs["gap_analysis"] is not None
        assert runs["gap_analysis"]["run_id"] == task.task_id
        assert runs["gap_analysis"]["status"] == "completed"
        assert runs["research"] is None
        assert runs["content"] is None

    def test_products_from_auth_store(
        self, client: TestClient, auth_store: AuthStore
    ) -> None:
        from core.models.organization import Product

        auth_store.create_company(
            slug="ramp",
            name="Ramp",
            domain="ramp.com",
            products=[
                Product(company_id="x", slug="corporate-card", name="Corporate Card"),
                Product(company_id="x", slug="travel", name="Ramp Travel"),
            ],
        )

        resp = client.get("/api/v1/companies/ramp")
        assert resp.status_code == 200
        products = resp.json()["products"]
        assert len(products) == 2
        assert products[0]["slug"] == "corporate-card"
        assert products[1]["name"] == "Ramp Travel"

    def test_draft_persona_not_included(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        """Draft .draft.md persona files should be excluded from the list."""
        p_dir = artifacts_root / "personas"
        p_dir.mkdir(parents=True)
        (p_dir / "ramp__persona-icp.draft.md").write_text("draft persona")

        resp = client.get("/api/v1/companies/ramp")
        # Should 404 because the only artifact is a draft persona
        # which is excluded from detection
        assert resp.status_code == 404
