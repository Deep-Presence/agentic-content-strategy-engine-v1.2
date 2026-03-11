"""Unit tests for core.research.orchestrator — Research Orchestrator (KB → AP → VSG).

Covers:
- Pydantic model instantiation, defaults, serialization, validation
- Skip logic helpers
- Core orchestrator flow with mocked sub-pipelines
- Error propagation
- Auto-approve distribution
- SSE event emission
- Edge cases (selective pipelines, all-skipped, HITL rejection)
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.research_orchestrator import (
    AutoApproveConfig,
    OrchestratorStatus,
    PipelineSkipConfig,
    ResearchOrchestratorInput,
    ResearchOrchestratorOutput,
    SubPipelineResult,
    SubPipelineStatus,
)
from core.research.orchestrator import (
    _build_ap_input,
    _build_kb_input,
    _build_vsg_input,
    _resolve_slugs,
    _should_skip_ap,
    _should_skip_kb,
    _should_skip_vsg,
    run_research_orchestrator,
)


# ═══════════════════════════════════════════════════════════════════════════
# Phase 1: Model Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestAutoApproveConfig:
    def test_defaults(self) -> None:
        cfg = AutoApproveConfig()
        assert cfg.kb == []
        assert cfg.ap == []
        assert cfg.vsg == []

    def test_with_values(self) -> None:
        cfg = AutoApproveConfig(kb=[1, 2, 3], ap=[1, 2], vsg=[1])
        assert cfg.kb == [1, 2, 3]
        assert cfg.ap == [1, 2]
        assert cfg.vsg == [1]

    def test_serialization_roundtrip(self) -> None:
        cfg = AutoApproveConfig(kb=[1, 3], ap=[2])
        data = cfg.model_dump(mode="json")
        restored = AutoApproveConfig.model_validate(data)
        assert restored == cfg


class TestPipelineSkipConfig:
    def test_defaults_all_true(self) -> None:
        cfg = PipelineSkipConfig()
        assert cfg.skip_kb_if_fresh is True
        assert cfg.skip_ap_if_fresh is True
        assert cfg.skip_vsg_if_fresh is True

    def test_override(self) -> None:
        cfg = PipelineSkipConfig(skip_kb_if_fresh=False)
        assert cfg.skip_kb_if_fresh is False
        assert cfg.skip_ap_if_fresh is True


class TestSubPipelineStatus:
    def test_enum_values(self) -> None:
        assert SubPipelineStatus.pending == "pending"
        assert SubPipelineStatus.running == "running"
        assert SubPipelineStatus.skipped == "skipped"
        assert SubPipelineStatus.completed == "completed"
        assert SubPipelineStatus.failed == "failed"


class TestSubPipelineResult:
    def test_defaults(self) -> None:
        r = SubPipelineResult()
        assert r.pipeline == ""
        assert r.status == SubPipelineStatus.pending
        assert r.skip_reason is None
        assert r.execution_time_s == 0.0
        assert r.error is None
        assert r.output_summary == {}

    def test_with_values(self) -> None:
        r = SubPipelineResult(
            pipeline="kb",
            status=SubPipelineStatus.completed,
            execution_time_s=12.5,
            output_summary={"synthesis_word_count": 500},
        )
        assert r.pipeline == "kb"
        assert r.status == SubPipelineStatus.completed
        assert r.output_summary["synthesis_word_count"] == 500

    def test_failed_with_error(self) -> None:
        r = SubPipelineResult(
            pipeline="ap",
            status=SubPipelineStatus.failed,
            error="Company context not found",
        )
        assert r.error == "Company context not found"

    def test_skipped_with_reason(self) -> None:
        r = SubPipelineResult(
            pipeline="vsg",
            status=SubPipelineStatus.skipped,
            skip_reason="Guide is fresh (v2)",
        )
        assert r.skip_reason == "Guide is fresh (v2)"


class TestOrchestratorStatus:
    def test_enum_values(self) -> None:
        assert OrchestratorStatus.completed == "completed"
        assert OrchestratorStatus.completed_partial == "completed_partial"
        assert OrchestratorStatus.failed == "failed"


class TestResearchOrchestratorInput:
    def test_minimal_required_fields(self) -> None:
        inp = ResearchOrchestratorInput(company_name="Test Co")
        assert inp.company_name == "Test Co"
        assert inp.domain == ""
        assert inp.pipelines == ["kb", "ap", "vsg"]
        assert inp.force_rerun is False
        assert inp.language == "en"
        assert inp.max_personas == 5
        assert inp.max_authors == 3

    def test_all_fields(self) -> None:
        inp = ResearchOrchestratorInput(
            company_name="Ramp",
            domain="ramp.com",
            company_slug="ramp",
            product_slug="expense-mgmt",
            product_name="Expense Management",
            seed_urls=["https://ramp.com/blog"],
            staleness_threshold_days=15,
            max_personas=4,
            max_authors=2,
            language="en",
            region="US",
            additional_constraints="Focus on fintech",
            force_rerun=True,
            auto_approve=AutoApproveConfig(kb=[1, 2, 3], ap=[1, 2], vsg=[1]),
            skip_config=PipelineSkipConfig(skip_kb_if_fresh=False),
            pipelines=["kb", "ap"],
        )
        assert inp.product_slug == "expense-mgmt"
        assert inp.auto_approve.kb == [1, 2, 3]
        assert inp.skip_config.skip_kb_if_fresh is False
        assert inp.pipelines == ["kb", "ap"]

    def test_selective_pipelines(self) -> None:
        inp = ResearchOrchestratorInput(
            company_name="Test", pipelines=["vsg"],
        )
        assert inp.pipelines == ["vsg"]

    def test_serialization_roundtrip(self) -> None:
        inp = ResearchOrchestratorInput(
            company_name="Test Co",
            domain="test.com",
            auto_approve=AutoApproveConfig(kb=[1, 2]),
            pipelines=["kb", "ap"],
        )
        data = inp.model_dump(mode="json")
        restored = ResearchOrchestratorInput.model_validate(data)
        assert restored.company_name == "Test Co"
        assert restored.auto_approve.kb == [1, 2]
        assert restored.pipelines == ["kb", "ap"]

    def test_max_personas_validation(self) -> None:
        with pytest.raises(Exception):
            ResearchOrchestratorInput(company_name="X", max_personas=1)
        with pytest.raises(Exception):
            ResearchOrchestratorInput(company_name="X", max_personas=10)


class TestResearchOrchestratorOutput:
    def test_defaults(self) -> None:
        out = ResearchOrchestratorOutput()
        assert out.slug == ""
        assert out.company_name == ""
        assert out.effective_slug == ""
        assert out.orchestrator_status == OrchestratorStatus.completed
        assert out.pipelines_run == []
        assert out.pipelines_skipped == []
        assert out.sub_results == {}
        assert out.total_execution_time_s == 0.0
        assert out.company_context_path is None
        assert out.persona_dir is None
        assert out.style_guide_path is None

    def test_with_sub_results(self) -> None:
        out = ResearchOrchestratorOutput(
            slug="test-co",
            company_name="Test Co",
            effective_slug="test-co",
            orchestrator_status=OrchestratorStatus.completed_partial,
            pipelines_run=["kb", "ap"],
            pipelines_skipped=["vsg"],
            sub_results={
                "kb": SubPipelineResult(
                    pipeline="kb", status=SubPipelineStatus.completed,
                ),
                "ap": SubPipelineResult(
                    pipeline="ap", status=SubPipelineStatus.completed,
                ),
                "vsg": SubPipelineResult(
                    pipeline="vsg",
                    status=SubPipelineStatus.skipped,
                    skip_reason="fresh",
                ),
            },
        )
        assert out.orchestrator_status == OrchestratorStatus.completed_partial
        assert len(out.sub_results) == 3

    def test_serialization_roundtrip(self) -> None:
        out = ResearchOrchestratorOutput(
            slug="test-co",
            orchestrator_status=OrchestratorStatus.failed,
            sub_results={
                "kb": SubPipelineResult(
                    pipeline="kb",
                    status=SubPipelineStatus.failed,
                    error="boom",
                ),
            },
        )
        data = out.model_dump(mode="json")
        restored = ResearchOrchestratorOutput.model_validate(data)
        assert restored.orchestrator_status == OrchestratorStatus.failed
        assert restored.sub_results["kb"].error == "boom"


# ═══════════════════════════════════════════════════════════════════════════
# Phase 2: Slug Resolution
# ═══════════════════════════════════════════════════════════════════════════


class TestResolveSlug:
    def test_company_only(self) -> None:
        inp = ResearchOrchestratorInput(company_name="Test Co")
        company, effective = _resolve_slugs(inp)
        assert company == "test-co"
        assert effective == "test-co"

    def test_with_product(self) -> None:
        inp = ResearchOrchestratorInput(
            company_name="Ramp", product_slug="expense",
        )
        company, effective = _resolve_slugs(inp)
        assert company == "ramp"
        assert effective == "ramp__expense"

    def test_explicit_company_slug(self) -> None:
        inp = ResearchOrchestratorInput(
            company_name="Ramp", company_slug="ramp-inc",
        )
        company, effective = _resolve_slugs(inp)
        assert company == "ramp-inc"
        assert effective == "ramp-inc"


# ═══════════════════════════════════════════════════════════════════════════
# Phase 2: Skip Logic Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSkipKB:
    def test_skip_when_fresh(self, tmp_path: Path) -> None:
        """KB skipped when synthesis exists and no stale/missing docs."""
        from core.models.knowledge_base import KBDocEntry, KBDocType, KBManifest
        from core.research.knowledge_base.storage import KBStorage

        storage = KBStorage(tmp_path, "test-co")
        # Write a manifest with synthesis > 0 and all docs present
        manifest = KBManifest(slug="test-co", synthesis_version=2)
        for dt in KBDocType:
            if dt == KBDocType.SYNTHESIS:
                continue
            manifest.documents[dt.value] = KBDocEntry(
                current_version=1,
                last_updated="2099-01-01T00:00:00+00:00",
            )
        storage.write_manifest(manifest)

        skip, reason = _should_skip_kb(tmp_path, "test-co", False, True)
        assert skip is True
        assert "fresh" in reason.lower()

    def test_no_skip_when_force_rerun(self, tmp_path: Path) -> None:
        skip, reason = _should_skip_kb(tmp_path, "test-co", True, True)
        assert skip is False

    def test_no_skip_when_no_synthesis(self, tmp_path: Path) -> None:
        from core.research.knowledge_base.storage import KBStorage

        storage = KBStorage(tmp_path, "test-co")
        # Empty manifest — synthesis_version == 0
        storage.write_manifest(storage.read_manifest())

        skip, reason = _should_skip_kb(tmp_path, "test-co", False, True)
        assert skip is False

    def test_no_skip_when_config_disabled(self, tmp_path: Path) -> None:
        skip, reason = _should_skip_kb(tmp_path, "test-co", False, False)
        assert skip is False


class TestSkipAP:
    def test_skip_when_personas_exist_and_kb_unchanged(self, tmp_path: Path) -> None:
        from core.models.audience_persona import PersonaManifest, PersonaProfileEntry
        from core.models.knowledge_base import KBManifest
        from core.research.audience_persona.storage import PersonaStorage
        from core.research.knowledge_base.storage import KBStorage

        # Set up KB with synthesis v2
        kb_storage = KBStorage(tmp_path, "test-co")
        kb_manifest = KBManifest(slug="test-co", synthesis_version=2)
        kb_storage.write_manifest(kb_manifest)

        # Set up AP with approved persona referencing KB v2
        ap_storage = PersonaStorage(tmp_path, "test-co")
        ap_manifest = PersonaManifest(
            slug="test-co",
            kb_synthesis_version=2,
            personas={"p1": PersonaProfileEntry(
                persona_id="p1", status="fresh", current_version=1,
            )},
        )
        ap_storage.write_manifest(ap_manifest)

        skip, reason = _should_skip_ap(tmp_path, "test-co", "test-co", False, True)
        assert skip is True

    def test_no_skip_when_kb_updated(self, tmp_path: Path) -> None:
        from core.models.audience_persona import PersonaManifest, PersonaProfileEntry
        from core.models.knowledge_base import KBManifest
        from core.research.audience_persona.storage import PersonaStorage
        from core.research.knowledge_base.storage import KBStorage

        # KB at v3, AP tracks v2
        kb_storage = KBStorage(tmp_path, "test-co")
        kb_storage.write_manifest(KBManifest(slug="test-co", synthesis_version=3))

        ap_storage = PersonaStorage(tmp_path, "test-co")
        ap_storage.write_manifest(PersonaManifest(
            slug="test-co",
            kb_synthesis_version=2,
            personas={"p1": PersonaProfileEntry(
                persona_id="p1", status="fresh", current_version=1,
            )},
        ))

        skip, reason = _should_skip_ap(tmp_path, "test-co", "test-co", False, True)
        assert skip is False

    def test_no_skip_when_no_personas(self, tmp_path: Path) -> None:
        from core.research.audience_persona.storage import PersonaStorage

        PersonaStorage(tmp_path, "test-co")  # creates empty manifest dir
        skip, reason = _should_skip_ap(tmp_path, "test-co", "test-co", False, True)
        assert skip is False


class TestSkipVSG:
    def test_skip_when_guide_fresh(self, tmp_path: Path) -> None:
        from core.models.voice_style_guide import (
            VoiceStyleGuideEntry,
            VoiceStyleGuideManifest,
        )
        from core.research.voice_style_guide.storage import VoiceStyleGuideStorage

        vsg_storage = VoiceStyleGuideStorage(tmp_path, "test-co")
        manifest = VoiceStyleGuideManifest(
            slug="test-co",
            guide=VoiceStyleGuideEntry(current_version=1, status="fresh"),
        )
        vsg_storage.write_manifest(manifest)

        # No AP personas → no AP version check needed
        skip, reason = _should_skip_vsg(tmp_path, "test-co", "test-co", False, True)
        assert skip is True

    def test_no_skip_when_guide_missing(self, tmp_path: Path) -> None:
        skip, reason = _should_skip_vsg(tmp_path, "test-co", "test-co", False, True)
        assert skip is False

    def test_no_skip_when_force_rerun(self, tmp_path: Path) -> None:
        skip, reason = _should_skip_vsg(tmp_path, "test-co", "test-co", True, True)
        assert skip is False


# ═══════════════════════════════════════════════════════════════════════════
# Phase 2: Input Construction Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestInputConstruction:
    def _make_input(self, **overrides: Any) -> ResearchOrchestratorInput:
        defaults = {
            "company_name": "Test Co",
            "domain": "test.com",
            "auto_approve": AutoApproveConfig(kb=[1, 2], ap=[1], vsg=[1]),
        }
        defaults.update(overrides)
        return ResearchOrchestratorInput(**defaults)

    def test_build_kb_input(self) -> None:
        inp = self._make_input(seed_urls=["https://test.com"])
        kb_inp = _build_kb_input(inp, "test-co")
        assert kb_inp.company_name == "Test Co"
        assert kb_inp.company_slug == "test-co"
        assert kb_inp.seed_urls == ["https://test.com"]
        assert kb_inp.auto_approve_checkpoints == [1, 2]

    def test_build_ap_input(self) -> None:
        inp = self._make_input(max_personas=4)
        ap_inp = _build_ap_input(inp, "test-co")
        assert ap_inp.company_name == "Test Co"
        assert ap_inp.max_personas == 4
        assert ap_inp.auto_approve_checkpoints == [1]

    def test_build_vsg_input(self) -> None:
        inp = self._make_input(max_authors=2)
        vsg_inp = _build_vsg_input(inp, "test-co")
        assert vsg_inp.company_name == "Test Co"
        assert vsg_inp.max_authors == 2
        assert vsg_inp.auto_approve_checkpoints == [1]


# ═══════════════════════════════════════════════════════════════════════════
# Phase 2: Core Orchestrator Flow Tests
# ═══════════════════════════════════════════════════════════════════════════


def _mock_kb_output(**overrides: Any) -> MagicMock:
    out = MagicMock()
    out.synthesis_md = overrides.get("synthesis_md", "# Synthesis\nSome text here")
    out.agent_results = overrides.get("agent_results", {})
    out.company_profile_path = overrides.get(
        "company_profile_path", "artifacts/company_context/test-co.md",
    )
    return out


def _mock_ap_output(**overrides: Any) -> MagicMock:
    out = MagicMock()
    out.briefs_suggested = overrides.get("briefs_suggested", 3)
    out.briefs_approved = overrides.get("briefs_approved", 2)
    out.profiles_generated = overrides.get("profiles_generated", 2)
    out.persona_dir = overrides.get("persona_dir", "artifacts/audience_personas/test-co")
    return out


def _mock_vsg_output(**overrides: Any) -> MagicMock:
    out = MagicMock()
    out.authors_discovered = overrides.get("authors_discovered", 3)
    out.authors_approved = overrides.get("authors_approved", 2)
    out.authors_researched = overrides.get("authors_researched", 2)
    out.guide_generated = overrides.get("guide_generated", True)
    out.style_guide_path = overrides.get(
        "style_guide_path", "artifacts/style_guides/test-co.md",
    )
    return out


# Patch targets — source modules (lazy-imported inside stage runners)
_KB_PATCH = "core.research.knowledge_base.pipeline.run_knowledge_base_pipeline"
_AP_PATCH = "core.research.audience_persona.pipeline.run_audience_persona_pipeline"
_VSG_PATCH = "core.research.voice_style_guide.pipeline.run_voice_style_guide_pipeline"


class TestFullOrchestration:
    """Tests for the full orchestrator flow with mocked sub-pipelines."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        self.root = tmp_path
        self.event_bus = MagicMock()
        self.task_store = MagicMock()

    def _input(self, **overrides: Any) -> ResearchOrchestratorInput:
        defaults = {
            "company_name": "Test Co",
            "domain": "test.com",
            "skip_config": PipelineSkipConfig(
                skip_kb_if_fresh=False,
                skip_ap_if_fresh=False,
                skip_vsg_if_fresh=False,
            ),
        }
        defaults.update(overrides)
        return ResearchOrchestratorInput(**defaults)

    @pytest.mark.asyncio
    @patch(_VSG_PATCH, new_callable=AsyncMock, return_value=_mock_vsg_output())
    @patch(_AP_PATCH, new_callable=AsyncMock, return_value=_mock_ap_output())
    @patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb_output())
    async def test_full_run_all_three(self, mock_kb, mock_ap, mock_vsg) -> None:
        """All 3 pipelines run successfully."""
        result = await run_research_orchestrator(
            self._input(),
            task_id="t1",
            task_store=self.task_store,
            event_bus=self.event_bus,
            artifacts_root=self.root,
        )

        assert result.orchestrator_status == OrchestratorStatus.completed
        assert result.pipelines_run == ["kb", "ap", "vsg"]
        assert result.pipelines_skipped == []
        assert "kb" in result.sub_results
        assert "ap" in result.sub_results
        assert "vsg" in result.sub_results
        assert result.company_context_path is not None
        assert result.persona_dir is not None
        assert result.style_guide_path is not None

        # Verify all 3 pipelines were called
        mock_kb.assert_awaited_once()
        mock_ap.assert_awaited_once()
        mock_vsg.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(_AP_PATCH, new_callable=AsyncMock, return_value=_mock_ap_output())
    @patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb_output())
    async def test_selective_pipelines_kb_ap_only(self, mock_kb, mock_ap) -> None:
        """Only KB and AP run when pipelines=["kb", "ap"]."""
        result = await run_research_orchestrator(
            self._input(pipelines=["kb", "ap"]),
            task_id="t1",
            task_store=self.task_store,
            event_bus=self.event_bus,
            artifacts_root=self.root,
        )

        assert result.pipelines_run == ["kb", "ap"]
        assert "vsg" not in result.sub_results
        mock_kb.assert_awaited_once()
        mock_ap.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(_VSG_PATCH, new_callable=AsyncMock, return_value=_mock_vsg_output())
    async def test_selective_pipeline_vsg_only(self, mock_vsg) -> None:
        """Only VSG runs when pipelines=["vsg"]."""
        result = await run_research_orchestrator(
            self._input(pipelines=["vsg"]),
            task_id="t1",
            task_store=self.task_store,
            event_bus=self.event_bus,
            artifacts_root=self.root,
        )

        assert result.pipelines_run == ["vsg"]
        mock_vsg.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_all_skipped(self) -> None:
        """All pipelines skipped returns completed_partial."""
        # Use skip_config=True (default) + mock the skip checks to return True
        with patch("core.research.orchestrator._should_skip_kb", return_value=(True, "KB fresh")), \
             patch("core.research.orchestrator._should_skip_ap", return_value=(True, "AP fresh")), \
             patch("core.research.orchestrator._should_skip_vsg", return_value=(True, "VSG fresh")):
            result = await run_research_orchestrator(
                ResearchOrchestratorInput(company_name="Test Co"),
                task_id="t1",
                task_store=self.task_store,
                event_bus=self.event_bus,
                artifacts_root=self.root,
            )

        assert result.orchestrator_status == OrchestratorStatus.completed_partial
        assert result.pipelines_run == []
        assert set(result.pipelines_skipped) == {"kb", "ap", "vsg"}

    @pytest.mark.asyncio
    @patch(_VSG_PATCH, new_callable=AsyncMock, return_value=_mock_vsg_output())
    @patch(_AP_PATCH, new_callable=AsyncMock, return_value=_mock_ap_output())
    async def test_kb_skipped_ap_vsg_run(self, mock_ap, mock_vsg) -> None:
        """KB skipped (fresh), AP and VSG run."""
        with patch("core.research.orchestrator._should_skip_kb", return_value=(True, "KB fresh")):
            result = await run_research_orchestrator(
                self._input(
                    skip_config=PipelineSkipConfig(
                        skip_kb_if_fresh=True,
                        skip_ap_if_fresh=False,
                        skip_vsg_if_fresh=False,
                    ),
                ),
                task_id="t1",
                task_store=self.task_store,
                event_bus=self.event_bus,
                artifacts_root=self.root,
            )

        assert result.pipelines_skipped == ["kb"]
        assert result.pipelines_run == ["ap", "vsg"]
        assert result.orchestrator_status == OrchestratorStatus.completed_partial


class TestErrorPropagation:
    """Tests for error handling and pipeline failure cascading."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        self.root = tmp_path
        self.event_bus = MagicMock()
        self.task_store = MagicMock()

    def _input(self) -> ResearchOrchestratorInput:
        return ResearchOrchestratorInput(
            company_name="Test Co",
            skip_config=PipelineSkipConfig(
                skip_kb_if_fresh=False,
                skip_ap_if_fresh=False,
                skip_vsg_if_fresh=False,
            ),
        )

    @pytest.mark.asyncio
    @patch(_KB_PATCH, new_callable=AsyncMock, side_effect=RuntimeError("KB exploded"))
    async def test_kb_failure_stops_ap_and_vsg(self, mock_kb) -> None:
        result = await run_research_orchestrator(
            self._input(),
            task_id="t1",
            task_store=self.task_store,
            event_bus=self.event_bus,
            artifacts_root=self.root,
        )

        assert result.orchestrator_status == OrchestratorStatus.failed
        assert result.sub_results["kb"].status == SubPipelineStatus.failed
        assert result.sub_results["kb"].error == "KB exploded"
        assert "ap" not in result.sub_results  # never reached
        assert "vsg" not in result.sub_results

    @pytest.mark.asyncio
    @patch(_AP_PATCH, new_callable=AsyncMock, side_effect=RuntimeError("AP failed"))
    @patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb_output())
    async def test_ap_failure_stops_vsg(self, mock_kb, mock_ap) -> None:
        result = await run_research_orchestrator(
            self._input(),
            task_id="t1",
            task_store=self.task_store,
            event_bus=self.event_bus,
            artifacts_root=self.root,
        )

        assert result.orchestrator_status == OrchestratorStatus.failed
        assert result.sub_results["kb"].status == SubPipelineStatus.completed
        assert result.sub_results["ap"].status == SubPipelineStatus.failed
        assert "vsg" not in result.sub_results

    @pytest.mark.asyncio
    @patch(_VSG_PATCH, new_callable=AsyncMock, side_effect=RuntimeError("VSG boom"))
    @patch(_AP_PATCH, new_callable=AsyncMock, return_value=_mock_ap_output())
    @patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb_output())
    async def test_vsg_failure_recorded(self, mock_kb, mock_ap, mock_vsg) -> None:
        result = await run_research_orchestrator(
            self._input(),
            task_id="t1",
            task_store=self.task_store,
            event_bus=self.event_bus,
            artifacts_root=self.root,
        )

        assert result.orchestrator_status == OrchestratorStatus.failed
        assert result.sub_results["kb"].status == SubPipelineStatus.completed
        assert result.sub_results["ap"].status == SubPipelineStatus.completed
        assert result.sub_results["vsg"].status == SubPipelineStatus.failed
        assert result.sub_results["vsg"].error == "VSG boom"


class TestSSEEvents:
    """Tests for SSE event emission during orchestration."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        self.root = tmp_path
        self.event_bus = MagicMock()
        self.task_store = MagicMock()

    @pytest.mark.asyncio
    @patch(_VSG_PATCH, new_callable=AsyncMock, return_value=_mock_vsg_output())
    @patch(_AP_PATCH, new_callable=AsyncMock, return_value=_mock_ap_output())
    @patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb_output())
    async def test_emits_stage_events(self, mock_kb, mock_ap, mock_vsg) -> None:
        inp = ResearchOrchestratorInput(
            company_name="Test Co",
            skip_config=PipelineSkipConfig(
                skip_kb_if_fresh=False,
                skip_ap_if_fresh=False,
                skip_vsg_if_fresh=False,
            ),
        )
        await run_research_orchestrator(
            inp,
            task_id="t1",
            task_store=self.task_store,
            event_bus=self.event_bus,
            artifacts_root=self.root,
        )

        # Collect all event types published
        event_types = [
            call.args[1] for call in self.event_bus.publish.call_args_list
        ]
        assert "pipeline_start" in event_types
        assert "orchestrator_stage_start" in event_types
        assert "orchestrator_stage_complete" in event_types
        assert "completed" in event_types

    @pytest.mark.asyncio
    async def test_emits_skipped_events(self) -> None:
        with patch("core.research.orchestrator._should_skip_kb", return_value=(True, "fresh")), \
             patch("core.research.orchestrator._should_skip_ap", return_value=(True, "fresh")), \
             patch("core.research.orchestrator._should_skip_vsg", return_value=(True, "fresh")):
            await run_research_orchestrator(
                ResearchOrchestratorInput(company_name="Test Co"),
                task_id="t1",
                task_store=self.task_store,
                event_bus=self.event_bus,
                artifacts_root=self.root,
            )

        event_types = [
            call.args[1] for call in self.event_bus.publish.call_args_list
        ]
        assert event_types.count("orchestrator_stage_skipped") == 3

    @pytest.mark.asyncio
    @patch(_KB_PATCH, new_callable=AsyncMock, side_effect=RuntimeError("fail"))
    async def test_emits_failed_event(self, mock_kb) -> None:
        inp = ResearchOrchestratorInput(
            company_name="Test Co",
            skip_config=PipelineSkipConfig(
                skip_kb_if_fresh=False,
                skip_ap_if_fresh=False,
                skip_vsg_if_fresh=False,
            ),
        )
        await run_research_orchestrator(
            inp,
            task_id="t1",
            task_store=self.task_store,
            event_bus=self.event_bus,
            artifacts_root=self.root,
        )

        event_types = [
            call.args[1] for call in self.event_bus.publish.call_args_list
        ]
        assert "orchestrator_stage_failed" in event_types
        # Terminal event should be "failed", not "completed" (Codex Review Fix #3)
        assert event_types[-1] == "failed"


class TestAutoApproveDistribution:
    """Tests that auto-approve config is correctly distributed to sub-pipelines."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        self.root = tmp_path

    @pytest.mark.asyncio
    @patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb_output())
    async def test_kb_auto_approve_passed(self, mock_kb) -> None:
        inp = ResearchOrchestratorInput(
            company_name="Test Co",
            auto_approve=AutoApproveConfig(kb=[1, 2, 3]),
            pipelines=["kb"],
            skip_config=PipelineSkipConfig(skip_kb_if_fresh=False),
        )
        await run_research_orchestrator(inp, artifacts_root=self.root)
        # Verify the KB input received the auto_approve checkpoints
        called_input = mock_kb.call_args[0][0]
        assert called_input.auto_approve_checkpoints == [1, 2, 3]

    @pytest.mark.asyncio
    @patch(_AP_PATCH, new_callable=AsyncMock, return_value=_mock_ap_output())
    async def test_ap_auto_approve_passed(self, mock_ap) -> None:
        inp = ResearchOrchestratorInput(
            company_name="Test Co",
            auto_approve=AutoApproveConfig(ap=[1, 2]),
            pipelines=["ap"],
            skip_config=PipelineSkipConfig(skip_ap_if_fresh=False),
        )
        await run_research_orchestrator(inp, artifacts_root=self.root)
        called_input = mock_ap.call_args[0][0]
        assert called_input.auto_approve_checkpoints == [1, 2]

    @pytest.mark.asyncio
    @patch(_VSG_PATCH, new_callable=AsyncMock, return_value=_mock_vsg_output())
    async def test_vsg_auto_approve_passed(self, mock_vsg) -> None:
        inp = ResearchOrchestratorInput(
            company_name="Test Co",
            auto_approve=AutoApproveConfig(vsg=[1]),
            pipelines=["vsg"],
            skip_config=PipelineSkipConfig(skip_vsg_if_fresh=False),
        )
        await run_research_orchestrator(inp, artifacts_root=self.root)
        called_input = mock_vsg.call_args[0][0]
        assert called_input.auto_approve_checkpoints == [1]


class TestNullSafeHelpers:
    """Test that orchestrator works without task_store/event_bus."""

    @pytest.mark.asyncio
    @patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb_output())
    async def test_runs_without_event_bus(self, mock_kb, tmp_path: Path) -> None:
        inp = ResearchOrchestratorInput(
            company_name="Test Co",
            pipelines=["kb"],
            skip_config=PipelineSkipConfig(skip_kb_if_fresh=False),
        )
        result = await run_research_orchestrator(
            inp, artifacts_root=tmp_path,
        )
        assert result.orchestrator_status == OrchestratorStatus.completed
