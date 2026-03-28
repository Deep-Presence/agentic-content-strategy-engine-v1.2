"""Tests for company profile endpoint GET /api/v1/companies/{slug}."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.auth.store import AuthStore
from api.tasks.models import TaskStatus


def _write_persona_storage(
    artifacts_root: Path,
    slug: str,
    persona_id: str,
    *,
    version: int = 1,
    status: str = "fresh",
    kind: str = "icp",
    content: str = "# Persona",
) -> None:
    """Write a persona via the audience_personas manifest + versioned file."""
    base = artifacts_root / "audience_personas" / slug
    base.mkdir(parents=True, exist_ok=True)
    persona_dir = base / persona_id
    persona_dir.mkdir(parents=True, exist_ok=True)
    (persona_dir / f"v{version}.md").write_text(content, encoding="utf-8")
    manifest_path = base / "_manifest.json"
    manifest: dict = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    personas = manifest.get("personas", {})
    personas[persona_id] = {
        "persona_name": persona_id.replace("-", " ").title(),
        "kind": kind,
        "status": status,
        "current_version": version,
        "last_updated": None,
    }
    manifest["personas"] = personas
    manifest.setdefault("slug", slug)
    manifest.setdefault("kb_synthesis_version", 0)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


class TestCompanyProfile:
    """Tests for GET /api/v1/companies/{slug}.

    The authenticated test user belongs to company slug="test-co"
    (created by the ``test_company`` conftest fixture that is transitively
    pulled in by the ``client`` fixture).
    """

    def test_returns_403_for_unknown_slug(self, client: TestClient) -> None:
        # "nonexistent" doesn't match authenticated user's company → 403
        resp = client.get("/api/v1/companies/nonexistent")
        assert resp.status_code == 403

    def test_returns_403_for_invalid_slug(self, client: TestClient) -> None:
        # Invalid slug doesn't match authenticated user's company → 403
        resp = client.get("/api/v1/companies/INVALID_SLUG!")
        assert resp.status_code == 403

    def test_returns_profile_from_auth_store(
        self, client: TestClient, test_company
    ) -> None:
        """test-co is already in auth store via the test_company fixture."""
        resp = client.get("/api/v1/companies/test-co")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "test-co"
        assert data["name"] == "Test Co"
        assert data["domain"] == "testco.com"
        assert data["has_research"] is False
        assert data["has_gap_analysis"] is False
        assert data["has_content"] is False

    def test_returns_profile_with_artifacts(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        """Company context artifact is found on disk."""
        cc_dir = artifacts_root / "company_context"
        cc_dir.mkdir(parents=True)
        (cc_dir / "test-co.md").write_text("# Test Co Company Context")

        resp = client.get("/api/v1/companies/test-co")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "test-co"
        assert data["has_research"] is True

    def test_research_summary_includes_artifacts(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        # Create company context (approved)
        cc_dir = artifacts_root / "company_context"
        cc_dir.mkdir(parents=True)
        (cc_dir / "test-co.md").write_text("approved context")

        # Create persona via PersonaStorage
        _write_persona_storage(artifacts_root, "test-co", "persona-icp", content="persona")

        # Create style guide (draft)
        sg_dir = artifacts_root / "style_guides"
        sg_dir.mkdir(parents=True)
        (sg_dir / "test-co.draft.md").write_text("style draft")

        resp = client.get("/api/v1/companies/test-co")
        assert resp.status_code == 200
        data = resp.json()
        rs = data["research_summary"]
        assert rs["company_context"] == "test-co.md"
        assert rs["company_context_status"] == "approved"
        assert "persona-icp.md" in rs["personas"]
        assert rs["style_guide"] == "test-co.draft.md"
        assert rs["style_guide_status"] == "draft"

    def test_gap_analysis_detection(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        # Create gap analysis directory with a file
        ga_dir = artifacts_root / "gap_analysis" / "test-co"
        ga_dir.mkdir(parents=True)
        (ga_dir / "gap_analysis_complete.json").write_text("{}")

        resp = client.get("/api/v1/companies/test-co")
        assert resp.status_code == 200
        assert resp.json()["has_gap_analysis"] is True

    def test_content_detection(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        content_dir = artifacts_root / "content" / "test-co"
        content_dir.mkdir(parents=True)
        (content_dir / "briefs.json").write_text("[]")

        resp = client.get("/api/v1/companies/test-co")
        assert resp.status_code == 200
        assert resp.json()["has_content"] is True

    def test_latest_runs_from_task_store(
        self,
        client: TestClient,
        task_store,
    ) -> None:
        task = task_store.create_task("gap_analysis", "test-co")
        task_store.update_task(task.task_id, status=TaskStatus.COMPLETED)

        resp = client.get("/api/v1/companies/test-co")
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

        # Add products to the test-co company (already exists from fixture)
        auth_store.add_product("test-co", Product(company_id="x", slug="corporate-card", name="Corporate Card"))
        auth_store.add_product("test-co", Product(company_id="x", slug="travel", name="Test Travel"))

        resp = client.get("/api/v1/companies/test-co")
        assert resp.status_code == 200
        products = resp.json()["products"]
        assert len(products) == 2
        assert products[0]["slug"] == "corporate-card"
        assert products[1]["name"] == "Test Travel"

    def test_inactive_persona_not_included(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        """Personas with status=pending_review and current_version=0 should be excluded."""
        _write_persona_storage(
            artifacts_root, "test-co", "persona-icp",
            status="pending_review", version=0, content="",
        )

        resp = client.get("/api/v1/companies/test-co")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_research"] is False
