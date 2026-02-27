"""FastAPI dependency injection helpers."""
from __future__ import annotations

from pathlib import Path

from fastapi import Request

from api.auth.store import AuthStore
from api.tasks.event_bus import EventBus
from api.tasks.store import TaskStore
from core.auth.json_service import JsonAuthService
from core.auth.service import AuthServiceProtocol


def get_task_store(request: Request) -> TaskStore:
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
