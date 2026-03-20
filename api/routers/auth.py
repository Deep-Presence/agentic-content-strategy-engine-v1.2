"""Authentication endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from core.audit import log_auth_event, AuditEventType
from api.auth.dependencies import require_auth, require_role
from api.auth.models import (
    CompanyResponse,
    LoginRequest,
    LoginResponse,
    MeResponse,
    RegisterRequest,
    UserResponse,
)
from api.dependencies import get_auth_service
from core.auth.service import AuthServiceProtocol
from core.auth.utils.passwords import DUMMY_HASH, verify_password
from core.models.organization import UserProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", status_code=201)
async def register(
    body: RegisterRequest,
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> LoginResponse:
    """Register a new user and create a new company.

    Creates a new isolated company. The user becomes 'superuser'.
    If the domain is already taken, returns 409. To join an existing
    company, use ``POST /api/v1/auth/join`` with an invite code.
    """
    try:
        user, company = await auth_service.register_user(
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

    await log_auth_event(
        AuditEventType.REGISTER,
        user_id=user.id, email=user.email, company_slug=company.slug,
        detail={"role": user.role, "company_name": company.name},
    )

    token = auth_service.create_access_token(user.id, company.slug)

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
async def login(
    body: LoginRequest,
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> LoginResponse:
    """Authenticate with email + password.

    Returns an access token, user info, and company info.
    """
    user = await auth_service.get_user_by_email(body.email)
    if not user:
        # Constant-time dummy hash to prevent timing oracle (Codex W7)
        verify_password(body.password, DUMMY_HASH)
        await log_auth_event(
            AuditEventType.LOGIN_FAILED,
            email=body.email,
            detail={"reason": "invalid_credentials"},
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(body.password, user["password_hash"]):
        await log_auth_event(
            AuditEventType.LOGIN_FAILED,
            email=body.email,
            detail={"reason": "invalid_credentials"},
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # C4 fix: reject deactivated users at login (before token issuance)
    if not user.get("is_active", True):
        await log_auth_event(
            AuditEventType.LOGIN_FAILED,
            user_id=user["id"], email=body.email,
            detail={"reason": "account_deactivated"},
        )
        raise HTTPException(status_code=401, detail="Account deactivated")

    company = await auth_service.get_company_by_id(user.get("company_id", ""))
    if not company:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = auth_service.create_access_token(user["id"], company.slug)

    await log_auth_event(
        AuditEventType.LOGIN_SUCCESS,
        user_id=user["id"], email=body.email, company_slug=company.slug,
    )

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
async def get_me(
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> MeResponse:
    """Return current user info from the auth token.

    Uses ``require_auth`` dependency to verify the token, check
    ``is_active``, and return the authenticated ``UserProfile``.
    """
    company_slug = getattr(request.state, "company_slug", None)
    company = (await auth_service.get_company_by_slug(company_slug)) if company_slug else None

    return MeResponse(
        user=UserResponse(
            id=current_user.id,
            email=current_user.email,
            first_name=current_user.first_name,
            last_name=current_user.last_name,
            role=current_user.role,
            company_id=current_user.company_id,
            is_active=current_user.is_active,
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
async def create_invite(
    body: InviteRequest,
    request: Request,
    _user: UserProfile = Depends(require_role("superuser")),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> InviteResponse:
    """Create an invite code for the current user's company.

    Only superusers can create invites. The invite code allows a new
    user to join the company via ``POST /api/v1/auth/join``.
    """
    company_slug = getattr(request.state, "company_slug", None)
    if not company_slug:
        raise HTTPException(status_code=401, detail="Not authenticated")

    code = await auth_service.create_invite(company_slug, role=body.role)
    await log_auth_event(
        AuditEventType.INVITE_CREATED,
        user_id=_user.id, company_slug=company_slug,
        detail={"role": body.role},
    )
    return InviteResponse(
        invite_code=code,
        company_slug=company_slug,
        role=body.role,
    )


@router.post("/join", status_code=201)
async def join_company(
    body: JoinRequest,
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> LoginResponse:
    """Join an existing company using an invite code.

    Public endpoint (no auth required). The invite code determines
    which company and role the user gets.
    """
    try:
        user, company = await auth_service.redeem_invite(
            invite_code=body.invite_code,
            first_name=body.first_name,
            last_name=body.last_name,
            email=body.email,
            password=body.password,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await log_auth_event(
        AuditEventType.INVITE_REDEEMED,
        user_id=user.id, email=user.email, company_slug=company.slug,
        detail={"role": user.role},
    )

    token = auth_service.create_access_token(user.id, company.slug)

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
