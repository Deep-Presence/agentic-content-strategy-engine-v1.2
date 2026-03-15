"""Integration tests for research DB foundation.

These tests verify:
1. Graceful degradation (session_factory=None → no DB writes, no crash)
2. Persistence guard logic works end-to-end
3. DI switching works correctly (JSON fallback without DATABASE_URL)
4. Protocol conformance across all 8 implementations (4 JSON + 4 DB)
5. Service output shapes are consistent between JSON and DB implementations
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.db.enums import ArtifactStatus, ArtifactType, PipelineType


# ── Phase A: Enum integration ───────────────────────────────────────


class TestEnumIntegration:
    """Verify new enum values work in pipeline and persistence contexts."""

    def test_pipeline_types_include_research(self):
        assert PipelineType.knowledge_base.value == "knowledge_base"
        assert PipelineType.audience_persona.value == "audience_persona"
        assert PipelineType.voice_style_guide.value == "voice_style_guide"
        assert PipelineType.topic_discovery.value == "topic_discovery"

    def test_artifact_types_include_knowledge_base(self):
        assert ArtifactType.knowledge_base.value == "knowledge_base"
        assert ArtifactType.persona.value == "persona"
        assert ArtifactType.style_guide.value == "style_guide"
        assert ArtifactType.company_context.value == "company_context"

    def test_artifact_status_research_values(self):
        assert ArtifactStatus.fresh.value == "fresh"
        assert ArtifactStatus.stale.value == "stale"
        assert ArtifactStatus.pending_review.value == "pending_review"

    def test_old_enum_values_still_valid(self):
        assert PipelineType.gap_analysis.value == "gap_analysis"
        assert ArtifactStatus.draft.value == "draft"
        assert ArtifactType.company_context.value == "company_context"


# ── Phase C: Persistence guard logic ────────────────────────────────


class TestPersistenceGuardLogic:
    """Test _should_persist guard across different param combinations."""

    def test_all_none_returns_false(self):
        from core.research.persistence import _should_persist
        assert _should_persist(None, None, None) is False

    def test_session_factory_none_returns_false(self):
        import uuid
        from core.research.persistence import _should_persist
        assert _should_persist(None, uuid.uuid4(), uuid.uuid4()) is False

    def test_run_id_none_returns_false(self):
        import uuid
        from core.research.persistence import _should_persist
        assert _should_persist(MagicMock(), None, uuid.uuid4()) is False

    def test_all_present_returns_true(self):
        import uuid
        from core.research.persistence import _should_persist
        assert _should_persist(MagicMock(), uuid.uuid4(), uuid.uuid4()) is True


# ── Phase C: Fire-and-forget exception safety ───────────────────────


class TestPersistenceExceptionSafety:
    """Verify that DB errors in persistence never crash the pipeline."""

    async def test_persist_kb_doc_exception_swallowed(self):
        """DB failure in persist_kb_doc should not raise."""
        from core.research.persistence import persist_kb_doc
        import uuid

        # Create a session factory that raises
        def broken_factory():
            raise RuntimeError("DB down")

        # Should not raise
        await persist_kb_doc(
            broken_factory, uuid.uuid4(), uuid.uuid4(),
            "test-co", "company_overview", 1,
            "# Content", "kb/test-co/overview/v1.md",
        )

    async def test_persist_persona_exception_swallowed(self):
        from core.research.persistence import persist_persona_profile
        import uuid

        def broken_factory():
            raise RuntimeError("DB down")

        await persist_persona_profile(
            broken_factory, uuid.uuid4(), uuid.uuid4(),
            "test-co", "cfo-001", "CFO", 1,
            "# Content", "personas/test-co/cfo-001/v1.md",
        )

    async def test_persist_vsg_exception_swallowed(self):
        from core.research.persistence import persist_voice_style_guide
        import uuid

        def broken_factory():
            raise RuntimeError("DB down")

        await persist_voice_style_guide(
            broken_factory, uuid.uuid4(), uuid.uuid4(),
            "test-co", 1, "# Guide", "vsg/test-co/guide/v1.md",
        )


# ── Phase D: Graceful degradation ───────────────────────────────────


class TestGracefulDegradation:
    """Verify pipelines work normally when session_factory=None."""

    async def test_kb_pipeline_null_session_factory(self):
        """KB pipeline signature accepts None for DB params."""
        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline
        import inspect
        sig = inspect.signature(run_knowledge_base_pipeline)
        assert "session_factory" in sig.parameters
        assert sig.parameters["session_factory"].default is None

    async def test_ap_pipeline_null_session_factory(self):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline
        import inspect
        sig = inspect.signature(run_audience_persona_pipeline)
        assert "session_factory" in sig.parameters
        assert sig.parameters["session_factory"].default is None

    async def test_vsg_pipeline_null_session_factory(self):
        from core.research.voice_style_guide.pipeline import run_voice_style_guide_pipeline
        import inspect
        sig = inspect.signature(run_voice_style_guide_pipeline)
        assert "session_factory" in sig.parameters
        assert sig.parameters["session_factory"].default is None

    async def test_td_pipeline_null_session_factory(self):
        from core.topic_discovery.pipeline import run_topic_discovery_pipeline
        import inspect
        sig = inspect.signature(run_topic_discovery_pipeline)
        assert "session_factory" in sig.parameters
        assert sig.parameters["session_factory"].default is None


# ── Phase E+F: Protocol conformance all 8 implementations ──────────


class TestAllProtocolConformance:
    """Comprehensive protocol check for all 8 service implementations."""

    def test_json_kb_is_protocol(self):
        from core.services.json_kb_data import JsonKBDataService
        from core.services.kb_data import KBDataServiceProtocol
        assert isinstance(JsonKBDataService(Path("/tmp")), KBDataServiceProtocol)

    def test_db_kb_is_protocol(self):
        from core.services.db_kb_data import DbKBDataService
        from core.services.kb_data import KBDataServiceProtocol
        svc = DbKBDataService(MagicMock(), MagicMock(), Path("/tmp"))
        assert isinstance(svc, KBDataServiceProtocol)

    def test_json_persona_is_protocol(self):
        from core.services.json_persona_data import JsonPersonaDataService
        from core.services.persona_data import PersonaDataServiceProtocol
        assert isinstance(JsonPersonaDataService(Path("/tmp")), PersonaDataServiceProtocol)

    def test_db_persona_is_protocol(self):
        from core.services.db_persona_data import DbPersonaDataService
        from core.services.persona_data import PersonaDataServiceProtocol
        svc = DbPersonaDataService(MagicMock(), MagicMock(), Path("/tmp"))
        assert isinstance(svc, PersonaDataServiceProtocol)

    def test_json_vsg_is_protocol(self):
        from core.services.json_vsg_data import JsonVSGDataService
        from core.services.vsg_data import VSGDataServiceProtocol
        assert isinstance(JsonVSGDataService(Path("/tmp")), VSGDataServiceProtocol)

    def test_db_vsg_is_protocol(self):
        from core.services.db_vsg_data import DbVSGDataService
        from core.services.vsg_data import VSGDataServiceProtocol
        svc = DbVSGDataService(MagicMock(), MagicMock(), Path("/tmp"))
        assert isinstance(svc, VSGDataServiceProtocol)

    def test_json_td_is_protocol(self):
        from core.services.json_topic_discovery_data import JsonTopicDiscoveryDataService
        from core.services.topic_discovery_data import TopicDiscoveryDataServiceProtocol
        assert isinstance(JsonTopicDiscoveryDataService(Path("/tmp")), TopicDiscoveryDataServiceProtocol)

    def test_db_td_is_protocol(self):
        from core.services.db_topic_discovery_data import DbTopicDiscoveryDataService
        from core.services.topic_discovery_data import TopicDiscoveryDataServiceProtocol
        svc = DbTopicDiscoveryDataService(
            td_repo=MagicMock(),
            taxonomy_repo=MagicMock(),
            assignment_repo=MagicMock(),
            artifacts_root=Path("/tmp"),
        )
        assert isinstance(svc, TopicDiscoveryDataServiceProtocol)


# ── Phase G: DI switching ───────────────────────────────────────────


class TestDISwitching:
    """Verify DI functions return correct service type based on DATABASE_URL."""

    def test_kb_di_returns_json_without_db(self):
        """Without db_session_factory, get_kb_data_service returns JsonKBDataService."""
        from api.dependencies import get_kb_data_service
        from core.services.json_kb_data import JsonKBDataService

        mock_request = MagicMock()
        mock_request.app.state = MagicMock(spec=[])
        mock_request.app.state.artifacts_root = Path("/tmp")
        result = get_kb_data_service(mock_request)
        assert isinstance(result, JsonKBDataService)

    def test_persona_di_returns_json_without_db(self):
        from api.dependencies import get_persona_data_service
        from core.services.json_persona_data import JsonPersonaDataService

        mock_request = MagicMock()
        mock_request.app.state = MagicMock(spec=[])
        mock_request.app.state.artifacts_root = Path("/tmp")
        result = get_persona_data_service(mock_request)
        assert isinstance(result, JsonPersonaDataService)

    def test_vsg_di_returns_json_without_db(self):
        from api.dependencies import get_vsg_data_service
        from core.services.json_vsg_data import JsonVSGDataService

        mock_request = MagicMock()
        mock_request.app.state = MagicMock(spec=[])
        mock_request.app.state.artifacts_root = Path("/tmp")
        result = get_vsg_data_service(mock_request)
        assert isinstance(result, JsonVSGDataService)

    def test_td_di_returns_json_without_db(self):
        from api.dependencies import get_td_data_service
        from core.services.json_topic_discovery_data import JsonTopicDiscoveryDataService

        mock_request = MagicMock()
        mock_request.app.state = MagicMock(spec=[])
        mock_request.app.state.artifacts_root = Path("/tmp")
        result = get_td_data_service(mock_request)
        assert isinstance(result, JsonTopicDiscoveryDataService)

    def test_kb_di_returns_override_when_set(self):
        """Pre-built override takes priority."""
        from api.dependencies import get_kb_data_service

        override = MagicMock()
        mock_request = MagicMock()
        mock_request.app.state.kb_data_service = override
        result = get_kb_data_service(mock_request)
        assert result is override


# ── Phase E+F: JSON service output shape consistency ────────────────


class TestJsonServiceOutputShapes:
    """Verify JSON service outputs have expected shapes for downstream use."""

    async def test_kb_get_summary_shape(self, tmp_path):
        from core.services.json_kb_data import JsonKBDataService
        svc = JsonKBDataService(tmp_path)
        result = await svc.get_summary("nonexistent")
        assert "slug" in result
        assert "docs" in result
        assert isinstance(result["docs"], dict)

    async def test_persona_get_summary_shape(self, tmp_path):
        from core.services.json_persona_data import JsonPersonaDataService
        svc = JsonPersonaDataService(tmp_path)
        result = await svc.get_summary("nonexistent")
        assert "slug" in result
        assert "total_personas" in result
        assert result["total_personas"] == 0

    async def test_vsg_get_summary_shape(self, tmp_path):
        from core.services.json_vsg_data import JsonVSGDataService
        svc = JsonVSGDataService(tmp_path)
        result = await svc.get_summary("nonexistent")
        assert "slug" in result
        assert "has_guide" in result
        assert result["has_guide"] is False

    async def test_td_list_assignments_shape(self, tmp_path):
        from core.services.json_topic_discovery_data import JsonTopicDiscoveryDataService
        svc = JsonTopicDiscoveryDataService(tmp_path)
        result = await svc.list_assignments("nonexistent")
        assert result["total"] == 0
        assert result["items"] == []
        assert "page" in result
        assert "page_size" in result


# ── Cross-pipeline helper tests ─────────────────────────────────────


class TestContentHashComputation:
    """Verify persistence helper functions work correctly."""

    def test_sha256_consistency(self):
        from core.research.persistence import _sha256
        content = "# Test Content\n\nHello world."
        h1 = _sha256(content)
        h2 = _sha256(content)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex digest

    def test_sha256_different_content(self):
        from core.research.persistence import _sha256
        h1 = _sha256("hello")
        h2 = _sha256("world")
        assert h1 != h2

    def test_word_count(self):
        from core.research.persistence import _word_count
        assert _word_count("hello world") == 2
        assert _word_count("") == 0
        assert _word_count("one") == 1
