"""GA4 analytics integration API endpoints.

Auth: Most endpoints require authentication + tenant isolation.
OAuth callback is public (Google redirects here — no auth token).
Sync-all is internal (API key auth for cron-triggered daily sync).

8 endpoints:
  GET    /authorize        Generate Google OAuth consent URL
  GET    /callback         Google OAuth redirect handler (public)
  GET    /connection       Get current GA4 connection status
  DELETE /connection       Disconnect GA4 integration
  GET    /properties       List accessible GA4 properties
  POST   /select-property  Store selected GA4 property
  POST   /sync             Trigger manual GA4 data sync (background task)
  POST   /sync-all         Trigger daily sync for all active connections (cron, API key)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from api.auth.dependencies import get_workspace_read_slug, get_workspace_write_slug, require_auth
from api.dependencies import get_auth_service, get_event_bus, get_task_store
from api.schemas.analytics import (
    AuthorizeResponse,
    ConnectionResponse,
    DisconnectResponse,
    GA4PropertyItem,
    PropertiesResponse,
    SelectPropertyRequest,
    SyncRequest,
)
from core.analytics.exceptions import GA4AuthError, GA4Error
from core.auth.service import AuthServiceProtocol
from core.models.organization import UserProfile
from core.services.task_store import TaskStoreProtocol

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analytics/google", tags=["analytics"])


# ── Helpers ──────────────────────────────────────────────────────────


# ── Lazy DI import ───────────────────────────────────────────────────
# Avoids circular imports — the DI function is registered in dependencies.py
# but we import it lazily to keep the module self-contained.

def _get_ga4_service_dep():
    """Return the DI dependency for GA4AnalyticsService."""
    from api.dependencies import get_ga4_analytics_service
    return get_ga4_analytics_service


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("/authorize", response_model=AuthorizeResponse)
async def authorize(
    http_request: Request,
    return_url: str = Query(default="", description="URL to redirect after OAuth"),
    company_slug: str = Depends(get_workspace_read_slug),
    _user: UserProfile = Depends(require_auth),
    ga4_service: Any = Depends(_get_ga4_service_dep()),
) -> AuthorizeResponse:
    """Generate Google OAuth consent URL for GA4 access."""
    secret_key = http_request.app.state.secret_key

    url = ga4_service.generate_authorize_url(
        secret_key=secret_key,
        company_slug=company_slug,
        return_url=return_url,
    )
    return AuthorizeResponse(authorization_url=url)


def _append_param(url: str, param: str) -> str:
    """Append a query parameter using & if the URL already has a query string."""
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{param}"


@router.get("/callback", include_in_schema=False)
async def oauth_callback(
    http_request: Request,
    code: str = Query(...),
    state: str = Query(...),
    ga4_service: Any = Depends(_get_ga4_service_dep()),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> RedirectResponse:
    """Handle Google OAuth redirect.  Exchanges code for tokens, stores connection."""
    from core.analytics.service import GA4AnalyticsService
    from core.config.settings import settings
    from core.services.analytics_cache import invalidate_ga4_connection

    secret_key = http_request.app.state.secret_key
    state_payload = GA4AnalyticsService.verify_oauth_state(secret_key, state)
    base_url = settings.google_oauth_frontend_settings_url

    if state_payload is None:
        return RedirectResponse(url=_append_param(base_url, "error=invalid_state"))

    company_slug = state_payload["company_slug"]
    raw_return_url = state_payload.get("return_url") or ""

    # Validate return_url to prevent open redirect attacks.
    # Only allow redirects to the same origin as the configured frontend URL.
    from urllib.parse import urlparse

    allowed_origin = urlparse(base_url).netloc
    parsed_return = urlparse(raw_return_url)
    if raw_return_url and parsed_return.netloc == allowed_origin:
        return_url = raw_return_url
    else:
        return_url = base_url

    # Resolve company_id from slug
    company = await auth_service.get_company_by_slug(company_slug)
    if company is None:
        return RedirectResponse(url=_append_param(return_url, "error=company_not_found"))

    try:
        await ga4_service.exchange_code_and_store(
            code=code,
            company_id=str(company.id),
            company_slug=company_slug,
            tenant_id=company_slug,
        )
    except Exception as exc:
        logger.exception("OAuth callback failed for %s: %s", company_slug, exc)
        return RedirectResponse(url=_append_param(return_url, "error=oauth_failed"))

    # Invalidate cached connection info (reconnect scenario)
    await asyncio.to_thread(invalidate_ga4_connection, company_slug, company_slug)

    return RedirectResponse(url=_append_param(return_url, "analytics_connected=true"))


@router.get("/connection", response_model=Optional[ConnectionResponse])
async def get_connection(
    company_slug: str = Depends(get_workspace_read_slug),
    _user: UserProfile = Depends(require_auth),
    ga4_service: Any = Depends(_get_ga4_service_dep()),
) -> Optional[ConnectionResponse]:
    """Get current GA4 connection status."""
    from core.services.analytics_cache import (
        get_cached_ga4_connection,
        set_cached_ga4_connection,
    )

    # Check cache first
    cached = await asyncio.to_thread(
        get_cached_ga4_connection, company_slug, company_slug
    )
    if cached is not None:
        return ConnectionResponse(**cached)

    info = await ga4_service.get_connection_info(company_slug, tenant_id=company_slug)
    if info is None:
        return None

    resp = ConnectionResponse(
        provider=info.provider,
        ga4_property_id=info.ga4_property_id,
        ga4_property_name=info.ga4_property_name,
        ga4_account_id=info.ga4_account_id,
        is_active=info.is_active,
        connected_at=info.connected_at,
        last_sync_at=info.last_sync_at,
        last_sync_status=info.last_sync_status,
        last_sync_error=info.last_sync_error,
    )

    # Populate cache
    await asyncio.to_thread(
        set_cached_ga4_connection,
        company_slug,
        company_slug,
        resp.model_dump(mode="json"),
    )

    return resp


@router.delete("/connection", response_model=DisconnectResponse)
async def disconnect(
    purge_data: bool = Query(
        default=False,
        description="If true, purge all synced GA4 data (GDPR compliance)",
    ),
    company_slug: str = Depends(get_workspace_write_slug),
    _user: UserProfile = Depends(require_auth),
    ga4_service: Any = Depends(_get_ga4_service_dep()),
) -> DisconnectResponse:
    """Revoke GA4 OAuth tokens and deactivate connection."""
    from core.services.analytics_cache import invalidate_all_ga4_caches

    try:
        result = await ga4_service.disconnect(
            company_slug, tenant_id=company_slug, purge_data=purge_data
        )
        await asyncio.to_thread(invalidate_all_ga4_caches, company_slug)
        return DisconnectResponse(
            disconnected=result,
            data_purged=purge_data if result else False,
        )
    except Exception as exc:
        logger.exception("GA4 disconnect failed for %s", company_slug)
        return DisconnectResponse(disconnected=False, error=str(exc))


@router.get("/properties", response_model=PropertiesResponse)
async def list_properties(
    company_slug: str = Depends(get_workspace_read_slug),
    _user: UserProfile = Depends(require_auth),
    ga4_service: Any = Depends(_get_ga4_service_dep()),
) -> PropertiesResponse:
    """List GA4 properties accessible to the connected account."""
    from core.services.analytics_cache import (
        get_cached_ga4_properties,
        set_cached_ga4_properties,
    )

    # Check cache first
    cached = await asyncio.to_thread(
        get_cached_ga4_properties, company_slug, company_slug
    )
    if cached is not None:
        return PropertiesResponse(
            properties=[GA4PropertyItem(**p) for p in cached]
        )

    try:
        properties = await ga4_service.list_properties(
            company_slug, tenant_id=company_slug
        )
    except GA4AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except GA4Error as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    items = [
        GA4PropertyItem(
            property_id=p.property_id,
            display_name=p.display_name,
            account_id=p.account_id,
            account_display_name=p.account_display_name,
        )
        for p in properties
    ]

    # Populate cache
    await asyncio.to_thread(
        set_cached_ga4_properties,
        company_slug,
        company_slug,
        [item.model_dump() for item in items],
    )

    return PropertiesResponse(properties=items)


@router.post("/select-property", status_code=200)
async def select_property(
    body: SelectPropertyRequest,
    company_slug: str = Depends(get_workspace_write_slug),
    _user: UserProfile = Depends(require_auth),
    ga4_service: Any = Depends(_get_ga4_service_dep()),
) -> dict[str, bool]:
    """Store the selected GA4 property for data syncing."""
    from core.services.analytics_cache import invalidate_all_ga4_caches

    try:
        await ga4_service.select_property(
            company_slug=company_slug,
            tenant_id=company_slug,
            property_id=body.property_id,
            property_name=body.property_name,
            account_id=body.account_id,
        )
    except GA4AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    # Invalidate caches (connection info changes with new property)
    await asyncio.to_thread(invalidate_all_ga4_caches, company_slug)

    return {"selected": True}


@router.post("/sync", status_code=202)
async def trigger_sync(
    http_request: Request,
    body: SyncRequest | None = None,
    company_slug: str = Depends(get_workspace_write_slug),
    _user: UserProfile = Depends(require_auth),
    ga4_service: Any = Depends(_get_ga4_service_dep()),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: Any = Depends(get_event_bus),
) -> dict[str, Any]:
    """Trigger a manual GA4 data sync (background task).  Returns 202 with task_id."""

    # Verify active connection with property selected
    conn_info = await ga4_service.get_connection_info(
        company_slug, tenant_id=company_slug
    )
    if conn_info is None or not conn_info.is_active:
        raise HTTPException(status_code=404, detail="No active GA4 connection")
    if not conn_info.ga4_property_id:
        raise HTTPException(status_code=400, detail="No GA4 property selected")

    task = task_store.create_task("ga4_sync", company_slug)

    from api.tasks.runner import run_ga4_sync_task
    from core.config.settings import settings

    session_factory = getattr(http_request.app.state, "db_session_factory", None)
    fernet_key = settings.cms_fernet_key or ""

    handle = asyncio.create_task(
        run_ga4_sync_task(
            task_id=task.task_id,
            company_slug=company_slug,
            tenant_id=company_slug,
            task_store=task_store,
            event_bus=event_bus,
            session_factory=session_factory,
            fernet_key=fernet_key,
            lookback_days=settings.ga4_sync_lookback_days,
            start_date_override=body.start_date if body else None,
            end_date_override=body.end_date if body else None,
        )
    )
    task_store.register_task_handle(task.task_id, handle)

    return {
        "run_id": task.task_id,
        "pipeline": "ga4_sync",
        "status": task.status.value,
        "company_slug": company_slug,
    }


# ── Cron-triggered daily sync ───────────────────────────────────────


@router.post("/sync-all", status_code=202, include_in_schema=False)
async def trigger_sync_all(
    http_request: Request,
    x_api_key: str = Header(..., alias="X-API-Key"),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: Any = Depends(get_event_bus),
) -> dict[str, Any]:
    """Trigger GA4 sync for ALL active connections (cron-triggered, API key auth).

    Called by Railway cron or external scheduler at 06:00 UTC daily.
    Each connection is synced as a separate background task with slug-lock
    deduplication — already-running syncs are skipped.
    """
    from api.tasks.runner import run_ga4_sync_task
    from core.config.settings import settings
    from core.db.repositories.analytics_repo import AnalyticsConnectionRepository

    # Validate API key
    if not settings.ga4_sync_api_key:
        raise HTTPException(
            status_code=503,
            detail="GA4 sync API key not configured",
        )
    if x_api_key != settings.ga4_sync_api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")

    session_factory = getattr(http_request.app.state, "db_session_factory", None)
    if session_factory is None:
        raise HTTPException(status_code=503, detail="Database not available")

    fernet_key = settings.cms_fernet_key or ""

    # Query all active connections
    session = session_factory()
    try:
        conn_repo = AnalyticsConnectionRepository(session)
        connections = await conn_repo.get_all_active()
    finally:
        await session.close()

    triggered = 0
    skipped = 0

    for conn in connections:
        # Skip connections without a selected property
        if not conn.ga4_property_id:
            skipped += 1
            continue

        # create_task acquires the slug lock internally — raises
        # TaskConflictError if a sync is already running for this company
        try:
            task = task_store.create_task("ga4_sync", conn.company_slug)
        except Exception:
            skipped += 1
            continue

        handle = asyncio.create_task(
            run_ga4_sync_task(
                task_id=task.task_id,
                company_slug=conn.company_slug,
                tenant_id=conn.tenant_id,
                task_store=task_store,
                event_bus=event_bus,
                session_factory=session_factory,
                fernet_key=fernet_key,
                lookback_days=settings.ga4_sync_lookback_days,
            )
        )
        task_store.register_task_handle(task.task_id, handle)
        triggered += 1

    return {
        "triggered": triggered,
        "skipped": skipped,
        "total": triggered + skipped,
    }
