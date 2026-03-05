"""Tests for KB models — DAG constant, staleness thresholds, health models."""
from __future__ import annotations

from datetime import datetime, timezone

from core.models.knowledge_base import (
    KB_DEFAULT_STALENESS_DAYS,
    KB_DEPENDENCY_GRAPH,
    KBDocHealth,
    KBDocType,
    KBHealthReport,
    KnowledgeBaseOutput,
    L2_DOC_TYPES,
)


# ---------------------------------------------------------------------------
# DAG Constant
# ---------------------------------------------------------------------------


class TestKBDependencyGraph:
    def test_dag_covers_all_l2_doc_types(self) -> None:
        for dt in L2_DOC_TYPES:
            assert dt in KB_DEPENDENCY_GRAPH, f"{dt} missing from DAG"

    def test_dag_does_not_include_synthesis(self) -> None:
        assert KBDocType.SYNTHESIS not in KB_DEPENDENCY_GRAPH

    def test_root_docs_have_no_dependencies(self) -> None:
        assert KB_DEPENDENCY_GRAPH[KBDocType.COMPANY_OVERVIEW] == []
        assert KB_DEPENDENCY_GRAPH[KBDocType.CUSTOMER_REVIEWS] == []

    def test_competitor_registry_depends_on_overview(self) -> None:
        deps = KB_DEPENDENCY_GRAPH[KBDocType.COMPETITOR_REGISTRY]
        assert KBDocType.COMPANY_OVERVIEW in deps

    def test_weakness_depends_on_overview_and_competitor(self) -> None:
        deps = KB_DEPENDENCY_GRAPH[KBDocType.WEAKNESS_ANALYSIS]
        assert KBDocType.COMPANY_OVERVIEW in deps
        assert KBDocType.COMPETITOR_REGISTRY in deps

    def test_brand_perception_dependencies(self) -> None:
        deps = KB_DEPENDENCY_GRAPH[KBDocType.BRAND_PERCEPTION]
        assert KBDocType.COMPANY_OVERVIEW in deps
        assert KBDocType.CUSTOMER_REVIEWS in deps
        assert KBDocType.COMPETITOR_REGISTRY in deps

    def test_no_circular_dependencies(self) -> None:
        """Topological sort should not detect cycles."""
        visited: set[KBDocType] = set()
        in_stack: set[KBDocType] = set()

        def _dfs(node: KBDocType) -> None:
            assert node not in in_stack, f"Cycle detected at {node}"
            if node in visited:
                return
            in_stack.add(node)
            for dep in KB_DEPENDENCY_GRAPH.get(node, []):
                _dfs(dep)
            in_stack.discard(node)
            visited.add(node)

        for dt in KB_DEPENDENCY_GRAPH:
            _dfs(dt)


# ---------------------------------------------------------------------------
# Staleness Thresholds
# ---------------------------------------------------------------------------


class TestKBDefaultStalenessThresholds:
    def test_covers_all_l2_doc_types(self) -> None:
        for dt in L2_DOC_TYPES:
            assert dt in KB_DEFAULT_STALENESS_DAYS, f"{dt} missing from thresholds"

    def test_all_values_positive(self) -> None:
        for dt, days in KB_DEFAULT_STALENESS_DAYS.items():
            assert days > 0, f"{dt} has non-positive threshold: {days}"

    def test_expected_values(self) -> None:
        assert KB_DEFAULT_STALENESS_DAYS[KBDocType.COMPANY_OVERVIEW] == 90
        assert KB_DEFAULT_STALENESS_DAYS[KBDocType.CUSTOMER_REVIEWS] == 30
        assert KB_DEFAULT_STALENESS_DAYS[KBDocType.COMPETITOR_REGISTRY] == 90
        assert KB_DEFAULT_STALENESS_DAYS[KBDocType.WEAKNESS_ANALYSIS] == 60
        assert KB_DEFAULT_STALENESS_DAYS[KBDocType.BRAND_PERCEPTION] == 45


# ---------------------------------------------------------------------------
# Health Models — Serialization
# ---------------------------------------------------------------------------


class TestKBDocHealth:
    def test_defaults(self) -> None:
        h = KBDocHealth()
        assert h.status == "missing"
        assert h.stale_reason is None
        assert h.age_days == 0
        assert h.dependencies == []

    def test_json_roundtrip(self) -> None:
        h = KBDocHealth(
            doc_type=KBDocType.CUSTOMER_REVIEWS,
            status="stale",
            current_version=3,
            last_updated=datetime(2026, 1, 1, tzinfo=timezone.utc),
            age_days=60,
            staleness_threshold_days=30,
            dependencies=[KBDocType.COMPANY_OVERVIEW],
            stale_reason="age_exceeded",
        )
        data = h.model_dump(mode="json")
        restored = KBDocHealth.model_validate(data)
        assert restored.doc_type == KBDocType.CUSTOMER_REVIEWS
        assert restored.stale_reason == "age_exceeded"
        assert restored.dependencies == [KBDocType.COMPANY_OVERVIEW]


class TestKBHealthReport:
    def test_defaults(self) -> None:
        r = KBHealthReport()
        assert r.overall_score == 0.0
        assert r.stale_docs == []
        assert r.missing_docs == []
        assert r.synthesis_needs_refresh is False

    def test_json_roundtrip(self) -> None:
        r = KBHealthReport(
            slug="test-co",
            overall_score=80.0,
            synthesis_version=2,
            synthesis_needs_refresh=True,
            stale_docs=["customer_reviews"],
            missing_docs=["brand_perception"],
        )
        data = r.model_dump(mode="json")
        restored = KBHealthReport.model_validate(data)
        assert restored.slug == "test-co"
        assert restored.overall_score == 80.0
        assert restored.stale_docs == ["customer_reviews"]


# ---------------------------------------------------------------------------
# KnowledgeBaseOutput — changed_docs field
# ---------------------------------------------------------------------------


class TestKnowledgeBaseOutputChangedDocs:
    def test_default_empty(self) -> None:
        o = KnowledgeBaseOutput(slug="x", company_name="X")
        assert o.changed_docs == []

    def test_roundtrip_with_changed_docs(self) -> None:
        o = KnowledgeBaseOutput(
            slug="x",
            company_name="X",
            changed_docs=["company_overview", "customer_reviews"],
        )
        data = o.model_dump(mode="json")
        restored = KnowledgeBaseOutput.model_validate(data)
        assert restored.changed_docs == ["company_overview", "customer_reviews"]
