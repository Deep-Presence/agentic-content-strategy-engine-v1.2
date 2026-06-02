"""CMS integration API endpoints.

Auth: All endpoints require authentication + tenant isolation.
Write operations require ``member`` or ``superuser`` role.

11 endpoints + 3 Webflow configure endpoints:
  POST   /connect             Connect a CMS (validate + store)
  GET    /connection           Get current connection info
  DELETE /connection           Disconnect CMS
  POST   /sync                Re-sync content from CMS (background task)
  GET    /synced-posts         List synced posts
  GET    /stale-actions        Stale content cards for Home dashboard
  POST   /stale-to-triage      Queue stale post for refresh
  POST   /publish              Publish brief to CMS
  POST   /refresh/{cms_post_id}  Update existing CMS post
  GET    /publish-history      Audit trail
  GET    /categories           CMS categories (for publish UI selector)
  GET    /webflow/collections  List Webflow collections (Webflow only)
  GET    /webflow/collections/{collection_id}/fields  Collection schema + mapping hints
  POST   /webflow/configure    Save Webflow provider_config (+ optional sync)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from core.services.cms_cache import (
    get_cached_connection_info,
    invalidate_all_cms_caches,
    invalidate_connection_info,
    set_cached_connection_info,
)
from core.services.analytics_cache import invalidate_all_ga4_caches

from api.auth.dependencies import get_workspace_read_slug, get_workspace_write_slug, require_auth
from api.dependencies import get_auth_service, get_cms_service, get_event_bus, get_task_store
from api.schemas.cms import (
    CMSCategoryItem,
    CMSConnectRequest,
    CMSConnectResponse,
    CMSConnectionInfoResponse,
    CMSPublishHistoryItem,
    CMSPublishRequest,
    CMSPublishResponse,
    CMSRefreshRequest,
    CMSSyncedPostSummary,
    CMSStaleToTriageRequest,
    StaleContentAction,
    StaleToTriageResponse,
    WebflowCollectionFieldsResponse,
    WebflowCollectionSummary,
    WebflowConfigureRequest,
    WebflowConfigureResponse,
    WebflowAuthorizeResponse,
    WebflowSiteSummary,
    WebflowSelectSiteRequest,
    WebflowSelectSiteResponse,
    WebflowFieldSchemaItem,
    WebflowFieldMappingResponse,
)
from core.auth.service import AuthServiceProtocol
from core.cms.models import CMSPublishMetadata
from core.cms.exceptions import (
    CMSAuthError,
    CMSConnectionError,
    CMSError,
    CMSNotFoundError,
    CMSRateLimitError,
)
from core.models.organization import UserProfile
from core.services.task_store import TaskConflictError, TaskStoreProtocol

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cms", tags=["cms"])


# ── Helpers ───────────────────────────────────────────────────────────


async def _get_connection_or_404(
    cms_service: Any, company_slug: str, tenant_id: str
) -> Any:
    """Fetch active CMS connection or raise 404."""
    conn = await cms_service.get_connection(company_slug, tenant_id)
    if conn is None:
        raise HTTPException(
            status_code=404, detail="No active CMS connection for this company"
        )
    return conn


def _derive_effective_slug(
    company_slug: str, product_slug: Optional[str]
) -> str:
    """Derive effective_slug using the double-underscore convention."""
    if product_slug:
        return f"{company_slug}__{product_slug}"
    return company_slug


def _handle_cms_error(exc: CMSError) -> HTTPException:
    """Map CMS exception hierarchy to HTTP status codes."""
    if isinstance(exc, CMSNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, CMSAuthError):
        return HTTPException(status_code=401, detail=str(exc))
    if isinstance(exc, CMSRateLimitError):
        return HTTPException(status_code=429, detail=str(exc))
    if isinstance(exc, CMSConnectionError):
        return HTTPException(status_code=502, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


async def _require_webflow_connection(
    cms_service: Any, company_slug: str
) -> Any:
    """Fetch active Webflow CMS connection or raise 404/422."""
    conn = await _get_connection_or_404(cms_service, company_slug, company_slug)
    provider = conn.provider.value if hasattr(conn.provider, "value") else str(conn.provider)
    if provider != "webflow":
        raise HTTPException(
            status_code=422,
            detail="Webflow endpoints require an active Webflow CMS connection",
        )
    return conn


async def _maybe_trigger_cms_sync(
    *,
    http_request: Request,
    company_slug: str,
    task_store: TaskStoreProtocol,
    event_bus: Any,
) -> str | None:
    """Launch a CMS sync background task; return task_id or None if locked."""
    try:
        task = task_store.create_task("cms_sync", company_slug)
    except TaskConflictError:
        logger.info("Webflow configure sync skipped for %s — sync already running", company_slug)
        return None

    from api.tasks.runner import run_cms_sync_task
    from core.config.settings import settings

    session_factory = getattr(http_request.app.state, "db_session_factory", None)
    storage = getattr(http_request.app.state, "storage_backend", None)

    handle = asyncio.create_task(
        run_cms_sync_task(
            task_id=task.task_id,
            company_slug=company_slug,
            tenant_id=company_slug,
            task_store=task_store,
            event_bus=event_bus,
            session_factory=session_factory,
            storage=storage,
            fernet_key=settings.cms_fernet_key or "",
        )
    )
    task_store.register_task_handle(task.task_id, handle)
    return task.task_id


# ── 1. Connect ────────────────────────────────────────────────────────


@router.post("/connect", response_model=CMSConnectResponse)
async def connect_cms(
    body: CMSConnectRequest,
    http_request: Request,
    company_slug: str = Depends(get_workspace_write_slug),
    _user: UserProfile = Depends(require_auth),
    cms_service: Any = Depends(get_cms_service),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: Any = Depends(get_event_bus),
) -> CMSConnectResponse:
    """Connect a CMS to the company's Deep Presence account.

    On first-time connect (``last_sync_at is None``), automatically launches
    a CMS sync background task to populate the content inventory.
    """
    # Resolve company_id
    company = await auth_service.get_company_by_slug(company_slug)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    try:
        result = await cms_service.connect(
            company_id=company.id,
            company_slug=company_slug,
            tenant_id=company_slug,
            provider=body.provider,
            site_url=body.site_url,
            username=body.username,
            api_key=body.api_key,
            provider_config=body.provider_config,
        )
    except (ValueError, CMSError) as exc:
        raise _handle_cms_error(exc) if isinstance(exc, CMSError) else HTTPException(
            status_code=422, detail=str(exc)
        )

    # Invalidate cached connection info after successful connect
    await asyncio.to_thread(invalidate_connection_info, company_slug, company_slug)

    response = CMSConnectResponse(**result)

    # ── Auto-sync on first connect ────────────────────────────────
    if response.connected:
        conn = await cms_service.get_connection(company_slug, company_slug)
        if conn is not None and conn.last_sync_at is None:
            try:
                task = task_store.create_task("cms_sync", company_slug)

                from api.tasks.runner import run_cms_sync_task
                from core.config.settings import settings

                session_factory = getattr(http_request.app.state, "db_session_factory", None)
                storage = getattr(http_request.app.state, "storage_backend", None)

                handle = asyncio.create_task(
                    run_cms_sync_task(
                        task_id=task.task_id,
                        company_slug=company_slug,
                        tenant_id=company_slug,
                        task_store=task_store,
                        event_bus=event_bus,
                        session_factory=session_factory,
                        storage=storage,
                        fernet_key=settings.cms_fernet_key or "",
                    )
                )
                task_store.register_task_handle(task.task_id, handle)
                response.sync_task_id = task.task_id
                logger.info(
                    "Auto-sync triggered on first CMS connect for %s (task=%s)",
                    company_slug, task.task_id,
                )
            except TaskConflictError:
                # Another sync is already running — skip silently
                logger.info(
                    "Auto-sync skipped for %s — sync already running",
                    company_slug,
                )

    return response


# ── 2. Get Connection ─────────────────────────────────────────────────


@router.get("/connection", response_model=Optional[CMSConnectionInfoResponse])
async def get_connection(
    company_slug: str = Depends(get_workspace_read_slug),
    _user: UserProfile = Depends(require_auth),
    cms_service: Any = Depends(get_cms_service),
) -> Optional[CMSConnectionInfoResponse]:
    """Get the current CMS connection info for this company."""
    # Redis cache check (display fields only, no credentials)
    cached = await asyncio.to_thread(
        get_cached_connection_info, company_slug, company_slug
    )
    if cached is not None:
        return CMSConnectionInfoResponse(**cached)

    conn = await cms_service.get_connection(company_slug, tenant_id=company_slug)
    if conn is None:
        return None

    response = CMSConnectionInfoResponse(
        provider=conn.provider.value if hasattr(conn.provider, "value") else str(conn.provider),
        site_url=conn.site_url,
        site_name=conn.site_name,
        cms_version=conn.cms_version,
        user_display_name=conn.user_display_name,
        is_active=conn.is_active,
        last_sync_at=conn.last_sync_at,
        sync_post_count=conn.sync_post_count,
        provider_config=conn.provider_config or {},
    )

    # Cache write (fire-and-forget)
    await asyncio.to_thread(
        set_cached_connection_info,
        company_slug,
        company_slug,
        response.model_dump(mode="json"),
    )

    return response


# ── 3. Disconnect ─────────────────────────────────────────────────────


@router.delete("/connection")
async def disconnect_cms(
    http_request: Request,
    company_slug: str = Depends(get_workspace_write_slug),
    _user: UserProfile = Depends(require_auth),
    cms_service: Any = Depends(get_cms_service),
) -> dict[str, bool]:
    """Disconnect the CMS integration. Does NOT delete synced data."""
    disconnected = await cms_service.disconnect(company_slug, tenant_id=company_slug)

    # Invalidate cached connection info after disconnect
    await asyncio.to_thread(invalidate_connection_info, company_slug, company_slug)

    return {"disconnected": disconnected}


# ── 4. Sync (Background Task) ────────────────────────────────────────


@router.post("/sync", status_code=202)
async def trigger_sync(
    http_request: Request,
    company_slug: str = Depends(get_workspace_write_slug),
    _user: UserProfile = Depends(require_auth),
    cms_service: Any = Depends(get_cms_service),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: Any = Depends(get_event_bus),
) -> dict[str, Any]:
    """Re-sync existing content from the CMS (background task)."""
    await _get_connection_or_404(cms_service, company_slug, company_slug)

    task = task_store.create_task("cms_sync", company_slug)

    from api.tasks.runner import run_cms_sync_task
    from core.config.settings import settings

    session_factory = getattr(http_request.app.state, "db_session_factory", None)
    storage = getattr(http_request.app.state, "storage_backend", None)

    handle = asyncio.create_task(
        run_cms_sync_task(
            task_id=task.task_id,
            company_slug=company_slug,
            tenant_id=company_slug,
            task_store=task_store,
            event_bus=event_bus,
            session_factory=session_factory,
            storage=storage,
            fernet_key=settings.cms_fernet_key or "",
        )
    )
    task_store.register_task_handle(task.task_id, handle)

    return {
        "run_id": task.task_id,
        "pipeline": "cms_sync",
        "status": task.status.value,
        "company_slug": company_slug,
    }


# ── 5. Synced Posts ───────────────────────────────────────────────────


@router.get("/synced-posts", response_model=list[CMSSyncedPostSummary])
async def list_synced_posts(
    stale_only: bool = False,
    limit: int = 100,
    offset: int = 0,
    company_slug: str = Depends(get_workspace_read_slug),
    _user: UserProfile = Depends(require_auth),
    cms_service: Any = Depends(get_cms_service),
) -> list[CMSSyncedPostSummary]:
    """List the locally indexed posts from the connected CMS."""
    posts = await cms_service.list_synced_posts(
        company_slug, stale_only=stale_only, limit=limit, offset=offset
    )
    return [
        CMSSyncedPostSummary(
            id=str(p.id),
            cms_post_id=p.cms_post_id,
            title=p.title,
            slug=p.slug,
            url=p.url,
            word_count=p.word_count,
            published_at=p.published_at,
            modified_at=p.modified_at,
            is_stale=p.is_stale,
            staleness_days=p.staleness_days,
            categories=p.categories or [],
            queued_for_refresh=p.queued_for_refresh,
        )
        for p in posts
    ]


# ── 6. Stale Actions ─────────────────────────────────────────────────


@router.get("/stale-actions", response_model=list[StaleContentAction])
async def get_stale_actions(
    company_slug: str = Depends(get_workspace_read_slug),
    _user: UserProfile = Depends(require_auth),
    cms_service: Any = Depends(get_cms_service),
) -> list[StaleContentAction]:
    """Get stale content cards for the Home dashboard Recommended Actions."""
    actions = await cms_service.get_stale_actions(company_slug)
    return [StaleContentAction(**a) for a in actions]


# ── 7. Stale → Triage ────────────────────────────────────────────────


@router.post("/stale-to-triage", response_model=StaleToTriageResponse)
async def stale_to_triage(
    body: CMSStaleToTriageRequest,
    http_request: Request,
    company_slug: str = Depends(get_workspace_write_slug),
    _user: UserProfile = Depends(require_auth),
    cms_service: Any = Depends(get_cms_service),
) -> StaleToTriageResponse:
    """Queue a stale post for content refresh (Recommended Actions → Triage)."""
    try:
        result = await cms_service.queue_stale_for_refresh(
            company_slug, body.cms_synced_post_id
        )
    except CMSError as exc:
        raise _handle_cms_error(exc)

    # Invalidate stale/posts caches after queuing for refresh
    await asyncio.to_thread(invalidate_all_cms_caches, company_slug)

    return StaleToTriageResponse(**result)


# ── 8. Publish ────────────────────────────────────────────────────────


@router.post("/publish", response_model=CMSPublishResponse)
async def publish_to_cms(
    body: CMSPublishRequest,
    http_request: Request,
    company_slug: str = Depends(get_workspace_write_slug),
    _user: UserProfile = Depends(require_auth),
    cms_service: Any = Depends(get_cms_service),
) -> CMSPublishResponse:
    """Publish an approved Content Engine brief to the connected CMS."""
    connection = await _get_connection_or_404(
        cms_service, company_slug, company_slug
    )

    effective_slug = (
        body.effective_slug
        or _derive_effective_slug(company_slug, body.product_slug)
    )

    try:
        post = await cms_service.publish_brief(
            company_slug,
            body.brief_id,
            connection,
            effective_slug=effective_slug,
            target_status=body.status,
            category_names=body.categories or None,
            slug_override=body.slug_override,
            publish_metadata=(
                CMSPublishMetadata(**body.publish_metadata.model_dump(mode="json"))
                if body.publish_metadata
                else None
            ),
            collection_id=body.collection_id,
        )
    except CMSError as exc:
        raise _handle_cms_error(exc)

    await asyncio.to_thread(invalidate_all_ga4_caches, company_slug)

    return CMSPublishResponse(
        cms_post_id=post.cms_id,
        url=post.url,
        slug=post.slug,
        title=post.title,
        status=post.status.value if hasattr(post.status, "value") else str(post.status),
        word_count=post.word_count,
    )


# ── 9. Refresh ────────────────────────────────────────────────────────


@router.post("/refresh/{cms_post_id}", response_model=CMSPublishResponse)
async def refresh_cms_post(
    cms_post_id: str,
    body: CMSRefreshRequest,
    http_request: Request,
    company_slug: str = Depends(get_workspace_write_slug),
    _user: UserProfile = Depends(require_auth),
    cms_service: Any = Depends(get_cms_service),
) -> CMSPublishResponse:
    """Update an existing CMS post with refreshed content."""
    connection = await _get_connection_or_404(
        cms_service, company_slug, company_slug
    )

    effective_slug = (
        body.effective_slug
        or _derive_effective_slug(company_slug, body.product_slug)
    )

    try:
        post = await cms_service.refresh_post(
            company_slug,
            cms_post_id,
            body.brief_id,
            connection,
            effective_slug=effective_slug,
        )
    except CMSError as exc:
        raise _handle_cms_error(exc)

    await asyncio.to_thread(invalidate_all_ga4_caches, company_slug)

    return CMSPublishResponse(
        cms_post_id=post.cms_id,
        url=post.url,
        slug=post.slug,
        title=post.title,
        status=post.status.value if hasattr(post.status, "value") else str(post.status),
        word_count=post.word_count,
    )


# ── 10. Publish History ──────────────────────────────────────────────


@router.get("/publish-history", response_model=list[CMSPublishHistoryItem])
async def get_publish_history(
    limit: int = 50,
    offset: int = 0,
    company_slug: str = Depends(get_workspace_read_slug),
    _user: UserProfile = Depends(require_auth),
    cms_service: Any = Depends(get_cms_service),
) -> list[CMSPublishHistoryItem]:
    """List all publish/refresh actions for this company."""
    records = await cms_service.list_publish_history(
        company_slug, limit=limit, offset=offset
    )
    return [
        CMSPublishHistoryItem(
            id=str(r.id),
            brief_id=r.brief_id,
            effective_slug=r.effective_slug,
            cms_post_id=r.cms_post_id,
            cms_post_url=r.cms_post_url,
            cms_post_slug=r.cms_post_slug,
            action=r.action.value if hasattr(r.action, "value") else str(r.action),
            status_at_publish=(
                r.status_at_publish.value
                if hasattr(r.status_at_publish, "value")
                else str(r.status_at_publish)
            ),
            published_at=r.published_at,
            title_published=r.title_published,
            word_count=r.word_count,
        )
        for r in records
    ]


# ── 11. Categories (Codex F4) ────────────────────────────────────────


@router.get("/categories", response_model=list[CMSCategoryItem])
async def list_categories(
    company_slug: str = Depends(get_workspace_read_slug),
    _user: UserProfile = Depends(require_auth),
    cms_service: Any = Depends(get_cms_service),
) -> list[CMSCategoryItem]:
    """Fetch categories from the connected CMS (for publish UI selector)."""
    connection = await _get_connection_or_404(
        cms_service, company_slug, company_slug
    )
    try:
        cats = await cms_service.list_categories(connection)
    except CMSError as exc:
        raise _handle_cms_error(exc)

    return [
        CMSCategoryItem(
            cms_id=c.cms_id,
            name=c.name,
            slug=c.slug,
            parent_id=c.parent_id,
            post_count=c.post_count,
        )
        for c in cats
    ]


# ── 12–14. Webflow configure (WF-2) ─────────────────────────────────


@router.get("/webflow/collections", response_model=list[WebflowCollectionSummary])
async def list_webflow_collections(
    company_slug: str = Depends(get_workspace_read_slug),
    _user: UserProfile = Depends(require_auth),
    cms_service: Any = Depends(get_cms_service),
) -> list[WebflowCollectionSummary]:
    """List Webflow CMS collections for the connected site."""
    connection = await _require_webflow_connection(cms_service, company_slug)
    try:
        collections = await cms_service.list_webflow_collections(connection)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CMSError as exc:
        raise _handle_cms_error(exc)

    return [WebflowCollectionSummary(**c) for c in collections]


@router.get(
    "/webflow/collections/{collection_id}/fields",
    response_model=WebflowCollectionFieldsResponse,
)
async def get_webflow_collection_fields(
    collection_id: str,
    company_slug: str = Depends(get_workspace_read_slug),
    _user: UserProfile = Depends(require_auth),
    cms_service: Any = Depends(get_cms_service),
) -> WebflowCollectionFieldsResponse:
    """Fetch Webflow collection schema and suggested field mapping."""
    connection = await _require_webflow_connection(cms_service, company_slug)
    try:
        payload = await cms_service.get_webflow_collection_fields(
            connection, collection_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CMSError as exc:
        raise _handle_cms_error(exc)

    return WebflowCollectionFieldsResponse(
        collection_id=payload["collection_id"],
        fields=[WebflowFieldSchemaItem(**f) for f in payload["fields"]],
        suggested_mapping=WebflowFieldMappingResponse(**payload["suggested_mapping"]),
    )


@router.post("/webflow/configure", response_model=WebflowConfigureResponse)
async def configure_webflow(
    body: WebflowConfigureRequest,
    http_request: Request,
    company_slug: str = Depends(get_workspace_write_slug),
    _user: UserProfile = Depends(require_auth),
    cms_service: Any = Depends(get_cms_service),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: Any = Depends(get_event_bus),
) -> WebflowConfigureResponse:
    """Save Webflow multi-collection config and optionally trigger a sync."""
    connection = await _require_webflow_connection(cms_service, company_slug)

    configure_payload = {
        "site_id": body.site_id,
        "collections": [c.model_dump(mode="json") for c in body.collections],
        "publish_mode": body.publish_mode,
        "default_collection_id": body.default_collection_id,
    }

    try:
        result = await cms_service.configure_webflow(
            company_slug,
            company_slug,
            connection,
            configure_payload=configure_payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CMSError as exc:
        raise _handle_cms_error(exc)

    await asyncio.to_thread(invalidate_connection_info, company_slug, company_slug)

    sync_task_id: str | None = None
    if body.trigger_sync:
        sync_task_id = await _maybe_trigger_cms_sync(
            http_request=http_request,
            company_slug=company_slug,
            task_store=task_store,
            event_bus=event_bus,
        )

    return WebflowConfigureResponse(
        configured=result["configured"],
        provider_config=result["provider_config"],
        sync_task_id=sync_task_id,
    )


# ── 15–18. Webflow OAuth + webhooks (WF-5) ──────────────────────────


def _append_param(url: str, param: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{param}"


@router.get("/webflow/authorize", response_model=WebflowAuthorizeResponse)
async def webflow_authorize(
    http_request: Request,
    return_url: str = Query(default="", description="URL to redirect after OAuth"),
    company_slug: str = Depends(get_workspace_read_slug),
    _user: UserProfile = Depends(require_auth),
    cms_service: Any = Depends(get_cms_service),
) -> WebflowAuthorizeResponse:
    """Generate Webflow OAuth consent URL."""
    secret_key = http_request.app.state.secret_key
    try:
        url = cms_service.generate_webflow_authorize_url(
            secret_key=secret_key,
            company_slug=company_slug,
            return_url=return_url,
        )
    except CMSError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return WebflowAuthorizeResponse(authorization_url=url)


@router.get("/webflow/callback", include_in_schema=False)
async def webflow_oauth_callback(
    http_request: Request,
    code: str = Query(...),
    state: str = Query(...),
    cms_service: Any = Depends(get_cms_service),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> RedirectResponse:
    """Handle Webflow OAuth redirect — exchange code and store connection."""
    from core.services.cms_service import CMSService

    secret_key = http_request.app.state.secret_key
    state_payload = CMSService.verify_webflow_oauth_state(secret_key, state)
    base_url = cms_service.webflow_oauth_frontend_settings_url

    if state_payload is None:
        return RedirectResponse(url=_append_param(base_url, "error=invalid_state"))

    company_slug = state_payload["company_slug"]
    raw_return_url = state_payload.get("return_url") or ""

    from urllib.parse import urlparse

    allowed_origin = urlparse(base_url).netloc
    parsed_return = urlparse(raw_return_url)
    if raw_return_url and parsed_return.netloc == allowed_origin:
        return_url = raw_return_url
    else:
        return_url = base_url

    company = await auth_service.get_company_by_slug(company_slug)
    if company is None:
        return RedirectResponse(url=_append_param(return_url, "error=company_not_found"))

    try:
        await cms_service.exchange_webflow_code_and_store(
            code=code,
            company_id=str(company.id),
            company_slug=company_slug,
            tenant_id=company_slug,
        )
    except Exception as exc:
        logger.exception("Webflow OAuth callback failed for %s: %s", company_slug, exc)
        return RedirectResponse(url=_append_param(return_url, "error=webflow_oauth_failed"))

    await asyncio.to_thread(invalidate_connection_info, company_slug, company_slug)
    return RedirectResponse(url=_append_param(return_url, "webflow_connected=true"))


@router.get("/webflow/sites", response_model=list[WebflowSiteSummary])
async def list_webflow_sites(
    company_slug: str = Depends(get_workspace_read_slug),
    _user: UserProfile = Depends(require_auth),
    cms_service: Any = Depends(get_cms_service),
) -> list[WebflowSiteSummary]:
    """List Webflow sites for OAuth or token connections."""
    connection = await _require_webflow_connection(cms_service, company_slug)
    try:
        sites = await cms_service.list_webflow_sites(connection)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CMSError as exc:
        raise _handle_cms_error(exc)
    return [WebflowSiteSummary(**s) for s in sites]


@router.post("/webflow/select-site", response_model=WebflowSelectSiteResponse)
async def select_webflow_site(
    body: WebflowSelectSiteRequest,
    company_slug: str = Depends(get_workspace_write_slug),
    _user: UserProfile = Depends(require_auth),
    cms_service: Any = Depends(get_cms_service),
) -> WebflowSelectSiteResponse:
    """Bind a Webflow OAuth connection to a specific site."""
    connection = await _require_webflow_connection(cms_service, company_slug)
    try:
        result = await cms_service.select_webflow_site(
            company_slug,
            company_slug,
            connection,
            site_id=body.site_id,
            site_url=body.site_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CMSError as exc:
        raise _handle_cms_error(exc)

    await asyncio.to_thread(invalidate_connection_info, company_slug, company_slug)
    return WebflowSelectSiteResponse(**result)


@router.post("/webflow/webhook", include_in_schema=False)
async def webflow_webhook(
    http_request: Request,
    cms_service: Any = Depends(get_cms_service),
) -> dict[str, str]:
    """Public Webflow webhook receiver for incremental CMS sync."""
    body = await http_request.body()
    signature = http_request.headers.get("x-webflow-signature", "")
    timestamp = http_request.headers.get("x-webflow-timestamp", "")

    if not cms_service.verify_incoming_webflow_webhook(
        timestamp=timestamp,
        body=body,
        signature=signature,
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        import json

        event = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    if isinstance(event, dict):
        await cms_service.handle_webflow_webhook_event(event)

    return {"status": "ok"}
