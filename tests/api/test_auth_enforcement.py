"""Comprehensive auth enforcement tests.

Covers:
  1. Middleware enforcement — public vs protected routes, token validation
  2. Deactivated user rejection
  3. Role-based access control (viewer vs member vs superuser)
  4. Tenant isolation — cross-company access denied
  5. Stream token mechanics
  6. Registration hardening
  7. Login behavior
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth.store import AuthStore
from api.tasks.models import PipelineTask, TaskStatus
from api.tasks.store import TaskStore
from core.models.organization import Company, UserProfile
from tests.api.conftest import _AuthTestClient


# ── Fixtures for cross-tenant testing ─────────────────────────────


@pytest.fixture
def other_company(auth_store: AuthStore) -> Company:
    """Create a second company for tenant isolation tests."""
    auth_store.create_company("other-co", "Other Co", "other.com")
    company = auth_store.get_company_by_slug("other-co")
    assert company is not None
    return company


@pytest.fixture
def other_user(auth_store: AuthStore, other_company: Company) -> UserProfile:
    """Create a member user in the other company."""
    return auth_store.create_user(
        company_id=other_company.id,
        email="user@other.com",
        password="otherpass123",
        first_name="Other",
        last_name="User",
        role="member",
    )


@pytest.fixture
def other_client(
    app: FastAPI, auth_store: AuthStore, other_company: Company, other_user: UserProfile
) -> TestClient:
    """Authenticated test client for the other company."""
    token = auth_store.create_access_token(other_user.id, other_company.slug)
    return _AuthTestClient(app, default_headers={"Authorization": f"Bearer {token}"})


@pytest.fixture
def test_co_task(task_store: TaskStore, test_company: Company) -> PipelineTask:
    """Create a task owned by test-co."""
    return task_store.create_task("gap_analysis", "test-co")


@pytest.fixture
def other_co_task(task_store: TaskStore, other_company: Company) -> PipelineTask:
    """Create a task owned by other-co."""
    return task_store.create_task("gap_analysis", "other-co")


# ═══════════════════════════════════════════════════════════════════
# 1. Middleware enforcement
# ═══════════════════════════════════════════════════════════════════


class TestMiddlewareEnforcement:
    """ASGI AuthMiddleware: public paths pass, protected paths require valid token."""

    def test_public_health_no_auth(self, public_client: TestClient) -> None:
        resp = public_client.get("/health")
        assert resp.status_code == 200

    def test_public_readiness_no_auth(self, public_client: TestClient) -> None:
        resp = public_client.get("/readiness")
        assert resp.status_code == 200

    def test_public_register_no_auth(self, public_client: TestClient) -> None:
        """POST /register is public — middleware does not block it."""
        resp = public_client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "New",
                "last_name": "User",
                "email": "new@newdomain.com",
                "password": "securepass123",
                "company_name": "New Domain Inc",
                "company_domain": "newdomain.com",
            },
        )
        assert resp.status_code == 201

    def test_public_login_no_auth(self, public_client: TestClient) -> None:
        """POST /login is public — middleware allows through (app returns 401 for missing user)."""
        resp = public_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@nowhere.com", "password": "securepass123"},
        )
        # Middleware lets it through; the handler returns 401 for invalid credentials
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

    def test_protected_route_401_without_token(self, public_client: TestClient) -> None:
        resp = public_client.get("/api/v1/tasks")
        assert resp.status_code == 401
        body = resp.json()
        assert body["code"] == "missing_token"

    def test_protected_route_401_with_expired_token(
        self,
        public_client: TestClient,
        auth_store: AuthStore,
        test_user: UserProfile,
        test_company: Company,
    ) -> None:
        expired_token = auth_store.create_access_token(
            test_user.id, test_company.slug, expires_hours=-1
        )
        resp = public_client.get(
            "/api/v1/tasks",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401
        assert resp.json()["code"] == "invalid_token"

    def test_protected_route_401_with_malformed_token(
        self, public_client: TestClient
    ) -> None:
        resp = public_client.get(
            "/api/v1/tasks",
            headers={"Authorization": "Bearer garbage.token.here"},
        )
        assert resp.status_code == 401

    def test_protected_route_200_with_valid_token(self, client: TestClient) -> None:
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# 2. Deactivated user
# ═══════════════════════════════════════════════════════════════════


class TestDeactivatedUser:
    """Users with is_active=False must be rejected at the dependency layer."""

    def test_deactivated_user_returns_401(
        self,
        app: FastAPI,
        auth_store: AuthStore,
        test_user: UserProfile,
        test_company: Company,
    ) -> None:
        # Deactivate the user directly in the store
        user_data = auth_store.get_user_by_id(test_user.id)
        assert user_data is not None
        user_data["is_active"] = False

        token = auth_store.create_access_token(test_user.id, test_company.slug)
        client = _AuthTestClient(app, default_headers={"Authorization": f"Bearer {token}"})

        # Middleware passes (token is valid), but require_auth checks is_active
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 401
        assert "deactivated" in resp.json()["detail"].lower()

    def test_deactivated_user_cannot_read_company(
        self,
        app: FastAPI,
        auth_store: AuthStore,
        test_user: UserProfile,
        test_company: Company,
    ) -> None:
        user_data = auth_store.get_user_by_id(test_user.id)
        assert user_data is not None
        user_data["is_active"] = False

        token = auth_store.create_access_token(test_user.id, test_company.slug)
        client = _AuthTestClient(app, default_headers={"Authorization": f"Bearer {token}"})

        resp = client.get("/api/v1/companies/test-co")
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════
# 3. Role-based access control
# ═══════════════════════════════════════════════════════════════════


class TestRoleBasedAccess:
    """Viewer role cannot perform write operations; member and superuser can."""

    def test_viewer_cannot_start_gap_analysis(self, viewer_client: TestClient) -> None:
        resp = viewer_client.post(
            "/api/v1/gap-analysis/start",
            json={"company_name": "Test Co", "domain": "testco.com"},
        )
        assert resp.status_code == 403

    def test_viewer_cannot_start_content(self, viewer_client: TestClient) -> None:
        resp = viewer_client.post(
            "/api/v1/content/start",
            json={"company_name": "Test Co", "domain": "testco.com"},
        )
        assert resp.status_code == 403

    def test_viewer_cannot_cancel_task(
        self, viewer_client: TestClient, test_co_task: PipelineTask
    ) -> None:
        resp = viewer_client.post(f"/api/v1/tasks/{test_co_task.task_id}/cancel")
        assert resp.status_code == 403

    def test_viewer_cannot_create_product(self, viewer_client: TestClient) -> None:
        resp = viewer_client.post(
            "/api/v1/companies/test-co/products",
            json={"slug": "new-product", "name": "New Product", "domain": "testco.com"},
        )
        assert resp.status_code == 403

    def test_viewer_cannot_update_product(self, viewer_client: TestClient) -> None:
        resp = viewer_client.put(
            "/api/v1/companies/test-co/products/nonexistent",
            json={"name": "Updated"},
        )
        assert resp.status_code == 403

    def test_viewer_cannot_delete_product(self, viewer_client: TestClient) -> None:
        resp = viewer_client.delete("/api/v1/companies/test-co/products/nonexistent")
        assert resp.status_code == 403

    def test_viewer_can_read_company_profile(
        self, viewer_client: TestClient, test_company: Company
    ) -> None:
        resp = viewer_client.get("/api/v1/companies/test-co")
        assert resp.status_code == 200

    def test_viewer_can_read_gap_data(self, viewer_client: TestClient) -> None:
        """Gap data endpoints use require_tenant (read-only). Viewer should pass auth."""
        resp = viewer_client.get("/api/v1/companies/test-co/gap-analysis/summary")
        # 404 (no artifacts on disk) proves auth passed — a viewer would get 403 if blocked
        assert resp.status_code in (200, 404)
        assert resp.status_code != 403

    @patch("api.routers.gap_analysis.asyncio.create_task", return_value=MagicMock())
    def test_member_can_start_gap_analysis(
        self, _mock_create_task: MagicMock, client: TestClient
    ) -> None:
        resp = client.post(
            "/api/v1/gap-analysis/start",
            json={"company_name": "Test Co", "domain": "testco.com"},
        )
        assert resp.status_code == 202

    def test_viewer_cannot_create_invite(self, viewer_client: TestClient) -> None:
        resp = viewer_client.post(
            "/api/v1/auth/invite",
            json={"role": "member"},
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════
# 4. Tenant isolation
# ═══════════════════════════════════════════════════════════════════


class TestTenantIsolation:
    """Users can only access resources belonging to their own company."""

    def test_user_cannot_read_other_company_profile(
        self, client: TestClient, other_company: Company
    ) -> None:
        resp = client.get("/api/v1/companies/other-co")
        assert resp.status_code == 403

    def test_user_cannot_start_pipeline_for_other_company(
        self, client: TestClient, other_company: Company
    ) -> None:
        resp = client.post(
            "/api/v1/gap-analysis/start",
            json={"company_name": "Other Co", "domain": "other.com"},
        )
        assert resp.status_code == 403

    def test_user_cannot_view_other_company_task(
        self, client: TestClient, other_co_task: PipelineTask
    ) -> None:
        resp = client.get(f"/api/v1/tasks/{other_co_task.task_id}")
        assert resp.status_code == 403

    def test_user_cannot_cancel_other_company_task(
        self, client: TestClient, other_co_task: PipelineTask
    ) -> None:
        resp = client.post(f"/api/v1/tasks/{other_co_task.task_id}/cancel")
        assert resp.status_code == 403

    def test_user_cannot_access_other_company_gap_data(
        self, client: TestClient, other_company: Company
    ) -> None:
        resp = client.get("/api/v1/companies/other-co/gap-analysis/summary")
        assert resp.status_code == 403

    def test_user_cannot_access_other_company_content_data(
        self, client: TestClient, other_company: Company
    ) -> None:
        resp = client.get("/api/v1/companies/other-co/content/briefs")
        assert resp.status_code == 403

    def test_user_cannot_access_other_company_artifacts(
        self, client: TestClient, other_company: Company
    ) -> None:
        resp = client.get("/api/v1/artifacts/company_context/other-co")
        assert resp.status_code == 403

    def test_tasks_auto_filtered_by_company(
        self,
        client: TestClient,
        other_client: TestClient,
        test_co_task: PipelineTask,
        other_co_task: PipelineTask,
    ) -> None:
        """GET /tasks auto-filters by authenticated user's company."""
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 200
        task_ids = [t["run_id"] for t in resp.json()["tasks"]]
        assert test_co_task.task_id in task_ids
        assert other_co_task.task_id not in task_ids

        # Verify the other company only sees its own tasks
        resp2 = other_client.get("/api/v1/tasks")
        assert resp2.status_code == 200
        other_ids = [t["run_id"] for t in resp2.json()["tasks"]]
        assert other_co_task.task_id in other_ids
        assert test_co_task.task_id not in other_ids

    def test_artifacts_list_companies_only_shows_own(
        self,
        client: TestClient,
        artifacts_root: Path,
        other_company: Company,
    ) -> None:
        """GET /artifacts/companies only returns slugs for the user's company."""
        # Create artifact dirs for both companies
        (artifacts_root / "gap_analysis" / "test-co").mkdir(parents=True, exist_ok=True)
        (artifacts_root / "gap_analysis" / "test-co" / "analysis.json").write_text("{}")
        (artifacts_root / "gap_analysis" / "other-co").mkdir(parents=True, exist_ok=True)
        (artifacts_root / "gap_analysis" / "other-co" / "analysis.json").write_text("{}")

        resp = client.get("/api/v1/artifacts/companies")
        assert resp.status_code == 200
        companies = resp.json()["companies"]
        assert "test-co" in companies
        assert "other-co" not in companies

    def test_user_cannot_stream_other_company_events(
        self, client: TestClient, other_co_task: PipelineTask
    ) -> None:
        resp = client.get(f"/api/v1/tasks/{other_co_task.task_id}/events")
        assert resp.status_code == 403

    def test_other_user_cannot_read_test_co_profile(
        self, other_client: TestClient, test_company: Company
    ) -> None:
        """Reverse direction: other-co user cannot read test-co profile."""
        resp = other_client.get("/api/v1/companies/test-co")
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════
# 5. Stream tokens
# ═══════════════════════════════════════════════════════════════════


class TestStreamTokens:
    """Stream tokens: short-lived, SSE-only tokens for EventSource clients."""

    def test_stream_token_endpoint_returns_token(
        self, client: TestClient, test_co_task: PipelineTask
    ) -> None:
        resp = client.post(f"/api/v1/tasks/{test_co_task.task_id}/stream-token")
        assert resp.status_code == 200
        data = resp.json()
        assert "stream_token" in data
        assert data["expires_in"] == 300

    def test_stream_token_works_for_sse(
        self,
        app: FastAPI,
        auth_store: AuthStore,
        test_co_task: PipelineTask,
        test_user: UserProfile,
        test_company: Company,
        event_bus,
    ) -> None:
        """Stream token in query param authenticates the SSE /events endpoint.

        We verify by checking that the middleware extracts the token and populates
        request state correctly. The token is verified against the auth store,
        and the ``stream_only`` flag is accepted for /events paths.
        """
        stream_token = auth_store.create_stream_token(test_user.id, test_company.slug)

        # Verify the token itself is valid and has stream_only flag
        payload = auth_store.verify_token(stream_token)
        assert payload is not None
        assert payload.get("stream_only") is True
        assert payload.get("user_id") == test_user.id
        assert payload.get("company_slug") == test_company.slug

        # Pre-publish a terminal event so the SSE stream completes immediately
        event_bus.publish(test_co_task.task_id, "completed", {"result": "ok"})

        # Use the stream token as query param (no Bearer header)
        unauthenticated = TestClient(app)
        resp = unauthenticated.get(
            f"/api/v1/tasks/{test_co_task.task_id}/events?stream_token={stream_token}",
        )
        # If middleware rejected the token we'd get 401; 200 confirms acceptance
        assert resp.status_code == 200

    def test_stream_token_rejected_for_non_sse_endpoint(
        self,
        public_client: TestClient,
        client: TestClient,
        test_co_task: PipelineTask,
    ) -> None:
        """Stream tokens must only work for /events endpoints."""
        token_resp = client.post(f"/api/v1/tasks/{test_co_task.task_id}/stream-token")
        stream_token = token_resp.json()["stream_token"]

        # Use the stream token as a Bearer header on a non-SSE endpoint
        resp = public_client.get(
            "/api/v1/tasks",
            headers={"Authorization": f"Bearer {stream_token}"},
        )
        assert resp.status_code == 401

    def test_stream_token_ownership_check(
        self, client: TestClient, other_co_task: PipelineTask
    ) -> None:
        """Cannot create a stream token for another company's task."""
        resp = client.post(f"/api/v1/tasks/{other_co_task.task_id}/stream-token")
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════
# 6. Registration hardening
# ═══════════════════════════════════════════════════════════════════


class TestRegistrationHardening:
    """Registration isolation and invite flows."""

    def test_register_duplicate_domain_returns_409(
        self, public_client: TestClient
    ) -> None:
        """Registering a second user with the same domain returns 409."""
        payload = {
            "first_name": "First",
            "last_name": "User",
            "email": "first@dupedomain.com",
            "password": "securepass123",
            "company_name": "Dupe Domain Inc",
            "company_domain": "dupedomain.com",
        }
        resp1 = public_client.post("/api/v1/auth/register", json=payload)
        assert resp1.status_code == 201

        payload2 = {**payload, "email": "second@dupedomain.com"}
        resp2 = public_client.post("/api/v1/auth/register", json=payload2)
        assert resp2.status_code == 409

    def test_register_creates_isolated_company(
        self, public_client: TestClient, auth_store: AuthStore
    ) -> None:
        """Two registrations with different domains create separate companies."""
        resp1 = public_client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "Alice",
                "last_name": "One",
                "email": "alice@alpha.com",
                "password": "securepass123",
                "company_name": "Alpha Inc",
                "company_domain": "alpha.com",
            },
        )
        assert resp1.status_code == 201

        resp2 = public_client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "Bob",
                "last_name": "Two",
                "email": "bob@beta.com",
                "password": "securepass123",
                "company_name": "Beta Inc",
                "company_domain": "beta.com",
            },
        )
        assert resp2.status_code == 201

        # Verify different companies
        company1 = resp1.json()["company"]
        company2 = resp2.json()["company"]
        assert company1["slug"] != company2["slug"]
        assert company1["id"] != company2["id"]

    def test_invite_requires_superuser(self, client: TestClient) -> None:
        """Member role cannot create invite codes (superuser required)."""
        resp = client.post("/api/v1/auth/invite", json={"role": "member"})
        assert resp.status_code == 403

    def test_join_with_valid_invite(
        self, public_client: TestClient, superuser_client: TestClient
    ) -> None:
        """Create invite via superuser, then join via public endpoint."""
        # Superuser creates an invite
        invite_resp = superuser_client.post(
            "/api/v1/auth/invite", json={"role": "member"}
        )
        assert invite_resp.status_code == 201
        invite_code = invite_resp.json()["invite_code"]

        # New user joins via the public /join endpoint
        join_resp = public_client.post(
            "/api/v1/auth/join",
            json={
                "invite_code": invite_code,
                "first_name": "Joined",
                "last_name": "User",
                "email": "joined@testco.com",
                "password": "securepass123",
            },
        )
        assert join_resp.status_code == 201
        data = join_resp.json()
        assert data["user"]["role"] == "member"
        assert data["company"]["slug"] == "test-co"


# ═══════════════════════════════════════════════════════════════════
# 7. Login behavior
# ═══════════════════════════════════════════════════════════════════


class TestLoginBehavior:
    """Login returns 401 for non-existent users (not blocked by middleware)."""

    def test_login_nonexistent_user_responds_401(
        self, public_client: TestClient
    ) -> None:
        resp = public_client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@nowhere.com", "password": "securepass123"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"


# ═══════════════════════════════════════════════════════════════════
# 8. Critical review fixes (C1, C2+C3, C4, C5)
# ═══════════════════════════════════════════════════════════════════


class TestC1ArtifactIDOR:
    """C1: Cross-tenant artifact read bypass on flat types.

    A user supplying their own slug in the URL but a different company's
    filename should be rejected with 403.
    """

    def test_flat_type_filename_must_match_slug(
        self,
        client: TestClient,
        artifacts_root: Path,
        other_company: Company,
    ) -> None:
        """test-co user cannot read other-co.md via /artifacts/company_context/test-co/other-co.md."""
        cc_dir = artifacts_root / "company_context"
        cc_dir.mkdir(parents=True, exist_ok=True)
        (cc_dir / "test-co.md").write_text("# Test Co context")
        (cc_dir / "other-co.md").write_text("# Other Co SECRET context")

        # Legit access — own file
        resp = client.get("/api/v1/artifacts/company_context/test-co/test-co.md")
        assert resp.status_code == 200
        assert "Test Co context" in resp.text

        # IDOR attempt — slug=test-co but filename=other-co.md
        resp = client.get("/api/v1/artifacts/company_context/test-co/other-co.md")
        assert resp.status_code == 403

    def test_flat_type_effective_slug_allowed(
        self,
        client: TestClient,
        artifacts_root: Path,
    ) -> None:
        """Effective slug files (test-co__product.md) are allowed for test-co user."""
        cc_dir = artifacts_root / "company_context"
        cc_dir.mkdir(parents=True, exist_ok=True)
        (cc_dir / "test-co__product.md").write_text("# Product context")

        resp = client.get(
            "/api/v1/artifacts/company_context/test-co/test-co__product.md"
        )
        assert resp.status_code == 200

    def test_flat_type_draft_file_allowed(
        self,
        client: TestClient,
        artifacts_root: Path,
    ) -> None:
        """Draft files (test-co.draft.md) are allowed for the owning company."""
        cc_dir = artifacts_root / "company_context"
        cc_dir.mkdir(parents=True, exist_ok=True)
        (cc_dir / "test-co.draft.md").write_text("# Draft context")

        resp = client.get(
            "/api/v1/artifacts/company_context/test-co/test-co.draft.md"
        )
        assert resp.status_code == 200

    def test_flat_type_persona_idor_blocked(
        self,
        client: TestClient,
        artifacts_root: Path,
        other_company: Company,
    ) -> None:
        """Persona files from other company also blocked."""
        persona_dir = artifacts_root / "personas"
        persona_dir.mkdir(parents=True, exist_ok=True)
        (persona_dir / "other-co__persona-icp.md").write_text("# Secret persona")

        resp = client.get(
            "/api/v1/artifacts/personas/test-co/other-co__persona-icp.md"
        )
        assert resp.status_code == 403


class TestC4DeactivatedUserLogin:
    """C4: Deactivated users must be rejected at login (before token issuance)."""

    def test_deactivated_user_cannot_login(
        self,
        public_client: TestClient,
        auth_store: AuthStore,
        test_user: UserProfile,
    ) -> None:
        # Deactivate the user directly in the store
        user_data = auth_store.get_user_by_id(test_user.id)
        assert user_data is not None
        user_data["is_active"] = False

        resp = public_client.post(
            "/api/v1/auth/login",
            json={"email": "dev@testco.com", "password": "testpassword123"},
        )
        assert resp.status_code == 401
        assert "deactivated" in resp.json()["detail"].lower()

    def test_active_user_can_login(
        self, public_client: TestClient, test_user: UserProfile
    ) -> None:
        """Sanity check: active user login still works."""
        resp = public_client.post(
            "/api/v1/auth/login",
            json={"email": "dev@testco.com", "password": "testpassword123"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()


class TestC2C3SSEAuthDependency:
    """C2+C3: SSE events endpoint must enforce is_active via require_auth."""

    def test_deactivated_user_cannot_stream_events(
        self,
        app: FastAPI,
        auth_store: AuthStore,
        test_user: UserProfile,
        test_company: Company,
        task_store: TaskStore,
        event_bus,
    ) -> None:
        """Deactivated user with valid token gets 401 from SSE endpoint."""
        task = task_store.create_task("gap_analysis", "test-co")
        event_bus.publish(task.task_id, "completed", {"result": "ok"})

        # Create token while user is still active
        token = auth_store.create_access_token(test_user.id, test_company.slug)

        # Deactivate user
        user_data = auth_store.get_user_by_id(test_user.id)
        assert user_data is not None
        user_data["is_active"] = False

        deactivated_client = _AuthTestClient(
            app, default_headers={"Authorization": f"Bearer {token}"}
        )
        resp = deactivated_client.get(f"/api/v1/tasks/{task.task_id}/events")
        assert resp.status_code == 401


class TestC5InviteRaceCondition:
    """C5: Invite code redemption must be atomic — no double-use."""

    def test_invite_code_single_use(
        self,
        public_client: TestClient,
        superuser_client: TestClient,
    ) -> None:
        """After one successful redemption, the same code returns 400."""
        # Create invite
        invite_resp = superuser_client.post(
            "/api/v1/auth/invite", json={"role": "member"}
        )
        assert invite_resp.status_code == 201
        code = invite_resp.json()["invite_code"]

        # First redemption — success
        resp1 = public_client.post(
            "/api/v1/auth/join",
            json={
                "invite_code": code,
                "first_name": "First",
                "last_name": "Redeemer",
                "email": "first-redeemer@example.com",
                "password": "securepass123",
            },
        )
        assert resp1.status_code == 201

        # Second redemption with same code — must fail (not 500)
        resp2 = public_client.post(
            "/api/v1/auth/join",
            json={
                "invite_code": code,
                "first_name": "Second",
                "last_name": "Redeemer",
                "email": "second-redeemer@example.com",
                "password": "securepass123",
            },
        )
        assert resp2.status_code == 400
        assert "invalid" in resp2.json()["detail"].lower() or "expired" in resp2.json()["detail"].lower()

    def test_invalid_invite_code_returns_400(
        self, public_client: TestClient
    ) -> None:
        resp = public_client.post(
            "/api/v1/auth/join",
            json={
                "invite_code": "nonexistent-code",
                "first_name": "Bad",
                "last_name": "Code",
                "email": "badcode@example.com",
                "password": "securepass123",
            },
        )
        assert resp.status_code == 400
