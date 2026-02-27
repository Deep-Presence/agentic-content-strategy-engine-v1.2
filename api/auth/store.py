"""JSON-file backed auth store for companies and users.

This is a v0 implementation that persists to local JSON files.
It will be replaced by a DB-backed AuthService (see core/auth/).

Files:
  artifacts/_auth/companies.json — List[Company]
  artifacts/_auth/users.json     — List[{...UserProfile, password_hash}]
"""
from __future__ import annotations

import json
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.auth.utils.domain import (
    COMPANY_MUTABLE_FIELDS as _COMPANY_MUTABLE_FIELDS,
    PRODUCT_MUTABLE_FIELDS as _PRODUCT_MUTABLE_FIELDS,
    USER_MUTABLE_FIELDS as _USER_MUTABLE_FIELDS,
    derive_slug as _derive_slug,
    normalize_domain,
)
from core.auth.utils.passwords import (
    DUMMY_HASH,
    hash_password,
    verify_password,
)
from core.auth.utils.tokens import (
    create_access_token as _create_access_token,
    create_stream_token as _create_stream_token,
    get_secret_key,
    verify_token as _verify_token,
)
from core.models.organization import Company, CompanyPipelineDefaults, Product, UserProfile


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuthStore:
    """JSON-file backed store for companies and users."""

    # Dummy hash for constant-time login failure (Codex W7)
    _DUMMY_HASH: str = DUMMY_HASH

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir / "_auth"
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._companies_file = self._base_dir / "companies.json"
        self._users_file = self._base_dir / "users.json"

        # JWT_SECRET_KEY enforcement (Codex W8) — delegated to utility
        self._secret_key = get_secret_key()

        # In-memory cache
        self._companies: Dict[str, Company] = {}
        self._users: Dict[str, Dict[str, Any]] = {}  # keyed by user.id

        # Reentrant mutex: serialises all check-then-mutate-then-save operations.
        # RLock (not Lock) because register_user calls create_user internally.
        # Read-only operations do not acquire this lock.
        self._lock = threading.RLock()

        self._load()

    # ── Persistence ───────────────────────────────────────────

    def _load(self) -> None:
        """Load companies and users from disk."""
        if self._companies_file.exists():
            raw = json.loads(self._companies_file.read_text())
            for c in raw:
                company = Company.model_validate(c)
                self._companies[company.slug] = company

        if self._users_file.exists():
            raw = json.loads(self._users_file.read_text())
            for u in raw:
                self._users[u["id"]] = u

    def _save_companies(self) -> None:
        """Persist companies to disk."""
        data = [c.model_dump(mode="json") for c in self._companies.values()]
        tmp = self._companies_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str))
        tmp.replace(self._companies_file)

    def _save_users(self) -> None:
        """Persist users to disk."""
        data = list(self._users.values())
        tmp = self._users_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str))
        tmp.replace(self._users_file)

    # ── Company operations ────────────────────────────────────

    def get_company_by_slug(self, slug: str) -> Optional[Company]:
        return self._companies.get(slug)

    def get_company_by_domain(self, raw_domain: str) -> Optional[Company]:
        """Find a company by its normalized root domain."""
        root, _ = normalize_domain(raw_domain)
        for company in self._companies.values():
            if company.domain == root:
                return company
        return None

    def list_companies(self) -> List[Company]:
        return list(self._companies.values())

    def create_company(
        self,
        slug: str,
        name: str,
        domain: str,
        products: Optional[List[Product]] = None,
        additional_domains: Optional[List[str]] = None,
    ) -> Company:
        with self._lock:
            if slug in self._companies:
                raise ValueError(f"Company with slug '{slug}' already exists")
            company = Company(
                slug=slug,
                name=name,
                domain=domain,
                products=products or [],
                additional_domains=additional_domains or [],
            )
            self._companies[slug] = company
            self._save_companies()
        return company

    def update_company(self, slug: str, **kwargs: Any) -> Company:
        with self._lock:
            company = self._companies.get(slug)
            if not company:
                raise ValueError(f"Company '{slug}' not found")
            for k, v in kwargs.items():
                if k in _COMPANY_MUTABLE_FIELDS:
                    setattr(company, k, v)
            company.updated_at = _utcnow()
            self._companies[slug] = company
            self._save_companies()
        return company

    # ── Product operations ────────────────────────────────────

    def add_product(self, company_slug: str, product: "Product") -> "Product":
        """Add a product to a company."""
        with self._lock:
            company = self._companies.get(company_slug)
            if not company:
                raise ValueError(f"Company '{company_slug}' not found")
            for p in company.products:
                if p.slug == product.slug:
                    raise ValueError(
                        f"Product with slug '{product.slug}' already exists in company '{company_slug}'"
                    )
            company.products.append(product)
            company.updated_at = _utcnow()
            self._save_companies()
        return product

    def get_product(self, company_slug: str, product_slug: str) -> Optional["Product"]:
        """Get a product by company slug and product slug."""
        company = self._companies.get(company_slug)
        if not company:
            return None
        for p in company.products:
            if p.slug == product_slug:
                return p
        return None

    def update_product(self, company_slug: str, product_slug: str, **kwargs: Any) -> "Product":
        """Update a product's fields (name, domain, description only)."""
        with self._lock:
            company = self._companies.get(company_slug)
            if not company:
                raise ValueError(f"Company '{company_slug}' not found")
            for i, p in enumerate(company.products):
                if p.slug == product_slug:
                    for k, v in kwargs.items():
                        if k in _PRODUCT_MUTABLE_FIELDS:
                            setattr(p, k, v)
                    p.updated_at = _utcnow()
                    company.products[i] = p
                    company.updated_at = _utcnow()
                    self._save_companies()
                    return p
        raise ValueError(f"Product '{product_slug}' not found in company '{company_slug}'")

    def remove_product(self, company_slug: str, product_slug: str) -> bool:
        """Remove a product from a company. Returns True if removed."""
        with self._lock:
            company = self._companies.get(company_slug)
            if not company:
                return False
            original_len = len(company.products)
            company.products = [p for p in company.products if p.slug != product_slug]
            if len(company.products) < original_len:
                company.updated_at = _utcnow()
                self._save_companies()
                return True
        return False

    # ── User operations ───────────────────────────────────────

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        for u in self._users.values():
            if u["email"] == email:
                return u
        return None

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._users.get(user_id)

    def list_users_for_company(self, company_id: str) -> List[UserProfile]:
        return [
            UserProfile.model_validate(
                {k: v for k, v in u.items() if k != "password_hash"}
            )
            for u in self._users.values()
            if u["company_id"] == company_id
        ]

    def create_user(
        self,
        company_id: str,
        email: str,
        password: str,
        first_name: str = "",
        last_name: str = "",
        role: str = "member",
    ) -> UserProfile:
        with self._lock:
            if self.get_user_by_email(email):
                raise ValueError(f"User with email '{email}' already exists")

            profile = UserProfile(
                company_id=company_id,
                email=email,
                first_name=first_name,
                last_name=last_name,
                role=role,
            )
            user_data = profile.model_dump(mode="json")
            user_data["password_hash"] = self._hash_password(password)
            self._users[profile.id] = user_data
            self._save_users()
        return profile

    def update_user(self, user_id: str, requesting_user_id: Optional[str] = None, **kwargs: Any) -> UserProfile:
        """Update mutable fields on a user profile.

        Only fields in ``_USER_MUTABLE_FIELDS`` are applied. Immutable fields
        (id, company_id, email, created_at) are silently ignored.

        Guards:
        - Cannot deactivate yourself (``requesting_user_id == user_id``
          and ``is_active=False``).
        - Cannot demote the last superuser of a company.
        """
        with self._lock:
            user_data = self._users.get(user_id)
            if not user_data:
                raise ValueError(f"User '{user_id}' not found")

            # Guard: cannot deactivate self
            if (
                requesting_user_id
                and requesting_user_id == user_id
                and kwargs.get("is_active") is False
            ):
                raise ValueError("Cannot deactivate your own account")

            # Guard: cannot demote last superuser
            current_role = user_data.get("role", "member")
            new_role = kwargs.get("role")
            if current_role == "superuser" and new_role and new_role != "superuser":
                company_id = user_data["company_id"]
                superuser_count = sum(
                    1
                    for u in self._users.values()
                    if u["company_id"] == company_id
                    and u["role"] == "superuser"
                    and u.get("is_active", True)
                )
                if superuser_count <= 1:
                    raise ValueError("Cannot demote the last superuser of this company")

            for k, v in kwargs.items():
                if k in _USER_MUTABLE_FIELDS:
                    user_data[k] = v
            user_data["updated_at"] = _utcnow().isoformat()
            self._users[user_id] = user_data
            self._save_users()

        return UserProfile.model_validate(
            {k: v for k, v in user_data.items() if k != "password_hash"}
        )

    # ── Registration (company dedup) ───────────────────────────

    def register_user(
        self,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
        company_name: str,
        company_domain: str,
    ) -> Tuple[UserProfile, Company]:
        """Register a new user — always creates an isolated company (Codex C1).

        - Normalizes the domain (strips www, extracts root)
        - If a company with the same root domain already exists, raises
          ``ValueError("domain_taken")`` — joining requires an invite
        - Otherwise creates a new company and the user becomes 'superuser'
        """
        with self._lock:
            if self.get_user_by_email(email):
                raise ValueError(f"User with email '{email}' already exists")

            root_domain, subdomain = normalize_domain(company_domain)

            # Block domain auto-join — registration always creates a new company
            existing = self.get_company_by_domain(root_domain)
            if existing:
                raise ValueError("domain_taken")

            # Create new company
            slug = _derive_slug(company_name)
            base_slug = slug
            counter = 1
            while slug in self._companies:
                slug = f"{base_slug}-{counter}"
                counter += 1

            additional = [subdomain] if subdomain else []
            company = Company(
                slug=slug,
                name=company_name,
                domain=root_domain,
                additional_domains=additional,
            )
            self._companies[slug] = company
            self._save_companies()

            # Create the user as superuser (first user of the new company)
            user = self.create_user(
                company_id=company.id,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=password,
                role="superuser",
            )

        return user, company

    # ── Invite flow (simple codes) ─────────────────────────────

    def create_invite(
        self, company_slug: str, role: str = "member"
    ) -> str:
        """Create a simple invite code for joining an existing company.

        Returns a 16-character hex invite code. The code, company slug,
        and target role are stored in an in-memory dict. For v0, invite
        codes are not persisted to disk (lost on restart).
        """
        if not hasattr(self, "_invites"):
            self._invites: Dict[str, Dict[str, str]] = {}
        code = secrets.token_hex(8)
        self._invites[code] = {"company_slug": company_slug, "role": role}
        return code

    def redeem_invite(
        self,
        invite_code: str,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
    ) -> Tuple[UserProfile, Company]:
        """Redeem an invite code to join an existing company.

        Raises ``ValueError`` if the invite is invalid, already used,
        or the email is already registered.

        C5 fix: entire operation (lookup + create + delete) runs inside
        the lock to prevent double-use race condition.
        """
        with self._lock:
            invites = getattr(self, "_invites", {})
            invite = invites.get(invite_code)
            if not invite:
                raise ValueError("Invalid or expired invite code")

            company = self.get_company_by_slug(invite["company_slug"])
            if not company:
                raise ValueError("Company no longer exists")

            if self.get_user_by_email(email):
                raise ValueError(f"User with email '{email}' already exists")

            user = self.create_user(
                company_id=company.id,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=password,
                role=invite["role"],
            )

            # Remove used invite (guaranteed to exist — we hold the lock)
            del self._invites[invite_code]

        return user, company

    # ── Pipeline Defaults (per-company) ─────────────────────────

    def _settings_dir(self) -> Path:
        """Return the settings directory, creating it if needed."""
        d = self._base_dir / "settings"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get_pipeline_defaults(self, company_slug: str) -> CompanyPipelineDefaults:
        """Load per-company pipeline defaults. Returns empty defaults if not set."""
        path = self._settings_dir() / f"{company_slug}.json"
        if not path.exists():
            return CompanyPipelineDefaults()
        try:
            data = json.loads(path.read_text())
            return CompanyPipelineDefaults.model_validate(data)
        except Exception:
            return CompanyPipelineDefaults()

    def update_pipeline_defaults(
        self, company_slug: str, **kwargs: Any
    ) -> CompanyPipelineDefaults:
        """Update per-company pipeline defaults. Only non-None values are applied."""
        with self._lock:
            current = self.get_pipeline_defaults(company_slug)
            for k, v in kwargs.items():
                if hasattr(current, k) and v is not None:
                    setattr(current, k, v)
            current.updated_at = _utcnow()
            path = self._settings_dir() / f"{company_slug}.json"
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(current.model_dump(mode="json"), indent=2, default=str))
            tmp.replace(path)
        return current

    # ── Password hashing (delegates to core.auth.utils.passwords) ──

    @staticmethod
    def _hash_password(password: str) -> str:
        return hash_password(password)

    @staticmethod
    def verify_password(password: str, stored_hash: str) -> bool:
        return verify_password(password, stored_hash)

    # ── JWT tokens (delegates to core.auth.utils.tokens) ─────

    def create_access_token(
        self, user_id: str, company_slug: str, expires_hours: int = 24
    ) -> str:
        return _create_access_token(
            self._secret_key, user_id, company_slug, expires_hours
        )

    def create_stream_token(
        self, user_id: str, company_slug: str, expires_minutes: int = 5
    ) -> str:
        return _create_stream_token(
            self._secret_key, user_id, company_slug, expires_minutes
        )

    def verify_token(self, token: str) -> Optional[Dict[str, str]]:
        return _verify_token(self._secret_key, token)
