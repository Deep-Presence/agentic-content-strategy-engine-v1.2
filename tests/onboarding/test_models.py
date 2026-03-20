"""Tests for onboarding pipeline models.

Covers:
- OnboardingInput defaults, validation, serialization
- OnboardingOutput structure and defaults
- OnboardingPhaseResult / OnboardingSubResult fields
- Enum values
- AudiencePersonaInput.seed_personas backward compat
- Company.industry backward compat
- PipelineTask 'onboarding' literal
"""
from __future__ import annotations

import json

import pytest

from core.models.onboarding import (
    OnboardingInput,
    OnboardingOutput,
    OnboardingPhase,
    OnboardingPhaseResult,
    OnboardingPhaseStatus,
    OnboardingStatus,
    OnboardingSubResult,
)


# ---------------------------------------------------------------------------
# OnboardingPhase enum
# ---------------------------------------------------------------------------


class TestOnboardingPhase:
    def test_phase_values(self) -> None:
        assert OnboardingPhase.phase_a == "phase_a"
        assert OnboardingPhase.phase_b == "phase_b"
        assert OnboardingPhase.phase_c == "phase_c"

    def test_phase_count(self) -> None:
        assert len(OnboardingPhase) == 3


# ---------------------------------------------------------------------------
# OnboardingPhaseStatus enum
# ---------------------------------------------------------------------------


class TestOnboardingPhaseStatus:
    def test_status_values(self) -> None:
        assert OnboardingPhaseStatus.pending == "pending"
        assert OnboardingPhaseStatus.running == "running"
        assert OnboardingPhaseStatus.completed == "completed"
        assert OnboardingPhaseStatus.failed == "failed"
        assert OnboardingPhaseStatus.skipped == "skipped"

    def test_status_count(self) -> None:
        assert len(OnboardingPhaseStatus) == 5


# ---------------------------------------------------------------------------
# OnboardingStatus enum
# ---------------------------------------------------------------------------


class TestOnboardingStatus:
    def test_terminal_values(self) -> None:
        assert OnboardingStatus.completed == "completed"
        assert OnboardingStatus.completed_partial == "completed_partial"
        assert OnboardingStatus.failed == "failed"


# ---------------------------------------------------------------------------
# OnboardingSubResult
# ---------------------------------------------------------------------------


class TestOnboardingSubResult:
    def test_defaults(self) -> None:
        r = OnboardingSubResult()
        assert r.pipeline == ""
        assert r.phase == ""
        assert r.status == "pending"
        assert r.skip_reason is None
        assert r.execution_time_s == 0.0
        assert r.error is None
        assert r.output_summary == {}

    def test_populated(self) -> None:
        r = OnboardingSubResult(
            pipeline="kb",
            phase="phase_a",
            status="completed",
            execution_time_s=42.5,
            output_summary={"docs": 6},
        )
        assert r.pipeline == "kb"
        assert r.execution_time_s == 42.5

    def test_json_roundtrip(self) -> None:
        r = OnboardingSubResult(pipeline="sa", error="timeout")
        data = r.model_dump(mode="json")
        r2 = OnboardingSubResult.model_validate(data)
        assert r2.error == "timeout"


# ---------------------------------------------------------------------------
# OnboardingPhaseResult
# ---------------------------------------------------------------------------


class TestOnboardingPhaseResult:
    def test_defaults(self) -> None:
        p = OnboardingPhaseResult()
        assert p.phase == ""
        assert p.status == "pending"
        assert p.pipelines == {}
        assert p.execution_time_s == 0.0

    def test_with_sub_results(self) -> None:
        sub = OnboardingSubResult(pipeline="kb", status="completed")
        p = OnboardingPhaseResult(
            phase="phase_a",
            status="completed",
            pipelines={"kb": sub},
        )
        assert "kb" in p.pipelines
        assert p.pipelines["kb"].status == "completed"


# ---------------------------------------------------------------------------
# OnboardingInput
# ---------------------------------------------------------------------------


class TestOnboardingInput:
    def test_minimal_construction(self) -> None:
        inp = OnboardingInput(company_name="Test Co")
        assert inp.company_name == "Test Co"
        assert inp.domain == ""
        assert inp.industry is None
        assert inp.seed_personas == []
        assert inp.max_pages == 200
        assert inp.max_depth == 4
        assert inp.max_personas == 5
        assert inp.max_authors == 3
        assert inp.max_queries == 75
        assert inp.language == "en"
        assert inp.region is None
        assert inp.force_rerun is False
        assert len(inp.phases) == 3
        assert len(inp.platforms) == 4

    def test_full_construction(self) -> None:
        inp = OnboardingInput(
            company_name="Ramp",
            domain="ramp.com",
            industry="Fintech",
            seed_personas=["CFO", "VP Engineering"],
            max_pages=100,
            max_depth=3,
            seed_urls=["https://ramp.com/blog"],
            max_personas=4,
            max_authors=2,
            max_queries=50,
            language="en",
            region="North America",
            force_rerun=True,
        )
        assert inp.industry == "Fintech"
        assert len(inp.seed_personas) == 2
        assert inp.max_pages == 100

    def test_max_pages_validation(self) -> None:
        with pytest.raises(Exception):
            OnboardingInput(company_name="X", max_pages=5)
        with pytest.raises(Exception):
            OnboardingInput(company_name="X", max_pages=600)

    def test_max_personas_validation(self) -> None:
        with pytest.raises(Exception):
            OnboardingInput(company_name="X", max_personas=1)
        with pytest.raises(Exception):
            OnboardingInput(company_name="X", max_personas=10)

    def test_max_authors_validation(self) -> None:
        with pytest.raises(Exception):
            OnboardingInput(company_name="X", max_authors=1)
        with pytest.raises(Exception):
            OnboardingInput(company_name="X", max_authors=5)

    def test_default_phases_all_three(self) -> None:
        inp = OnboardingInput(company_name="X")
        assert OnboardingPhase.phase_a in inp.phases
        assert OnboardingPhase.phase_b in inp.phases
        assert OnboardingPhase.phase_c in inp.phases

    def test_json_roundtrip(self) -> None:
        inp = OnboardingInput(
            company_name="Test Co",
            industry="SaaS",
            seed_personas=["CTO", "VP Sales"],
        )
        data = inp.model_dump(mode="json")
        inp2 = OnboardingInput.model_validate(data)
        assert inp2.industry == "SaaS"
        assert inp2.seed_personas == ["CTO", "VP Sales"]

    def test_json_string_roundtrip(self) -> None:
        inp = OnboardingInput(company_name="Test Co")
        s = json.dumps(inp.model_dump(mode="json"))
        data = json.loads(s)
        inp2 = OnboardingInput.model_validate(data)
        assert inp2.company_name == "Test Co"


# ---------------------------------------------------------------------------
# OnboardingOutput
# ---------------------------------------------------------------------------


class TestOnboardingOutput:
    def test_defaults(self) -> None:
        out = OnboardingOutput()
        assert out.slug == ""
        assert out.company_name == ""
        assert out.onboarding_status == OnboardingStatus.completed
        assert out.phases == {}
        assert out.sub_results == {}
        assert out.total_execution_time_s == 0.0
        assert out.audit_run_id is None
        assert out.company_context_path is None
        assert out.persona_dir is None
        assert out.style_guide_path is None
        assert out.gap_analysis_dir is None
        assert out.topic_discovery_id is None
        assert out.completed_at is None

    def test_populated(self) -> None:
        out = OnboardingOutput(
            slug="test-co",
            company_name="Test Co",
            onboarding_status=OnboardingStatus.completed_partial,
            total_execution_time_s=300.0,
            company_context_path="artifacts/company_context/test-co.md",
        )
        assert out.onboarding_status == "completed_partial"
        assert out.company_context_path is not None

    def test_json_roundtrip(self) -> None:
        out = OnboardingOutput(
            slug="x",
            onboarding_status=OnboardingStatus.failed,
        )
        data = out.model_dump(mode="json")
        out2 = OnboardingOutput.model_validate(data)
        assert out2.onboarding_status == OnboardingStatus.failed


# ---------------------------------------------------------------------------
# Backward compatibility — AudiencePersonaInput.seed_personas
# ---------------------------------------------------------------------------


class TestAudiencePersonaSeedPersonasCompat:
    def test_default_empty_list(self) -> None:
        from core.models.audience_persona import AudiencePersonaInput

        inp = AudiencePersonaInput(company_name="Test Co")
        assert inp.seed_personas == []

    def test_with_seeds(self) -> None:
        from core.models.audience_persona import AudiencePersonaInput

        inp = AudiencePersonaInput(
            company_name="Test Co",
            seed_personas=["CTO", "VP Sales"],
        )
        assert inp.seed_personas == ["CTO", "VP Sales"]

    def test_existing_json_without_seed_personas_still_loads(self) -> None:
        """Existing serialized JSON without seed_personas must still deserialize."""
        from core.models.audience_persona import AudiencePersonaInput

        old_json = {
            "company_name": "Test Co",
            "max_personas": 5,
            "language": "en",
            "auto_approve_checkpoints": [1, 2],
        }
        inp = AudiencePersonaInput.model_validate(old_json)
        assert inp.seed_personas == []
        assert inp.auto_approve_checkpoints == [1, 2]


# ---------------------------------------------------------------------------
# Backward compatibility — Company.industry
# ---------------------------------------------------------------------------


class TestCompanyIndustryCompat:
    def test_default_none(self) -> None:
        from core.models.organization import Company

        c = Company(slug="test", name="Test", domain="test.com")
        assert c.industry is None

    def test_with_industry(self) -> None:
        from core.models.organization import Company

        c = Company(slug="test", name="Test", domain="test.com", industry="Fintech")
        assert c.industry == "Fintech"

    def test_existing_json_without_industry_still_loads(self) -> None:
        """Existing serialized JSON without industry must still deserialize."""
        from core.models.organization import Company

        old_json = {
            "id": "abc",
            "slug": "test",
            "name": "Test",
            "domain": "test.com",
            "additional_domains": [],
            "products": [],
        }
        c = Company.model_validate(old_json)
        assert c.industry is None


# ---------------------------------------------------------------------------
# PipelineTask accepts 'onboarding'
# ---------------------------------------------------------------------------


class TestPipelineTaskOnboardingLiteral:
    def test_onboarding_is_valid_pipeline(self) -> None:
        from api.tasks.models import PipelineTask

        task = PipelineTask(task_id="t1", pipeline="onboarding")
        assert task.pipeline == "onboarding"

    def test_existing_pipelines_still_valid(self) -> None:
        from api.tasks.models import PipelineTask

        for p in [
            "research", "gap_analysis", "content", "content_v13",
            "site_audit", "knowledge_base", "audience_persona",
            "voice_style_guide", "topic_discovery", "topic_expansion",
            "research_orchestrator", "td_content",
        ]:
            task = PipelineTask(task_id="t1", pipeline=p)
            assert task.pipeline == p
