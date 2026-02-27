"""Tests for core.auth.utils — pure utility functions (no I/O)."""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from core.auth.utils.domain import (
    COMPANY_MUTABLE_FIELDS,
    PRODUCT_MUTABLE_FIELDS,
    USER_MUTABLE_FIELDS,
    derive_slug,
    normalize_domain,
)
from core.auth.utils.passwords import DUMMY_HASH, hash_password, verify_password
from core.auth.utils.tokens import (
    create_access_token,
    create_stream_token,
    get_secret_key,
    verify_token,
)


# ── Password hashing ──────────────────────────────────────────


class TestHashPassword:
    def test_roundtrip(self) -> None:
        hashed = hash_password("my-secret")
        assert verify_password("my-secret", hashed)

    def test_wrong_password(self) -> None:
        hashed = hash_password("correct-horse")
        assert not verify_password("wrong-horse", hashed)

    def test_hash_format(self) -> None:
        hashed = hash_password("test")
        parts = hashed.split(":")
        assert len(parts) == 2
        salt, digest = parts
        assert len(salt) == 32  # 16 bytes hex
        assert len(digest) == 64  # 32 bytes hex

    def test_different_salts(self) -> None:
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # different random salts


class TestVerifyPassword:
    def test_malformed_hash(self) -> None:
        assert not verify_password("any", "not-a-valid-hash")

    def test_empty_hash(self) -> None:
        assert not verify_password("any", "")

    def test_dummy_hash_rejects(self) -> None:
        assert not verify_password("anything", DUMMY_HASH)


class TestDummyHash:
    def test_format(self) -> None:
        parts = DUMMY_HASH.split(":")
        assert len(parts) == 2
        assert len(parts[0]) == 32
        assert len(parts[1]) == 64


# ── Token signing ─────────────────────────────────────────────

SECRET = "test-secret-key-for-unit-tests"


class TestCreateAccessToken:
    def test_create_and_verify(self) -> None:
        token = create_access_token(SECRET, "user-1", "acme", expires_hours=1)
        payload = verify_token(SECRET, token)
        assert payload is not None
        assert payload["user_id"] == "user-1"
        assert payload["company_slug"] == "acme"
        assert "exp" in payload

    def test_wrong_secret_rejects(self) -> None:
        token = create_access_token(SECRET, "user-1", "acme")
        assert verify_token("wrong-secret", token) is None

    def test_expired_token(self) -> None:
        token = create_access_token(SECRET, "user-1", "acme", expires_hours=-1)
        assert verify_token(SECRET, token) is None


class TestCreateStreamToken:
    def test_create_and_verify(self) -> None:
        token = create_stream_token(SECRET, "user-2", "beta", expires_minutes=5)
        payload = verify_token(SECRET, token)
        assert payload is not None
        assert payload["user_id"] == "user-2"
        assert payload["company_slug"] == "beta"
        assert payload["stream_only"] is True

    def test_expired_stream_token(self) -> None:
        token = create_stream_token(SECRET, "user-2", "beta", expires_minutes=-1)
        assert verify_token(SECRET, token) is None


class TestVerifyToken:
    def test_garbage_token(self) -> None:
        assert verify_token(SECRET, "not.a.valid.token") is None

    def test_empty_token(self) -> None:
        assert verify_token(SECRET, "") is None

    def test_tampered_payload(self) -> None:
        token = create_access_token(SECRET, "user-1", "acme")
        parts = token.split(".")
        # Tamper with payload (flip a character)
        tampered = parts[0][:-1] + ("A" if parts[0][-1] != "A" else "B")
        assert verify_token(SECRET, f"{tampered}.{parts[1]}") is None

    def test_tampered_signature(self) -> None:
        token = create_access_token(SECRET, "user-1", "acme")
        parts = token.split(".")
        tampered_sig = parts[1][:-1] + ("a" if parts[1][-1] != "a" else "b")
        assert verify_token(SECRET, f"{parts[0]}.{tampered_sig}") is None


class TestGetSecretKey:
    def test_from_env(self) -> None:
        with patch.dict("os.environ", {"JWT_SECRET_KEY": "my-key"}):
            assert get_secret_key() == "my-key"

    def test_auto_generate_in_dev(self) -> None:
        with patch.dict("os.environ", {"ENVIRONMENT": "development"}, clear=False):
            import os
            os.environ.pop("JWT_SECRET_KEY", None)
            key = get_secret_key()
            assert len(key) == 64  # 32 bytes hex

    def test_raises_in_production(self) -> None:
        with patch.dict("os.environ", {"ENVIRONMENT": "production"}, clear=False):
            import os
            os.environ.pop("JWT_SECRET_KEY", None)
            with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
                get_secret_key()


# ── Domain normalization ──────────────────────────────────────


class TestNormalizeDomain:
    def test_simple_domain(self) -> None:
        assert normalize_domain("ramp.com") == ("ramp.com", None)

    def test_www_stripped(self) -> None:
        assert normalize_domain("www.ramp.com") == ("ramp.com", None)

    def test_subdomain_extracted(self) -> None:
        assert normalize_domain("app.ramp.com") == ("ramp.com", "app.ramp.com")

    def test_protocol_stripped(self) -> None:
        assert normalize_domain("https://ramp.com/pricing") == ("ramp.com", None)

    def test_multi_part_tld(self) -> None:
        assert normalize_domain("example.co.uk") == ("example.co.uk", None)

    def test_multi_part_tld_with_subdomain(self) -> None:
        assert normalize_domain("app.example.co.uk") == (
            "example.co.uk",
            "app.example.co.uk",
        )

    def test_port_stripped(self) -> None:
        assert normalize_domain("ramp.com:8080") == ("ramp.com", None)

    def test_uppercase_lowered(self) -> None:
        assert normalize_domain("Ramp.COM") == ("ramp.com", None)

    def test_http_protocol(self) -> None:
        assert normalize_domain("http://www.ramp.com") == ("ramp.com", None)


class TestDeriveSlug:
    def test_simple_name(self) -> None:
        assert derive_slug("Ramp") == "ramp"

    def test_multi_word(self) -> None:
        assert derive_slug("Deep Presence") == "deep-presence"

    def test_special_chars(self) -> None:
        assert derive_slug("Acme, Inc.") == "acme-inc"

    def test_already_slug(self) -> None:
        assert derive_slug("my-company") == "my-company"


# ── Mutable field allowlists ──────────────────────────────────


class TestMutableFields:
    def test_company_fields(self) -> None:
        assert "name" in COMPANY_MUTABLE_FIELDS
        assert "domain" in COMPANY_MUTABLE_FIELDS
        assert "slug" not in COMPANY_MUTABLE_FIELDS
        assert "id" not in COMPANY_MUTABLE_FIELDS

    def test_product_fields(self) -> None:
        assert "name" in PRODUCT_MUTABLE_FIELDS
        assert "description" in PRODUCT_MUTABLE_FIELDS
        assert "slug" not in PRODUCT_MUTABLE_FIELDS

    def test_user_fields(self) -> None:
        assert "role" in USER_MUTABLE_FIELDS
        assert "is_active" in USER_MUTABLE_FIELDS
        assert "email" not in USER_MUTABLE_FIELDS
        assert "company_id" not in USER_MUTABLE_FIELDS
