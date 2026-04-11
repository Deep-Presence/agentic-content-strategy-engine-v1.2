# Core Auth Module

> **Location:** `core/auth/`
> **Owner:** Core
> **Dependencies:** `core/db/repositories/`, `core/models/organization.py`, hashlib, hmac
> **Dependents:** `api/auth/`, `api/dependencies.py`, all authenticated endpoints
> **Last Updated:** 2026-04-09

## Overview

The auth module provides authentication, authorization, and user/company management. It follows the Protocol-based design pattern where `AuthServiceProtocol` defines the interface and `DbAuthService` is the production implementation using SQLAlchemy ORM repositories. Token creation uses a custom v0 format (base64 payload + HMAC-SHA256 signature) rather than JWT libraries. Password hashing uses PBKDF2-HMAC-SHA256 with constant-time comparison.

## Architecture

```
AuthServiceProtocol (runtime-checkable Protocol)
        │
        ▼
DbAuthService (production implementation)
    ├── CompanyRepository
    ├── AuthRepository
    ├── InviteRepository
    ├── ProductRepository
    └── PipelineDefaultsRepository
```

## File Structure

| File | Purpose | Key Exports |
|------|---------|-------------|
| `__init__.py` | Re-exports | `AuthServiceProtocol`, `DbAuthService` |
| `service.py` | Protocol definition | `AuthServiceProtocol` |
| `db_service.py` | DB implementation | `DbAuthService` |
| `utils/domain.py` | Domain utilities | `normalize_domain`, `derive_slug`, mutable field sets |
| `utils/passwords.py` | Password hashing | `hash_password`, `verify_password` |
| `utils/tokens.py` | Token creation/verification | `create_access_token`, `create_stream_token`, `verify_token` |

## Detailed Reference

### `AuthServiceProtocol` (23 methods)

Runtime-checkable async Protocol. All methods are `async def`. Key operations:

**Company CRUD:** `get_company_by_slug`, `get_company_by_id`, `get_company_by_domain`, `list_companies`, `create_company`, `update_company`

**Product CRUD:** `get_product`, `add_product`, `update_product`, `remove_product`

**User CRUD:** `get_user_by_email`, `get_user_by_id`, `list_users_for_company`, `create_user`, `update_user`

**Registration & Invites:** `register_user`, `create_invite`, `redeem_invite`

**Pipeline Defaults:** `get_pipeline_defaults`, `update_pipeline_defaults`

**Tokens:** `create_access_token`, `create_stream_token`, `verify_token`

### `DbAuthService`

Production implementation with guards:
- Cannot deactivate self
- Cannot demote last superuser of a company
- Mutable field allowlists prevent unauthorized updates
- Domain normalization and slug collision handling on registration

### Password Hashing (`utils/passwords.py`)

| Function | Signature | Description |
|----------|-----------|-------------|
| `hash_password` | `(password: str) -> str` | PBKDF2-HMAC-SHA256, 16-byte salt, returns `{salt_hex}:{hash_hex}` |
| `verify_password` | `(password: str, stored_hash: str) -> bool` | Constant-time comparison via `hmac.compare_digest` |

`DUMMY_HASH` constant prevents timing oracle attacks on non-existent users.

### Token System (`utils/tokens.py`)

| Function | Signature | Description |
|----------|-----------|-------------|
| `get_secret_key` | `() -> str` | Resolves from `JWT_SECRET_KEY` env var, auto-generates for dev |
| `create_access_token` | `(secret_key, user_id, company_slug, expires_hours=24) -> str` | 24h access token |
| `create_stream_token` | `(secret_key, user_id, company_slug, expires_minutes=60) -> str` | SSE-only token with `stream_only: True` |
| `verify_token` | `(secret_key, token) -> Optional[Dict]` | Returns payload if valid and not expired |

Token format: `base64(JSON payload).HMAC-SHA256(payload, secret_key)`

### Domain Utilities (`utils/domain.py`)

| Function | Signature | Description |
|----------|-----------|-------------|
| `normalize_domain` | `(raw: str) -> Tuple[str, Optional[str]]` | Returns `(root_domain, subdomain_or_none)`. Handles protocol stripping, www removal, multi-part TLDs |
| `derive_slug` | `(name: str) -> str` | Converts to kebab-case URL-safe slug |

| Constant | Value | Purpose |
|----------|-------|---------|
| `_MULTI_PART_TLDS` | frozenset (co.uk, com.au, etc.) | Known multi-part TLDs |
| `COMPANY_MUTABLE_FIELDS` | `{"name", "domain", "additional_domains", "industry"}` | Allowlist for company updates |
| `PRODUCT_MUTABLE_FIELDS` | `{"name", "domain", "description"}` | Allowlist for product updates |
| `USER_MUTABLE_FIELDS` | `{"role", "first_name", "last_name", "is_active"}` | Allowlist for user updates |

## Integration Points

- **API Auth Middleware** (`api/auth/`) — verifies tokens, injects user context
- **API Dependencies** (`api/dependencies.py`) — `get_auth_service()` builds `DbAuthService` per-request
- **BFF Proxy** (frontend) — calls auth API routes, manages httpOnly cookies
