"""Protocol conformance tests for service layer.

These tests verify that both Json and Db implementations
satisfy their respective Protocol interfaces.
No DB required — uses isinstance checks only.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.services.gap_data import GapDataServiceProtocol
from core.services.brand_data import BrandDataServiceProtocol
from core.services.content_data import ContentDataServiceProtocol
from core.services.task_store import TaskStoreProtocol


# ── GapDataServiceProtocol ────────────────────────────────────────────


class TestGapDataProtocol:
    """Verify both implementations satisfy GapDataServiceProtocol."""

    def test_json_gap_data_is_protocol(self):
        from core.services.json_gap_data import JsonGapDataService

        instance = JsonGapDataService(
            artifacts_root=Path("/tmp"),
            task_store=MagicMock(),
        )
        assert isinstance(instance, GapDataServiceProtocol)

    def test_db_gap_data_is_protocol(self):
        from core.services.db_gap_data import DbGapDataService

        instance = DbGapDataService(
            gap_repo=MagicMock(),
            pipeline_repo=MagicMock(),
            signal_repo=MagicMock(),
            platform_repo=MagicMock(),
            artifacts_root=Path("/tmp"),
        )
        assert isinstance(instance, GapDataServiceProtocol)


# ── BrandDataServiceProtocol ──────────────────────────────────────────


class TestBrandDataProtocol:
    """Verify both implementations satisfy BrandDataServiceProtocol."""

    def test_json_brand_data_is_protocol(self):
        from core.services.json_brand_data import JsonBrandDataService

        instance = JsonBrandDataService(
            artifacts_root=Path("/tmp"),
            task_store=MagicMock(),
        )
        assert isinstance(instance, BrandDataServiceProtocol)

    def test_db_brand_data_is_protocol(self):
        from core.services.db_brand_data import DbBrandDataService

        instance = DbBrandDataService(
            pipeline_repo=MagicMock(),
            artifacts_root=Path("/tmp"),
        )
        assert isinstance(instance, BrandDataServiceProtocol)


# ── ContentDataServiceProtocol ────────────────────────────────────────


class TestContentDataProtocol:
    """Verify both implementations satisfy ContentDataServiceProtocol."""

    def test_json_content_data_is_protocol(self):
        from core.services.json_content_data import JsonContentDataService

        instance = JsonContentDataService(
            artifacts_root=Path("/tmp"),
        )
        assert isinstance(instance, ContentDataServiceProtocol)

    def test_db_content_data_is_protocol(self):
        from core.services.db_content_data import DbContentDataService

        instance = DbContentDataService(
            content_repo=MagicMock(),
            pipeline_repo=MagicMock(),
            artifacts_root=Path("/tmp"),
        )
        assert isinstance(instance, ContentDataServiceProtocol)


# ── Protocol method completeness ──────────────────────────────────────


class TestProtocolCompleteness:
    """Ensure all protocol methods exist on implementations."""

    def test_gap_protocol_methods(self):
        expected = {
            "get_summary", "get_queries", "get_clusters", "get_signals",
            "get_platforms", "get_heatmap", "get_embedding_projection",
            "get_spa_trend",
        }
        from core.services.json_gap_data import JsonGapDataService
        from core.services.db_gap_data import DbGapDataService

        for cls in (JsonGapDataService, DbGapDataService):
            for method in expected:
                assert hasattr(cls, method), f"{cls.__name__} missing {method}"

    def test_brand_protocol_methods(self):
        expected = {"get_research_artifacts", "get_run_history"}
        from core.services.json_brand_data import JsonBrandDataService
        from core.services.db_brand_data import DbBrandDataService

        for cls in (JsonBrandDataService, DbBrandDataService):
            for method in expected:
                assert hasattr(cls, method), f"{cls.__name__} missing {method}"

    def test_content_protocol_methods(self):
        expected = {"get_briefs", "get_brief_detail", "get_brief_stage_content"}
        from core.services.json_content_data import JsonContentDataService
        from core.services.db_content_data import DbContentDataService

        for cls in (JsonContentDataService, DbContentDataService):
            for method in expected:
                assert hasattr(cls, method), f"{cls.__name__} missing {method}"


# ── TaskStoreProtocol ────────────────────────────────────────────────


class TestTaskStoreProtocol:
    """Verify TaskStore satisfies TaskStoreProtocol."""

    def test_task_store_is_protocol(self, tmp_path: Path):
        from api.tasks.event_bus import EventBus
        from api.tasks.store import TaskStore

        instance = TaskStore(
            base_dir=tmp_path / "_jobs",
            event_bus=EventBus(),
        )
        assert isinstance(instance, TaskStoreProtocol)

    def test_task_store_protocol_methods(self):
        expected = {
            "semaphore", "create_task", "get_task", "update_task",
            "list_tasks", "acquire_slug_lock", "release_slug_lock",
            "register_task_handle", "cancel_task_handle", "remove_task_handle",
            "wait_for_approval", "submit_approval",
        }
        from api.tasks.store import TaskStore

        for method in expected:
            assert hasattr(TaskStore, method), f"TaskStore missing {method}"

    def test_db_task_store_is_protocol(self):
        from core.services.db_task_store import DbTaskStore

        instance = DbTaskStore(session_factory=MagicMock())
        assert isinstance(instance, TaskStoreProtocol)

    def test_db_task_store_protocol_methods(self):
        expected = {
            "semaphore", "create_task", "get_task", "update_task",
            "list_tasks", "acquire_slug_lock", "release_slug_lock",
            "register_task_handle", "cancel_task_handle", "remove_task_handle",
            "wait_for_approval", "submit_approval",
        }
        from core.services.db_task_store import DbTaskStore

        for method in expected:
            assert hasattr(DbTaskStore, method), f"DbTaskStore missing {method}"


# ── DI wiring ──────────────────────────────────────────────────────


class TestDIWiring:
    """Verify get_task_store returns TaskStoreProtocol."""

    def test_get_task_store_returns_protocol(self, tmp_path: Path):
        """DI helper returns an object satisfying TaskStoreProtocol."""
        from fastapi.testclient import TestClient

        from api.app import create_app
        from api.tasks.event_bus import EventBus
        from api.tasks.store import TaskStore

        app = create_app()
        store = TaskStore(base_dir=tmp_path / "_jobs", event_bus=EventBus())
        app.state.task_store = store
        assert isinstance(store, TaskStoreProtocol)

    def test_get_task_store_annotation_is_protocol(self):
        """get_task_store return annotation is TaskStoreProtocol."""
        from typing import get_type_hints

        from api.dependencies import get_task_store

        hints = get_type_hints(get_task_store)
        assert hints["return"] is TaskStoreProtocol
