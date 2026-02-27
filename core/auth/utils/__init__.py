"""Pure auth utilities — zero I/O, no DB or file dependencies."""
from core.auth.utils.passwords import DUMMY_HASH, hash_password, verify_password
from core.auth.utils.tokens import (
    create_access_token,
    create_stream_token,
    get_secret_key,
    verify_token,
)
from core.auth.utils.domain import (
    COMPANY_MUTABLE_FIELDS,
    PRODUCT_MUTABLE_FIELDS,
    USER_MUTABLE_FIELDS,
    derive_slug,
    normalize_domain,
)

__all__ = [
    "DUMMY_HASH",
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_stream_token",
    "get_secret_key",
    "verify_token",
    "normalize_domain",
    "derive_slug",
    "COMPANY_MUTABLE_FIELDS",
    "PRODUCT_MUTABLE_FIELDS",
    "USER_MUTABLE_FIELDS",
]
