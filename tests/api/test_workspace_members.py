"""Workspace member list, update, and invite endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient


class TestWorkspaceMembers:
    def test_list_members_includes_total(self, client: TestClient) -> None:
        resp = client.get("/api/v1/workspaces/test-co/members")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        assert len(body["members"]) == body["total"]

    def test_viewer_cannot_patch_member(self, viewer_client: TestClient) -> None:
        members = viewer_client.get("/api/v1/workspaces/test-co/members").json()["members"]
        target_id = members[0]["user_id"]
        resp = viewer_client.patch(
            f"/api/v1/workspaces/test-co/members/{target_id}",
            json={"role": "viewer"},
        )
        assert resp.status_code == 403

    def test_owner_can_update_member_role(
        self, superuser_client: TestClient, auth_store, test_user
    ) -> None:
        other = auth_store.create_user(
            company_id=test_user.company_id,
            email="editor@example.com",
            password="password123",
            first_name="Ed",
            last_name="Itor",
            role="member",
        )
        resp = superuser_client.patch(
            f"/api/v1/workspaces/test-co/members/{other.id}",
            json={"role": "viewer"},
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "viewer"

    def test_create_workspace_invite(self, superuser_client: TestClient) -> None:
        resp = superuser_client.post(
            "/api/v1/workspaces/test-co/invites",
            json={"role": "member"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["workspace_slug"] == "test-co"
        assert len(body["invite_code"]) >= 8

    def test_viewer_cannot_create_invite(self, viewer_client: TestClient) -> None:
        resp = viewer_client.post(
            "/api/v1/workspaces/test-co/invites",
            json={"role": "viewer"},
        )
        assert resp.status_code == 403
