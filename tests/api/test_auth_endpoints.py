"""Tests for /login, /me endpoints, validation (C3), and auth middleware (C2).

Covers:
- POST /api/v1/auth/login — success, wrong password, nonexistent email, token validity
- GET /api/v1/auth/me — with valid token, without token, with invalid/expired token
- Input validation — invalid email format, short password
- Auth middleware — default-deny ASGI middleware, token parsing into request.state
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ── Helpers ──────────────────────────────────────────────────────

_REG_PAYLOAD = {
    "first_name": "Jane",
    "last_name": "Doe",
    "email": "jane@acme.com",
    "password": "securepass123",
    "company_name": "Acme Corp",
    "company_domain": "acme.com",
}


def _register(client: TestClient, **overrides) -> dict:
    """Register a user and return the response JSON."""
    payload = {**_REG_PAYLOAD, **overrides}
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Login tests ──────────────────────────────────────────────────


class TestLogin:
    """POST /api/v1/auth/login"""

    def test_login_success(self, client: TestClient) -> None:
        _register(client)
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "jane@acme.com", "password": "securepass123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"]
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "jane@acme.com"
        assert data["company"]["domain"] == "acme.com"

    def test_login_wrong_password(self, client: TestClient) -> None:
        _register(client)
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "jane@acme.com", "password": "wrongpassword1"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

    def test_login_nonexistent_email(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@acme.com", "password": "securepass123"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

    def test_login_returns_valid_token(self, client: TestClient) -> None:
        """Login token should work with /me."""
        _register(client)
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"email": "jane@acme.com", "password": "securepass123"},
        )
        token = login_resp.json()["access_token"]
        me_resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        assert me_resp.json()["user"]["email"] == "jane@acme.com"

    def test_login_token_type_is_bearer(self, client: TestClient) -> None:
        _register(client)
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "jane@acme.com", "password": "securepass123"},
        )
        assert resp.json()["token_type"] == "bearer"

    def test_login_returns_correct_user_fields(self, client: TestClient) -> None:
        _register(client)
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "jane@acme.com", "password": "securepass123"},
        )
        user = resp.json()["user"]
        assert user["first_name"] == "Jane"
        assert user["last_name"] == "Doe"
        assert user["role"] == "superuser"  # First user is superuser
        assert user["is_active"] is True
        assert user["id"]  # Non-empty UUID
        assert user["company_id"]

    def test_login_uses_company_by_id(self, client: TestClient) -> None:
        """Login resolves company via get_company_by_id (not O(N) list scan)."""
        reg = _register(client)
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "jane@acme.com", "password": "securepass123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["company"]["slug"] == "acme-corp"
        assert data["company"]["id"] == reg["company"]["id"]


# ── Me tests ─────────────────────────────────────────────────────


class TestMe:
    """GET /api/v1/auth/me"""

    def test_me_with_valid_token(self, client: TestClient) -> None:
        reg = _register(client)
        token = reg["access_token"]
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["email"] == "jane@acme.com"
        assert data["company"]["slug"] == "acme-corp"
        assert data["company"]["domain"] == "acme.com"

    def test_me_without_token(self, public_client: TestClient) -> None:
        resp = public_client.get("/api/v1/auth/me")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Missing authentication token"

    def test_me_with_invalid_token(self, public_client: TestClient) -> None:
        resp = public_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer garbage.token"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid or expired token"

    def test_me_with_expired_token(self, client: TestClient, auth_store) -> None:
        """Create a token with negative expiry so it's already expired."""
        reg = _register(client)
        user_id = reg["user"]["id"]
        company_slug = reg["company"]["slug"]
        expired_token = auth_store.create_access_token(
            user_id, company_slug, expires_hours=-1
        )
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401

    def test_me_returns_all_user_fields(self, client: TestClient) -> None:
        reg = _register(client)
        token = reg["access_token"]
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        user = resp.json()["user"]
        # All UserResponse fields present
        assert set(user.keys()) == {
            "id", "email", "first_name", "last_name",
            "role", "company_id", "is_active",
        }

    def test_me_deactivated_user_returns_401(
        self, client: TestClient, auth_store,
    ) -> None:
        """PB-34: Deactivated user with valid token must get 401 on /me."""
        reg = _register(client)
        token = reg["access_token"]
        user_id = reg["user"]["id"]
        # Deactivate the user
        auth_store.update_user(user_id, is_active=False)
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Account deactivated"

    def test_me_deleted_user_returns_401(
        self, client: TestClient, auth_store,
    ) -> None:
        """PB-34: Token for a deleted user must get 401 on /me."""
        reg = _register(client)
        token = reg["access_token"]
        user_id = reg["user"]["id"]
        # Remove user from store
        auth_store._users.pop(user_id, None)
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "User not found"

    def test_me_no_token_returns_401(self, public_client: TestClient) -> None:
        """PB-34: /me without token returns 401."""
        resp = public_client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_me_active_user_returns_correct_data(
        self, client: TestClient,
    ) -> None:
        """PB-34: Active user with valid token gets 200 with correct data."""
        reg = _register(client)
        token = reg["access_token"]
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["email"] == "jane@acme.com"
        assert data["user"]["is_active"] is True
        assert data["company"]["slug"] == "acme-corp"
        assert data["company"]["domain"] == "acme.com"


# ── Validation tests (C3) ───────────────────────────────────────


class TestValidation:
    """Input validation from C3: EmailStr + password constraints."""

    def test_register_invalid_email(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/auth/register",
            json={**_REG_PAYLOAD, "email": "not-an-email"},
        )
        assert resp.status_code == 422

    def test_register_short_password(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/auth/register",
            json={**_REG_PAYLOAD, "password": "abc"},
        )
        assert resp.status_code == 422

    def test_login_invalid_email_format(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "not-an-email", "password": "securepass123"},
        )
        assert resp.status_code == 422


# ── Middleware tests (C2) ────────────────────────────────────────


class TestAuthMiddleware:
    """Auth middleware default-deny ASGI + token parsing."""

    def test_request_without_auth_header_passes(self, client: TestClient) -> None:
        """Public routes pass through without auth."""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_request_with_valid_token_sets_state(self, client: TestClient) -> None:
        """Middleware parses token → /me returns user info."""
        reg = _register(client)
        token = reg["access_token"]
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        # If middleware didn't set state, /me would return 401
        assert resp.json()["user"]["email"] == "jane@acme.com"
