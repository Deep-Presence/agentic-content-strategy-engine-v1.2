"""Tests for core.models.knowledge_base — model validation + JSON roundtrip."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from core.models.knowledge_base import (
    L2_DOC_TYPES,
    BrandPerceptionStructured,
    CompetitorProfile,
    CompetitorRegistryStructured,
    CompetitorWeakness,
    CustomerReview,
    CustomerReviewsStructured,
    KBAgentResult,
    KBDocEntry,
    KBDocType,
    KBDocVersion,
    KBManifest,
    KnowledgeBaseInput,
    KnowledgeBaseOutput,
    WeaknessAnalysisStructured,
)


# ---------------------------------------------------------------------------
# KBDocType enum
# ---------------------------------------------------------------------------


class TestKBDocType:
    def test_all_values(self) -> None:
        assert set(KBDocType) == {
            KBDocType.COMPANY_OVERVIEW,
            KBDocType.CUSTOMER_REVIEWS,
            KBDocType.COMPETITOR_REGISTRY,
            KBDocType.WEAKNESS_ANALYSIS,
            KBDocType.BRAND_PERCEPTION,
            KBDocType.SYNTHESIS,
        }

    def test_string_values(self) -> None:
        assert KBDocType.COMPANY_OVERVIEW.value == "company_overview"
        assert KBDocType.BRAND_PERCEPTION.value == "brand_perception"

    def test_synthesis_enum_value(self) -> None:
        """CX-3: SYNTHESIS is a valid doc type with correct string value."""
        assert KBDocType.SYNTHESIS.value == "synthesis"

    def test_from_string(self) -> None:
        assert KBDocType("company_overview") == KBDocType.COMPANY_OVERVIEW

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            KBDocType("invalid_type")


class TestL2DocTypes:
    """CX-3: L2_DOC_TYPES excludes synthesis."""

    def test_excludes_synthesis(self) -> None:
        assert KBDocType.SYNTHESIS not in L2_DOC_TYPES

    def test_contains_all_5_l2_types(self) -> None:
        assert len(L2_DOC_TYPES) == 5
        expected = {
            KBDocType.COMPANY_OVERVIEW,
            KBDocType.CUSTOMER_REVIEWS,
            KBDocType.COMPETITOR_REGISTRY,
            KBDocType.WEAKNESS_ANALYSIS,
            KBDocType.BRAND_PERCEPTION,
        }
        assert set(L2_DOC_TYPES) == expected


# ---------------------------------------------------------------------------
# KBDocVersion
# ---------------------------------------------------------------------------


class TestKBDocVersion:
    def test_defaults(self) -> None:
        v = KBDocVersion()
        assert v.version == 1
        assert v.created_by == "agent"
        assert v.content_md == ""
        assert v.content_json is None
        assert v.word_count == 0
        assert v.sha256 == ""

    def test_created_at_auto_set(self) -> None:
        v = KBDocVersion()
        assert isinstance(v.created_at, datetime)
        assert v.created_at.tzinfo is not None

    def test_json_roundtrip(self) -> None:
        v = KBDocVersion(
            version=3,
            content_md="# Hello",
            word_count=42,
            sha256="abc123",
        )
        data = json.loads(v.model_dump_json())
        v2 = KBDocVersion.model_validate(data)
        assert v2.version == 3
        assert v2.content_md == "# Hello"
        assert v2.word_count == 42

    def test_with_content_json(self) -> None:
        v = KBDocVersion(content_json={"key": "value"})
        assert v.content_json == {"key": "value"}
        data = v.model_dump(mode="json")
        v2 = KBDocVersion.model_validate(data)
        assert v2.content_json == {"key": "value"}


# ---------------------------------------------------------------------------
# KBDocEntry
# ---------------------------------------------------------------------------


class TestKBDocEntry:
    def test_defaults(self) -> None:
        e = KBDocEntry()
        assert e.doc_type == KBDocType.COMPANY_OVERVIEW
        assert e.current_version == 0
        assert e.last_updated is None
        assert e.staleness_days == 90
        assert e.status == "missing"
        assert e.dependencies == []

    def test_with_dependencies(self) -> None:
        e = KBDocEntry(
            doc_type=KBDocType.COMPETITOR_REGISTRY,
            dependencies=[KBDocType.COMPANY_OVERVIEW],
        )
        assert e.dependencies == [KBDocType.COMPANY_OVERVIEW]

    def test_status_values(self) -> None:
        for status in ("fresh", "stale", "missing"):
            e = KBDocEntry(status=status)
            assert e.status == status

    def test_json_roundtrip(self) -> None:
        e = KBDocEntry(
            doc_type=KBDocType.WEAKNESS_ANALYSIS,
            current_version=2,
            status="fresh",
        )
        data = json.loads(e.model_dump_json())
        e2 = KBDocEntry.model_validate(data)
        assert e2.doc_type == KBDocType.WEAKNESS_ANALYSIS
        assert e2.current_version == 2


# ---------------------------------------------------------------------------
# KBManifest
# ---------------------------------------------------------------------------


class TestKBManifest:
    def test_defaults(self) -> None:
        m = KBManifest()
        assert m.slug == ""
        assert m.documents == {}
        assert m.synthesis_version == 0
        assert m.synthesis_last_updated is None

    def test_with_documents(self) -> None:
        m = KBManifest(
            slug="ramp",
            company_name="Ramp",
            documents={
                "company_overview": KBDocEntry(
                    doc_type=KBDocType.COMPANY_OVERVIEW,
                    current_version=1,
                    status="fresh",
                )
            },
        )
        assert "company_overview" in m.documents
        assert m.documents["company_overview"].status == "fresh"

    def test_json_roundtrip(self) -> None:
        m = KBManifest(
            slug="ramp",
            company_name="Ramp",
            documents={
                "company_overview": KBDocEntry(
                    doc_type=KBDocType.COMPANY_OVERVIEW,
                    current_version=1,
                    status="fresh",
                )
            },
            synthesis_version=2,
        )
        data = json.loads(m.model_dump_json())
        m2 = KBManifest.model_validate(data)
        assert m2.slug == "ramp"
        assert m2.synthesis_version == 2
        assert m2.documents["company_overview"].current_version == 1


# ---------------------------------------------------------------------------
# KBAgentResult
# ---------------------------------------------------------------------------


class TestKBAgentResult:
    def test_defaults(self) -> None:
        r = KBAgentResult()
        assert r.doc_type == KBDocType.COMPANY_OVERVIEW
        assert r.content_md == ""
        assert r.error is None
        assert r.execution_time_s == 0.0
        assert r.is_partial is False

    def test_is_partial_default_false(self) -> None:
        """CX-8: is_partial defaults to False for backward compat."""
        r = KBAgentResult()
        assert r.is_partial is False

    def test_is_partial_json_roundtrip(self) -> None:
        """CX-8: is_partial=True survives JSON roundtrip."""
        r = KBAgentResult(
            doc_type=KBDocType.BRAND_PERCEPTION,
            content_md="# Partial",
            is_partial=True,
        )
        data = json.loads(r.model_dump_json())
        r2 = KBAgentResult.model_validate(data)
        assert r2.is_partial is True

    def test_success_result(self) -> None:
        r = KBAgentResult(
            doc_type=KBDocType.CUSTOMER_REVIEWS,
            content_md="# Reviews\nGreat product!",
            word_count=3,
            execution_time_s=12.5,
        )
        assert r.error is None
        assert r.word_count == 3

    def test_error_result(self) -> None:
        r = KBAgentResult(
            doc_type=KBDocType.COMPETITOR_REGISTRY,
            error="Timeout after 300s",
            execution_time_s=300.0,
        )
        assert r.error == "Timeout after 300s"
        assert r.content_md == ""

    def test_json_roundtrip(self) -> None:
        r = KBAgentResult(
            doc_type=KBDocType.BRAND_PERCEPTION,
            content_md="# Brand",
            sources=[{"url": "https://example.com", "title": "Example"}],
            word_count=100,
        )
        data = json.loads(r.model_dump_json())
        r2 = KBAgentResult.model_validate(data)
        assert r2.sources[0]["url"] == "https://example.com"


# ---------------------------------------------------------------------------
# KnowledgeBaseInput
# ---------------------------------------------------------------------------


class TestKnowledgeBaseInput:
    def test_minimal(self) -> None:
        i = KnowledgeBaseInput(company_name="Ramp")
        assert i.company_name == "Ramp"
        assert i.domain is None
        assert i.language == "en"
        assert i.staleness_threshold_days == 30
        assert i.auto_approve_checkpoints == []

    def test_full(self) -> None:
        i = KnowledgeBaseInput(
            company_name="Ramp",
            domain="ramp.com",
            company_slug="ramp",
            product_slug="payables",
            refresh_docs=[KBDocType.COMPANY_OVERVIEW, KBDocType.CUSTOMER_REVIEWS],
            auto_approve_checkpoints=[1, 2],
        )
        assert i.refresh_docs is not None
        assert len(i.refresh_docs) == 2
        assert i.auto_approve_checkpoints == [1, 2]

    def test_json_roundtrip(self) -> None:
        i = KnowledgeBaseInput(
            company_name="Carta",
            domain="carta.com",
            seed_urls=["https://carta.com/blog"],
        )
        data = json.loads(i.model_dump_json())
        i2 = KnowledgeBaseInput.model_validate(data)
        assert i2.seed_urls == ["https://carta.com/blog"]


# ---------------------------------------------------------------------------
# KnowledgeBaseOutput
# ---------------------------------------------------------------------------


class TestKnowledgeBaseOutput:
    def test_defaults(self) -> None:
        o = KnowledgeBaseOutput()
        assert o.slug == ""
        assert o.synthesis_md == ""
        assert o.agent_results == {}
        assert o.total_execution_time_s == 0.0

    def test_json_roundtrip(self) -> None:
        o = KnowledgeBaseOutput(
            slug="ramp",
            company_name="Ramp",
            synthesis_md="# Company Profile",
            company_profile_path="artifacts/company_context/ramp.md",
            agent_results={
                "company_overview": KBAgentResult(
                    doc_type=KBDocType.COMPANY_OVERVIEW,
                    content_md="# Overview",
                    word_count=500,
                )
            },
        )
        data = json.loads(o.model_dump_json())
        o2 = KnowledgeBaseOutput.model_validate(data)
        assert o2.agent_results["company_overview"].word_count == 500


# ---------------------------------------------------------------------------
# Per-Agent Structured Output Models
# ---------------------------------------------------------------------------


class TestCustomerReview:
    def test_defaults(self) -> None:
        r = CustomerReview()
        assert r.sentiment == "neutral"
        assert r.themes == []

    def test_all_sentiments(self) -> None:
        for s in ("positive", "negative", "neutral", "mixed"):
            r = CustomerReview(sentiment=s)
            assert r.sentiment == s


class TestCustomerReviewsStructured:
    def test_json_roundtrip(self) -> None:
        s = CustomerReviewsStructured(
            total_reviews_analyzed=10,
            reviews=[CustomerReview(quote="Great!", sentiment="positive")],
            top_positive_themes=["ease of use"],
        )
        data = json.loads(s.model_dump_json())
        s2 = CustomerReviewsStructured.model_validate(data)
        assert s2.reviews[0].quote == "Great!"


class TestCompetitorProfile:
    def test_relevance_types(self) -> None:
        for rel in ("direct", "indirect", "mindshare", "niche"):
            p = CompetitorProfile(relevance=rel)
            assert p.relevance == rel


class TestCompetitorRegistryStructured:
    def test_json_roundtrip(self) -> None:
        s = CompetitorRegistryStructured(
            direct_competitors=[CompetitorProfile(name="Brex", domain="brex.com")],
        )
        data = json.loads(s.model_dump_json())
        s2 = CompetitorRegistryStructured.model_validate(data)
        assert s2.direct_competitors[0].name == "Brex"


class TestCompetitorWeakness:
    def test_severity_values(self) -> None:
        for sev in ("critical", "significant", "minor"):
            w = CompetitorWeakness(severity=sev)
            assert w.severity == sev


class TestWeaknessAnalysisStructured:
    def test_json_roundtrip(self) -> None:
        s = WeaknessAnalysisStructured(
            per_competitor={
                "Brex": [
                    CompetitorWeakness(
                        competitor_name="Brex",
                        weakness_category="UI",
                        description="Complex interface",
                        severity="significant",
                    )
                ]
            },
            systemic_industry_problems=["High fees"],
        )
        data = json.loads(s.model_dump_json())
        s2 = WeaknessAnalysisStructured.model_validate(data)
        assert len(s2.per_competitor["Brex"]) == 1


class TestBrandPerceptionStructured:
    def test_json_roundtrip(self) -> None:
        s = BrandPerceptionStructured(
            market_position="Leader in corporate cards",
            key_differentiators=["AI-powered insights", "Real-time tracking"],
        )
        data = json.loads(s.model_dump_json())
        s2 = BrandPerceptionStructured.model_validate(data)
        assert len(s2.key_differentiators) == 2
