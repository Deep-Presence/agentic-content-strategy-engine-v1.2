"""DbAuthService — database-backed auth service.

Implements ``AuthServiceProtocol`` using SQLAlchemy repos.
Ports all business logic from the JSON-backed AuthStore:
- Registration with domain dedup + slug collision avoidance
- Invite create/redeem with TTL
- User update guards (self-deactivation, last-superuser)
- ORM ↔ Pydantic conversion

Session lifecycle (commit/rollback) is owned by the DI layer,
not this service.
"""
from __future__ import annotations

import secrets
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.auth.utils.domain import (
    COMPANY_MUTABLE_FIELDS,
    PRODUCT_MUTABLE_FIELDS,
    USER_MUTABLE_FIELDS,
    derive_slug,
    normalize_domain,
)
from core.auth.utils.passwords import hash_password
from core.auth.utils.tokens import (
    create_access_token as _create_access_token,
    create_stream_token as _create_stream_token,
    verify_token as _verify_token,
)
from core.config.settings import settings
from core.db.enums import UserRole
from core.db.models.organization import (
    CompanyModel,
    InviteModel,
    PipelineDefaultsModel,
    ProductModel,
    UserModel,
)
from core.db.repositories.auth_repo import AuthRepository
from core.db.repositories.company_repo import CompanyRepository
from core.db.repositories.invite_repo import InviteRepository
from core.db.repositories.pipeline_defaults_repo import PipelineDefaultsRepository
from core.db.repositories.product_repo import ProductRepository
from core.models.organization import Company, CompanyPipelineDefaults, Product, UserProfile


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DbAuthService:
    """Database-backed auth service implementing AuthServiceProtocol."""

    def __init__(
        self,
        company_repo: CompanyRepository,
        auth_repo: AuthRepository,
        invite_repo: InviteRepository,
        product_repo: ProductRepository,
        defaults_repo: PipelineDefaultsRepository,
        secret_key: str,
    ) -> None:
        self._company_repo = company_repo
        self._auth_repo = auth_repo
        self._invite_repo = invite_repo
        self._product_repo = product_repo
        self._defaults_repo = defaults_repo
        self._secret_key = secret_key

    # ── ORM → Pydantic conversion ─────────────────────────────

    @staticmethod
    def _orm_to_company(model: CompanyModel) -> Company:
        return Company(
            id=str(model.id),
            slug=model.slug,
            name=model.name,
            domain=model.domain,
            additional_domains=model.additional_domains or [],
            industry=model.industry,
            products=[
                Product(
                    id=str(p.id),
                    company_id=str(p.company_id),
                    slug=p.slug,
                    name=p.name,
                    domain=p.domain,
                    description=p.description,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                )
                for p in (model.products or [])
            ],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _orm_to_user_dict(model: UserModel) -> Dict[str, Any]:
        """Convert ORM user to dict (includes password_hash — matches AuthStore)."""
        return {
            "id": str(model.id),
            "company_id": str(model.company_id),
            "email": model.email,
            "password_hash": model.password_hash,
            "first_name": model.first_name,
            "last_name": model.last_name,
            "role": model.role.value if isinstance(model.role, UserRole) else model.role,
            "is_active": model.is_active,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
        }

    @staticmethod
    def _orm_to_user_profile(model: UserModel) -> UserProfile:
        """Convert ORM user to UserProfile (excludes password_hash)."""
        return UserProfile(
            id=str(model.id),
            company_id=str(model.company_id),
            email=model.email,
            first_name=model.first_name,
            last_name=model.last_name,
            role=model.role.value if isinstance(model.role, UserRole) else model.role,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    # ── Company ops ────────────────────────────────────────────

    async def get_company_by_slug(self, slug: str) -> Optional[Company]:
        model = await self._company_repo.get_by_slug(slug)
        return self._orm_to_company(model) if model else None

    async def get_company_by_id(self, company_id: str) -> Optional[Company]:
        model = await self._company_repo.get_by_id(company_id)
        return self._orm_to_company(model) if model else None

    async def get_company_by_domain(self, raw_domain: str) -> Optional[Company]:
        root, _ = normalize_domain(raw_domain)
        model = await self._company_repo.get_by_domain(root)
        return self._orm_to_company(model) if model else None

    async def list_companies(self) -> List[Company]:
        models = await self._company_repo.list_active()
        return [self._orm_to_company(m) for m in models]

    async def create_company(
        self,
        slug: str,
        name: str,
        domain: str,
        products: Optional[List[Product]] = None,
        additional_domains: Optional[List[str]] = None,
    ) -> Company:
        if await self._company_repo.slug_exists(slug):
            raise ValueError(f"Company with slug '{slug}' already exists")
        model = await self._company_repo.create(
            slug=slug,
            name=name,
            domain=domain,
            additional_domains=additional_domains or [],
        )
        # Eagerly load products relationship to avoid lazy-load in async context
        await self._company_repo._session.refresh(model, ["products"])
        company = self._orm_to_company(model)
        # Create products if provided
        if products:
            for p in products:
                await self._product_repo.create(
                    company_id=model.id,
                    slug=p.slug,
                    name=p.name,
                    domain=p.domain,
                    description=p.description,
                )
        return company

    async def update_company(self, slug: str, **kwargs: Any) -> Company:
        model = await self._company_repo.get_by_slug(slug)
        if not model:
            raise ValueError(f"Company '{slug}' not found")
        filtered = {k: v for k, v in kwargs.items() if k in COMPANY_MUTABLE_FIELDS}
        if filtered:
            for k, v in filtered.items():
                setattr(model, k, v)
            model.updated_at = _utcnow()  # type: ignore[assignment]
            await self._company_repo._session.flush()
        return self._orm_to_company(model)

    # ── Product ops ────────────────────────────────────────────

    async def get_product(
        self, company_slug: str, product_slug: str
    ) -> Optional[Product]:
        company = await self._company_repo.get_by_slug(company_slug)
        if not company:
            return None
        model = await self._product_repo.get_by_slugs(company.id, product_slug)
        if not model:
            return None
        return Product(
            id=str(model.id),
            company_id=str(model.company_id),
            slug=model.slug,
            name=model.name,
            domain=model.domain,
            description=model.description,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def add_product(
        self, company_slug: str, product: Product
    ) -> Product:
        company = await self._company_repo.get_by_slug(company_slug)
        if not company:
            raise ValueError(f"Company '{company_slug}' not found")
        existing = await self._product_repo.get_by_slugs(company.id, product.slug)
        if existing:
            raise ValueError(
                f"Product with slug '{product.slug}' already exists in company '{company_slug}'"
            )
        model = await self._product_repo.create(
            company_id=company.id,
            slug=product.slug,
            name=product.name,
            domain=product.domain,
            description=product.description,
        )
        return Product(
            id=str(model.id),
            company_id=str(model.company_id),
            slug=model.slug,
            name=model.name,
            domain=model.domain,
            description=model.description,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def update_product(
        self, company_slug: str, product_slug: str, **kwargs: Any
    ) -> Product:
        company = await self._company_repo.get_by_slug(company_slug)
        if not company:
            raise ValueError(f"Company '{company_slug}' not found")
        model = await self._product_repo.get_by_slugs(company.id, product_slug)
        if not model:
            raise ValueError(
                f"Product '{product_slug}' not found in company '{company_slug}'"
            )
        filtered = {k: v for k, v in kwargs.items() if k in PRODUCT_MUTABLE_FIELDS}
        if filtered:
            for k, v in filtered.items():
                setattr(model, k, v)
            model.updated_at = _utcnow()  # type: ignore[assignment]
            await self._product_repo._session.flush()
        return Product(
            id=str(model.id),
            company_id=str(model.company_id),
            slug=model.slug,
            name=model.name,
            domain=model.domain,
            description=model.description,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def remove_product(
        self, company_slug: str, product_slug: str
    ) -> bool:
        company = await self._company_repo.get_by_slug(company_slug)
        if not company:
            return False
        model = await self._product_repo.get_by_slugs(company.id, product_slug)
        if not model:
            return False
        return await self._product_repo.delete(model.id)

    # ── User ops ───────────────────────────────────────────────

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        model = await self._auth_repo.get_by_email(email)
        return self._orm_to_user_dict(model) if model else None

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        model = await self._auth_repo.get_by_id(user_id)
        return self._orm_to_user_dict(model) if model else None

    async def list_users_for_company(self, company_id: str) -> List[UserProfile]:
        uid = _uuid.UUID(company_id)
        models = await self._auth_repo.list_by_company(uid)
        return [self._orm_to_user_profile(m) for m in models]

    async def create_user(
        self,
        company_id: str,
        email: str,
        password: str,
        first_name: str = "",
        last_name: str = "",
        role: str = "member",
    ) -> UserProfile:
        existing = await self._auth_repo.get_by_email(email)
        if existing:
            raise ValueError(f"User with email '{email}' already exists")
        model = await self._auth_repo.create(
            company_id=_uuid.UUID(company_id),
            email=email,
            password_hash=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            role=UserRole(role),
            is_active=True,
        )
        return self._orm_to_user_profile(model)

    async def update_user(
        self, user_id: str, requesting_user_id: Optional[str] = None, **kwargs: Any
    ) -> UserProfile:
        model = await self._auth_repo.get_by_id(user_id)
        if not model:
            raise ValueError(f"User '{user_id}' not found")

        # Guard: cannot deactivate self
        if (
            requesting_user_id
            and requesting_user_id == user_id
            and kwargs.get("is_active") is False
        ):
            raise ValueError("Cannot deactivate your own account")

        # Guard: cannot demote last superuser
        current_role = model.role.value if isinstance(model.role, UserRole) else model.role
        new_role = kwargs.get("role")
        if current_role == "superuser" and new_role and new_role != "superuser":
            superuser_count = await self._auth_repo.count_superusers(model.company_id)
            if superuser_count <= 1:
                raise ValueError("Cannot demote the last superuser of this company")

        # Apply mutable fields
        for k, v in kwargs.items():
            if k in USER_MUTABLE_FIELDS:
                if k == "role":
                    setattr(model, k, UserRole(v))
                else:
                    setattr(model, k, v)
        model.updated_at = _utcnow()  # type: ignore[assignment]
        await self._auth_repo._session.flush()

        return self._orm_to_user_profile(model)

    # ── Registration (company dedup) ───────────────────────────

    async def register_user(
        self,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
        company_name: str,
        company_domain: str,
    ) -> Tuple[UserProfile, Company]:
        # Check email uniqueness
        if await self._auth_repo.get_by_email(email):
            raise ValueError(f"User with email '{email}' already exists")

        root_domain, subdomain = normalize_domain(company_domain)

        # Block domain auto-join — registration always creates a new company
        if await self._company_repo.get_by_domain(root_domain):
            raise ValueError("domain_taken")

        # Slug collision loop
        slug = derive_slug(company_name)
        base_slug = slug
        counter = 1
        while await self._company_repo.slug_exists(slug):
            slug = f"{base_slug}-{counter}"
            counter += 1

        additional = [subdomain] if subdomain else []
        company_model = await self._company_repo.create(
            slug=slug,
            name=company_name,
            domain=root_domain,
            additional_domains=additional,
        )

        # Create the user as superuser (first user of the new company)
        user_model = await self._auth_repo.create(
            company_id=company_model.id,
            email=email,
            password_hash=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            role=UserRole.superuser,
            is_active=True,
        )

        # Eagerly load products relationship to avoid lazy-load in async context
        await self._company_repo._session.refresh(company_model, ["products"])

        return self._orm_to_user_profile(user_model), self._orm_to_company(company_model)

    # ── Invite flow ────────────────────────────────────────────

    async def create_invite(
        self, company_slug: str, role: str = "member"
    ) -> str:
        company = await self._company_repo.get_by_slug(company_slug)
        if not company:
            raise ValueError(f"Company '{company_slug}' not found")
        code = secrets.token_hex(8)
        ttl_days = settings.invite_ttl_days
        await self._invite_repo.create(
            company_id=company.id,
            code=code,
            role=UserRole(role),
            expires_at=_utcnow() + timedelta(days=ttl_days),
        )
        return code

    async def redeem_invite(
        self,
        invite_code: str,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
    ) -> Tuple[UserProfile, Company]:
        invite = await self._invite_repo.get_by_code(invite_code)
        if not invite:
            raise ValueError("Invalid or expired invite code")

        company = await self._company_repo.get_by_id(invite.company_id)
        if not company:
            raise ValueError("Company no longer exists")

        if await self._auth_repo.get_by_email(email):
            raise ValueError(f"User with email '{email}' already exists")

        user_model = await self._auth_repo.create(
            company_id=company.id,
            email=email,
            password_hash=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            role=invite.role,
            is_active=True,
        )

        await self._invite_repo.mark_redeemed(invite.id, user_model.id)

        return self._orm_to_user_profile(user_model), self._orm_to_company(company)

    # ── Pipeline defaults ──────────────────────────────────────

    async def get_pipeline_defaults(
        self, company_slug: str
    ) -> CompanyPipelineDefaults:
        company = await self._company_repo.get_by_slug(company_slug)
        if not company:
            return CompanyPipelineDefaults()
        model = await self._defaults_repo.get_by_company(company.id)
        if not model or not model.defaults_json:
            return CompanyPipelineDefaults()
        return CompanyPipelineDefaults.model_validate(model.defaults_json)

    async def update_pipeline_defaults(
        self, company_slug: str, **kwargs: Any
    ) -> CompanyPipelineDefaults:
        company = await self._company_repo.get_by_slug(company_slug)
        if not company:
            raise ValueError(f"Company '{company_slug}' not found")
        current = await self.get_pipeline_defaults(company_slug)
        for k, v in kwargs.items():
            if hasattr(current, k) and v is not None:
                setattr(current, k, v)
        current.updated_at = _utcnow()
        data = current.model_dump(mode="json")
        await self._defaults_repo.upsert(company.id, data)
        return current

    # ── Tokens (sync — pure computation) ───────────────────────

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
