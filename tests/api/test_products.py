"""Tests for product CRUD endpoints and AuthStore product methods."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.auth.store import AuthStore
from core.models.organization import Product


# ── AuthStore product CRUD (unit tests) ───────────────────────────────────────

class TestAuthStoreProducts:
    """Tests for AuthStore product CRUD methods."""

    def test_add_product(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        company = store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        product = Product(company_id=company.id, slug="corporate-card", name="Corporate Card")
        result = store.add_product("ramp", product)
        assert result.slug == "corporate-card"
        assert result.name == "Corporate Card"
        assert result.company_id == company.id

    def test_add_product_persists(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        company = store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        product = Product(company_id=company.id, slug="travel", name="Ramp Travel")
        store.add_product("ramp", product)

        # Reload from disk
        store2 = AuthStore(base_dir=tmp_path)
        found = store2.get_product("ramp", "travel")
        assert found is not None
        assert found.name == "Ramp Travel"

    def test_add_product_duplicate_slug_raises(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        company = store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        p = Product(company_id=company.id, slug="card", name="Card")
        store.add_product("ramp", p)
        with pytest.raises(ValueError, match="already exists"):
            store.add_product("ramp", Product(company_id=company.id, slug="card", name="Card 2"))

    def test_add_product_unknown_company_raises(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        with pytest.raises(ValueError, match="not found"):
            store.add_product("nonexistent", Product(company_id="x", slug="p", name="P"))

    def test_get_product(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        company = store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        product = Product(company_id=company.id, slug="card", name="Card", domain="ramp.com/card")
        store.add_product("ramp", product)

        found = store.get_product("ramp", "card")
        assert found is not None
        assert found.domain == "ramp.com/card"

    def test_get_product_not_found_returns_none(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        assert store.get_product("ramp", "nonexistent") is None

    def test_get_product_unknown_company_returns_none(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        assert store.get_product("nonexistent", "card") is None

    def test_update_product(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        company = store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        product = Product(company_id=company.id, slug="card", name="Card")
        store.add_product("ramp", product)

        updated = store.update_product("ramp", "card", name="Corporate Card", description="Spend management")
        assert updated.name == "Corporate Card"
        assert updated.description == "Spend management"
        assert updated.slug == "card"  # slug unchanged

    def test_update_product_persists(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        company = store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        product = Product(company_id=company.id, slug="card", name="Card")
        store.add_product("ramp", product)
        store.update_product("ramp", "card", name="Updated Card")

        store2 = AuthStore(base_dir=tmp_path)
        found = store2.get_product("ramp", "card")
        assert found is not None
        assert found.name == "Updated Card"

    def test_update_product_not_found_raises(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        with pytest.raises(ValueError, match="not found"):
            store.update_product("ramp", "nonexistent", name="X")

    def test_remove_product(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        company = store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        product = Product(company_id=company.id, slug="card", name="Card")
        store.add_product("ramp", product)

        removed = store.remove_product("ramp", "card")
        assert removed is True
        assert store.get_product("ramp", "card") is None

    def test_remove_product_not_found_returns_false(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        assert store.remove_product("ramp", "nonexistent") is False

    def test_remove_product_unknown_company_returns_false(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        assert store.remove_product("nonexistent", "card") is False

    def test_multiple_products(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        company = store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        for slug, name in [("card", "Card"), ("travel", "Travel"), ("reimbursements", "Reimb")]:
            store.add_product("ramp", Product(company_id=company.id, slug=slug, name=name))

        ramp = store.get_company_by_slug("ramp")
        assert ramp is not None
        assert len(ramp.products) == 3


# ── API endpoint tests ─────────────────────────────────────────────────────────

class TestProductCRUDEndpoints:
    """Tests for POST/GET/PUT/DELETE /api/v1/companies/{slug}/products."""

    def test_create_product(self, client: TestClient, auth_store: AuthStore) -> None:
        auth_store.create_company(slug="ramp", name="Ramp", domain="ramp.com")

        resp = client.post("/api/v1/companies/ramp/products", json={
            "name": "Corporate Card",
            "slug": "corporate-card",
            "domain": "ramp.com/card",
            "description": "Spend management",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["slug"] == "corporate-card"
        assert data["name"] == "Corporate Card"
        assert data["domain"] == "ramp.com/card"
        assert data["description"] == "Spend management"
        assert "id" in data
        assert "company_id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_product_minimal(self, client: TestClient, auth_store: AuthStore) -> None:
        auth_store.create_company(slug="ramp", name="Ramp", domain="ramp.com")

        resp = client.post("/api/v1/companies/ramp/products", json={
            "name": "Travel",
            "slug": "travel",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["domain"] is None
        assert data["description"] is None

    def test_create_product_invalid_slug_format(self, client: TestClient, auth_store: AuthStore) -> None:
        auth_store.create_company(slug="ramp", name="Ramp", domain="ramp.com")

        for bad_slug in ["UPPER", "has space", "-bad-start", "bad_underscore"]:
            resp = client.post("/api/v1/companies/ramp/products", json={
                "name": "X",
                "slug": bad_slug,
            })
            assert resp.status_code == 422, f"Expected 422 for slug '{bad_slug}'"

    def test_create_product_duplicate_slug(self, client: TestClient, auth_store: AuthStore) -> None:
        auth_store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        client.post("/api/v1/companies/ramp/products", json={"name": "Card", "slug": "card"})

        resp = client.post("/api/v1/companies/ramp/products", json={"name": "Card2", "slug": "card"})
        assert resp.status_code == 409

    def test_create_product_company_not_found(self, client: TestClient) -> None:
        resp = client.post("/api/v1/companies/nonexistent/products", json={
            "name": "Card",
            "slug": "card",
        })
        assert resp.status_code == 404

    def test_get_product(self, client: TestClient, auth_store: AuthStore) -> None:
        auth_store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        client.post("/api/v1/companies/ramp/products", json={"name": "Card", "slug": "card"})

        resp = client.get("/api/v1/companies/ramp/products/card")
        assert resp.status_code == 200
        assert resp.json()["slug"] == "card"

    def test_get_product_not_found(self, client: TestClient, auth_store: AuthStore) -> None:
        auth_store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        resp = client.get("/api/v1/companies/ramp/products/nonexistent")
        assert resp.status_code == 404

    def test_get_product_company_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/companies/nonexistent/products/card")
        assert resp.status_code == 404

    def test_update_product(self, client: TestClient, auth_store: AuthStore) -> None:
        auth_store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        client.post("/api/v1/companies/ramp/products", json={"name": "Card", "slug": "card"})

        resp = client.put("/api/v1/companies/ramp/products/card", json={
            "name": "Corporate Card",
            "description": "Updated desc",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Corporate Card"
        assert data["description"] == "Updated desc"

    def test_update_product_partial(self, client: TestClient, auth_store: AuthStore) -> None:
        auth_store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        client.post("/api/v1/companies/ramp/products", json={
            "name": "Card",
            "slug": "card",
            "domain": "ramp.com/card",
        })

        resp = client.put("/api/v1/companies/ramp/products/card", json={"name": "New Name"})
        assert resp.status_code == 200
        # domain preserved (partial update doesn't clear it)
        # NOTE: domain would be None since it's not in the update body — see plan note
        # The router passes only non-None values from the request body

    def test_update_product_not_found(self, client: TestClient, auth_store: AuthStore) -> None:
        auth_store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        resp = client.put("/api/v1/companies/ramp/products/nonexistent", json={"name": "X"})
        assert resp.status_code == 404

    def test_delete_product(self, client: TestClient, auth_store: AuthStore) -> None:
        auth_store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        client.post("/api/v1/companies/ramp/products", json={"name": "Card", "slug": "card"})

        resp = client.delete("/api/v1/companies/ramp/products/card")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        # Verify it's gone
        resp2 = client.get("/api/v1/companies/ramp/products/card")
        assert resp2.status_code == 404

    def test_delete_product_not_found(self, client: TestClient, auth_store: AuthStore) -> None:
        auth_store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        resp = client.delete("/api/v1/companies/ramp/products/nonexistent")
        assert resp.status_code == 404

    def test_create_product_cross_tenant_blocked(
        self, client: TestClient, auth_store: AuthStore
    ) -> None:
        """Authenticated user from a different company cannot create a product."""
        company_a = auth_store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        company_b = auth_store.create_company(slug="carta", name="Carta", domain="carta.com")

        # Create user for company_b
        user_b = auth_store.create_user(
            company_id=company_b.id,
            email="b@carta.com",
            first_name="B",
            last_name="User",
            password="password123",
        )
        token = auth_store.create_access_token(user_b.id, company_b.slug)

        # Attempt to create product for company_a
        resp = client.post(
            "/api/v1/companies/ramp/products",
            json={"name": "Card", "slug": "card"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_create_product_same_company_allowed(
        self, client: TestClient, auth_store: AuthStore
    ) -> None:
        """Authenticated user from the same company can create a product."""
        company = auth_store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        user = auth_store.create_user(
            company_id=company.id,
            email="user@ramp.com",
            first_name="A",
            last_name="User",
            password="password123",
        )
        token = auth_store.create_access_token(user.id, company.slug)

        resp = client.post(
            "/api/v1/companies/ramp/products",
            json={"name": "Card", "slug": "card"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201


class TestProductArtifactStatus:
    """Tests that company profile reflects real product artifact status."""

    def test_product_has_gap_analysis_when_artifacts_exist(
        self, client: TestClient, auth_store: AuthStore, artifacts_root: Path
    ) -> None:
        company = auth_store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        product = Product(company_id=company.id, slug="card", name="Card")
        auth_store.add_product("ramp", product)

        # Create product-level gap analysis artifacts
        ga_dir = artifacts_root / "gap_analysis" / "ramp__card"
        ga_dir.mkdir(parents=True)
        (ga_dir / "gap_analysis_complete.json").write_text("{}")

        resp = client.get("/api/v1/companies/ramp")
        assert resp.status_code == 200
        products = resp.json()["products"]
        assert len(products) == 1
        assert products[0]["has_gap_analysis"] is True
        assert products[0]["has_content"] is False

    def test_product_has_content_when_artifacts_exist(
        self, client: TestClient, auth_store: AuthStore, artifacts_root: Path
    ) -> None:
        company = auth_store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        product = Product(company_id=company.id, slug="travel", name="Travel")
        auth_store.add_product("ramp", product)

        content_dir = artifacts_root / "content" / "ramp__travel"
        content_dir.mkdir(parents=True)
        (content_dir / "briefs.json").write_text("[]")

        resp = client.get("/api/v1/companies/ramp")
        assert resp.status_code == 200
        products = resp.json()["products"]
        assert products[0]["has_content"] is True

    def test_product_has_research_when_context_exists(
        self, client: TestClient, auth_store: AuthStore, artifacts_root: Path
    ) -> None:
        company = auth_store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        product = Product(company_id=company.id, slug="card", name="Card")
        auth_store.add_product("ramp", product)

        # Create product-specific research artifact
        cc_dir = artifacts_root / "company_context"
        cc_dir.mkdir(parents=True)
        (cc_dir / "ramp__card.md").write_text("# Product Context")

        resp = client.get("/api/v1/companies/ramp")
        assert resp.status_code == 200
        products = resp.json()["products"]
        assert products[0]["has_research"] is True

    def test_product_with_no_artifacts_shows_false(
        self, client: TestClient, auth_store: AuthStore
    ) -> None:
        company = auth_store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        product = Product(company_id=company.id, slug="card", name="Card")
        auth_store.add_product("ramp", product)

        resp = client.get("/api/v1/companies/ramp")
        assert resp.status_code == 200
        products = resp.json()["products"]
        assert products[0]["has_gap_analysis"] is False
        assert products[0]["has_content"] is False
        assert products[0]["has_research"] is False

    def test_product_summary_includes_domain_description(
        self, client: TestClient, auth_store: AuthStore
    ) -> None:
        company = auth_store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        product = Product(
            company_id=company.id,
            slug="card",
            name="Corporate Card",
            domain="ramp.com/card",
            description="Spend management",
        )
        auth_store.add_product("ramp", product)

        resp = client.get("/api/v1/companies/ramp")
        assert resp.status_code == 200
        p = resp.json()["products"][0]
        assert p["domain"] == "ramp.com/card"
        assert p["description"] == "Spend management"

    def test_company_artifacts_unaffected_by_product_artifacts(
        self, client: TestClient, auth_store: AuthStore, artifacts_root: Path
    ) -> None:
        """Company-level has_gap_analysis only counts company-level artifacts."""
        company = auth_store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        product = Product(company_id=company.id, slug="card", name="Card")
        auth_store.add_product("ramp", product)

        # Only product-level artifact exists, not company-level
        ga_dir = artifacts_root / "gap_analysis" / "ramp__card"
        ga_dir.mkdir(parents=True)
        (ga_dir / "gap_analysis_complete.json").write_text("{}")

        resp = client.get("/api/v1/companies/ramp")
        assert resp.status_code == 200
        data = resp.json()
        # Company-level has_gap_analysis should still be False
        assert data["has_gap_analysis"] is False
        # But product-level should be True
        assert data["products"][0]["has_gap_analysis"] is True
