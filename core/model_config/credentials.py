"""Credential encryption, masking, and fingerprinting helpers."""
from __future__ import annotations

import hashlib

from cryptography.fernet import Fernet


def normalize_api_key(api_key: str) -> str:
    return api_key.strip()


def mask_api_key(api_key: str) -> str:
    normalized = normalize_api_key(api_key)
    if not normalized:
        return ""
    return f"{normalized[:5]}...{normalized[-4:]}" if len(normalized) > 9 else "***"


def fingerprint_api_key(api_key: str, *, pepper: str) -> str:
    normalized = normalize_api_key(api_key)
    return hashlib.sha256(f"{pepper}:{normalized}".encode("utf-8")).hexdigest()


def encrypt_api_key(api_key: str, *, fernet_key: str) -> str:
    normalized = normalize_api_key(api_key)
    return Fernet(fernet_key.encode()).encrypt(normalized.encode("utf-8")).decode()


def decrypt_api_key(encrypted_api_key: str, *, fernet_key: str) -> str:
    return (
        Fernet(fernet_key.encode())
        .decrypt(encrypted_api_key.encode("utf-8"))
        .decode("utf-8")
    )


def resolve_fernet_key() -> str:
    from core.config.settings import settings

    key = settings.credential_fernet_key or settings.cms_fernet_key
    if not key:
        raise RuntimeError("CREDENTIAL_FERNET_KEY is required for BYOK credentials")
    return key


def resolve_fingerprint_pepper() -> str:
    from core.config.settings import settings

    return settings.credential_fernet_key or settings.cms_fernet_key or "local-dev"
