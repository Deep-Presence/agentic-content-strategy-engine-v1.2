"""JSON-file backed auth store for companies and users.

This is a v0 implementation that persists to local JSON files.
It will be replaced by Supabase Auth + DB tables later.

Files:
  artifacts/_auth/companies.json — List[Company]
  artifacts/_auth/users.json     — List[{...UserProfile, password_hash}]
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from core.models.organization import Company, Product, UserProfile


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Known multi-part TLDs where the second-level domain is part of the TLD.
_MULTI_PART_TLDS = frozenset({
    "co.uk", "co.jp", "co.in", "co.kr", "co.nz", "co.za", "co.id",
    "com.au", "com.br", "com.cn", "com.mx", "com.tw", "com.sg",
    "org.uk", "net.au", "ac.uk", "gov.uk",
})


def normalize_domain(raw: str) -> Tuple[str, Optional[str]]:
    """Normalize a domain to its root form.

    Returns (root_domain, subdomain_or_none).

    - Strips protocol (http/https), path, trailing slash
    - Strips www (not considered a meaningful subdomain)
    - Extracts root domain vs subdomain
    - Handles multi-part TLDs (.co.uk, .com.au, etc.)
    - Returns lowercase

    Examples:
        "ramp.com"           → ("ramp.com", None)
        "www.ramp.com"       → ("ramp.com", None)
        "app.ramp.com"       → ("ramp.com", "app.ramp.com")
        "https://ramp.com/p" → ("ramp.com", None)
        "app.example.co.uk"  → ("example.co.uk", "app.example.co.uk")
    """
    domain = raw.strip().lower()

    # Strip protocol
    if "://" in domain:
        domain = urlparse(domain).netloc or domain.split("://", 1)[1]

    # Strip path / trailing slash
    domain = domain.split("/")[0]
    # Strip port
    domain = domain.split(":")[0]

    # Strip www
    original = domain
    if domain.startswith("www."):
        domain = domain[4:]

    parts = domain.split(".")

    if len(parts) <= 2:
        # Already a root domain (e.g., ramp.com)
        return domain, None

    # Check for multi-part TLD
    possible_tld = ".".join(parts[-2:])
    if possible_tld in _MULTI_PART_TLDS:
        # e.g., app.example.co.uk → root = example.co.uk
        root = ".".join(parts[-3:])
        if len(parts) > 3:
            return root, domain
        return root, None
    else:
        # e.g., app.ramp.com → root = ramp.com
        root = ".".join(parts[-2:])
        subdomain = domain if domain != root else None
        # Don't return www-stripped as a subdomain
        if subdomain and original.startswith("www."):
            subdomain = None
        return root, subdomain


# Allowlists for mutable fields — prevents callers from overwriting immutable
# identity fields (id, created_at, slug) via **kwargs in update_* methods.
_COMPANY_MUTABLE_FIELDS: frozenset = frozenset({"name", "domain", "additional_domains"})
_PRODUCT_MUTABLE_FIELDS: frozenset = frozenset({"name", "domain", "description"})


def _derive_slug(name: str) -> str:
    """Derive a URL-safe slug from a company name."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


class AuthStore:
    """JSON-file backed store for companies and users."""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir / "_auth"
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._companies_file = self._base_dir / "companies.json"
        self._users_file = self._base_dir / "users.json"
        self._secret_key = os.environ.get("JWT_SECRET_KEY", secrets.token_hex(32))

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
        """Register a new user with automatic company deduplication.

        - Normalizes the domain (strips www, extracts root)
        - If a company with the same root domain exists, joins it as 'member'
        - If not, creates a new company and the user becomes 'superuser'
        - Subdomains are saved to company.additional_domains
        """
        with self._lock:
            if self.get_user_by_email(email):
                raise ValueError(f"User with email '{email}' already exists")

            root_domain, subdomain = normalize_domain(company_domain)

            # Try to find existing company by root domain
            existing = self.get_company_by_domain(root_domain)

            if existing:
                company = existing
                role = "member"
                # Save subdomain if it's new
                if subdomain and subdomain not in company.additional_domains:
                    company.additional_domains.append(subdomain)
                    company.updated_at = _utcnow()
                    self._save_companies()
            else:
                # Create new company
                slug = _derive_slug(company_name)
                # Handle slug collision
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
                role = "superuser"

            # Create the user (RLock allows re-entry from this context)
            user = self.create_user(
                company_id=company.id,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=password,
                role=role,
            )

        return user, company

    # ── Password hashing ──────────────────────────────────────

    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash password with salt using SHA-256.

        Simple implementation for v0. Will be replaced by Supabase Auth.
        """
        salt = secrets.token_hex(16)
        hashed = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), 100_000
        )
        return f"{salt}:{hashed.hex()}"

    @staticmethod
    def verify_password(password: str, stored_hash: str) -> bool:
        """Verify password against stored hash."""
        try:
            salt, hash_hex = stored_hash.split(":", 1)
            expected = hashlib.pbkdf2_hmac(
                "sha256", password.encode(), salt.encode(), 100_000
            )
            return hmac.compare_digest(expected.hex(), hash_hex)
        except (ValueError, AttributeError):
            return False

    # ── JWT token (simple implementation) ─────────────────────

    def create_access_token(
        self, user_id: str, company_slug: str, expires_hours: int = 24
    ) -> str:
        """Create a simple JWT-like token.

        v0: base64-encoded JSON with HMAC signature.
        Will be replaced by proper JWT or Supabase session tokens.
        """
        import base64

        payload = {
            "user_id": user_id,
            "company_slug": company_slug,
            "exp": (_utcnow() + timedelta(hours=expires_hours)).isoformat(),
        }
        payload_bytes = json.dumps(payload).encode()
        payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode()
        sig = hmac.new(
            self._secret_key.encode(), payload_bytes, hashlib.sha256
        ).hexdigest()
        return f"{payload_b64}.{sig}"

    def verify_token(self, token: str) -> Optional[Dict[str, str]]:
        """Verify and decode an access token.

        Returns payload dict or None if invalid/expired.
        """
        import base64

        try:
            parts = token.split(".", 1)
            if len(parts) != 2:
                return None
            payload_b64, sig = parts
            payload_bytes = base64.urlsafe_b64decode(payload_b64)
            expected_sig = hmac.new(
                self._secret_key.encode(), payload_bytes, hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(sig, expected_sig):
                return None
            payload = json.loads(payload_bytes)
            exp = datetime.fromisoformat(payload["exp"])
            if _utcnow() > exp:
                return None
            return payload
        except Exception:
            return None
