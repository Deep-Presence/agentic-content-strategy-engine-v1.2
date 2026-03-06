"""Tests for artifacts API endpoints."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def populated_artifacts(tmp_path: Path) -> Path:
    """Create a realistic artifact directory structure."""
    root = tmp_path / "artifacts"

    # company_context
    cc = root / "company_context"
    cc.mkdir(parents=True)
    (cc / "test-co.md").write_text("# Test Co Company Context")

    # personas
    personas = root / "personas"
    personas.mkdir()
    (personas / "test-co__persona-icp.md").write_text("# Test Co Personas")

    # style_guides
    sg = root / "style_guides"
    sg.mkdir()
    (sg / "test-co__style-guide.md").write_text("# Test Co Style Guide")

    # gap_analysis with nested structure
    ga = root / "gap_analysis" / "test-co"
    ga.mkdir(parents=True)
    (ga / "gap_report.md").write_text("# Test Co Gap Report")
    (ga / "gap_report.json").write_text(json.dumps({"summary": "test"}))
    viz = ga / "visualizations"
    viz.mkdir()
    (viz / "heatmap.html").write_text("<html>heatmap</html>")

    # content
    content = root / "content" / "test-co"
    content.mkdir(parents=True)
    (content / "article_1.md").write_text("# Article 1")

    # chroma_db (should be excluded)
    chroma = root / "chroma_db"
    chroma.mkdir()
    (chroma / "index.db").write_text("binary data")

    # _logs (should be excluded)
    logs = root / "_logs"
    logs.mkdir()
    (logs / "run.log").write_text("log data")

    return root


@pytest.fixture
def artifacts_client(app, populated_artifacts: Path, auth_headers: dict) -> TestClient:
    """Authenticated TestClient with artifacts root pointing to populated fixture."""
    app.state.artifacts_root = populated_artifacts
    return TestClient(app, headers=auth_headers)


class TestListCompanies:
    def test_returns_aggregated_companies(self, artifacts_client: TestClient) -> None:
        resp = artifacts_client.get("/api/v1/artifacts/companies")
        assert resp.status_code == 200
        data = resp.json()
        slugs = data["companies"]
        assert "test-co" in slugs

    def test_excludes_chroma_db(self, artifacts_client: TestClient) -> None:
        resp = artifacts_client.get("/api/v1/artifacts/companies")
        data = resp.json()
        slugs = data["companies"]
        assert "chroma_db" not in slugs
        assert "_logs" not in slugs


class TestListArtifacts:
    def test_list_company_context(self, artifacts_client: TestClient) -> None:
        resp = artifacts_client.get("/api/v1/artifacts/company_context/test-co")
        assert resp.status_code == 200
        files = resp.json()["files"]
        names = [f["name"] for f in files]
        assert "test-co.md" in names

    def test_list_gap_analysis(self, artifacts_client: TestClient) -> None:
        resp = artifacts_client.get("/api/v1/artifacts/gap_analysis/test-co")
        assert resp.status_code == 200
        files = resp.json()["files"]
        names = [f["name"] for f in files]
        assert "gap_report.md" in names
        assert "gap_report.json" in names

    def test_invalid_type_returns_422(self, artifacts_client: TestClient) -> None:
        resp = artifacts_client.get("/api/v1/artifacts/invalid_type/test-co")
        assert resp.status_code == 422

    def test_not_found_returns_403(self, artifacts_client: TestClient) -> None:
        # "nonexistent" doesn't match the authenticated user's company → 403
        resp = artifacts_client.get("/api/v1/artifacts/gap_analysis/nonexistent")
        assert resp.status_code == 403


class TestGetArtifactContent:
    def test_get_markdown(self, artifacts_client: TestClient) -> None:
        resp = artifacts_client.get("/api/v1/artifacts/gap_analysis/test-co/gap_report.md")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"] or "text/markdown" in resp.headers["content-type"]
        assert "# Test Co Gap Report" in resp.text

    def test_get_json(self, artifacts_client: TestClient) -> None:
        resp = artifacts_client.get("/api/v1/artifacts/gap_analysis/test-co/gap_report.json")
        assert resp.status_code == 200
        assert resp.json()["summary"] == "test"

    def test_get_html(self, artifacts_client: TestClient) -> None:
        resp = artifacts_client.get(
            "/api/v1/artifacts/gap_analysis/test-co/visualizations/heatmap.html"
        )
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "heatmap" in resp.text

    def test_not_found(self, artifacts_client: TestClient) -> None:
        resp = artifacts_client.get("/api/v1/artifacts/gap_analysis/test-co/nonexistent.md")
        assert resp.status_code == 404

    def test_path_traversal_blocked(self, artifacts_client: TestClient) -> None:
        # FastAPI normalizes `..` in URL paths, so we test the handler directly
        # by passing a filename that contains `..` via the path parameter
        resp = artifacts_client.get(
            "/api/v1/artifacts/gap_analysis/test-co/subdir/..%2f..%2fpasswords.txt"
        )
        # Should either be 400 (traversal blocked) or 404 (not found after normalization)
        assert resp.status_code in (400, 404)

    def test_company_context_flat_file(self, artifacts_client: TestClient) -> None:
        """company_context stores files as {slug}.md at root level, not in subdirs."""
        resp = artifacts_client.get("/api/v1/artifacts/company_context/test-co/test-co.md")
        assert resp.status_code == 200
        assert "# Test Co Company Context" in resp.text
