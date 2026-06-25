"""API tests for workspace tenant routes."""
from __future__ import annotations

from fastapi.testclient import TestClient


class TestWorkspaceRoutes:
    def test_list_workspaces_returns_membership(self, client: TestClient) -> None:
        resp = client.get("/api/v1/workspaces")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["workspaces"]) >= 1
        assert body["workspaces"][0]["slug"] == "test-co"
        assert body["workspaces"][0]["role"] in {"owner", "admin", "member", "viewer"}

    def test_get_workspace_profile(self, client: TestClient) -> None:
        resp = client.get("/api/v1/workspaces/test-co/profile")
        assert resp.status_code == 200
        body = resp.json()
        assert body["slug"] == "test-co"
        assert body["name"] == "Test Co"
        assert "integrations" in body
        assert "artifact_status" in body

    def test_non_member_workspace_forbidden(
        self,
        client: TestClient,
        auth_store,
    ) -> None:
        auth_store.create_company("other-co", "Other Co", "other.com")
        resp = client.get("/api/v1/workspaces/other-co/profile")
        assert resp.status_code == 403

    def test_create_second_workspace(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/workspaces",
            json={
                "name": "Second Brand",
                "primary_domain": "secondbrand.com",
                "slug": "second-brand",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["slug"] == "second-brand"
        assert body["role"] == "owner"

        listed = client.get("/api/v1/workspaces").json()["workspaces"]
        slugs = {item["slug"] for item in listed}
        assert "second-brand" in slugs

    def test_viewer_cannot_update_workspace(self, viewer_client: TestClient) -> None:
        resp = viewer_client.put(
            "/api/v1/workspaces/test-co",
            json={"name": "Renamed"},
        )
        assert resp.status_code == 403

    def test_unauthenticated_list_rejected(self, public_client: TestClient) -> None:
        resp = public_client.get("/api/v1/workspaces")
        assert resp.status_code == 401
