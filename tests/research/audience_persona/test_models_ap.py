"""Tests for Audience Persona models — enums, briefs, manifest, pipeline I/O."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.models.audience_persona import (
    PERSONA_DEFAULT_STALENESS_DAYS,
    AudiencePersonaInput,
    AudiencePersonaOutput,
    PersonaAgentResult,
    PersonaBrief,
    PersonaBriefDecision,
    PersonaBriefReview,
    PersonaManifest,
    PersonaProfileDecision,
    PersonaProfileEntry,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestPersonaBriefDecision:
    def test_values(self) -> None:
        assert PersonaBriefDecision.APPROVE == "approve"
        assert PersonaBriefDecision.MODIFY == "modify"
        assert PersonaBriefDecision.REJECT == "reject"

    def test_from_string(self) -> None:
        assert PersonaBriefDecision("approve") is PersonaBriefDecision.APPROVE


class TestPersonaProfileDecision:
    def test_values(self) -> None:
        assert PersonaProfileDecision.APPROVE == "approve"
        assert PersonaProfileDecision.REVISE == "revise"
        assert PersonaProfileDecision.REJECT == "reject"


class TestStalenessConstant:
    def test_default_days_positive(self) -> None:
        assert PERSONA_DEFAULT_STALENESS_DAYS > 0

    def test_default_value(self) -> None:
        assert PERSONA_DEFAULT_STALENESS_DAYS == 60


# ---------------------------------------------------------------------------
# PersonaBrief
# ---------------------------------------------------------------------------


class TestPersonaBrief:
    def test_defaults(self) -> None:
        b = PersonaBrief()
        assert b.brief_id == ""
        assert b.persona_name == ""
        assert b.tagline == ""
        assert b.description == ""
        assert b.rationale == []
        assert b.source == "agent"

    def test_full_construction(self) -> None:
        b = PersonaBrief(
            brief_id="pb-001",
            persona_name="Sarah",
            tagline="VP of Finance at mid-market SaaS",
            description="Manages all financial operations.",
            rationale=["Evidence from G2 reviews", "Common title in customer data"],
            source="manual",
        )
        assert b.brief_id == "pb-001"
        assert b.persona_name == "Sarah"
        assert b.source == "manual"
        assert len(b.rationale) == 2

    def test_json_roundtrip(self) -> None:
        b = PersonaBrief(
            brief_id="pb-002",
            persona_name="Marcus",
            tagline="Head of Ops",
            description="Oversees operations.",
            rationale=["R1"],
            source="hybrid",
        )
        data = b.model_dump(mode="json")
        restored = PersonaBrief.model_validate(data)
        assert restored.brief_id == "pb-002"
        assert restored.source == "hybrid"
        assert restored.rationale == ["R1"]


# ---------------------------------------------------------------------------
# PersonaBriefReview
# ---------------------------------------------------------------------------


class TestPersonaBriefReview:
    def test_defaults(self) -> None:
        r = PersonaBriefReview()
        assert r.brief_id == ""
        assert r.decision == PersonaBriefDecision.APPROVE
        assert r.modified_brief is None

    def test_modify_with_brief(self) -> None:
        modified = PersonaBrief(persona_name="Updated Sarah", tagline="CFO at enterprise")
        r = PersonaBriefReview(
            brief_id="pb-001",
            decision=PersonaBriefDecision.MODIFY,
            modified_brief=modified,
        )
        assert r.decision == PersonaBriefDecision.MODIFY
        assert r.modified_brief is not None
        assert r.modified_brief.persona_name == "Updated Sarah"

    def test_json_roundtrip_with_nested_brief(self) -> None:
        r = PersonaBriefReview(
            brief_id="pb-003",
            decision=PersonaBriefDecision.MODIFY,
            modified_brief=PersonaBrief(persona_name="Jane", tagline="CTO"),
        )
        data = r.model_dump(mode="json")
        restored = PersonaBriefReview.model_validate(data)
        assert restored.modified_brief is not None
        assert restored.modified_brief.persona_name == "Jane"


# ---------------------------------------------------------------------------
# PersonaProfileEntry
# ---------------------------------------------------------------------------


class TestPersonaProfileEntry:
    def test_defaults(self) -> None:
        e = PersonaProfileEntry()
        assert e.persona_id == ""
        assert e.persona_name == ""
        assert e.kind == "secondary"
        assert e.current_version == 0
        assert e.last_updated is None
        assert e.status == "missing"
        assert e.created_by == "agent"
        assert e.word_count == 0
        assert e.sha256 == ""

    def test_icp_kind(self) -> None:
        e = PersonaProfileEntry(kind="icp")
        assert e.kind == "icp"

    def test_all_statuses(self) -> None:
        for status in ("fresh", "stale", "missing", "pending_review", "archived"):
            e = PersonaProfileEntry(status=status)
            assert e.status == status

    def test_json_roundtrip(self) -> None:
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        e = PersonaProfileEntry(
            persona_id="vp-finance",
            persona_name="Sarah",
            tagline="VP of Finance",
            kind="icp",
            current_version=2,
            last_updated=now,
            status="fresh",
            created_by="hybrid",
            word_count=3200,
            sha256="abc123",
        )
        data = e.model_dump(mode="json")
        restored = PersonaProfileEntry.model_validate(data)
        assert restored.persona_id == "vp-finance"
        assert restored.kind == "icp"
        assert restored.current_version == 2
        assert restored.status == "fresh"
        assert restored.created_by == "hybrid"


# ---------------------------------------------------------------------------
# PersonaManifest
# ---------------------------------------------------------------------------


class TestPersonaManifest:
    def test_defaults(self) -> None:
        m = PersonaManifest()
        assert m.slug == ""
        assert m.company_name == ""
        assert m.created_at is not None
        assert m.last_full_run is None
        assert m.personas == {}
        assert m.kb_synthesis_version is None
        assert m.kb_synthesis_updated_at is None

    def test_with_personas(self) -> None:
        m = PersonaManifest(
            slug="test-co",
            company_name="Test Co",
            personas={
                "vp-finance": PersonaProfileEntry(
                    persona_id="vp-finance",
                    persona_name="Sarah",
                    kind="icp",
                    current_version=1,
                    status="fresh",
                ),
                "head-ops": PersonaProfileEntry(
                    persona_id="head-ops",
                    persona_name="Marcus",
                    kind="secondary",
                    current_version=1,
                    status="fresh",
                ),
            },
        )
        assert len(m.personas) == 2
        assert m.personas["vp-finance"].kind == "icp"

    def test_json_roundtrip(self) -> None:
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        m = PersonaManifest(
            slug="test-co",
            company_name="Test Co",
            created_at=now,
            last_full_run=now,
            kb_synthesis_version=3,
            kb_synthesis_updated_at=now,
            personas={
                "vp-finance": PersonaProfileEntry(
                    persona_id="vp-finance",
                    persona_name="Sarah",
                    current_version=2,
                    status="stale",
                )
            },
        )
        data = m.model_dump(mode="json")
        restored = PersonaManifest.model_validate(data)
        assert restored.slug == "test-co"
        assert restored.kb_synthesis_version == 3
        assert "vp-finance" in restored.personas
        assert restored.personas["vp-finance"].current_version == 2


# ---------------------------------------------------------------------------
# PersonaAgentResult
# ---------------------------------------------------------------------------


class TestPersonaAgentResult:
    def test_defaults(self) -> None:
        r = PersonaAgentResult()
        assert r.brief_id == ""
        assert r.persona_name == ""
        assert r.content_md == ""
        assert r.content_json is None
        assert r.word_count == 0
        assert r.execution_time_s == 0.0
        assert r.error is None

    def test_success_result(self) -> None:
        r = PersonaAgentResult(
            brief_id="pb-001",
            persona_name="Sarah",
            content_md="# Persona: Sarah\nFull profile here.",
            word_count=3200,
            execution_time_s=45.3,
        )
        assert r.word_count == 3200
        assert r.error is None

    def test_error_result(self) -> None:
        r = PersonaAgentResult(
            brief_id="pb-002",
            persona_name="Marcus",
            error="Perplexity API timeout after 300s",
        )
        assert r.error is not None
        assert r.word_count == 0

    def test_json_roundtrip(self) -> None:
        r = PersonaAgentResult(
            brief_id="pb-001",
            persona_name="Sarah",
            content_md="# Persona",
            content_json={"sections": {"summary": "text"}},
            word_count=100,
            execution_time_s=10.0,
        )
        data = r.model_dump(mode="json")
        restored = PersonaAgentResult.model_validate(data)
        assert restored.content_json == {"sections": {"summary": "text"}}


# ---------------------------------------------------------------------------
# AudiencePersonaInput
# ---------------------------------------------------------------------------


class TestAudiencePersonaInput:
    def test_minimal(self) -> None:
        inp = AudiencePersonaInput(company_name="Test Co")
        assert inp.company_name == "Test Co"
        assert inp.domain is None
        assert inp.max_personas == 5
        assert inp.language == "en"
        assert inp.region is None
        assert inp.auto_approve_checkpoints == []

    def test_full_construction(self) -> None:
        inp = AudiencePersonaInput(
            company_name="Ramp",
            domain="ramp.com",
            company_slug="ramp",
            product_slug="expense-management",
            product_name="Ramp Expense",
            max_personas=4,
            language="en",
            region="US",
            additional_constraints="Focus on mid-market",
            auto_approve_checkpoints=[1, 2],
        )
        assert inp.max_personas == 4
        assert inp.auto_approve_checkpoints == [1, 2]

    def test_max_personas_min_bound(self) -> None:
        with pytest.raises(Exception):
            AudiencePersonaInput(company_name="X", max_personas=2)

    def test_max_personas_max_bound(self) -> None:
        with pytest.raises(Exception):
            AudiencePersonaInput(company_name="X", max_personas=8)

    def test_json_roundtrip(self) -> None:
        inp = AudiencePersonaInput(
            company_name="Test Co",
            max_personas=3,
            auto_approve_checkpoints=[1],
        )
        data = inp.model_dump(mode="json")
        restored = AudiencePersonaInput.model_validate(data)
        assert restored.max_personas == 3
        assert restored.auto_approve_checkpoints == [1]


# ---------------------------------------------------------------------------
# AudiencePersonaOutput
# ---------------------------------------------------------------------------


class TestAudiencePersonaOutput:
    def test_defaults(self) -> None:
        o = AudiencePersonaOutput()
        assert o.slug == ""
        assert o.company_name == ""
        assert o.manifest is None
        assert o.briefs_suggested == 0
        assert o.briefs_approved == 0
        assert o.profiles_generated == 0
        assert o.persona_results == {}
        assert o.persona_dir == ""
        assert o.total_execution_time_s == 0.0

    def test_with_results(self) -> None:
        o = AudiencePersonaOutput(
            slug="test-co",
            company_name="Test Co",
            briefs_suggested=5,
            briefs_approved=3,
            profiles_generated=3,
            persona_results={
                "pb-001": PersonaAgentResult(
                    brief_id="pb-001",
                    persona_name="Sarah",
                    word_count=3200,
                ),
            },
            persona_dir="artifacts/audience_personas/test-co",
            total_execution_time_s=120.5,
        )
        assert o.profiles_generated == 3
        assert "pb-001" in o.persona_results

    def test_json_roundtrip(self) -> None:
        manifest = PersonaManifest(slug="test-co", company_name="Test Co")
        o = AudiencePersonaOutput(
            slug="test-co",
            company_name="Test Co",
            manifest=manifest,
            briefs_suggested=4,
            briefs_approved=3,
            profiles_generated=3,
        )
        data = o.model_dump(mode="json")
        restored = AudiencePersonaOutput.model_validate(data)
        assert restored.manifest is not None
        assert restored.manifest.slug == "test-co"
        assert restored.briefs_approved == 3
