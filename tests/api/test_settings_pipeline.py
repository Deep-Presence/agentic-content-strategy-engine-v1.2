"""Tests for Phase 1C: Pipeline Defaults settings endpoints.

Endpoints tested:
  GET  /api/v1/companies/{slug}/settings/pipeline-defaults
  PUT  /api/v1/companies/{slug}/settings/pipeline-defaults
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.auth.store import AuthStore
from core.models.organization import Company, UserProfile


class TestGetPipelineDefaults:
    """GET /companies/{slug}/settings/pipeline-defaults."""

    def test_get_defaults_empty(
        self, client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        """New company has empty (all-None) defaults."""
        resp = client.get(f"/api/v1/companies/{test_company.slug}/settings/pipeline-defaults")
        assert resp.status_code == 200
        data = resp.json()
        assert data["max_crawl_pages"] is None
        assert data["max_queries"] is None
        assert data["auto_approve_research"] is False
        assert data["auto_approve_content"] is False

    def test_get_defaults_cross_tenant_blocked(
        self, client: TestClient, auth_store: AuthStore
    ) -> None:
        auth_store.create_company("other-co", "Other Co", "other.com")
        resp = client.get("/api/v1/companies/other-co/settings/pipeline-defaults")
        assert resp.status_code == 403

    def test_get_defaults_unauthenticated(
        self, public_client: TestClient, test_company: Company
    ) -> None:
        resp = public_client.get(
            f"/api/v1/companies/{test_company.slug}/settings/pipeline-defaults"
        )
        assert resp.status_code == 401


class TestUpdatePipelineDefaults:
    """PUT /companies/{slug}/settings/pipeline-defaults."""

    def test_superuser_can_set_gap_defaults(
        self, superuser_client: TestClient, test_company: Company
    ) -> None:
        resp = superuser_client.put(
            f"/api/v1/companies/{test_company.slug}/settings/pipeline-defaults",
            json={"max_crawl_pages": 200, "max_queries": 50},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["max_crawl_pages"] == 200
        assert data["max_queries"] == 50

    def test_superuser_can_set_research_defaults(
        self, superuser_client: TestClient, test_company: Company
    ) -> None:
        resp = superuser_client.put(
            f"/api/v1/companies/{test_company.slug}/settings/pipeline-defaults",
            json={"max_personas": 3, "auto_approve_research": True},
        )
        assert resp.status_code == 200
        assert resp.json()["max_personas"] == 3
        assert resp.json()["auto_approve_research"] is True

    def test_superuser_can_set_content_defaults(
        self, superuser_client: TestClient, test_company: Company
    ) -> None:
        resp = superuser_client.put(
            f"/api/v1/companies/{test_company.slug}/settings/pipeline-defaults",
            json={"max_briefs": 10, "max_revision_cycles": 2, "auto_approve_content": True},
        )
        assert resp.status_code == 200
        assert resp.json()["max_briefs"] == 10
        assert resp.json()["max_revision_cycles"] == 2

    def test_partial_update_preserves_existing(
        self, superuser_client: TestClient, test_company: Company
    ) -> None:
        """Partial update doesn't clear previously set values."""
        # First set max_crawl_pages
        superuser_client.put(
            f"/api/v1/companies/{test_company.slug}/settings/pipeline-defaults",
            json={"max_crawl_pages": 200},
        )
        # Then set max_queries — max_crawl_pages should be preserved
        resp = superuser_client.put(
            f"/api/v1/companies/{test_company.slug}/settings/pipeline-defaults",
            json={"max_queries": 50},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["max_crawl_pages"] == 200
        assert data["max_queries"] == 50

    def test_member_cannot_update(
        self, client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        resp = client.put(
            f"/api/v1/companies/{test_company.slug}/settings/pipeline-defaults",
            json={"max_crawl_pages": 100},
        )
        assert resp.status_code == 403

    def test_viewer_cannot_update(
        self, viewer_client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        resp = viewer_client.put(
            f"/api/v1/companies/{test_company.slug}/settings/pipeline-defaults",
            json={"max_crawl_pages": 100},
        )
        assert resp.status_code == 403

    def test_cross_tenant_update_blocked(
        self, superuser_client: TestClient, auth_store: AuthStore
    ) -> None:
        auth_store.create_company("other-co", "Other Co", "other.com")
        resp = superuser_client.put(
            "/api/v1/companies/other-co/settings/pipeline-defaults",
            json={"max_crawl_pages": 100},
        )
        assert resp.status_code == 403

    def test_validation_rejects_invalid_values(
        self, superuser_client: TestClient, test_company: Company
    ) -> None:
        """Validation rejects out-of-range values."""
        resp = superuser_client.put(
            f"/api/v1/companies/{test_company.slug}/settings/pipeline-defaults",
            json={"max_crawl_pages": 0},
        )
        assert resp.status_code == 422

    def test_get_reflects_updates(
        self, superuser_client: TestClient, client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        """GET returns values set by PUT."""
        superuser_client.put(
            f"/api/v1/companies/{test_company.slug}/settings/pipeline-defaults",
            json={"max_crawl_pages": 300, "platforms": ["openai", "claude"]},
        )
        resp = client.get(f"/api/v1/companies/{test_company.slug}/settings/pipeline-defaults")
        assert resp.status_code == 200
        data = resp.json()
        assert data["max_crawl_pages"] == 300
        assert data["platforms"] == ["openai", "claude"]
        assert data["updated_at"] is not None
