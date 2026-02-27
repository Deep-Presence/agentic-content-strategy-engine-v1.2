"""Tests for Phase 1A: User/Team Management settings endpoints.

Endpoints tested:
  GET  /api/v1/companies/{slug}/settings/team
  PUT  /api/v1/companies/{slug}/settings/team/{user_id}
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.auth.store import AuthStore
from core.models.organization import Company, UserProfile


# ── GET /settings/team ────────────────────────────────────


class TestListTeam:
    """GET /companies/{slug}/settings/team."""

    def test_list_team_returns_all_members(
        self, client: TestClient, auth_store: AuthStore, test_company: Company, test_user: UserProfile
    ) -> None:
        """Authenticated member can list team members."""
        # Create a second user
        auth_store.create_user(
            company_id=test_company.id,
            email="second@testco.com",
            password="password123",
            first_name="Second",
            last_name="User",
            role="viewer",
        )
        resp = client.get(f"/api/v1/companies/{test_company.slug}/settings/team")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        emails = {m["email"] for m in data["members"]}
        assert "dev@testco.com" in emails
        assert "second@testco.com" in emails

    def test_list_team_includes_expected_fields(
        self, client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        resp = client.get(f"/api/v1/companies/{test_company.slug}/settings/team")
        assert resp.status_code == 200
        member = resp.json()["members"][0]
        for field in ("id", "email", "first_name", "last_name", "role", "is_active", "created_at"):
            assert field in member

    def test_list_team_cross_tenant_blocked(
        self, client: TestClient, auth_store: AuthStore
    ) -> None:
        """Cannot list team of another company."""
        auth_store.create_company("other-co", "Other Co", "other.com")
        resp = client.get("/api/v1/companies/other-co/settings/team")
        assert resp.status_code == 403

    def test_list_team_unauthenticated(
        self, public_client: TestClient, test_company: Company
    ) -> None:
        resp = public_client.get(f"/api/v1/companies/{test_company.slug}/settings/team")
        assert resp.status_code == 401

    def test_list_team_viewer_can_read(
        self, viewer_client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        """Viewers have read access to team list."""
        resp = viewer_client.get(f"/api/v1/companies/{test_company.slug}/settings/team")
        assert resp.status_code == 200


# ── PUT /settings/team/{user_id} ─────────────────────────


class TestUpdateUser:
    """PUT /companies/{slug}/settings/team/{user_id}."""

    def test_superuser_can_update_role(
        self,
        superuser_client: TestClient,
        auth_store: AuthStore,
        test_company: Company,
        test_user: UserProfile,
    ) -> None:
        """Superuser can change another user's role."""
        resp = superuser_client.put(
            f"/api/v1/companies/{test_company.slug}/settings/team/{test_user.id}",
            json={"role": "viewer"},
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "viewer"

    def test_superuser_can_deactivate_user(
        self,
        superuser_client: TestClient,
        auth_store: AuthStore,
        test_company: Company,
        test_user: UserProfile,
    ) -> None:
        resp = superuser_client.put(
            f"/api/v1/companies/{test_company.slug}/settings/team/{test_user.id}",
            json={"is_active": False},
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_superuser_can_update_name(
        self,
        superuser_client: TestClient,
        test_company: Company,
        test_user: UserProfile,
    ) -> None:
        resp = superuser_client.put(
            f"/api/v1/companies/{test_company.slug}/settings/team/{test_user.id}",
            json={"first_name": "Updated", "last_name": "Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["first_name"] == "Updated"
        assert resp.json()["last_name"] == "Name"

    def test_member_cannot_update_roles(
        self,
        client: TestClient,
        test_company: Company,
        test_user: UserProfile,
    ) -> None:
        """Member role cannot update team settings (403)."""
        resp = client.put(
            f"/api/v1/companies/{test_company.slug}/settings/team/{test_user.id}",
            json={"role": "viewer"},
        )
        assert resp.status_code == 403

    def test_viewer_cannot_update_roles(
        self,
        viewer_client: TestClient,
        test_company: Company,
        test_user: UserProfile,
    ) -> None:
        resp = viewer_client.put(
            f"/api/v1/companies/{test_company.slug}/settings/team/{test_user.id}",
            json={"role": "member"},
        )
        assert resp.status_code == 403

    def test_cannot_deactivate_self(
        self,
        superuser_client: TestClient,
        auth_store: AuthStore,
        test_company: Company,
    ) -> None:
        """Superuser cannot deactivate their own account."""
        # Find the superuser
        users = auth_store.list_users_for_company(test_company.id)
        su = next(u for u in users if u.role == "superuser")
        resp = superuser_client.put(
            f"/api/v1/companies/{test_company.slug}/settings/team/{su.id}",
            json={"is_active": False},
        )
        assert resp.status_code == 400
        assert "cannot deactivate" in resp.json()["detail"].lower()

    def test_cannot_demote_last_superuser(
        self,
        superuser_client: TestClient,
        auth_store: AuthStore,
        test_company: Company,
    ) -> None:
        """Cannot change role of the only superuser."""
        users = auth_store.list_users_for_company(test_company.id)
        su = next(u for u in users if u.role == "superuser")
        resp = superuser_client.put(
            f"/api/v1/companies/{test_company.slug}/settings/team/{su.id}",
            json={"role": "member"},
        )
        assert resp.status_code == 400
        assert "last superuser" in resp.json()["detail"].lower()

    def test_cross_tenant_update_blocked(
        self,
        superuser_client: TestClient,
        auth_store: AuthStore,
        test_user: UserProfile,
    ) -> None:
        """Cannot update users in another company."""
        auth_store.create_company("other-co", "Other Co", "other.com")
        resp = superuser_client.put(
            f"/api/v1/companies/other-co/settings/team/{test_user.id}",
            json={"role": "viewer"},
        )
        assert resp.status_code == 403

    def test_update_nonexistent_user(
        self,
        superuser_client: TestClient,
        test_company: Company,
    ) -> None:
        resp = superuser_client.put(
            f"/api/v1/companies/{test_company.slug}/settings/team/nonexistent-id",
            json={"role": "viewer"},
        )
        assert resp.status_code == 404

    def test_update_user_in_different_company_blocked(
        self,
        superuser_client: TestClient,
        auth_store: AuthStore,
        test_company: Company,
    ) -> None:
        """Cannot update a user that belongs to a different company."""
        other = auth_store.create_company("other-co", "Other Co", "other.com")
        other_user = auth_store.create_user(
            company_id=other.id,
            email="other@other.com",
            password="password123",
            first_name="Other",
            last_name="User",
            role="member",
        )
        resp = superuser_client.put(
            f"/api/v1/companies/{test_company.slug}/settings/team/{other_user.id}",
            json={"role": "viewer"},
        )
        assert resp.status_code == 404

    def test_demote_superuser_when_multiple_exist(
        self,
        superuser_client: TestClient,
        auth_store: AuthStore,
        test_company: Company,
    ) -> None:
        """Can demote a superuser if there's another superuser."""
        # Create a second superuser
        su2 = auth_store.create_user(
            company_id=test_company.id,
            email="su2@testco.com",
            password="password123",
            first_name="Super",
            last_name="Two",
            role="superuser",
        )
        resp = superuser_client.put(
            f"/api/v1/companies/{test_company.slug}/settings/team/{su2.id}",
            json={"role": "member"},
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "member"
