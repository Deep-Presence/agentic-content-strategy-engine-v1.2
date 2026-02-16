"""Shared fixtures for API tests."""
from __future__ import annotations

from pathlib import Path
from typing import AsyncGenerator

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from api.app import create_app
from api.tasks.event_bus import EventBus
from api.tasks.store import TaskStore


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def task_store(tmp_path: Path, event_bus: EventBus) -> TaskStore:
    return TaskStore(base_dir=tmp_path / "_jobs", event_bus=event_bus)


@pytest.fixture
def artifacts_root(tmp_path: Path) -> Path:
    root = tmp_path / "artifacts"
    root.mkdir(exist_ok=True)
    return root


@pytest.fixture
def app(task_store: TaskStore, event_bus: EventBus, artifacts_root: Path):
    application = create_app()
    application.state.task_store = task_store
    application.state.event_bus = event_bus
    application.state.artifacts_root = artifacts_root
    return application


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture
async def async_client(app) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
