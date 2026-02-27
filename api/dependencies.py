"""FastAPI dependency injection helpers."""
from __future__ import annotations

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
from core.services.task_store import TaskStoreProtocol


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


def get_gap_data_service(request: Request) -> GapDataServiceProtocol:
    """Return the gap data service.

    Checks for a pre-built service on app.state (e.g., from dependency
    override or DbGapDataService when DATABASE_URL is configured).
    Defaults to JsonGapDataService wrapping the filesystem functions.
    """
    service = getattr(request.app.state, "gap_data_service", None)
    if service is not None:
        return service
    return JsonGapDataService(
        artifacts_root=request.app.state.artifacts_root,
        task_store=request.app.state.task_store,
    )


def get_brand_data_service(request: Request) -> BrandDataServiceProtocol:
    """Return the brand data service.

    Defaults to JsonBrandDataService wrapping the filesystem + TaskStore.
    """
    service = getattr(request.app.state, "brand_data_service", None)
    if service is not None:
        return service
    return JsonBrandDataService(
        artifacts_root=request.app.state.artifacts_root,
        task_store=request.app.state.task_store,
    )


def get_content_data_service(request: Request) -> ContentDataServiceProtocol:
    """Return the content data service.

    Defaults to JsonContentDataService wrapping the filesystem functions.
    """
    service = getattr(request.app.state, "content_data_service", None)
    if service is not None:
        return service
    return JsonContentDataService(
        artifacts_root=request.app.state.artifacts_root,
    )
