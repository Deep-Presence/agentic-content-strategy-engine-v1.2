"""Authentication endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from api.auth.dependencies import require_auth, require_role
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
from core.models.organization import UserProfile

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
        msg = str(e)
        if msg == "domain_taken":
            raise HTTPException(
                status_code=409,
                detail=(
                    "A company with this domain already exists. "
                    "Ask your admin for an invite code."
                ),
            )
        raise HTTPException(status_code=409, detail=msg)

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
    if not user:
        # Constant-time dummy hash to prevent timing oracle (Codex W7)
        auth_store.verify_password(body.password, AuthStore._DUMMY_HASH)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not auth_store.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # C4 fix: reject deactivated users at login (before token issuance)
    if not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="Account deactivated")

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


# ── Invite flow (Codex C1) ──────────────────────────────────


class InviteRequest(BaseModel):
    role: str = Field(default="member", pattern="^(member|viewer)$")


class InviteResponse(BaseModel):
    invite_code: str
    company_slug: str
    role: str


class JoinRequest(BaseModel):
    invite_code: str
    first_name: str
    last_name: str
    email: EmailStr
    password: str = Field(min_length=8)


@router.post("/invite", status_code=201)
def create_invite(
    body: InviteRequest,
    request: Request,
    _user: UserProfile = Depends(require_role("superuser")),
    auth_store: AuthStore = Depends(get_auth_store),
) -> InviteResponse:
    """Create an invite code for the current user's company.

    Only superusers can create invites. The invite code allows a new
    user to join the company via ``POST /api/v1/auth/join``.
    """
    company_slug = getattr(request.state, "company_slug", None)
    if not company_slug:
        raise HTTPException(status_code=401, detail="Not authenticated")

    code = auth_store.create_invite(company_slug, role=body.role)
    return InviteResponse(
        invite_code=code,
        company_slug=company_slug,
        role=body.role,
    )


@router.post("/join", status_code=201)
def join_company(
    body: JoinRequest,
    auth_store: AuthStore = Depends(get_auth_store),
) -> LoginResponse:
    """Join an existing company using an invite code.

    Public endpoint (no auth required). The invite code determines
    which company and role the user gets.
    """
    try:
        user, company = auth_store.redeem_invite(
            invite_code=body.invite_code,
            first_name=body.first_name,
            last_name=body.last_name,
            email=body.email,
            password=body.password,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

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
