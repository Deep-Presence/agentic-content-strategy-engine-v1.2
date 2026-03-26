"""Tests for Phase 3 — Product-level pipeline execution wiring.

Covers:
- RunScope / _resolve_scope() helper (unit)
- resolve_artifacts() fallback chain (unit)
- _derive_slug() (unit)
- Gap analysis start with product_slug → effective_slug in response
- Company-level and product-level runs coexist (no 409)
- Same product lock blocks second run
- Research artifact fallback chain in resolve_artifacts()
- GapAnalysisInput inherits product fields from scope
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.tasks.runner import (
    _derive_slug,
    _resolve_scope,
    resolve_artifacts,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def artifacts_root(tmp_path: Path) -> Path:
    root = tmp_path / "artifacts"
    root.mkdir()
    (root / "company_context").mkdir()
    (root / "style_guides").mkdir()
    return root


@pytest.fixture
def app_client(app, auth_headers: dict):
    """Authenticated FastAPI test client reusing the standard conftest app fixture."""
    yield TestClient(app, raise_server_exceptions=True, headers=auth_headers)


# ---------------------------------------------------------------------------
# Unit: _derive_slug
# ---------------------------------------------------------------------------

class TestDeriveSlug:
    def test_basic(self) -> None:
        assert _derive_slug("Ramp Inc") == "ramp-inc"

    def test_special_chars(self) -> None:
        assert _derive_slug("Hello, World!") == "hello-world"

    def test_already_slug(self) -> None:
        assert _derive_slug("ramp") == "ramp"

    def test_uses_provided_slug(self) -> None:
        assert _derive_slug("Ramp", company_slug="custom-slug") == "custom-slug"


# ---------------------------------------------------------------------------
# Unit: _resolve_scope
# ---------------------------------------------------------------------------

class TestResolveScope:
    def test_company_level_no_auth_store(self) -> None:
        scope = _resolve_scope("ramp", None)
        assert scope.company_slug == "ramp"
        assert scope.product_slug is None
        assert scope.effective_slug == "ramp"
        assert scope.product_name is None
        assert scope.product_domain is None

    def test_product_effective_slug(self) -> None:
        scope = _resolve_scope("ramp", "corporate-card")
        assert scope.effective_slug == "ramp__corporate-card"
        assert scope.product_slug == "corporate-card"

    def test_product_no_auth_store(self) -> None:
        """Without auth_store, product fields remain None."""
        scope = _resolve_scope("ramp", "corporate-card", auth_store=None)
        assert scope.product_name is None
        assert scope.product_description is None
        assert scope.product_domain is None

    def test_product_with_auth_store_hit(self) -> None:
        """Product details populated from auth_store when product found."""
        mock_product = MagicMock()
        mock_product.name = "Corporate Card"
        mock_product.description = "Ramp's card product"
        mock_product.domain = "ramp.com/card"

        mock_auth = MagicMock()
        mock_auth.get_product.return_value = mock_product

        scope = _resolve_scope("ramp", "corporate-card", auth_store=mock_auth)
        assert scope.product_name == "Corporate Card"
        assert scope.product_description == "Ramp's card product"
        assert scope.product_domain == "ramp.com/card"
        mock_auth.get_product.assert_called_once_with("ramp", "corporate-card")

    def test_product_with_auth_store_miss(self) -> None:
        """Product not found in auth_store → fields remain None."""
        mock_auth = MagicMock()
        mock_auth.get_product.return_value = None

        scope = _resolve_scope("ramp", "nonexistent", auth_store=mock_auth)
        assert scope.product_name is None
        assert scope.product_domain is None
        assert scope.effective_slug == "ramp__nonexistent"

    def test_effective_slug_double_underscore(self) -> None:
        scope = _resolve_scope("ramp", "ramp-corporate-card")
        assert "__" in scope.effective_slug
        assert scope.effective_slug == "ramp__ramp-corporate-card"


# ---------------------------------------------------------------------------
# Unit: resolve_artifacts fallback chain
# ---------------------------------------------------------------------------

class TestResolveArtifacts:
    def test_company_level_finds_context(self, artifacts_root: Path) -> None:
        (artifacts_root / "company_context" / "ramp.md").write_text("ctx")
        result = resolve_artifacts("ramp", artifacts_root)
        assert result["company_context_path"] is not None
        assert "ramp.md" in result["company_context_path"]

    def test_missing_context_returns_none(self, artifacts_root: Path) -> None:
        result = resolve_artifacts("ramp", artifacts_root)
        assert result["company_context_path"] is None
        assert result["persona_paths"] == []
        assert result["style_guide_path"] is None

    def test_product_fallback_uses_company_context(self, artifacts_root: Path) -> None:
        """When no product-specific context exists, falls back to company context."""
        (artifacts_root / "company_context" / "ramp.md").write_text("company ctx")
        result = resolve_artifacts(
            "ramp", artifacts_root, effective_slug="ramp__corporate-card"
        )
        assert result["company_context_path"] is not None
        assert "ramp.md" in result["company_context_path"]

    def test_product_specific_context_preferred(self, artifacts_root: Path) -> None:
        """Product-specific context takes precedence over company context."""
        (artifacts_root / "company_context" / "ramp.md").write_text("company ctx")
        (artifacts_root / "company_context" / "ramp__corporate-card.md").write_text(
            "product ctx"
        )
        result = resolve_artifacts(
            "ramp", artifacts_root, effective_slug="ramp__corporate-card"
        )
        assert "ramp__corporate-card.md" in result["company_context_path"]

    def test_persona_fallback_to_company(self, artifacts_root: Path) -> None:
        """Personas fall back to company-level when no product-specific files."""
        from core.research.audience_persona.storage import PersonaStorage

        ps = PersonaStorage(artifacts_root, "ramp")
        ps.write_version("persona-icp", "ICP Persona", "persona content")
        result = resolve_artifacts(
            "ramp", artifacts_root, effective_slug="ramp__corporate-card"
        )
        assert len(result["persona_paths"]) == 1
        assert "persona-icp" in result["persona_paths"][0]

    def test_product_persona_preferred(self, artifacts_root: Path) -> None:
        """Product-level persona files take precedence."""
        from core.research.audience_persona.storage import PersonaStorage

        # Company-level persona
        ps_company = PersonaStorage(artifacts_root, "ramp")
        ps_company.write_version("persona-icp", "ICP Persona", "company persona")
        # Product-level persona
        ps_product = PersonaStorage(artifacts_root, "ramp__corporate-card")
        ps_product.write_version("persona-icp", "ICP Persona", "product persona")
        result = resolve_artifacts(
            "ramp", artifacts_root, effective_slug="ramp__corporate-card"
        )
        assert any(
            "ramp__corporate-card" in p for p in result["persona_paths"]
        )

    def test_style_guide_fallback_to_company(self, artifacts_root: Path) -> None:
        (artifacts_root / "style_guides" / "ramp.md").write_text("style")
        result = resolve_artifacts(
            "ramp", artifacts_root, effective_slug="ramp__corporate-card"
        )
        assert result["style_guide_path"] is not None
        assert "ramp.md" in result["style_guide_path"]

    def test_product_style_guide_preferred(self, artifacts_root: Path) -> None:
        (artifacts_root / "style_guides" / "ramp.md").write_text("company style")
        (artifacts_root / "style_guides" / "ramp__corporate-card.md").write_text(
            "product style"
        )
        result = resolve_artifacts(
            "ramp", artifacts_root, effective_slug="ramp__corporate-card"
        )
        assert "ramp__corporate-card.md" in result["style_guide_path"]

    def test_archived_personas_excluded(self, artifacts_root: Path) -> None:
        """Personas with non-active status are excluded from persona_paths."""
        from core.research.audience_persona.storage import PersonaStorage

        ps = PersonaStorage(artifacts_root, "ramp")
        ps.write_version(
            "persona-icp", "ICP Persona", "archived persona", status="archived",
        )
        result = resolve_artifacts("ramp", artifacts_root)
        assert result["persona_paths"] == []

    def test_no_effective_slug_no_fallback(self, artifacts_root: Path) -> None:
        """Without effective_slug, only bare slug is searched."""
        (artifacts_root / "company_context" / "ramp__card.md").write_text("product ctx")
        result = resolve_artifacts("ramp", artifacts_root)
        # Should NOT find the product-scoped file when no effective_slug given
        assert result["company_context_path"] is None


# ---------------------------------------------------------------------------
# API integration: gap analysis start with product_slug
# ---------------------------------------------------------------------------

class TestGapAnalysisProductStart:
    def _start(
        self,
        client: TestClient,
        product_slug: Optional[str] = None,
    ) -> dict:
        body: dict = {
            "company_name": "Test Co",
            "domain": "testco.com",
            "skip_stages": ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"],
        }
        if product_slug:
            body["product_slug"] = product_slug

        with patch("api.routers.gap_analysis.asyncio.create_task") as mock_create:
            mock_create.return_value = MagicMock()
            resp = client.post("/api/v1/gap-analysis/start", json=body)
        return resp

    def test_start_returns_202(self, app_client: TestClient) -> None:
        resp = self._start(app_client)
        assert resp.status_code == 202

    def test_company_level_effective_slug(self, app_client: TestClient) -> None:
        resp = self._start(app_client)
        data = resp.json()
        assert data["effective_slug"] == "test-co"
        assert data["product_slug"] is None

    def test_product_level_effective_slug(self, app_client: TestClient) -> None:
        resp = self._start(app_client, product_slug="corporate-card")
        data = resp.json()
        assert data["effective_slug"] == "test-co__corporate-card"
        assert data["product_slug"] == "corporate-card"
        assert data["company_slug"] == "test-co"

    def test_company_and_product_coexist(self, app_client: TestClient) -> None:
        """Company-level run and product-level run can start simultaneously."""
        with patch("api.routers.gap_analysis.asyncio.create_task") as mock_create:
            mock_create.return_value = MagicMock()

            r1 = app_client.post(
                "/api/v1/gap-analysis/start",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                    "skip_stages": ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"],
                },
            )
            r2 = app_client.post(
                "/api/v1/gap-analysis/start",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                    "product_slug": "corporate-card",
                    "skip_stages": ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"],
                },
            )
        assert r1.status_code == 202
        assert r2.status_code == 202
        assert r1.json()["run_id"] != r2.json()["run_id"]

    def test_same_product_second_run_conflicts(self, app_client: TestClient) -> None:
        """Two concurrent product runs with same slug → 409.

        asyncio.create_task is patched to a no-op so the background task never
        starts and never releases the slug lock between the two HTTP requests.
        """
        with patch("api.routers.gap_analysis.asyncio.create_task") as mock_create:
            mock_create.return_value = MagicMock()

            r1 = app_client.post(
                "/api/v1/gap-analysis/start",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                    "product_slug": "corporate-card",
                    "skip_stages": ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"],
                },
            )
            r2 = app_client.post(
                "/api/v1/gap-analysis/start",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                    "product_slug": "corporate-card",
                    "skip_stages": ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"],
                },
            )
        assert r1.status_code == 202
        assert r2.status_code == 409

    def test_response_includes_pipeline_field(self, app_client: TestClient) -> None:
        resp = self._start(app_client)
        assert resp.json()["pipeline"] == "gap_analysis"

    def test_response_has_run_id(self, app_client: TestClient) -> None:
        resp = self._start(app_client)
        assert "run_id" in resp.json()
        assert len(resp.json()["run_id"]) > 0


# ---------------------------------------------------------------------------
# Unit: GapAnalysisInput product fields threaded through scope
# ---------------------------------------------------------------------------

class TestGapAnalysisInputProductFields:
    def test_product_fields_optional_defaults(self) -> None:
        from core.models.gap_analysis import GapAnalysisInput
        inp = GapAnalysisInput(
            company_name="Ramp",
            domain="ramp.com",
            company_slug="ramp",
        )
        assert inp.product_slug is None
        assert inp.product_name is None
        assert inp.product_description is None

    def test_product_fields_set(self) -> None:
        from core.models.gap_analysis import GapAnalysisInput
        inp = GapAnalysisInput(
            company_name="Ramp",
            domain="ramp.com",
            company_slug="ramp__corporate-card",
            product_slug="corporate-card",
            product_name="Ramp Corporate Card",
            product_description="A spend management card",
        )
        assert inp.product_slug == "corporate-card"
        assert inp.product_name == "Ramp Corporate Card"
        assert inp.product_description == "A spend management card"

    def test_json_roundtrip(self) -> None:
        from core.models.gap_analysis import GapAnalysisInput
        import json
        inp = GapAnalysisInput(
            company_name="Ramp",
            domain="ramp.com",
            company_slug="ramp__card",
            product_slug="card",
            product_name="Card",
            product_description="desc",
        )
        data = json.loads(inp.model_dump_json())
        restored = GapAnalysisInput(**data)
        assert restored.product_slug == "card"
        assert restored.product_name == "Card"


# ---------------------------------------------------------------------------
# Unit: ContentGenerationInput product fields
# ---------------------------------------------------------------------------

class TestContentGenerationInputProductFields:
    def test_defaults(self) -> None:
        from core.models.content_generation import ContentGenerationInput
        inp = ContentGenerationInput(company_name="Ramp", domain="ramp.com")
        assert inp.product_slug is None
        assert inp.product_name is None
        assert inp.product_description is None

    def test_fields_set(self) -> None:
        from core.models.content_generation import ContentGenerationInput
        inp = ContentGenerationInput(
            company_name="Ramp",
            domain="ramp.com",
            product_slug="card",
            product_name="Card",
            product_description="A card",
        )
        assert inp.product_slug == "card"

    def test_json_roundtrip(self) -> None:
        from core.models.content_generation import ContentGenerationInput
        import json
        inp = ContentGenerationInput(
            company_name="Ramp",
            domain="ramp.com",
            product_slug="card",
            product_name="Card",
        )
        data = json.loads(inp.model_dump_json())
        restored = ContentGenerationInput(**data)
        assert restored.product_slug == "card"


# ---------------------------------------------------------------------------
# API integration: product_slug validator rejects invalid values (P0)
# ---------------------------------------------------------------------------

class TestProductSlugValidation:
    """product_slug field validator (api/schemas/common.py) rejects bad values.

    Bad slugs must return 422 Unprocessable Entity for all three pipeline
    start endpoints.  Valid slugs must continue to return 202.
    """

    _INVALID_SLUGS = [
        "../evil",        # path traversal
        "UPPER_CASE",     # uppercase not allowed
        "has space",      # spaces not allowed
        "-bad-start",     # leading hyphen
        "has/slash",      # path separator
        "",               # empty string (falsy, but pydantic sees it as a value)
    ]

    def _start_gap(self, client: TestClient, product_slug: str) -> int:
        with patch("api.routers.gap_analysis.asyncio.create_task") as m:
            m.return_value = MagicMock()
            return client.post(
                "/api/v1/gap-analysis/start",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                    "product_slug": product_slug,
                    "skip_stages": ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"],
                },
            ).status_code

    def _start_content(self, client: TestClient, product_slug: str) -> int:
        with patch("api.routers.content.asyncio.create_task") as m:
            m.return_value = MagicMock()
            return client.post(
                "/api/v1/content/start",
                json={
                    "company_name": "Test Co",
                    "domain": "testco.com",
                    "product_slug": product_slug,
                },
            ).status_code

    def test_gap_analysis_rejects_invalid_product_slug(
        self, app_client: TestClient
    ) -> None:
        for bad in self._INVALID_SLUGS:
            status = self._start_gap(app_client, bad)
            assert status == 422, (
                f"Expected 422 for product_slug={bad!r}, got {status}"
            )

    def test_content_rejects_invalid_product_slug(
        self, app_client: TestClient
    ) -> None:
        for bad in self._INVALID_SLUGS:
            status = self._start_content(app_client, bad)
            assert status == 422, (
                f"Expected 422 for product_slug={bad!r}, got {status}"
            )

    def test_valid_product_slug_passes_validation(
        self, app_client: TestClient
    ) -> None:
        """Regression: confirm well-formed slugs still return 202."""
        status = self._start_gap(app_client, "corporate-card")
        assert status == 202
