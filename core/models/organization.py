"""Organization models: Company, Product, UserProfile.

These models define the multi-tenant data structure:
  Company (1) → Products (many)
  Company (1) → Users/Employees (many)

Pipelines can run at company-level or product-level scope.
For now, these are persisted as JSON files. They will migrate
to Supabase tables when the database layer is added.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid4())


class Product(BaseModel):
    """A product within a company. Pipelines can run at product level."""

    id: str = Field(default_factory=_uuid)
    company_id: str
    slug: str
    name: str
    domain: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Company(BaseModel):
    """Company entity. The slug scopes all artifact directories."""

    id: str = Field(default_factory=_uuid)
    slug: str
    name: str
    domain: str
    additional_domains: List[str] = Field(default_factory=list)
    industry: Optional[str] = None
    products: List[Product] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class UserProfile(BaseModel):
    """Employee/user who belongs to a company.

    Password hash is NOT stored here — it lives in the auth store
    (and will move to Supabase Auth later).
    """

    id: str = Field(default_factory=_uuid)
    company_id: str
    email: str
    first_name: str = ""
    last_name: str = ""
    role: Literal["superuser", "member", "viewer"] = "member"
    is_active: bool = True
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @property
    def full_name(self) -> str:
        """Concatenated first + last name."""
        return f"{self.first_name} {self.last_name}".strip()


class PipelineScope(BaseModel):
    """Tracks whether a pipeline run is company-level or product-level."""

    scope: Literal["company", "product"] = "company"
    company_slug: str
    product_slug: Optional[str] = None


class CompanyPipelineDefaults(BaseModel):
    """Per-company pipeline default overrides.

    All fields are optional — ``None`` means "use global default from settings.py".
    Only non-None values override the global defaults at pipeline invocation time.
    """

    # Gap analysis
    max_crawl_pages: Optional[int] = None
    max_crawl_depth: Optional[int] = None
    max_queries: Optional[int] = None
    platforms: Optional[List[str]] = None

    # Research
    max_personas: Optional[int] = None
    auto_approve_research: bool = False

    # Content
    max_briefs: Optional[int] = None
    max_revision_cycles: Optional[int] = None
    auto_approve_content: bool = False

    updated_at: Optional[datetime] = None
