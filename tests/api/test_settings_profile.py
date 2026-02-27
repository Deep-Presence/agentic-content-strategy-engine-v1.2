"""Tests for Phase 1B: Company Profile settings endpoints.

Endpoints tested:
  GET  /api/v1/companies/{slug}/settings/profile
  PUT  /api/v1/companies/{slug}/settings/profile
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.auth.store import AuthStore
from core.models.organization import Company, UserProfile


class TestGetProfile:
    """GET /companies/{slug}/settings/profile."""

    def test_get_profile(
        self, client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        resp = client.get(f"/api/v1/companies/{test_company.slug}/settings/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == test_company.slug
        assert data["name"] == "Test Co"
        assert data["domain"] == "testco.com"
        assert "created_at" in data
        assert "updated_at" in data

    def test_get_profile_cross_tenant_blocked(
        self, client: TestClient, auth_store: AuthStore
    ) -> None:
        auth_store.create_company("other-co", "Other Co", "other.com")
        resp = client.get("/api/v1/companies/other-co/settings/profile")
        assert resp.status_code == 403

    def test_get_profile_unauthenticated(
        self, public_client: TestClient, test_company: Company
    ) -> None:
        resp = public_client.get(f"/api/v1/companies/{test_company.slug}/settings/profile")
        assert resp.status_code == 401

    def test_get_profile_viewer_can_read(
        self, viewer_client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        resp = viewer_client.get(f"/api/v1/companies/{test_company.slug}/settings/profile")
        assert resp.status_code == 200


class TestUpdateProfile:
    """PUT /companies/{slug}/settings/profile."""

    def test_superuser_can_update_name(
        self, superuser_client: TestClient, test_company: Company
    ) -> None:
        resp = superuser_client.put(
            f"/api/v1/companies/{test_company.slug}/settings/profile",
            json={"name": "Updated Co"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Co"
        assert resp.json()["slug"] == test_company.slug  # slug unchanged

    def test_superuser_can_update_domain(
        self, superuser_client: TestClient, test_company: Company
    ) -> None:
        resp = superuser_client.put(
            f"/api/v1/companies/{test_company.slug}/settings/profile",
            json={"domain": "newdomain.com"},
        )
        assert resp.status_code == 200
        assert resp.json()["domain"] == "newdomain.com"

    def test_superuser_can_update_additional_domains(
        self, superuser_client: TestClient, test_company: Company
    ) -> None:
        resp = superuser_client.put(
            f"/api/v1/companies/{test_company.slug}/settings/profile",
            json={"additional_domains": ["app.testco.com", "docs.testco.com"]},
        )
        assert resp.status_code == 200
        assert resp.json()["additional_domains"] == ["app.testco.com", "docs.testco.com"]

    def test_member_cannot_update_profile(
        self, client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        resp = client.put(
            f"/api/v1/companies/{test_company.slug}/settings/profile",
            json={"name": "Hacked"},
        )
        assert resp.status_code == 403

    def test_viewer_cannot_update_profile(
        self, viewer_client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        resp = viewer_client.put(
            f"/api/v1/companies/{test_company.slug}/settings/profile",
            json={"name": "Hacked"},
        )
        assert resp.status_code == 403

    def test_cross_tenant_update_blocked(
        self, superuser_client: TestClient, auth_store: AuthStore
    ) -> None:
        auth_store.create_company("other-co", "Other Co", "other.com")
        resp = superuser_client.put(
            "/api/v1/companies/other-co/settings/profile",
            json={"name": "Hacked"},
        )
        assert resp.status_code == 403

    def test_empty_update_no_change(
        self, superuser_client: TestClient, test_company: Company
    ) -> None:
        """PUT with no fields is a no-op, returns current profile."""
        resp = superuser_client.put(
            f"/api/v1/companies/{test_company.slug}/settings/profile",
            json={},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Co"
