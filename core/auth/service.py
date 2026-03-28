"""AuthServiceProtocol — async interface for auth operations.

``DbAuthService`` (uses DB repos) is the sole production implementation.
Router code programs to the protocol. DATABASE_URL is required at startup.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable

from core.models.organization import Company, CompanyPipelineDefaults, Product, UserProfile


@runtime_checkable
class AuthServiceProtocol(Protocol):
    """Async auth service interface."""

    # ── Company ops ────────────────────────────────────────────

    async def get_company_by_slug(self, slug: str) -> Optional[Company]: ...

    async def get_company_by_id(self, company_id: str) -> Optional[Company]: ...

    async def get_company_by_domain(self, raw_domain: str) -> Optional[Company]: ...

    async def list_companies(self) -> List[Company]: ...

    async def create_company(
        self,
        slug: str,
        name: str,
        domain: str,
        products: Optional[List[Product]] = None,
        additional_domains: Optional[List[str]] = None,
    ) -> Company: ...

    async def update_company(self, slug: str, **kwargs: Any) -> Company: ...

    # ── Product ops ────────────────────────────────────────────

    async def get_product(
        self, company_slug: str, product_slug: str
    ) -> Optional[Product]: ...

    async def add_product(
        self, company_slug: str, product: Product
    ) -> Product: ...

    async def update_product(
        self, company_slug: str, product_slug: str, **kwargs: Any
    ) -> Product: ...

    async def remove_product(
        self, company_slug: str, product_slug: str
    ) -> bool: ...

    # ── User ops ───────────────────────────────────────────────

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]: ...

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]: ...

    async def list_users_for_company(self, company_id: str) -> List[UserProfile]: ...

    async def create_user(
        self,
        company_id: str,
        email: str,
        password: str,
        first_name: str = "",
        last_name: str = "",
        role: str = "member",
    ) -> UserProfile: ...

    async def update_user(
        self, user_id: str, requesting_user_id: Optional[str] = None, **kwargs: Any
    ) -> UserProfile: ...

    # ── Registration + invite ──────────────────────────────────

    async def register_user(
        self,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
        company_name: str,
        company_domain: str,
    ) -> Tuple[UserProfile, Company]: ...

    async def create_invite(
        self, company_slug: str, role: str = "member"
    ) -> str: ...

    async def redeem_invite(
        self,
        invite_code: str,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
    ) -> Tuple[UserProfile, Company]: ...

    # ── Pipeline defaults ──────────────────────────────────────

    async def get_pipeline_defaults(
        self, company_slug: str
    ) -> CompanyPipelineDefaults: ...

    async def update_pipeline_defaults(
        self, company_slug: str, **kwargs: Any
    ) -> CompanyPipelineDefaults: ...

    # ── Tokens (sync — pure computation) ───────────────────────

    def create_access_token(
        self, user_id: str, company_slug: str, expires_hours: int = 24
    ) -> str: ...

    def create_stream_token(
        self, user_id: str, company_slug: str, expires_minutes: int = 5
    ) -> str: ...

    def verify_token(self, token: str) -> Optional[Dict[str, str]]: ...
