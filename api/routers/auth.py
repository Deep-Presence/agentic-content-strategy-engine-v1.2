"""Authentication endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from api.auth.models import (
    CompanyResponse,
    LoginRequest,
    LoginResponse,
    MeResponse,
    RegisterRequest,
    UserResponse,
)
from api.auth.store import AuthStore
from api.dependencies import get_auth_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", status_code=201)
def register(
    body: RegisterRequest,
    auth_store: AuthStore = Depends(get_auth_store),
) -> LoginResponse:
    """Register a new user.

    - If company_domain matches an existing company, user joins as 'member'.
    - If not, a new company is created and user becomes 'superuser'.
    - Subdomains are normalized to root domain; originals saved to additional_domains.
    """
    try:
        user, company = auth_store.register_user(
            first_name=body.first_name,
            last_name=body.last_name,
            email=body.email,
            password=body.password,
            company_name=body.company_name,
            company_domain=body.company_domain,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    token = auth_store.create_access_token(user.id, company.slug)

    return LoginResponse(
        access_token=token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role,
            company_id=user.company_id,
            is_active=user.is_active,
        ),
        company=CompanyResponse(
            id=company.id,
            slug=company.slug,
            name=company.name,
            domain=company.domain,
        ),
    )


@router.post("/login")
def login(
    body: LoginRequest,
    auth_store: AuthStore = Depends(get_auth_store),
) -> LoginResponse:
    """Authenticate with email + password.

    Returns an access token, user info, and company info.
    """
    user = auth_store.get_user_by_email(body.email)
    if not user or not auth_store.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    company = auth_store.get_company_by_slug(user.get("company_slug", ""))
    if not company:
        # Fallback: look up company by company_id stored on the user
        company_id = user.get("company_id", "")
        for c in auth_store.list_companies():
            if c.id == company_id:
                company = c
                break
    if not company:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = auth_store.create_access_token(user["id"], company.slug)

    return LoginResponse(
        access_token=token,
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            first_name=user["first_name"],
            last_name=user["last_name"],
            role=user["role"],
            company_id=user["company_id"],
            is_active=user.get("is_active", True),
        ),
        company=CompanyResponse(
            id=company.id,
            slug=company.slug,
            name=company.name,
            domain=company.domain,
        ),
    )


@router.get("/me")
def get_me(
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> MeResponse:
    """Return current user info from the auth token.

    Requires a valid Bearer token (parsed by AuthMiddleware).
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = auth_store.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    company_slug = getattr(request.state, "company_slug", None)
    company = auth_store.get_company_by_slug(company_slug) if company_slug else None

    return MeResponse(
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            first_name=user["first_name"],
            last_name=user["last_name"],
            role=user["role"],
            company_id=user["company_id"],
            is_active=user.get("is_active", True),
        ),
        company=CompanyResponse(
            id=company.id if company else "",
            slug=company.slug if company else "",
            name=company.name if company else "",
            domain=company.domain if company else "",
        ),
    )
