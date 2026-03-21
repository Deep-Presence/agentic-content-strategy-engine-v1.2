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

from core.auth.service import AuthServiceProtocol
from core.services.brand_data import BrandDataServiceProtocol
from core.services.content_data import ContentDataServiceProtocol
from core.services.gap_data import GapDataServiceProtocol
from core.services.kb_data import KBDataServiceProtocol
from core.services.persona_data import PersonaDataServiceProtocol
from core.services.site_audit_data import SiteAuditDataServiceProtocol
from core.services.topic_discovery_data import TopicDiscoveryDataServiceProtocol
from core.services.vsg_data import VSGDataServiceProtocol
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

    def test_site_audit_protocol_methods(self):
        expected = {
            "get_audit_summary", "get_audit_detail", "list_audits",
            "get_findings", "get_page_results", "audit_exists",
            "get_latest_audit_id",
        }
        from core.services.json_site_audit_data import JsonSiteAuditDataService
        from core.services.db_site_audit_data import DbSiteAuditDataService

        for cls in (JsonSiteAuditDataService, DbSiteAuditDataService):
            for method in expected:
                assert hasattr(cls, method), f"{cls.__name__} missing {method}"

    def test_auth_protocol_methods(self):
        expected = {
            "get_company_by_slug", "get_company_by_id", "get_company_by_domain",
            "list_companies", "create_company", "update_company",
            "get_product", "add_product", "update_product", "remove_product",
            "get_user_by_email", "get_user_by_id", "list_users_for_company",
            "create_user", "update_user",
            "register_user", "create_invite", "redeem_invite",
            "get_pipeline_defaults", "update_pipeline_defaults",
            "create_access_token", "create_stream_token", "verify_token",
        }
        from core.auth.json_service import JsonAuthService
        from core.auth.db_service import DbAuthService

        for cls in (JsonAuthService, DbAuthService):
            for method in expected:
                assert hasattr(cls, method), f"{cls.__name__} missing {method}"


# ── SiteAuditDataServiceProtocol ──────────────────────────────────────


class TestSiteAuditDataProtocol:
    """Verify both implementations satisfy SiteAuditDataServiceProtocol."""

    def test_json_site_audit_data_is_protocol(self):
        from core.services.json_site_audit_data import JsonSiteAuditDataService

        instance = JsonSiteAuditDataService(artifacts_root=Path("/tmp"))
        assert isinstance(instance, SiteAuditDataServiceProtocol)

    def test_db_site_audit_data_is_protocol(self):
        from core.services.db_site_audit_data import DbSiteAuditDataService

        instance = DbSiteAuditDataService(
            audit_repo=MagicMock(),
            company_repo=MagicMock(),
            artifacts_root=Path("/tmp"),
        )
        assert isinstance(instance, SiteAuditDataServiceProtocol)


# ── AuthServiceProtocol ──────────────────────────────────────────────


class TestAuthServiceProtocol:
    """Verify both implementations satisfy AuthServiceProtocol."""

    def test_json_auth_service_is_protocol(self):
        from core.auth.json_service import JsonAuthService

        instance = JsonAuthService(store=MagicMock())
        assert isinstance(instance, AuthServiceProtocol)

    def test_db_auth_service_is_protocol(self):
        from core.auth.db_service import DbAuthService

        instance = DbAuthService(
            company_repo=MagicMock(),
            auth_repo=MagicMock(),
            invite_repo=MagicMock(),
            product_repo=MagicMock(),
            defaults_repo=MagicMock(),
            secret_key="test-secret",
        )
        assert isinstance(instance, AuthServiceProtocol)


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


# ── KBDataServiceProtocol ────────────────────────────────────────────


class TestKBDataProtocol:
    """Verify both implementations satisfy KBDataServiceProtocol."""

    def test_json_is_protocol(self):
        from core.services.json_kb_data import JsonKBDataService

        instance = JsonKBDataService(artifacts_root=Path("/tmp"))
        assert isinstance(instance, KBDataServiceProtocol)

    def test_db_is_protocol(self):
        from core.services.db_kb_data import DbKBDataService

        instance = DbKBDataService(
            kb_run_repo=MagicMock(),
            kb_doc_repo=MagicMock(),
            kb_synth_repo=MagicMock(),
            pipeline_repo=MagicMock(),
            artifacts_root=Path("/tmp"),
        )
        assert isinstance(instance, KBDataServiceProtocol)

    def test_protocol_methods(self):
        expected = {"get_summary", "get_doc", "get_synthesis", "get_health", "get_staleness_report"}
        from core.services.json_kb_data import JsonKBDataService
        from core.services.db_kb_data import DbKBDataService

        for cls in (JsonKBDataService, DbKBDataService):
            for method in expected:
                assert hasattr(cls, method), f"{cls.__name__} missing {method}"


# ── PersonaDataServiceProtocol ──────────────────────────────────────


class TestPersonaDataProtocol:
    """Verify both implementations satisfy PersonaDataServiceProtocol."""

    def test_json_is_protocol(self):
        from core.services.json_persona_data import JsonPersonaDataService

        instance = JsonPersonaDataService(artifacts_root=Path("/tmp"))
        assert isinstance(instance, PersonaDataServiceProtocol)

    def test_db_is_protocol(self):
        from core.services.db_persona_data import DbPersonaDataService

        instance = DbPersonaDataService(
            persona_run_repo=MagicMock(),
            persona_profile_repo=MagicMock(),
            pipeline_repo=MagicMock(),
            artifacts_root=Path("/tmp"),
        )
        assert isinstance(instance, PersonaDataServiceProtocol)

    def test_protocol_methods(self):
        expected = {"list_personas", "get_persona", "get_summary", "check_staleness"}
        from core.services.json_persona_data import JsonPersonaDataService
        from core.services.db_persona_data import DbPersonaDataService

        for cls in (JsonPersonaDataService, DbPersonaDataService):
            for method in expected:
                assert hasattr(cls, method), f"{cls.__name__} missing {method}"


# ── VSGDataServiceProtocol ──────────────────────────────────────────


class TestVSGDataProtocol:
    """Verify both implementations satisfy VSGDataServiceProtocol."""

    def test_json_is_protocol(self):
        from core.services.json_vsg_data import JsonVSGDataService

        instance = JsonVSGDataService(artifacts_root=Path("/tmp"))
        assert isinstance(instance, VSGDataServiceProtocol)

    def test_db_is_protocol(self):
        from core.services.db_vsg_data import DbVSGDataService

        instance = DbVSGDataService(
            vsg_run_repo=MagicMock(),
            vsg_author_repo=MagicMock(),
            vsg_guide_repo=MagicMock(),
            pipeline_repo=MagicMock(),
            artifacts_root=Path("/tmp"),
        )
        assert isinstance(instance, VSGDataServiceProtocol)

    def test_protocol_methods(self):
        expected = {"get_summary", "get_guide", "list_authors", "get_author_research"}
        from core.services.json_vsg_data import JsonVSGDataService
        from core.services.db_vsg_data import DbVSGDataService

        for cls in (JsonVSGDataService, DbVSGDataService):
            for method in expected:
                assert hasattr(cls, method), f"{cls.__name__} missing {method}"


# ── TopicDiscoveryDataServiceProtocol ───────────────────────────────


class TestTopicDiscoveryDataProtocol:
    """Verify both implementations satisfy TopicDiscoveryDataServiceProtocol."""

    def test_json_is_protocol(self):
        from core.services.json_topic_discovery_data import JsonTopicDiscoveryDataService

        instance = JsonTopicDiscoveryDataService(artifacts_root=Path("/tmp"))
        assert isinstance(instance, TopicDiscoveryDataServiceProtocol)

    def test_db_is_protocol(self):
        from core.services.db_topic_discovery_data import DbTopicDiscoveryDataService

        instance = DbTopicDiscoveryDataService(
            td_repo=MagicMock(),
            taxonomy_repo=MagicMock(),
            assignment_repo=MagicMock(),
            artifacts_root=Path("/tmp"),
        )
        assert isinstance(instance, TopicDiscoveryDataServiceProtocol)

    def test_protocol_methods(self):
        expected = {
            "get_discovery_summary", "get_taxonomy", "get_matrix",
            "list_assignments", "get_scored_subdomains", "get_persona_affinity",
        }
        from core.services.json_topic_discovery_data import JsonTopicDiscoveryDataService
        from core.services.db_topic_discovery_data import DbTopicDiscoveryDataService

        for cls in (JsonTopicDiscoveryDataService, DbTopicDiscoveryDataService):
            for method in expected:
                assert hasattr(cls, method), f"{cls.__name__} missing {method}"


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

    def test_get_auth_service_annotation_is_protocol(self):
        """get_auth_service return annotation yields AuthServiceProtocol."""
        from collections.abc import AsyncGenerator
        from typing import get_args, get_origin, get_type_hints

        from api.dependencies import get_auth_service

        hints = get_type_hints(get_auth_service)
        ret = hints["return"]
        # Now an AsyncGenerator[AuthServiceProtocol, None]
        assert get_origin(ret) is AsyncGenerator
        assert get_args(ret)[0] is AuthServiceProtocol

    def test_get_site_audit_data_service_annotation_is_protocol(self):
        """get_site_audit_data_service return annotation yields SiteAuditDataServiceProtocol."""
        from collections.abc import AsyncGenerator
        from typing import get_args, get_origin, get_type_hints

        from api.dependencies import get_site_audit_data_service

        hints = get_type_hints(get_site_audit_data_service)
        ret = hints["return"]
        assert get_origin(ret) is AsyncGenerator
        assert get_args(ret)[0] is SiteAuditDataServiceProtocol

    def test_get_kb_data_service_annotation_is_protocol(self):
        from collections.abc import AsyncGenerator
        from typing import get_args, get_origin, get_type_hints

        from api.dependencies import get_kb_data_service

        hints = get_type_hints(get_kb_data_service)
        ret = hints["return"]
        assert get_origin(ret) is AsyncGenerator
        assert get_args(ret)[0] is KBDataServiceProtocol

    def test_get_persona_data_service_annotation_is_protocol(self):
        from collections.abc import AsyncGenerator
        from typing import get_args, get_origin, get_type_hints

        from api.dependencies import get_persona_data_service

        hints = get_type_hints(get_persona_data_service)
        ret = hints["return"]
        assert get_origin(ret) is AsyncGenerator
        assert get_args(ret)[0] is PersonaDataServiceProtocol

    def test_get_vsg_data_service_annotation_is_protocol(self):
        from collections.abc import AsyncGenerator
        from typing import get_args, get_origin, get_type_hints

        from api.dependencies import get_vsg_data_service

        hints = get_type_hints(get_vsg_data_service)
        ret = hints["return"]
        assert get_origin(ret) is AsyncGenerator
        assert get_args(ret)[0] is VSGDataServiceProtocol

    def test_get_td_data_service_annotation_is_protocol(self):
        from collections.abc import AsyncGenerator
        from typing import get_args, get_origin, get_type_hints

        from api.dependencies import get_td_data_service

        hints = get_type_hints(get_td_data_service)
        ret = hints["return"]
        assert get_origin(ret) is AsyncGenerator
        assert get_args(ret)[0] is TopicDiscoveryDataServiceProtocol
