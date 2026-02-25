"""Auth request/response models.

These are API-layer models for authentication endpoints.
The core business models (Company, Product, UserProfile) live
in core/models/organization.py.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


# ── Request models ────────────────────────────────────────────


class LoginRequest(BaseModel):
    """Email + password login."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RegisterRequest(BaseModel):
    """Register a new user with company deduplication.

    Required: first_name, last_name, email, password, company_name, company_domain.
    Company dedup: if company_domain matches an existing company's root domain,
    the user joins that company as 'member'. Otherwise, a new company is created
    and the user becomes 'superuser'.
    """

    first_name: str
    last_name: str
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    company_name: str
    company_domain: str


# ── Response models ───────────────────────────────────────────


class UserResponse(BaseModel):
    """Authenticated user info."""

    id: str
    email: str
    first_name: str
    last_name: str
    role: str
    company_id: str
    is_active: bool


class CompanyResponse(BaseModel):
    """Company info included in auth responses."""

    id: str
    slug: str
    name: str
    domain: str


class LoginResponse(BaseModel):
    """Returned after successful login."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    company: CompanyResponse


class MeResponse(BaseModel):
    """Returned from GET /api/v1/auth/me."""

    user: UserResponse
    company: CompanyResponse
