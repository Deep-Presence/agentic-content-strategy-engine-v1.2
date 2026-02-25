"""FastAPI dependency injection helpers."""
from __future__ import annotations

from pathlib import Path

from fastapi import Request

from api.auth.store import AuthStore
from api.tasks.event_bus import EventBus
from api.tasks.store import TaskStore


def get_task_store(request: Request) -> TaskStore:
    return request.app.state.task_store


def get_event_bus(request: Request) -> EventBus:
    return request.app.state.event_bus


def get_artifacts_root(request: Request) -> Path:
    return request.app.state.artifacts_root


def get_auth_store(request: Request) -> AuthStore:
    return request.app.state.auth_store
