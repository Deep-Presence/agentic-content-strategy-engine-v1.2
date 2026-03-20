"""Tests for core.db.enums — Phase A of DB Foundation Sprint.

Verifies that new enum values (knowledge_base, audience_persona,
voice_style_guide pipeline types; knowledge_base artifact type;
fresh/stale/pending_review artifact statuses) serialize/deserialize
correctly and that all pre-existing values remain valid.
"""

import pytest

from core.db.enums import (
    ArtifactStatus,
    ArtifactType,
    PipelineType,
)


# ── PipelineType ─────────────────────────────────────────────────────

class TestPipelineTypeEnum:
    """PipelineType enum — new research pipeline values."""

    @pytest.mark.parametrize(
        "member,expected_value",
        [
            (PipelineType.knowledge_base, "knowledge_base"),
            (PipelineType.audience_persona, "audience_persona"),
            (PipelineType.voice_style_guide, "voice_style_guide"),
        ],
    )
    def test_new_pipeline_types_have_correct_values(self, member, expected_value):
        assert member.value == expected_value

    def test_new_pipeline_types_roundtrip_from_string(self):
        for val in ("knowledge_base", "audience_persona", "voice_style_guide"):
            assert PipelineType(val).value == val

    @pytest.mark.parametrize(
        "legacy_value",
        ["research", "gap_analysis", "content", "content_refresh", "site_audit", "topic_discovery", "topic_expansion"],
    )
    def test_legacy_pipeline_types_still_valid(self, legacy_value):
        member = PipelineType(legacy_value)
        assert member.value == legacy_value
        assert isinstance(member, str)

    def test_pipeline_type_is_str_subclass(self):
        assert isinstance(PipelineType.knowledge_base, str)
        assert PipelineType.knowledge_base == "knowledge_base"


# ── ArtifactType ─────────────────────────────────────────────────────

class TestArtifactTypeEnum:
    """ArtifactType enum — new knowledge_base value."""

    def test_knowledge_base_artifact_type_exists(self):
        assert ArtifactType.knowledge_base.value == "knowledge_base"

    def test_knowledge_base_roundtrip(self):
        assert ArtifactType("knowledge_base") is ArtifactType.knowledge_base

    @pytest.mark.parametrize(
        "legacy_value",
        ["company_context", "persona", "style_guide"],
    )
    def test_legacy_artifact_types_still_valid(self, legacy_value):
        member = ArtifactType(legacy_value)
        assert member.value == legacy_value


# ── ArtifactStatus ───────────────────────────────────────────────────

class TestArtifactStatusEnum:
    """ArtifactStatus enum — new research status vocabulary."""

    @pytest.mark.parametrize(
        "member,expected_value",
        [
            (ArtifactStatus.fresh, "fresh"),
            (ArtifactStatus.stale, "stale"),
            (ArtifactStatus.pending_review, "pending_review"),
        ],
    )
    def test_new_statuses_have_correct_values(self, member, expected_value):
        assert member.value == expected_value

    def test_new_statuses_roundtrip_from_string(self):
        for val in ("fresh", "stale", "pending_review"):
            assert ArtifactStatus(val).value == val

    @pytest.mark.parametrize(
        "legacy_value",
        ["draft", "approved", "archived"],
    )
    def test_legacy_statuses_still_valid(self, legacy_value):
        member = ArtifactStatus(legacy_value)
        assert member.value == legacy_value

    def test_artifact_status_is_str_subclass(self):
        assert isinstance(ArtifactStatus.fresh, str)
        assert ArtifactStatus.fresh == "fresh"
