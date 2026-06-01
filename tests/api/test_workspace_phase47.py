"""Phase 4–7 workspace tenant tests."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestWorkspaceProfileParity:
    def test_workspace_and_company_profile_equivalent_fields(
        self, client: TestClient
    ) -> None:
        company_resp = client.get("/api/v1/companies/test-co")
        workspace_resp = client.get("/api/v1/workspaces/test-co/profile")
        assert company_resp.status_code == 200
        assert workspace_resp.status_code == 200

        company_body = company_resp.json()
        workspace_body = workspace_resp.json()

        assert company_body["slug"] == workspace_body["slug"] == "test-co"
        assert company_body["name"] == workspace_body["name"]
        assert company_body["domain"] == workspace_body["primary_domain"]
        assert company_body["has_research"] == workspace_body["has_research"]
        assert company_body["has_gap_analysis"] == workspace_body["has_gap_analysis"]
        assert company_body["has_content"] == workspace_body["has_content"]
        assert company_body["research_summary"] == workspace_body["research_summary"]

    def test_workspace_profile_includes_extended_sections(
        self, client: TestClient
    ) -> None:
        resp = client.get("/api/v1/workspaces/test-co/profile")
        assert resp.status_code == 200
        body = resp.json()
        assert "stats" in body
        assert "topic_discovery" in body
        assert "content_studio" in body
        assert "running_tasks" in body
        assert "integrations" in body


class TestWorkspaceAuthorization:
    def test_archived_workspace_hidden_from_list(
        self,
        client: TestClient,
    ) -> None:
        create_resp = client.post(
            "/api/v1/workspaces",
            json={
                "name": "Archive Me",
                "primary_domain": "archive-me.com",
                "slug": "archive-me",
            },
        )
        assert create_resp.status_code == 201

        archive_resp = client.delete("/api/v1/workspaces/archive-me")
        assert archive_resp.status_code == 200

        listed = client.get("/api/v1/workspaces").json()["workspaces"]
        slugs = {item["slug"] for item in listed}
        assert "archive-me" not in slugs

    def test_archived_workspace_profile_still_readable(
        self,
        client: TestClient,
    ) -> None:
        client.post(
            "/api/v1/workspaces",
            json={
                "name": "Archive Read",
                "primary_domain": "archive-read.com",
                "slug": "archive-read",
            },
        )
        client.delete("/api/v1/workspaces/archive-read")
        resp = client.get("/api/v1/workspaces/archive-read/profile")
        assert resp.status_code == 200
        assert resp.json()["is_archived"] is True

    def test_company_route_still_works_as_legacy_alias(
        self, client: TestClient
    ) -> None:
        resp = client.get("/api/v1/companies/test-co")
        assert resp.status_code == 200
        assert resp.json()["slug"] == "test-co"


class TestWorkspaceStreamAccess:
    def test_sse_rejects_non_member(self, client: TestClient, auth_store) -> None:
        auth_store.create_company("stream-co", "Stream Co", "stream.co")
        resp = client.get("/api/v1/companies/stream-co/stream")
        assert resp.status_code == 403


class TestWorkspacePipelineAuthorization:
    def test_viewer_cannot_start_gap_analysis(
        self, viewer_client: TestClient
    ) -> None:
        resp = viewer_client.post(
            "/api/v1/gap-analysis/start",
            json={"company_name": "Test Co", "company_slug": "test-co"},
        )
        assert resp.status_code == 403
