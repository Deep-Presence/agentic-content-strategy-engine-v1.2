"""Unit tests for core.onboarding.orchestrator — Onboarding Pipeline Orchestrator.

Covers:
- Helper functions (_resolve_slugs, _build_constraints, input builders)
- Full orchestrator flow with mocked sub-pipelines
- Phase A: SA + KB parallel (SA fail proceeds, KB fail → skip B+C)
- Phase B: AP sequential (AP fail → skip TD, run VSG+GA)
- Phase C: VSG + GA + TD parallel (individual failures don't block siblings)
- Auto-approve distribution to sub-pipelines
- Seed persona passthrough
- Industry constraint injection
- SSE meta-event emission
- Null-safe helpers (no event_bus / task_store)
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.onboarding import (
    OnboardingInput,
    OnboardingOutput,
    OnboardingPhase,
    OnboardingStatus,
    OnboardingSubResult,
)
from core.onboarding.orchestrator import (
    _build_ap_input,
    _build_constraints,
    _build_ga_input,
    _build_kb_input,
    _build_sa_input,
    _build_td_input,
    _build_vsg_input,
    _resolve_slugs,
    run_onboarding_pipeline,
)


# ═══════════════════════════════════════════════════════════════════════════
# Mock outputs for sub-pipelines
# ═══════════════════════════════════════════════════════════════════════════


def _mock_sa_result(**overrides: Any) -> MagicMock:
    out = MagicMock()
    out.status = overrides.get("status", "completed")
    out.audit_id = overrides.get("audit_id", "sa-001")
    out.pages_crawled = overrides.get("pages_crawled", 50)
    out.error_message = overrides.get("error_message", "")
    return out


def _mock_kb_output(**overrides: Any) -> MagicMock:
    out = MagicMock()
    out.company_profile_path = overrides.get(
        "company_profile_path", "artifacts/company_context/test-co.md"
    )
    return out


def _mock_ap_output(**overrides: Any) -> MagicMock:
    out = MagicMock()
    out.persona_dir = overrides.get("persona_dir", "artifacts/audience_personas/test-co")
    out.profiles_generated = overrides.get("profiles_generated", 3)
    return out


def _mock_vsg_output(**overrides: Any) -> MagicMock:
    out = MagicMock()
    out.style_guide_path = overrides.get(
        "style_guide_path", "artifacts/style_guides/test-co.md"
    )
    return out


def _mock_ga_output(**overrides: Any) -> MagicMock:
    out = MagicMock()
    out.slug = overrides.get("slug", "test-co")
    return out


def _mock_td_output(**overrides: Any) -> MagicMock:
    out = MagicMock()
    out.total_subdomains_discovered = overrides.get("total_subdomains_discovered", 12)
    return out


# ═══════════════════════════════════════════════════════════════════════════
# Patch targets — source modules (lazy-imported inside stage runners)
# ═══════════════════════════════════════════════════════════════════════════

_SA_PATCH = "core.site_audit.pipeline.run_site_audit"
_KB_PATCH = "core.research.knowledge_base.pipeline.run_knowledge_base_pipeline"
_AP_PATCH = "core.research.audience_persona.pipeline.run_audience_persona_pipeline"
_VSG_PATCH = "core.research.voice_style_guide.pipeline.run_voice_style_guide_pipeline"
_GA_PATCH = "core.gap_analysis.pipeline.run_gap_analysis"
_TD_PATCH = "core.topic_discovery.pipeline.run_topic_discovery_pipeline"


# ═══════════════════════════════════════════════════════════════════════════
# Helper Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestResolveSlug:
    def test_from_company_name(self) -> None:
        inp = OnboardingInput(company_name="Test Co")
        assert _resolve_slugs(inp) == "test-co"

    def test_explicit_slug(self) -> None:
        inp = OnboardingInput(company_name="Test Co", company_slug="custom-slug")
        assert _resolve_slugs(inp) == "custom-slug"


class TestBuildConstraints:
    def test_with_industry(self) -> None:
        inp = OnboardingInput(company_name="X", industry="Fintech")
        assert _build_constraints(inp) == "Industry: Fintech"

    def test_without_industry(self) -> None:
        inp = OnboardingInput(company_name="X")
        assert _build_constraints(inp) is None


# ═══════════════════════════════════════════════════════════════════════════
# Input Builder Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestInputBuilders:
    def _base_input(self, **overrides: Any) -> OnboardingInput:
        defaults: dict[str, Any] = {
            "company_name": "Test Co",
            "domain": "test.com",
            "industry": "SaaS",
            "seed_personas": ["VP Engineering", "CTO"],
            "seed_urls": ["https://test.com/blog"],
            "language": "en",
            "region": "US",
        }
        defaults.update(overrides)
        return OnboardingInput(**defaults)

    def test_build_sa_input(self) -> None:
        inp = self._base_input(max_pages=100, max_depth=3)
        sa = _build_sa_input(inp, "test-co")
        assert sa.company_name == "Test Co"
        assert sa.domain == "test.com"
        assert sa.company_slug == "test-co"
        assert sa.max_pages == 100
        assert sa.max_depth == 3

    def test_build_kb_input(self) -> None:
        inp = self._base_input()
        kb = _build_kb_input(inp, "test-co", "Industry: SaaS")
        assert kb.company_name == "Test Co"
        assert kb.company_slug == "test-co"
        assert kb.seed_urls == ["https://test.com/blog"]
        assert kb.auto_approve_checkpoints == [1, 2, 3]
        assert kb.additional_constraints == "Industry: SaaS"
        assert kb.language == "en"
        assert kb.region == "US"

    def test_build_ap_input_with_seeds(self) -> None:
        inp = self._base_input(max_personas=4)
        ap = _build_ap_input(inp, "test-co", "Industry: SaaS")
        assert ap.company_name == "Test Co"
        assert ap.max_personas == 4
        assert ap.auto_approve_checkpoints == [1, 2]
        assert ap.seed_personas == ["VP Engineering", "CTO"]
        assert ap.additional_constraints == "Industry: SaaS"

    def test_build_ap_input_no_seeds(self) -> None:
        inp = self._base_input(seed_personas=[])
        ap = _build_ap_input(inp, "test-co", None)
        assert ap.seed_personas == []
        assert ap.additional_constraints is None

    def test_build_vsg_input(self) -> None:
        inp = self._base_input(max_authors=2)
        vsg = _build_vsg_input(inp, "test-co", None)
        assert vsg.company_name == "Test Co"
        assert vsg.max_authors == 2
        assert vsg.auto_approve_checkpoints == [1]

    def test_build_ga_input(self) -> None:
        inp = self._base_input(max_queries=50, platforms=["perplexity", "openai"])
        ga = _build_ga_input(inp, "test-co", "Industry: SaaS")
        assert ga.company_name == "Test Co"
        assert ga.max_queries == 50
        assert ga.platforms == ["perplexity", "openai"]
        assert ga.additional_constraints == "Industry: SaaS"

    def test_build_td_input(self) -> None:
        inp = self._base_input()
        td = _build_td_input(inp, "test-co", "Industry: SaaS")
        assert td.company_name == "Test Co"
        assert td.seed_urls == ["https://test.com/blog"]
        assert td.auto_approve_checkpoints == [1]
        assert td.additional_constraints == "Industry: SaaS"


# ═══════════════════════════════════════════════════════════════════════════
# Full Orchestration Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestFullOrchestration:
    """Happy-path and selective phase tests."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        self.root = tmp_path
        self.event_bus = MagicMock()
        self.task_store = MagicMock()

    def _input(self, **overrides: Any) -> OnboardingInput:
        defaults: dict[str, Any] = {
            "company_name": "Test Co",
            "domain": "test.com",
            "industry": "SaaS",
            "seed_personas": ["VP Eng", "Head of Marketing"],
        }
        defaults.update(overrides)
        return OnboardingInput(**defaults)

    @pytest.mark.asyncio
    @patch(_TD_PATCH, new_callable=AsyncMock, return_value=_mock_td_output())
    @patch(_GA_PATCH, new_callable=AsyncMock, return_value=_mock_ga_output())
    @patch(_VSG_PATCH, new_callable=AsyncMock, return_value=_mock_vsg_output())
    @patch(_AP_PATCH, new_callable=AsyncMock, return_value=_mock_ap_output())
    @patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb_output())
    @patch(_SA_PATCH, new_callable=AsyncMock, return_value=_mock_sa_result())
    async def test_happy_path_all_pipelines(
        self, mock_sa, mock_kb, mock_ap, mock_vsg, mock_ga, mock_td,
    ) -> None:
        """All 6 pipelines succeed → completed."""
        result = await run_onboarding_pipeline(
            self._input(),
            task_id="t1",
            task_store=self.task_store,
            event_bus=self.event_bus,
            artifacts_root=self.root,
        )

        assert result.onboarding_status == OnboardingStatus.completed
        assert result.slug == "test-co"
        assert result.company_name == "Test Co"

        # All 6 sub-results present
        assert set(result.sub_results.keys()) == {
            "site_audit", "kb", "ap", "vsg", "ga", "td",
        }
        for name, sr in result.sub_results.items():
            assert sr.status == "completed", f"{name} should be completed"

        # Artifact paths promoted
        assert result.audit_run_id == "sa-001"
        assert result.company_context_path is not None
        assert result.persona_dir is not None
        assert result.style_guide_path is not None

        # Phase results
        assert result.phases["phase_a"].status == "completed"
        assert result.phases["phase_b"].status == "completed"
        assert result.phases["phase_c"].status == "completed"

        assert result.total_execution_time_s > 0

        # All pipelines called
        mock_sa.assert_awaited_once()
        mock_kb.assert_awaited_once()
        mock_ap.assert_awaited_once()
        mock_vsg.assert_awaited_once()
        mock_ga.assert_awaited_once()
        mock_td.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb_output())
    @patch(_SA_PATCH, new_callable=AsyncMock, return_value=_mock_sa_result())
    async def test_phase_a_only(self, mock_sa, mock_kb) -> None:
        """Only Phase A runs when phases=[phase_a]."""
        result = await run_onboarding_pipeline(
            self._input(phases=[OnboardingPhase.phase_a]),
            task_id="t1",
            task_store=self.task_store,
            event_bus=self.event_bus,
            artifacts_root=self.root,
        )

        assert result.onboarding_status == OnboardingStatus.completed
        assert "site_audit" in result.sub_results
        assert "kb" in result.sub_results
        assert "ap" not in result.sub_results
        assert "vsg" not in result.sub_results

    @pytest.mark.asyncio
    @patch(_TD_PATCH, new_callable=AsyncMock, return_value=_mock_td_output())
    @patch(_GA_PATCH, new_callable=AsyncMock, return_value=_mock_ga_output())
    @patch(_VSG_PATCH, new_callable=AsyncMock, return_value=_mock_vsg_output())
    @patch(_AP_PATCH, new_callable=AsyncMock, return_value=_mock_ap_output())
    @patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb_output())
    @patch(_SA_PATCH, new_callable=AsyncMock, return_value=_mock_sa_result())
    async def test_seed_personas_passed_to_ap(
        self, mock_sa, mock_kb, mock_ap, mock_vsg, mock_ga, mock_td,
    ) -> None:
        """seed_personas flows from onboarding input to AP pipeline."""
        await run_onboarding_pipeline(
            self._input(seed_personas=["CTO", "VP Eng", "Head of Product"]),
            artifacts_root=self.root,
        )

        ap_call_input = mock_ap.call_args[0][0]
        assert ap_call_input.seed_personas == ["CTO", "VP Eng", "Head of Product"]

    @pytest.mark.asyncio
    @patch(_TD_PATCH, new_callable=AsyncMock, return_value=_mock_td_output())
    @patch(_GA_PATCH, new_callable=AsyncMock, return_value=_mock_ga_output())
    @patch(_VSG_PATCH, new_callable=AsyncMock, return_value=_mock_vsg_output())
    @patch(_AP_PATCH, new_callable=AsyncMock, return_value=_mock_ap_output())
    @patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb_output())
    @patch(_SA_PATCH, new_callable=AsyncMock, return_value=_mock_sa_result())
    async def test_industry_constraint_injected(
        self, mock_sa, mock_kb, mock_ap, mock_vsg, mock_ga, mock_td,
    ) -> None:
        """Industry from onboarding flows as additional_constraints."""
        await run_onboarding_pipeline(
            self._input(industry="Fintech"),
            artifacts_root=self.root,
        )

        # KB gets constraints
        kb_input = mock_kb.call_args[0][0]
        assert kb_input.additional_constraints == "Industry: Fintech"

        # AP gets constraints
        ap_input = mock_ap.call_args[0][0]
        assert ap_input.additional_constraints == "Industry: Fintech"

        # GA gets constraints
        ga_input = mock_ga.call_args[0][0]
        assert ga_input.additional_constraints == "Industry: Fintech"

    @pytest.mark.asyncio
    @patch(_TD_PATCH, new_callable=AsyncMock, return_value=_mock_td_output())
    @patch(_GA_PATCH, new_callable=AsyncMock, return_value=_mock_ga_output())
    @patch(_VSG_PATCH, new_callable=AsyncMock, return_value=_mock_vsg_output())
    @patch(_AP_PATCH, new_callable=AsyncMock, return_value=_mock_ap_output())
    @patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb_output())
    @patch(_SA_PATCH, new_callable=AsyncMock, return_value=_mock_sa_result())
    async def test_no_industry_no_constraints(
        self, mock_sa, mock_kb, mock_ap, mock_vsg, mock_ga, mock_td,
    ) -> None:
        """No industry → additional_constraints=None."""
        await run_onboarding_pipeline(
            self._input(industry=None),
            artifacts_root=self.root,
        )

        kb_input = mock_kb.call_args[0][0]
        assert kb_input.additional_constraints is None


# ═══════════════════════════════════════════════════════════════════════════
# Phase A Error Handling
# ═══════════════════════════════════════════════════════════════════════════


class TestPhaseAErrors:
    """SA failures are tolerated. KB failures cascade to skip B+C."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        self.root = tmp_path
        self.event_bus = MagicMock()
        self.task_store = MagicMock()

    def _input(self, **overrides: Any) -> OnboardingInput:
        defaults: dict[str, Any] = {"company_name": "Test Co", "domain": "test.com"}
        defaults.update(overrides)
        return OnboardingInput(**defaults)

    @pytest.mark.asyncio
    @patch(_TD_PATCH, new_callable=AsyncMock, return_value=_mock_td_output())
    @patch(_GA_PATCH, new_callable=AsyncMock, return_value=_mock_ga_output())
    @patch(_VSG_PATCH, new_callable=AsyncMock, return_value=_mock_vsg_output())
    @patch(_AP_PATCH, new_callable=AsyncMock, return_value=_mock_ap_output())
    @patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb_output())
    @patch(_SA_PATCH, new_callable=AsyncMock, return_value=_mock_sa_result(status="failed", error_message="crawl timeout"))
    async def test_sa_fails_kb_succeeds_pipeline_continues(
        self, mock_sa, mock_kb, mock_ap, mock_vsg, mock_ga, mock_td,
    ) -> None:
        """SA failure is fire-and-forget — pipeline continues through all phases."""
        result = await run_onboarding_pipeline(
            self._input(),
            task_id="t1",
            task_store=self.task_store,
            event_bus=self.event_bus,
            artifacts_root=self.root,
        )

        # SA failed but overall still completes (SA is non-critical)
        assert result.sub_results["site_audit"].status == "failed"
        assert result.sub_results["kb"].status == "completed"
        assert result.sub_results["ap"].status == "completed"
        assert result.sub_results["vsg"].status == "completed"
        # SA failure doesn't make it partial — only non-SA failures count
        assert result.onboarding_status == OnboardingStatus.completed

    @pytest.mark.asyncio
    @patch(_SA_PATCH, new_callable=AsyncMock, side_effect=RuntimeError("SA crash"))
    @patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb_output())
    @patch(_AP_PATCH, new_callable=AsyncMock, return_value=_mock_ap_output())
    @patch(_VSG_PATCH, new_callable=AsyncMock, return_value=_mock_vsg_output())
    @patch(_GA_PATCH, new_callable=AsyncMock, return_value=_mock_ga_output())
    @patch(_TD_PATCH, new_callable=AsyncMock, return_value=_mock_td_output())
    async def test_sa_exception_caught_pipeline_continues(
        self, mock_td, mock_ga, mock_vsg, mock_ap, mock_kb, mock_sa,
    ) -> None:
        """SA raising exception is caught — pipeline continues."""
        result = await run_onboarding_pipeline(
            self._input(),
            task_id="t1",
            task_store=self.task_store,
            event_bus=self.event_bus,
            artifacts_root=self.root,
        )

        assert result.sub_results["site_audit"].status == "failed"
        assert "SA crash" in result.sub_results["site_audit"].error
        assert result.sub_results["kb"].status == "completed"
        # Pipeline proceeds through phases B + C
        assert result.onboarding_status == OnboardingStatus.completed

    @pytest.mark.asyncio
    @patch(_SA_PATCH, new_callable=AsyncMock, return_value=_mock_sa_result())
    @patch(_KB_PATCH, new_callable=AsyncMock, side_effect=RuntimeError("KB exploded"))
    async def test_kb_fails_skips_phase_b_and_c(
        self, mock_kb, mock_sa,
    ) -> None:
        """KB failure → skip Phase B (AP) and Phase C (VSG+GA+TD) → failed."""
        result = await run_onboarding_pipeline(
            self._input(),
            task_id="t1",
            task_store=self.task_store,
            event_bus=self.event_bus,
            artifacts_root=self.root,
        )

        assert result.onboarding_status == OnboardingStatus.failed
        assert result.sub_results["kb"].status == "failed"
        assert "KB exploded" in result.sub_results["kb"].error

        # Phase B and C are skipped
        assert result.phases["phase_b"].status == "skipped"
        assert result.phases["phase_c"].status == "skipped"

        # No AP/VSG/GA/TD in sub_results (never ran)
        assert "ap" not in result.sub_results
        assert "vsg" not in result.sub_results
        assert "ga" not in result.sub_results
        assert "td" not in result.sub_results


# ═══════════════════════════════════════════════════════════════════════════
# Phase B Error Handling
# ═══════════════════════════════════════════════════════════════════════════


class TestPhaseBErrors:
    """AP failure → skip TD (needs personas), still run VSG + GA."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        self.root = tmp_path
        self.event_bus = MagicMock()
        self.task_store = MagicMock()

    def _input(self, **overrides: Any) -> OnboardingInput:
        defaults: dict[str, Any] = {"company_name": "Test Co", "domain": "test.com"}
        defaults.update(overrides)
        return OnboardingInput(**defaults)

    @pytest.mark.asyncio
    @patch(_TD_PATCH, new_callable=AsyncMock, return_value=_mock_td_output())
    @patch(_GA_PATCH, new_callable=AsyncMock, return_value=_mock_ga_output())
    @patch(_VSG_PATCH, new_callable=AsyncMock, return_value=_mock_vsg_output())
    @patch(_AP_PATCH, new_callable=AsyncMock, side_effect=RuntimeError("AP failed"))
    @patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb_output())
    @patch(_SA_PATCH, new_callable=AsyncMock, return_value=_mock_sa_result())
    async def test_ap_fails_skips_td_runs_vsg_ga(
        self, mock_sa, mock_kb, mock_ap, mock_vsg, mock_ga, mock_td,
    ) -> None:
        """AP failure → TD skipped (needs personas), VSG+GA still run."""
        result = await run_onboarding_pipeline(
            self._input(),
            task_id="t1",
            task_store=self.task_store,
            event_bus=self.event_bus,
            artifacts_root=self.root,
        )

        assert result.onboarding_status == OnboardingStatus.completed_partial
        assert result.sub_results["ap"].status == "failed"

        # Phase C: VSG + GA run, TD skipped (ap_succeeded=False)
        assert result.sub_results["vsg"].status == "completed"
        assert result.sub_results["ga"].status == "completed"
        assert "td" not in result.sub_results  # never launched

        # TD not called
        mock_td.assert_not_awaited()


# ═══════════════════════════════════════════════════════════════════════════
# Phase C Error Handling
# ═══════════════════════════════════════════════════════════════════════════


class TestPhaseCErrors:
    """Individual Phase C failures don't block siblings."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        self.root = tmp_path
        self.event_bus = MagicMock()
        self.task_store = MagicMock()

    def _input(self, **overrides: Any) -> OnboardingInput:
        defaults: dict[str, Any] = {"company_name": "Test Co", "domain": "test.com"}
        defaults.update(overrides)
        return OnboardingInput(**defaults)

    @pytest.mark.asyncio
    @patch(_TD_PATCH, new_callable=AsyncMock, return_value=_mock_td_output())
    @patch(_GA_PATCH, new_callable=AsyncMock, side_effect=RuntimeError("GA boom"))
    @patch(_VSG_PATCH, new_callable=AsyncMock, return_value=_mock_vsg_output())
    @patch(_AP_PATCH, new_callable=AsyncMock, return_value=_mock_ap_output())
    @patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb_output())
    @patch(_SA_PATCH, new_callable=AsyncMock, return_value=_mock_sa_result())
    async def test_ga_fails_vsg_td_succeed(
        self, mock_sa, mock_kb, mock_ap, mock_vsg, mock_ga, mock_td,
    ) -> None:
        """GA fails but VSG + TD succeed → completed_partial."""
        result = await run_onboarding_pipeline(
            self._input(),
            task_id="t1",
            task_store=self.task_store,
            event_bus=self.event_bus,
            artifacts_root=self.root,
        )

        assert result.onboarding_status == OnboardingStatus.completed_partial
        assert result.sub_results["ga"].status == "failed"
        assert "GA boom" in result.sub_results["ga"].error
        assert result.sub_results["vsg"].status == "completed"
        assert result.sub_results["td"].status == "completed"

    @pytest.mark.asyncio
    @patch(_TD_PATCH, new_callable=AsyncMock, side_effect=RuntimeError("TD fail"))
    @patch(_GA_PATCH, new_callable=AsyncMock, return_value=_mock_ga_output())
    @patch(_VSG_PATCH, new_callable=AsyncMock, side_effect=RuntimeError("VSG fail"))
    @patch(_AP_PATCH, new_callable=AsyncMock, return_value=_mock_ap_output())
    @patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb_output())
    @patch(_SA_PATCH, new_callable=AsyncMock, return_value=_mock_sa_result())
    async def test_vsg_td_fail_ga_succeeds(
        self, mock_sa, mock_kb, mock_ap, mock_vsg, mock_ga, mock_td,
    ) -> None:
        """VSG+TD fail, GA succeeds → completed_partial."""
        result = await run_onboarding_pipeline(
            self._input(),
            task_id="t1",
            task_store=self.task_store,
            event_bus=self.event_bus,
            artifacts_root=self.root,
        )

        assert result.onboarding_status == OnboardingStatus.completed_partial
        assert result.sub_results["vsg"].status == "failed"
        assert result.sub_results["td"].status == "failed"
        assert result.sub_results["ga"].status == "completed"

    @pytest.mark.asyncio
    @patch(_TD_PATCH, new_callable=AsyncMock, side_effect=RuntimeError("TD fail"))
    @patch(_GA_PATCH, new_callable=AsyncMock, side_effect=RuntimeError("GA fail"))
    @patch(_VSG_PATCH, new_callable=AsyncMock, side_effect=RuntimeError("VSG fail"))
    @patch(_AP_PATCH, new_callable=AsyncMock, return_value=_mock_ap_output())
    @patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb_output())
    @patch(_SA_PATCH, new_callable=AsyncMock, return_value=_mock_sa_result())
    async def test_all_phase_c_fail(
        self, mock_sa, mock_kb, mock_ap, mock_vsg, mock_ga, mock_td,
    ) -> None:
        """All Phase C pipelines fail → completed_partial (KB+AP still succeeded)."""
        result = await run_onboarding_pipeline(
            self._input(),
            task_id="t1",
            task_store=self.task_store,
            event_bus=self.event_bus,
            artifacts_root=self.root,
        )

        assert result.onboarding_status == OnboardingStatus.completed_partial
        assert result.sub_results["vsg"].status == "failed"
        assert result.sub_results["ga"].status == "failed"
        assert result.sub_results["td"].status == "failed"
        # KB + AP still completed
        assert result.sub_results["kb"].status == "completed"
        assert result.sub_results["ap"].status == "completed"


# ═══════════════════════════════════════════════════════════════════════════
# Auto-Approve Distribution
# ═══════════════════════════════════════════════════════════════════════════


class TestAutoApproveDistribution:
    """Auto-approve checkpoints are correctly set on sub-pipeline inputs."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        self.root = tmp_path

    @pytest.mark.asyncio
    @patch(_TD_PATCH, new_callable=AsyncMock, return_value=_mock_td_output())
    @patch(_GA_PATCH, new_callable=AsyncMock, return_value=_mock_ga_output())
    @patch(_VSG_PATCH, new_callable=AsyncMock, return_value=_mock_vsg_output())
    @patch(_AP_PATCH, new_callable=AsyncMock, return_value=_mock_ap_output())
    @patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb_output())
    @patch(_SA_PATCH, new_callable=AsyncMock, return_value=_mock_sa_result())
    async def test_auto_approve_on_all_pipelines(
        self, mock_sa, mock_kb, mock_ap, mock_vsg, mock_ga, mock_td,
    ) -> None:
        """KB gets [1,2,3], AP gets [1,2], VSG gets [1], TD gets [1]."""
        await run_onboarding_pipeline(
            OnboardingInput(company_name="Test Co", domain="test.com"),
            artifacts_root=self.root,
        )

        kb_input = mock_kb.call_args[0][0]
        assert kb_input.auto_approve_checkpoints == [1, 2, 3]

        ap_input = mock_ap.call_args[0][0]
        assert ap_input.auto_approve_checkpoints == [1, 2]

        vsg_input = mock_vsg.call_args[0][0]
        assert vsg_input.auto_approve_checkpoints == [1]

        td_input = mock_td.call_args[0][0]
        assert td_input.auto_approve_checkpoints == [1]


# ═══════════════════════════════════════════════════════════════════════════
# SSE Events
# ═══════════════════════════════════════════════════════════════════════════


class TestSSEEvents:
    """Verify meta-events are emitted for onboarding lifecycle."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        self.root = tmp_path
        self.event_bus = MagicMock()
        self.task_store = MagicMock()

    def _input(self, **overrides: Any) -> OnboardingInput:
        defaults: dict[str, Any] = {"company_name": "Test Co", "domain": "test.com"}
        defaults.update(overrides)
        return OnboardingInput(**defaults)

    def _event_types(self) -> list[str]:
        return [c.args[1] for c in self.event_bus.publish.call_args_list]

    @pytest.mark.asyncio
    @patch(_TD_PATCH, new_callable=AsyncMock, return_value=_mock_td_output())
    @patch(_GA_PATCH, new_callable=AsyncMock, return_value=_mock_ga_output())
    @patch(_VSG_PATCH, new_callable=AsyncMock, return_value=_mock_vsg_output())
    @patch(_AP_PATCH, new_callable=AsyncMock, return_value=_mock_ap_output())
    @patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb_output())
    @patch(_SA_PATCH, new_callable=AsyncMock, return_value=_mock_sa_result())
    async def test_happy_path_events(
        self, mock_sa, mock_kb, mock_ap, mock_vsg, mock_ga, mock_td,
    ) -> None:
        """Happy path emits start, phase starts, sub starts/completes, terminal."""
        await run_onboarding_pipeline(
            self._input(),
            task_id="t1",
            task_store=self.task_store,
            event_bus=self.event_bus,
            artifacts_root=self.root,
        )

        events = self._event_types()
        assert events[0] == "onboarding_start"
        assert "onboarding_phase_start" in events
        assert "onboarding_sub_start" in events
        assert "onboarding_sub_complete" in events
        assert "onboarding_phase_complete" in events
        assert events[-1] == "completed"

    @pytest.mark.asyncio
    @patch(_SA_PATCH, new_callable=AsyncMock, return_value=_mock_sa_result())
    @patch(_KB_PATCH, new_callable=AsyncMock, side_effect=RuntimeError("KB fail"))
    async def test_kb_failure_emits_skipped_and_failed(
        self, mock_kb, mock_sa,
    ) -> None:
        """KB fail → phase_b skipped, phase_c skipped, terminal=failed."""
        await run_onboarding_pipeline(
            self._input(),
            task_id="t1",
            task_store=self.task_store,
            event_bus=self.event_bus,
            artifacts_root=self.root,
        )

        events = self._event_types()
        assert "onboarding_sub_failed" in events
        assert "onboarding_phase_skipped" in events
        assert events[-1] == "failed"

    @pytest.mark.asyncio
    @patch(_TD_PATCH, new_callable=AsyncMock, return_value=_mock_td_output())
    @patch(_GA_PATCH, new_callable=AsyncMock, return_value=_mock_ga_output())
    @patch(_VSG_PATCH, new_callable=AsyncMock, return_value=_mock_vsg_output())
    @patch(_AP_PATCH, new_callable=AsyncMock, side_effect=RuntimeError("AP fail"))
    @patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb_output())
    @patch(_SA_PATCH, new_callable=AsyncMock, return_value=_mock_sa_result())
    async def test_ap_failure_emits_sub_failed(
        self, mock_sa, mock_kb, mock_ap, mock_vsg, mock_ga, mock_td,
    ) -> None:
        """AP fail → sub_failed emitted, terminal=completed (partial)."""
        await run_onboarding_pipeline(
            self._input(),
            task_id="t1",
            task_store=self.task_store,
            event_bus=self.event_bus,
            artifacts_root=self.root,
        )

        events = self._event_types()
        assert "onboarding_sub_failed" in events
        # Terminal is "completed" not "failed" (KB succeeded, partial)
        assert events[-1] == "completed"


# ═══════════════════════════════════════════════════════════════════════════
# Null-Safe Helpers
# ═══════════════════════════════════════════════════════════════════════════


class TestNullSafeHelpers:
    """Orchestrator works without task_store / event_bus."""

    @pytest.mark.asyncio
    @patch(_TD_PATCH, new_callable=AsyncMock, return_value=_mock_td_output())
    @patch(_GA_PATCH, new_callable=AsyncMock, return_value=_mock_ga_output())
    @patch(_VSG_PATCH, new_callable=AsyncMock, return_value=_mock_vsg_output())
    @patch(_AP_PATCH, new_callable=AsyncMock, return_value=_mock_ap_output())
    @patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb_output())
    @patch(_SA_PATCH, new_callable=AsyncMock, return_value=_mock_sa_result())
    async def test_runs_without_event_bus_or_task_store(
        self, mock_sa, mock_kb, mock_ap, mock_vsg, mock_ga, mock_td,
        tmp_path: Path,
    ) -> None:
        """No event_bus/task_store → still completes (null-safe helpers)."""
        result = await run_onboarding_pipeline(
            OnboardingInput(company_name="Test Co", domain="test.com"),
            artifacts_root=tmp_path,
        )

        assert result.onboarding_status == OnboardingStatus.completed
        assert len(result.sub_results) == 6

    @pytest.mark.asyncio
    @patch(_SA_PATCH, new_callable=AsyncMock, return_value=_mock_sa_result())
    @patch(_KB_PATCH, new_callable=AsyncMock, side_effect=RuntimeError("fail"))
    async def test_failure_without_event_bus(
        self, mock_kb, mock_sa, tmp_path: Path,
    ) -> None:
        """KB failure without event_bus → still returns failed result."""
        result = await run_onboarding_pipeline(
            OnboardingInput(company_name="Test Co", domain="test.com"),
            artifacts_root=tmp_path,
        )

        assert result.onboarding_status == OnboardingStatus.failed


# ═══════════════════════════════════════════════════════════════════════════
# Parallelism Verification
# ═══════════════════════════════════════════════════════════════════════════


class TestParallelism:
    """Verify SA+KB and VSG+GA+TD run in parallel."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        self.root = tmp_path

    @pytest.mark.asyncio
    async def test_phase_a_sa_and_kb_run_concurrently(self) -> None:
        """SA and KB should overlap (both started before either finishes)."""
        call_order: list[str] = []

        async def slow_sa(*a: Any, **kw: Any) -> MagicMock:
            call_order.append("sa_start")
            await asyncio.sleep(0.05)
            call_order.append("sa_end")
            return _mock_sa_result()

        async def slow_kb(*a: Any, **kw: Any) -> MagicMock:
            call_order.append("kb_start")
            await asyncio.sleep(0.05)
            call_order.append("kb_end")
            return _mock_kb_output()

        with patch(_SA_PATCH, side_effect=slow_sa), \
             patch(_KB_PATCH, side_effect=slow_kb), \
             patch(_AP_PATCH, new_callable=AsyncMock, return_value=_mock_ap_output()), \
             patch(_VSG_PATCH, new_callable=AsyncMock, return_value=_mock_vsg_output()), \
             patch(_GA_PATCH, new_callable=AsyncMock, return_value=_mock_ga_output()), \
             patch(_TD_PATCH, new_callable=AsyncMock, return_value=_mock_td_output()):
            await run_onboarding_pipeline(
                OnboardingInput(company_name="Test Co", domain="test.com"),
                artifacts_root=self.root,
            )

        # Both should start before either ends
        assert call_order.index("sa_start") < call_order.index("kb_end")
        assert call_order.index("kb_start") < call_order.index("sa_end")

    @pytest.mark.asyncio
    async def test_phase_c_pipelines_run_concurrently(self) -> None:
        """VSG, GA, TD should all start before any finish."""
        call_order: list[str] = []

        async def slow_vsg(*a: Any, **kw: Any) -> MagicMock:
            call_order.append("vsg_start")
            await asyncio.sleep(0.05)
            call_order.append("vsg_end")
            return _mock_vsg_output()

        async def slow_ga(*a: Any, **kw: Any) -> MagicMock:
            call_order.append("ga_start")
            await asyncio.sleep(0.05)
            call_order.append("ga_end")
            return _mock_ga_output()

        async def slow_td(*a: Any, **kw: Any) -> MagicMock:
            call_order.append("td_start")
            await asyncio.sleep(0.05)
            call_order.append("td_end")
            return _mock_td_output()

        with patch(_SA_PATCH, new_callable=AsyncMock, return_value=_mock_sa_result()), \
             patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb_output()), \
             patch(_AP_PATCH, new_callable=AsyncMock, return_value=_mock_ap_output()), \
             patch(_VSG_PATCH, side_effect=slow_vsg), \
             patch(_GA_PATCH, side_effect=slow_ga), \
             patch(_TD_PATCH, side_effect=slow_td):
            await run_onboarding_pipeline(
                OnboardingInput(company_name="Test Co", domain="test.com"),
                artifacts_root=self.root,
            )

        # All three should start before any finishes
        starts = [i for i, x in enumerate(call_order) if x.endswith("_start")]
        ends = [i for i, x in enumerate(call_order) if x.endswith("_end")]
        assert len(starts) == 3
        assert max(starts) < min(ends)
