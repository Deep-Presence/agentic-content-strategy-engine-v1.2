"""FastAPI dependency injection helpers."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import Request

from api.auth.store import AuthStore
from api.tasks.event_bus import EventBus
from core.auth.json_service import JsonAuthService
from core.auth.service import AuthServiceProtocol
from core.services.brand_data import BrandDataServiceProtocol
from core.services.content_data import ContentDataServiceProtocol
from core.services.gap_data import GapDataServiceProtocol
from core.services.json_brand_data import JsonBrandDataService
from core.services.json_content_data import JsonContentDataService
from core.services.json_gap_data import JsonGapDataService
from core.services.json_site_audit_data import JsonSiteAuditDataService
from core.services.site_audit_data import SiteAuditDataServiceProtocol
from core.services.task_store import TaskStoreProtocol

_logger = logging.getLogger(__name__)


def get_task_store(request: Request) -> TaskStoreProtocol:
    """Return the task store — JSON-backed TaskStore or DbTaskStore.

    When DATABASE_URL is configured, this will return DbTaskStore.
    For now, always returns the JSON-backed TaskStore.
    """
    return request.app.state.task_store


def get_event_bus(request: Request) -> EventBus:
    return request.app.state.event_bus


def get_artifacts_root(request: Request) -> Path:
    return request.app.state.artifacts_root


def get_auth_store(request: Request) -> AuthStore:
    return request.app.state.auth_store


def get_auth_service(request: Request) -> AuthServiceProtocol:
    """Return the auth service — JsonAuthService wrapping AuthStore.

    When DATABASE_URL is configured, this will return DbAuthService.
    For now, always returns JsonAuthService wrapping the existing AuthStore.
    """
    # Check if a pre-built service is available (e.g., from dependency override)
    service = getattr(request.app.state, "auth_service", None)
    if service is not None:
        return service
    # Default: wrap the existing AuthStore
    return JsonAuthService(request.app.state.auth_store)


def _build_db_gap_data_service(request: Request) -> GapDataServiceProtocol | None:
    """Try to build a per-request DbGapDataService.

    Returns None if db_session_factory is not available or import fails.
    """
    sf = getattr(request.app.state, "db_session_factory", None)
    if sf is None:
        return None
    try:
        from core.db.repositories.gap_analysis_repo import GapAnalysisRepository
        from core.db.repositories.pipeline_repo import PipelineRepository
        from core.db.repositories.platform_repo import PlatformRepository
        from core.db.repositories.signal_repo import SignalRepository
        from core.services.db_gap_data import DbGapDataService

        session = sf()
        return DbGapDataService(
            gap_repo=GapAnalysisRepository(session),
            pipeline_repo=PipelineRepository(session),
            signal_repo=SignalRepository(session),
            platform_repo=PlatformRepository(session),
            artifacts_root=request.app.state.artifacts_root,
        )
    except Exception:
        _logger.debug("Failed to build DbGapDataService", exc_info=True)
        return None


def _build_db_brand_data_service(request: Request) -> BrandDataServiceProtocol | None:
    """Try to build a per-request DbBrandDataService."""
    sf = getattr(request.app.state, "db_session_factory", None)
    if sf is None:
        return None
    try:
        from core.db.repositories.pipeline_repo import PipelineRepository
        from core.services.db_brand_data import DbBrandDataService

        session = sf()
        return DbBrandDataService(
            pipeline_repo=PipelineRepository(session),
            artifacts_root=request.app.state.artifacts_root,
        )
    except Exception:
        _logger.debug("Failed to build DbBrandDataService", exc_info=True)
        return None


def _build_db_content_data_service(request: Request) -> ContentDataServiceProtocol | None:
    """Try to build a per-request DbContentDataService."""
    sf = getattr(request.app.state, "db_session_factory", None)
    if sf is None:
        return None
    try:
        from core.db.repositories.content_repo import ContentRepository
        from core.db.repositories.pipeline_repo import PipelineRepository
        from core.services.db_content_data import DbContentDataService

        session = sf()
        return DbContentDataService(
            content_repo=ContentRepository(session),
            pipeline_repo=PipelineRepository(session),
            artifacts_root=request.app.state.artifacts_root,
        )
    except Exception:
        _logger.debug("Failed to build DbContentDataService", exc_info=True)
        return None


def get_gap_data_service(request: Request) -> GapDataServiceProtocol:
    """Return the gap data service.

    Checks for a pre-built service on app.state (e.g., from dependency
    override in tests). When db_session_factory is available, constructs
    a per-request DbGapDataService. Falls back to JsonGapDataService.
    """
    # 1. Pre-built override (tests, etc.)
    service = getattr(request.app.state, "gap_data_service", None)
    if service is not None:
        return service
    # 2. Per-request DB service (when DATABASE_URL is set)
    db_service = _build_db_gap_data_service(request)
    if db_service is not None:
        return db_service
    # 3. Fallback: filesystem-backed
    return JsonGapDataService(
        artifacts_root=request.app.state.artifacts_root,
        task_store=request.app.state.task_store,
    )


def get_brand_data_service(request: Request) -> BrandDataServiceProtocol:
    """Return the brand data service.

    Per-request DbBrandDataService when DATABASE_URL set, else JsonBrandDataService.
    """
    service = getattr(request.app.state, "brand_data_service", None)
    if service is not None:
        return service
    db_service = _build_db_brand_data_service(request)
    if db_service is not None:
        return db_service
    return JsonBrandDataService(
        artifacts_root=request.app.state.artifacts_root,
        task_store=request.app.state.task_store,
    )


def get_content_data_service(request: Request) -> ContentDataServiceProtocol:
    """Return the content data service.

    Per-request DbContentDataService when DATABASE_URL set, else JsonContentDataService.
    """
    service = getattr(request.app.state, "content_data_service", None)
    if service is not None:
        return service
    db_service = _build_db_content_data_service(request)
    if db_service is not None:
        return db_service
    return JsonContentDataService(
        artifacts_root=request.app.state.artifacts_root,
    )


def get_site_audit_data_service(request: Request) -> SiteAuditDataServiceProtocol:
    """Return the site audit data service.

    Checks for a pre-built service on app.state (e.g., from dependency
    override in tests).  Falls back to JsonSiteAuditDataService which reads
    from artifacts/site_audit/{slug}/{audit_id}/audit_result.json.
    """
    service = getattr(request.app.state, "site_audit_data_service", None)
    if service is not None:
        return service
    return JsonSiteAuditDataService(
        artifacts_root=request.app.state.artifacts_root,
    )
