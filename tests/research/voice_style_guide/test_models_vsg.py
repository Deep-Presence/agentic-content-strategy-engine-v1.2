"""Tests for Voice Style Guide Pydantic models.

Phase A of the Voice Style Guide pipeline.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from core.models.voice_style_guide import (
    AuthorBrief,
    AuthorEntry,
    AuthorResearchResult,
    VoiceStyleGuideEntry,
    VoiceStyleGuideInput,
    VoiceStyleGuideManifest,
    VoiceStyleGuideOutput,
    WorkPersonaMapping,
)


# ---------------------------------------------------------------------------
# WorkPersonaMapping
# ---------------------------------------------------------------------------


class TestWorkPersonaMapping:
    def test_defaults(self):
        m = WorkPersonaMapping()
        assert m.work_title == ""
        assert m.persona_id == ""
        assert m.persona_name == ""
        assert m.relevance == ""

    def test_populated(self):
        m = WorkPersonaMapping(
            work_title="Everybody Writes",
            persona_id="vp-marketing",
            persona_name="Sarah",
            relevance="Content marketing focus matches persona needs",
        )
        assert m.work_title == "Everybody Writes"
        assert m.persona_id == "vp-marketing"

    def test_serialization_roundtrip(self):
        m = WorkPersonaMapping(work_title="On Writing Well", persona_id="cto")
        data = m.model_dump(mode="json")
        m2 = WorkPersonaMapping.model_validate(data)
        assert m2.work_title == m.work_title


# ---------------------------------------------------------------------------
# AuthorBrief
# ---------------------------------------------------------------------------


class TestAuthorBrief:
    def test_defaults(self):
        b = AuthorBrief()
        assert b.author_id == ""
        assert b.name == ""
        assert b.description == ""
        assert b.famous_works == []
        assert b.resonance_rationale == ""
        assert b.work_persona_mapping == []
        assert b.source == "agent"

    def test_populated(self):
        b = AuthorBrief(
            author_id="ann-handley",
            name="Ann Handley",
            description="Marketing content pioneer",
            famous_works=["Everybody Writes", "Content Rules"],
            resonance_rationale="B2B content marketing authority",
            work_persona_mapping=[
                WorkPersonaMapping(
                    work_title="Everybody Writes",
                    persona_id="vp-marketing",
                    persona_name="Sarah",
                    relevance="Practical content advice for marketers",
                ),
            ],
            source="agent",
        )
        assert b.author_id == "ann-handley"
        assert len(b.famous_works) == 2
        assert len(b.work_persona_mapping) == 1
        assert b.work_persona_mapping[0].work_title == "Everybody Writes"

    def test_serialization_roundtrip(self):
        b = AuthorBrief(
            author_id="test",
            name="Test Author",
            famous_works=["Book A"],
            work_persona_mapping=[WorkPersonaMapping(work_title="Book A")],
        )
        data = json.loads(b.model_dump_json())
        b2 = AuthorBrief.model_validate(data)
        assert b2.author_id == b.author_id
        assert b2.work_persona_mapping[0].work_title == "Book A"

    def test_source_literal_values(self):
        for source in ("agent", "manual", "hybrid"):
            b = AuthorBrief(source=source)
            assert b.source == source

    def test_invalid_source_rejected(self):
        with pytest.raises(Exception):
            AuthorBrief(source="unknown")


# ---------------------------------------------------------------------------
# AuthorResearchResult
# ---------------------------------------------------------------------------


class TestAuthorResearchResult:
    def test_defaults(self):
        r = AuthorResearchResult()
        assert r.author_id == ""
        assert r.name == ""
        assert r.content_md == ""
        assert r.word_count == 0
        assert r.execution_time_s == 0.0
        assert r.error is None

    def test_success_result(self):
        r = AuthorResearchResult(
            author_id="ann-handley",
            name="Ann Handley",
            content_md="# Ann Handley\n\nDeep research...",
            word_count=150,
            execution_time_s=42.5,
        )
        assert r.error is None
        assert r.word_count == 150

    def test_error_result(self):
        r = AuthorResearchResult(
            author_id="failing-author",
            name="Failing Author",
            error="Timeout after 300s",
            execution_time_s=300.0,
        )
        assert r.error == "Timeout after 300s"
        assert r.content_md == ""

    def test_serialization_roundtrip(self):
        r = AuthorResearchResult(
            author_id="test", content_md="# Test", word_count=1,
        )
        data = r.model_dump(mode="json")
        r2 = AuthorResearchResult.model_validate(data)
        assert r2.author_id == r.author_id


# ---------------------------------------------------------------------------
# AuthorEntry (manifest entry)
# ---------------------------------------------------------------------------


class TestAuthorEntry:
    def test_defaults(self):
        e = AuthorEntry()
        assert e.author_id == ""
        assert e.name == ""
        assert e.current_version == 0
        assert e.last_updated is None
        assert e.status == "missing"
        assert e.word_count == 0
        assert e.sha256 == ""

    def test_populated(self):
        now = datetime.now(timezone.utc)
        e = AuthorEntry(
            author_id="ann-handley",
            name="Ann Handley",
            current_version=2,
            last_updated=now,
            status="fresh",
            word_count=500,
            sha256="abc123",
        )
        assert e.current_version == 2
        assert e.status == "fresh"

    def test_status_values(self):
        for status in ("fresh", "stale", "missing", "archived"):
            e = AuthorEntry(status=status)
            assert e.status == status

    def test_serialization_roundtrip(self):
        now = datetime.now(timezone.utc)
        e = AuthorEntry(
            author_id="test", current_version=1, last_updated=now, status="fresh",
        )
        data = e.model_dump(mode="json")
        e2 = AuthorEntry.model_validate(data)
        assert e2.current_version == 1


# ---------------------------------------------------------------------------
# VoiceStyleGuideEntry (guide manifest entry)
# ---------------------------------------------------------------------------


class TestVoiceStyleGuideEntry:
    def test_defaults(self):
        g = VoiceStyleGuideEntry()
        assert g.current_version == 0
        assert g.last_updated is None
        assert g.status == "missing"
        assert g.word_count == 0
        assert g.sha256 == ""
        assert g.source_authors == []

    def test_populated(self):
        g = VoiceStyleGuideEntry(
            current_version=1,
            status="fresh",
            source_authors=["ann-handley", "paul-graham"],
        )
        assert len(g.source_authors) == 2


# ---------------------------------------------------------------------------
# VoiceStyleGuideManifest
# ---------------------------------------------------------------------------


class TestVoiceStyleGuideManifest:
    def test_defaults(self):
        m = VoiceStyleGuideManifest()
        assert m.slug == ""
        assert m.company_name == ""
        assert m.created_at is None
        assert m.last_full_run is None
        assert m.authors == {}
        assert isinstance(m.guide, VoiceStyleGuideEntry)
        assert m.ap_manifest_version is None

    def test_populated(self):
        now = datetime.now(timezone.utc)
        m = VoiceStyleGuideManifest(
            slug="ramp",
            company_name="Ramp",
            created_at=now,
            authors={
                "ann-handley": AuthorEntry(
                    author_id="ann-handley", name="Ann Handley", status="fresh",
                ),
            },
            guide=VoiceStyleGuideEntry(current_version=1, status="fresh"),
        )
        assert m.slug == "ramp"
        assert "ann-handley" in m.authors
        assert m.guide.current_version == 1

    def test_json_roundtrip(self):
        now = datetime.now(timezone.utc)
        m = VoiceStyleGuideManifest(
            slug="test-co",
            company_name="Test Co",
            created_at=now,
            authors={
                "author-1": AuthorEntry(
                    author_id="author-1", name="Author One",
                    current_version=1, status="fresh",
                ),
            },
            guide=VoiceStyleGuideEntry(
                current_version=1, status="fresh",
                source_authors=["author-1"],
            ),
            ap_manifest_version="v3",
        )
        json_str = m.model_dump_json()
        m2 = VoiceStyleGuideManifest.model_validate_json(json_str)
        assert m2.slug == "test-co"
        assert m2.authors["author-1"].name == "Author One"
        assert m2.guide.source_authors == ["author-1"]
        assert m2.ap_manifest_version == "v3"


# ---------------------------------------------------------------------------
# VoiceStyleGuideInput
# ---------------------------------------------------------------------------


class TestVoiceStyleGuideInput:
    def test_minimal(self):
        i = VoiceStyleGuideInput(company_name="Ramp")
        assert i.company_name == "Ramp"
        assert i.domain is None
        assert i.company_slug is None
        assert i.product_slug is None
        assert i.product_name is None
        assert i.max_authors == 3
        assert i.language == "en"
        assert i.region is None
        assert i.additional_constraints is None
        assert i.auto_approve_checkpoints == []

    def test_full(self):
        i = VoiceStyleGuideInput(
            company_name="Ramp",
            domain="fintech",
            company_slug="ramp",
            product_slug="expense",
            product_name="Expense Management",
            max_authors=2,
            language="en",
            region="US",
            additional_constraints="Focus on B2B SaaS tone",
            auto_approve_checkpoints=[1],
        )
        assert i.max_authors == 2
        assert i.auto_approve_checkpoints == [1]

    def test_max_authors_range(self):
        # min 2
        with pytest.raises(Exception):
            VoiceStyleGuideInput(company_name="X", max_authors=1)
        # max 5
        with pytest.raises(Exception):
            VoiceStyleGuideInput(company_name="X", max_authors=6)
        # valid boundaries
        VoiceStyleGuideInput(company_name="X", max_authors=2)
        VoiceStyleGuideInput(company_name="X", max_authors=5)

    def test_serialization_roundtrip(self):
        i = VoiceStyleGuideInput(
            company_name="Test Co",
            domain="tech",
            max_authors=3,
            auto_approve_checkpoints=[1],
        )
        data = i.model_dump(mode="json")
        i2 = VoiceStyleGuideInput.model_validate(data)
        assert i2.company_name == "Test Co"
        assert i2.auto_approve_checkpoints == [1]


# ---------------------------------------------------------------------------
# VoiceStyleGuideOutput
# ---------------------------------------------------------------------------


class TestVoiceStyleGuideOutput:
    def test_defaults(self):
        o = VoiceStyleGuideOutput()
        assert o.slug == ""
        assert o.company_name == ""
        assert o.manifest is None
        assert o.authors_discovered == 0
        assert o.authors_approved == 0
        assert o.authors_researched == 0
        assert o.guide_generated is False
        assert o.guide_dir == ""
        assert o.style_guide_path == ""
        assert o.total_execution_time_s == 0.0

    def test_populated(self):
        m = VoiceStyleGuideManifest(slug="ramp", company_name="Ramp")
        o = VoiceStyleGuideOutput(
            slug="ramp",
            company_name="Ramp",
            manifest=m,
            authors_discovered=3,
            authors_approved=2,
            authors_researched=2,
            guide_generated=True,
            guide_dir="artifacts/voice_style_guide/ramp",
            style_guide_path="artifacts/style_guides/ramp.md",
            total_execution_time_s=120.5,
        )
        assert o.guide_generated is True
        assert o.authors_researched == 2

    def test_serialization_roundtrip(self):
        o = VoiceStyleGuideOutput(
            slug="test",
            authors_discovered=3,
            guide_generated=True,
        )
        data = o.model_dump(mode="json")
        o2 = VoiceStyleGuideOutput.model_validate(data)
        assert o2.slug == "test"
        assert o2.guide_generated is True
