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
    (cc / "ramp.md").write_text("# Ramp Company Context")
    (cc / "carta.md").write_text("# Carta Company Context")

    # personas
    personas = root / "personas"
    personas.mkdir()
    (personas / "ramp__persona-icp.md").write_text("# Ramp Personas")
    (personas / "carta__persona-icp.md").write_text("# Carta Personas")

    # style_guides
    sg = root / "style_guides"
    sg.mkdir()
    (sg / "ramp__style-guide.md").write_text("# Ramp Style Guide")

    # gap_analysis with nested structure
    ga_ramp = root / "gap_analysis" / "ramp"
    ga_ramp.mkdir(parents=True)
    (ga_ramp / "gap_report.md").write_text("# Ramp Gap Report")
    (ga_ramp / "gap_report.json").write_text(json.dumps({"summary": "test"}))
    viz = ga_ramp / "visualizations"
    viz.mkdir()
    (viz / "heatmap.html").write_text("<html>heatmap</html>")

    ga_carta = root / "gap_analysis" / "carta"
    ga_carta.mkdir(parents=True)
    (ga_carta / "gap_report.md").write_text("# Carta Gap Report")

    # content
    content = root / "content" / "ramp"
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
def artifacts_client(app, populated_artifacts: Path) -> TestClient:
    """TestClient with artifacts root pointing to populated fixture."""
    app.state.artifacts_root = populated_artifacts
    return TestClient(app)


class TestListCompanies:
    def test_returns_aggregated_companies(self, artifacts_client: TestClient) -> None:
        resp = artifacts_client.get("/api/v1/artifacts/companies")
        assert resp.status_code == 200
        data = resp.json()
        slugs = data["companies"]
        # Both ramp and carta appear across different artifact types
        assert "ramp" in slugs
        assert "carta" in slugs

    def test_excludes_chroma_db(self, artifacts_client: TestClient) -> None:
        resp = artifacts_client.get("/api/v1/artifacts/companies")
        data = resp.json()
        slugs = data["companies"]
        assert "chroma_db" not in slugs
        assert "_logs" not in slugs


class TestListArtifacts:
    def test_list_company_context(self, artifacts_client: TestClient) -> None:
        resp = artifacts_client.get("/api/v1/artifacts/company_context/ramp")
        assert resp.status_code == 200
        files = resp.json()["files"]
        names = [f["name"] for f in files]
        assert "ramp.md" in names

    def test_list_gap_analysis(self, artifacts_client: TestClient) -> None:
        resp = artifacts_client.get("/api/v1/artifacts/gap_analysis/ramp")
        assert resp.status_code == 200
        files = resp.json()["files"]
        names = [f["name"] for f in files]
        assert "gap_report.md" in names
        assert "gap_report.json" in names

    def test_invalid_type_returns_422(self, artifacts_client: TestClient) -> None:
        resp = artifacts_client.get("/api/v1/artifacts/invalid_type/ramp")
        assert resp.status_code == 422

    def test_not_found_returns_404(self, artifacts_client: TestClient) -> None:
        resp = artifacts_client.get("/api/v1/artifacts/gap_analysis/nonexistent")
        assert resp.status_code == 404


class TestGetArtifactContent:
    def test_get_markdown(self, artifacts_client: TestClient) -> None:
        resp = artifacts_client.get("/api/v1/artifacts/gap_analysis/ramp/gap_report.md")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"] or "text/markdown" in resp.headers["content-type"]
        assert "# Ramp Gap Report" in resp.text

    def test_get_json(self, artifacts_client: TestClient) -> None:
        resp = artifacts_client.get("/api/v1/artifacts/gap_analysis/ramp/gap_report.json")
        assert resp.status_code == 200
        assert resp.json()["summary"] == "test"

    def test_get_html(self, artifacts_client: TestClient) -> None:
        resp = artifacts_client.get(
            "/api/v1/artifacts/gap_analysis/ramp/visualizations/heatmap.html"
        )
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "heatmap" in resp.text

    def test_not_found(self, artifacts_client: TestClient) -> None:
        resp = artifacts_client.get("/api/v1/artifacts/gap_analysis/ramp/nonexistent.md")
        assert resp.status_code == 404

    def test_path_traversal_blocked(self, artifacts_client: TestClient) -> None:
        # FastAPI normalizes `..` in URL paths, so we test the handler directly
        # by passing a filename that contains `..` via the path parameter
        resp = artifacts_client.get(
            "/api/v1/artifacts/gap_analysis/ramp/subdir/..%2f..%2fpasswords.txt"
        )
        # Should either be 400 (traversal blocked) or 404 (not found after normalization)
        assert resp.status_code in (400, 404)

    def test_company_context_flat_file(self, artifacts_client: TestClient) -> None:
        """company_context stores files as {slug}.md at root level, not in subdirs."""
        resp = artifacts_client.get("/api/v1/artifacts/company_context/ramp/ramp.md")
        assert resp.status_code == 200
        assert "# Ramp Company Context" in resp.text
