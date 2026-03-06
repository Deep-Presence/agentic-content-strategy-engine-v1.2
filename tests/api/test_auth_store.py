"""Tests for JSON-file backed AuthStore."""
from __future__ import annotations

from pathlib import Path

import pytest

from api.auth.store import AuthStore
from core.models.organization import Product


class TestAuthStoreCompanies:
    """Tests for company CRUD operations."""

    def test_create_company(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        company = store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        assert company.slug == "ramp"
        assert company.name == "Ramp"
        assert company.domain == "ramp.com"
        assert company.id  # UUID generated

    def test_create_company_duplicate_raises(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        with pytest.raises(ValueError, match="already exists"):
            store.create_company(slug="ramp", name="Ramp 2", domain="ramp2.com")

    def test_get_company_by_slug(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        store.create_company(slug="ramp", name="Ramp", domain="ramp.com")

        found = store.get_company_by_slug("ramp")
        assert found is not None
        assert found.name == "Ramp"

        assert store.get_company_by_slug("nonexistent") is None

    def test_list_companies(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        store.create_company(slug="carta", name="Carta", domain="carta.com")

        companies = store.list_companies()
        slugs = {c.slug for c in companies}
        assert slugs == {"ramp", "carta"}

    def test_update_company(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        store.create_company(slug="ramp", name="Ramp", domain="ramp.com")

        updated = store.update_company("ramp", name="Ramp Inc.")
        assert updated.name == "Ramp Inc."
        assert updated.domain == "ramp.com"

    def test_update_nonexistent_raises(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        with pytest.raises(ValueError, match="not found"):
            store.update_company("nonexistent", name="X")

    def test_create_company_with_products(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        products = [
            Product(company_id="x", slug="card", name="Corporate Card"),
        ]
        company = store.create_company(
            slug="ramp", name="Ramp", domain="ramp.com", products=products
        )
        assert len(company.products) == 1
        assert company.products[0].slug == "card"

    def test_persistence_across_instances(self, tmp_path: Path) -> None:
        """Data persists to disk and survives new AuthStore instances."""
        store1 = AuthStore(base_dir=tmp_path)
        store1.create_company(slug="ramp", name="Ramp", domain="ramp.com")

        # Create new instance from same directory
        store2 = AuthStore(base_dir=tmp_path)
        found = store2.get_company_by_slug("ramp")
        assert found is not None
        assert found.name == "Ramp"


class TestAuthStoreUsers:
    """Tests for user CRUD operations."""

    def test_create_user(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        company = store.create_company(slug="ramp", name="Ramp", domain="ramp.com")

        user = store.create_user(
            company_id=company.id,
            email="aryan@ramp.com",
            first_name="Aryan",
            last_name="Keshri",
            password="securepassword",
            role="superuser",
        )
        assert user.email == "aryan@ramp.com"
        assert user.first_name == "Aryan"
        assert user.last_name == "Keshri"
        assert user.full_name == "Aryan Keshri"
        assert user.role == "superuser"
        assert user.company_id == company.id

    def test_create_user_duplicate_email_raises(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        company = store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        store.create_user(
            company_id=company.id,
            email="aryan@ramp.com",
            first_name="Aryan",
            last_name="K",
            password="pass1",
        )
        with pytest.raises(ValueError, match="already exists"):
            store.create_user(
                company_id=company.id,
                email="aryan@ramp.com",
                first_name="Aryan",
                last_name="K2",
                password="pass2",
            )

    def test_get_user_by_email(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        company = store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        store.create_user(
            company_id=company.id,
            email="aryan@ramp.com",
            first_name="Aryan",
            last_name="K",
            password="pass",
        )

        found = store.get_user_by_email("aryan@ramp.com")
        assert found is not None
        assert found["first_name"] == "Aryan"

        assert store.get_user_by_email("nobody@ramp.com") is None

    def test_list_users_for_company(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        c1 = store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        c2 = store.create_company(slug="carta", name="Carta", domain="carta.com")

        store.create_user(c1.id, "a@ramp.com", "p1", first_name="A", last_name="X")
        store.create_user(c1.id, "b@ramp.com", "p2", first_name="B", last_name="Y")
        store.create_user(c2.id, "c@carta.com", "p3", first_name="C", last_name="Z")

        ramp_users = store.list_users_for_company(c1.id)
        assert len(ramp_users) == 2
        carta_users = store.list_users_for_company(c2.id)
        assert len(carta_users) == 1


class TestAuthStorePassword:
    """Tests for password hashing and verification."""

    def test_verify_correct_password(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        company = store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        store.create_user(
            company_id=company.id,
            email="test@ramp.com",
            first_name="Test",
            last_name="User",
            password="correctpassword",
        )

        user_data = store.get_user_by_email("test@ramp.com")
        assert store.verify_password("correctpassword", user_data["password_hash"])

    def test_verify_wrong_password(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        company = store.create_company(slug="ramp", name="Ramp", domain="ramp.com")
        store.create_user(
            company_id=company.id,
            email="test@ramp.com",
            first_name="Test",
            last_name="User",
            password="correctpassword",
        )

        user_data = store.get_user_by_email("test@ramp.com")
        assert not store.verify_password("wrongpassword", user_data["password_hash"])

    def test_verify_invalid_hash_format(self) -> None:
        assert not AuthStore.verify_password("any", "invalid-hash-format")


class TestAuthStoreTokens:
    """Tests for JWT-like token creation and verification."""

    def test_create_and_verify_token(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        token = store.create_access_token("user-123", "ramp")

        payload = store.verify_token(token)
        assert payload is not None
        assert payload["user_id"] == "user-123"
        assert payload["company_slug"] == "ramp"

    def test_verify_invalid_token(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        assert store.verify_token("garbage-token") is None

    def test_verify_tampered_token(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        token = store.create_access_token("user-123", "ramp")

        # Tamper with the signature
        parts = token.split(".", 1)
        tampered = parts[0] + ".tampered_signature"
        assert store.verify_token(tampered) is None

    def test_expired_token(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        # Create token that expires immediately (0 hours)
        token = store.create_access_token("user-123", "ramp", expires_hours=0)
        # Should be expired immediately
        assert store.verify_token(token) is None
