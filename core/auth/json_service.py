"""JsonAuthService — async wrapper around the JSON-file AuthStore.

Implements ``AuthServiceProtocol`` so routers can program to the
protocol.  Read ops call the sync store directly (in-memory dict
lookups, near-instant).  Write ops that touch disk are delegated
via ``asyncio.to_thread()`` to avoid blocking the event loop.

This is the *default* implementation when ``DATABASE_URL`` is not set.
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from core.models.organization import Company, CompanyPipelineDefaults, Product, UserProfile

if TYPE_CHECKING:
    from api.auth.store import AuthStore


class JsonAuthService:
    """Async adapter around the sync ``AuthStore``."""

    def __init__(self, store: AuthStore) -> None:
        self._store = store

    # ── Company ops (read = sync, write = threaded) ────────────

    async def get_company_by_slug(self, slug: str) -> Optional[Company]:
        return self._store.get_company_by_slug(slug)

    async def get_company_by_id(self, company_id: str) -> Optional[Company]:
        for company in self._store._companies.values():
            if company.id == company_id:
                return company
        return None

    async def get_company_by_domain(self, raw_domain: str) -> Optional[Company]:
        return self._store.get_company_by_domain(raw_domain)

    async def list_companies(self) -> List[Company]:
        return self._store.list_companies()

    async def create_company(
        self,
        slug: str,
        name: str,
        domain: str,
        products: Optional[List[Product]] = None,
        additional_domains: Optional[List[str]] = None,
    ) -> Company:
        return await asyncio.to_thread(
            self._store.create_company, slug, name, domain, products, additional_domains
        )

    async def update_company(self, slug: str, **kwargs: Any) -> Company:
        return await asyncio.to_thread(self._store.update_company, slug, **kwargs)

    # ── Product ops ────────────────────────────────────────────

    async def get_product(
        self, company_slug: str, product_slug: str
    ) -> Optional[Product]:
        return self._store.get_product(company_slug, product_slug)

    async def add_product(
        self, company_slug: str, product: Product
    ) -> Product:
        return await asyncio.to_thread(self._store.add_product, company_slug, product)

    async def update_product(
        self, company_slug: str, product_slug: str, **kwargs: Any
    ) -> Product:
        return await asyncio.to_thread(
            self._store.update_product, company_slug, product_slug, **kwargs
        )

    async def remove_product(
        self, company_slug: str, product_slug: str
    ) -> bool:
        return await asyncio.to_thread(
            self._store.remove_product, company_slug, product_slug
        )

    # ── User ops ───────────────────────────────────────────────

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        return self._store.get_user_by_email(email)

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._store.get_user_by_id(user_id)

    async def list_users_for_company(self, company_id: str) -> List[UserProfile]:
        return self._store.list_users_for_company(company_id)

    async def create_user(
        self,
        company_id: str,
        email: str,
        password: str,
        first_name: str = "",
        last_name: str = "",
        role: str = "member",
    ) -> UserProfile:
        return await asyncio.to_thread(
            self._store.create_user, company_id, email, password,
            first_name, last_name, role,
        )

    async def update_user(
        self, user_id: str, requesting_user_id: Optional[str] = None, **kwargs: Any
    ) -> UserProfile:
        return await asyncio.to_thread(
            self._store.update_user, user_id, requesting_user_id, **kwargs
        )

    # ── Registration + invite ──────────────────────────────────

    async def register_user(
        self,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
        company_name: str,
        company_domain: str,
    ) -> Tuple[UserProfile, Company]:
        return await asyncio.to_thread(
            self._store.register_user,
            first_name, last_name, email, password, company_name, company_domain,
        )

    async def create_invite(
        self, company_slug: str, role: str = "member"
    ) -> str:
        return await asyncio.to_thread(self._store.create_invite, company_slug, role)

    async def redeem_invite(
        self,
        invite_code: str,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
    ) -> Tuple[UserProfile, Company]:
        return await asyncio.to_thread(
            self._store.redeem_invite,
            invite_code, first_name, last_name, email, password,
        )

    # ── Pipeline defaults ──────────────────────────────────────

    async def get_pipeline_defaults(
        self, company_slug: str
    ) -> CompanyPipelineDefaults:
        return self._store.get_pipeline_defaults(company_slug)

    async def update_pipeline_defaults(
        self, company_slug: str, **kwargs: Any
    ) -> CompanyPipelineDefaults:
        return await asyncio.to_thread(
            self._store.update_pipeline_defaults, company_slug, **kwargs
        )

    # ── Tokens (sync — pure computation, no I/O) ──────────────

    def create_access_token(
        self, user_id: str, company_slug: str, expires_hours: int = 24
    ) -> str:
        return self._store.create_access_token(user_id, company_slug, expires_hours)

    def create_stream_token(
        self, user_id: str, company_slug: str, expires_minutes: int = 5
    ) -> str:
        return self._store.create_stream_token(user_id, company_slug, expires_minutes)

    def verify_token(self, token: str) -> Optional[Dict[str, str]]:
        return self._store.verify_token(token)
