"""Tests for BYOK credential helpers."""
from __future__ import annotations

from cryptography.fernet import Fernet

from core.model_config.credentials import (
    decrypt_api_key,
    encrypt_api_key,
    fingerprint_api_key,
    mask_api_key,
    normalize_api_key,
)


def test_encrypt_decrypt_roundtrip() -> None:
    fernet_key = Fernet.generate_key().decode()
    encrypted = encrypt_api_key(" sk-or-test-secret ", fernet_key=fernet_key)
    assert "sk-or-test-secret" not in encrypted
    assert decrypt_api_key(encrypted, fernet_key=fernet_key) == "sk-or-test-secret"


def test_mask_api_key_keeps_only_prefix_and_suffix() -> None:
    masked = mask_api_key("sk-or-abcdef123456")
    assert masked == "sk-or...3456"
    assert "abcdef12" not in masked


def test_fingerprint_uses_pepper() -> None:
    raw = "sk-or-test-secret"
    first = fingerprint_api_key(raw, pepper="one")
    second = fingerprint_api_key(raw, pepper="two")
    assert first != second
    assert first == fingerprint_api_key(f" {raw} ", pepper="one")


def test_normalize_api_key_trims_whitespace() -> None:
    assert normalize_api_key(" sk-or-test\n") == "sk-or-test"
