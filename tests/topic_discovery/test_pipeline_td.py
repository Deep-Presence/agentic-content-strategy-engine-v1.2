"""Tests for Topic Discovery pipeline orchestrator.

Covers:
- Slug resolution + preflight loading
- Full happy path (all agents mocked, both HITLs auto-approved)
- Missing company context → RuntimeError
- Missing personas → RuntimeError
- Partial source failure → pipeline continues
- SSE events emitted at each phase boundary
- Task store status transitions
- Product slug → effective_slug routing
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.models.topic_discovery import (
    BuyerStage,
    CaptureRecaptureResult,
    IntentType,
    RelevanceCell,
    SourceResult,
    SubdomainCandidate,
    SubdomainNode,
    TaxonomyTree,
    TDSource,
    TopicAssignment,
    TopicDiscoveryInput,
    TopicDiscoveryOutput,
    TopicDiscoveryStatus,
)

# Patch targets
_P = "core.topic_discovery.pipeline"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def td_input() -> TopicDiscoveryInput:
    return TopicDiscoveryInput(
        company_name="Test Co",
        domain="test.com",
        company_slug="test-co",
        auto_approve_checkpoints=[1, 2],
        max_expansion_rounds=2,
        dedup_threshold=0.85,
    )


@pytest.fixture
def artifacts_dir(tmp_path: Path) -> Path:
    """Artifacts dir with company context only. Personas are mocked."""
    ctx_dir = tmp_path / "company_context"
    ctx_dir.mkdir()
    (ctx_dir / "test-co.md").write_text(
        "# Test Co\nA fintech company specializing in expense management.",
        encoding="utf-8",
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _make_source(source: TDSource, count: int = 3) -> SourceResult:
    return SourceResult(
        source=source,
        candidates=[
            SubdomainCandidate(
                name=f"{source.value}-sub-{i}",
                description=f"Desc {i}",
                source=source,
                round_number=1,
                confidence=0.8,
            )
            for i in range(1, count + 1)
        ],
        total_rounds=2,
        singletons=1,
        doubletons=1,
        execution_time_s=5.0,
    )


def _make_taxonomy() -> TaxonomyTree:
    return TaxonomyTree(
        domain_name="test.com",
        version=1,
        root_nodes=[
            SubdomainNode(name="Expense Management", depth=0, confidence=0.9),
            SubdomainNode(name="Corporate Cards", depth=0, confidence=0.8),
        ],
        total_subdomains=2,
        max_depth=0,
    )


def _make_coverage() -> CaptureRecaptureResult:
    return CaptureRecaptureResult(
        pairwise_estimates={"source_a_source_b": 10.0},
        median_estimate=10.0,
        estimate_range=[10.0, 10.0],
        chao1_lower_bound=8.0,
        sample_coverage=0.88,
        observed_count=6,
        total_singletons=2,
        total_doubletons=1,
    )


def _make_topics(count: int = 2) -> list[TopicAssignment]:
    return [
        TopicAssignment(
            subdomain_name="Expense Management",
            topic_text=f"Topic {i}",
            buyer_stage=BuyerStage.TOFU,
            intent_type=IntentType.informational,
            audience_segment="Persona 1",
            relevance=RelevanceCell.relevant,
            priority_score=0.7,
        )
        for i in range(1, count + 1)
    ]


def _pipeline_patches(
    source_a=None, source_b=None, source_c=None, source_d=None,
    deduped=None, coverage=None, taxonomy=None,
    relevance=None, topics=None,
):
    """Return a context manager that patches all pipeline externals."""
    sa = source_a or _make_source(TDSource.source_a)
    sb = source_b or _make_source(TDSource.source_b)
    sc = source_c or _make_source(TDSource.source_c, 2)
    sd = source_d or _make_source(TDSource.source_d, 2)
    tax = taxonomy or _make_taxonomy()
    cov = coverage or _make_coverage()
    ded = deduped or sa.candidates
    rel = relevance if relevance is not None else []
    top = topics or _make_topics()

    from contextlib import contextmanager

    @contextmanager
    def _ctx():
        with (
            patch(f"{_P}.configure_litellm_callbacks"),
            patch(f"{_P}.create_session", return_value="s"),
            patch(f"{_P}.create_trace", return_value=MagicMock()),
            patch(f"{_P}.end_span"),
            patch(f"{_P}.flush"),
            patch(f"{_P}._load_persona_profiles", return_value=["## Persona 1\nCFO persona."]),
            patch(f"{_P}.run_source_a_company_brainstorm", return_value=sa),
            patch(f"{_P}.run_source_b_persona_brainstorm", return_value=sb),
            patch(f"{_P}.run_source_c_competitor_sitemaps", return_value=sc),
            patch(f"{_P}.run_source_d_adversarial", return_value=sd),
            patch(f"{_P}.deduplicate_subdomains", return_value=ded),
            patch(f"{_P}.compute_all_coverage_metrics", return_value=cov),
            patch(f"{_P}.run_hierarchy_construction", return_value=tax),
            patch(f"{_P}.run_relevance_filtering", return_value=rel),
            patch(f"{_P}.run_topic_generation", return_value=top),
        ):
            yield

    return _ctx()


# ═══════════════════════════════════════════════════════════════════════
# Slug resolution
# ═══════════════════════════════════════════════════════════════════════


class TestSlugResolution:

    def test_resolve_slug_from_company_slug(self):
        from core.topic_discovery.pipeline import _resolve_slug
        inp = TopicDiscoveryInput(company_name="Test Co", company_slug="test-co")
        assert _resolve_slug(inp) == "test-co"

    def test_resolve_slug_from_company_name(self):
        from core.topic_discovery.pipeline import _resolve_slug
        inp = TopicDiscoveryInput(company_name="My Company Inc.")
        assert _resolve_slug(inp) == "my-company-inc"

    def test_effective_slug_no_product(self):
        from core.topic_discovery.pipeline import _resolve_effective_slug
        inp = TopicDiscoveryInput(company_name="Test Co", company_slug="test-co")
        assert _resolve_effective_slug(inp) == "test-co"

    def test_effective_slug_with_product(self):
        from core.topic_discovery.pipeline import _resolve_effective_slug
        inp = TopicDiscoveryInput(
            company_name="Test Co", company_slug="test-co", product_slug="cards",
        )
        assert _resolve_effective_slug(inp) == "test-co__cards"


# ═══════════════════════════════════════════════════════════════════════
# Preflight errors
# ═══════════════════════════════════════════════════════════════════════


class TestPreflightErrors:

    @pytest.mark.asyncio
    async def test_missing_company_context(self, td_input, tmp_path):
        with (
            patch(f"{_P}.configure_litellm_callbacks"),
            patch(f"{_P}.create_session", return_value="s"),
            patch(f"{_P}.create_trace", return_value=MagicMock()),
            patch(f"{_P}.end_span"),
            patch(f"{_P}.flush"),
        ):
            from core.topic_discovery.pipeline import run_topic_discovery_pipeline
            with pytest.raises(RuntimeError, match="Company context not found"):
                await run_topic_discovery_pipeline(td_input, artifacts_root=tmp_path)

    @pytest.mark.asyncio
    async def test_missing_personas(self, td_input, artifacts_dir):
        with (
            patch(f"{_P}.configure_litellm_callbacks"),
            patch(f"{_P}.create_session", return_value="s"),
            patch(f"{_P}.create_trace", return_value=MagicMock()),
            patch(f"{_P}.end_span"),
            patch(f"{_P}.flush"),
            patch(f"{_P}._load_persona_profiles", return_value=[]),
        ):
            from core.topic_discovery.pipeline import run_topic_discovery_pipeline
            with pytest.raises(RuntimeError, match="No active persona profiles"):
                await run_topic_discovery_pipeline(td_input, artifacts_root=artifacts_dir)


# ═══════════════════════════════════════════════════════════════════════
# Happy path
# ═══════════════════════════════════════════════════════════════════════


class TestHappyPath:

    @pytest.mark.asyncio
    async def test_full_pipeline_auto_approve(self, td_input, artifacts_dir):
        with _pipeline_patches():
            from core.topic_discovery.pipeline import run_topic_discovery_pipeline
            output = await run_topic_discovery_pipeline(
                td_input, artifacts_root=artifacts_dir,
            )

        assert isinstance(output, TopicDiscoveryOutput)
        assert output.slug == "test-co"
        assert output.effective_slug == "test-co"
        assert output.company_name == "Test Co"
        assert output.taxonomy is not None
        assert output.matrix is not None
        assert output.coverage is not None
        assert output.total_execution_time_s > 0
        assert output.status == TopicDiscoveryStatus.approved

    @pytest.mark.asyncio
    async def test_pipeline_writes_manifest(self, td_input, artifacts_dir):
        with _pipeline_patches():
            from core.topic_discovery.pipeline import run_topic_discovery_pipeline
            await run_topic_discovery_pipeline(td_input, artifacts_root=artifacts_dir)

        manifest_path = artifacts_dir / "topic_discovery" / "test-co" / "_manifest.json"
        assert manifest_path.exists()

        from core.topic_discovery.storage import TopicDiscoveryStorage
        storage = TopicDiscoveryStorage(artifacts_dir, "test-co")
        manifest = storage.read_manifest()
        assert manifest.company_name == "Test Co"
        assert manifest.status == TopicDiscoveryStatus.approved

    @pytest.mark.asyncio
    async def test_pipeline_writes_taxonomy_to_storage(self, td_input, artifacts_dir):
        with _pipeline_patches():
            from core.topic_discovery.pipeline import run_topic_discovery_pipeline
            await run_topic_discovery_pipeline(td_input, artifacts_root=artifacts_dir)

        from core.topic_discovery.storage import TopicDiscoveryStorage
        storage = TopicDiscoveryStorage(artifacts_dir, "test-co")
        tax = storage.get_latest_taxonomy()
        assert tax is not None
        assert tax.status == TopicDiscoveryStatus.approved

    @pytest.mark.asyncio
    async def test_pipeline_writes_matrix_to_storage(self, td_input, artifacts_dir):
        with _pipeline_patches():
            from core.topic_discovery.pipeline import run_topic_discovery_pipeline
            await run_topic_discovery_pipeline(td_input, artifacts_root=artifacts_dir)

        from core.topic_discovery.storage import TopicDiscoveryStorage
        storage = TopicDiscoveryStorage(artifacts_dir, "test-co")
        mat = storage.get_latest_matrix()
        assert mat is not None
        assert mat.status == TopicDiscoveryStatus.approved


# ═══════════════════════════════════════════════════════════════════════
# Partial source failure
# ═══════════════════════════════════════════════════════════════════════


class TestPartialSourceFailure:

    @pytest.mark.asyncio
    async def test_source_b_exception_continues(self, td_input, artifacts_dir):
        with _pipeline_patches(
            source_b=RuntimeError("LLM timeout"),
        ):
            # source_b is an exception → gather catches it
            # We need to patch differently since _pipeline_patches uses return_value
            pass

        # Re-do with side_effect for source_b
        sa = _make_source(TDSource.source_a)
        with (
            patch(f"{_P}.configure_litellm_callbacks"),
            patch(f"{_P}.create_session", return_value="s"),
            patch(f"{_P}.create_trace", return_value=MagicMock()),
            patch(f"{_P}.end_span"),
            patch(f"{_P}.flush"),
            patch(f"{_P}._load_persona_profiles", return_value=["persona md"]),
            patch(f"{_P}.run_source_a_company_brainstorm", return_value=sa),
            patch(f"{_P}.run_source_b_persona_brainstorm", side_effect=RuntimeError("LLM timeout")),
            patch(f"{_P}.run_source_c_competitor_sitemaps", return_value=_make_source(TDSource.source_c, 2)),
            patch(f"{_P}.run_source_d_adversarial", return_value=_make_source(TDSource.source_d, 2)),
            patch(f"{_P}.deduplicate_subdomains", return_value=sa.candidates),
            patch(f"{_P}.compute_all_coverage_metrics", return_value=_make_coverage()),
            patch(f"{_P}.run_hierarchy_construction", return_value=_make_taxonomy()),
            patch(f"{_P}.run_relevance_filtering", return_value=[]),
            patch(f"{_P}.run_topic_generation", return_value=_make_topics()),
        ):
            from core.topic_discovery.pipeline import run_topic_discovery_pipeline
            output = await run_topic_discovery_pipeline(td_input, artifacts_root=artifacts_dir)

        assert output.status == TopicDiscoveryStatus.approved

    @pytest.mark.asyncio
    async def test_all_sources_zero_candidates_raises(self, td_input, artifacts_dir):
        empty = SourceResult(source=TDSource.source_a)
        with (
            patch(f"{_P}.configure_litellm_callbacks"),
            patch(f"{_P}.create_session", return_value="s"),
            patch(f"{_P}.create_trace", return_value=MagicMock()),
            patch(f"{_P}.end_span"),
            patch(f"{_P}.flush"),
            patch(f"{_P}._load_persona_profiles", return_value=["persona md"]),
            patch(f"{_P}.run_source_a_company_brainstorm", return_value=empty),
            patch(f"{_P}.run_source_b_persona_brainstorm", return_value=empty),
            patch(f"{_P}.run_source_c_competitor_sitemaps", return_value=empty),
            patch(f"{_P}.run_source_d_adversarial", return_value=empty),
        ):
            from core.topic_discovery.pipeline import run_topic_discovery_pipeline
            with pytest.raises(RuntimeError, match="0 candidates"):
                await run_topic_discovery_pipeline(td_input, artifacts_root=artifacts_dir)


# ═══════════════════════════════════════════════════════════════════════
# SSE events
# ═══════════════════════════════════════════════════════════════════════


class TestSSEEvents:

    @pytest.mark.asyncio
    async def test_events_emitted(self, td_input, artifacts_dir):
        event_bus = MagicMock()

        with _pipeline_patches():
            from core.topic_discovery.pipeline import run_topic_discovery_pipeline
            await run_topic_discovery_pipeline(
                td_input, artifacts_root=artifacts_dir,
                task_id="task-sse", event_bus=event_bus,
            )

        event_types = [call[0][1] for call in event_bus.publish.call_args_list]
        assert "pipeline_start" in event_types
        assert "completed" in event_types
        assert "td_phase_start" in event_types
        assert "td_phase_complete" in event_types
        assert "td_source_complete" in event_types


# ═══════════════════════════════════════════════════════════════════════
# Task store transitions
# ═══════════════════════════════════════════════════════════════════════


class TestTaskStore:

    @pytest.mark.asyncio
    async def test_task_store_step_progression(self, td_input, artifacts_dir):
        task_store = MagicMock()

        with _pipeline_patches():
            from core.topic_discovery.pipeline import run_topic_discovery_pipeline
            await run_topic_discovery_pipeline(
                td_input, artifacts_root=artifacts_dir,
                task_id="task-steps", task_store=task_store,
            )

        steps = [
            c.kwargs.get("current_step")
            for c in task_store.update_task.call_args_list
            if c.kwargs.get("current_step")
        ]
        assert "preflight" in steps
        assert "phase_1_multi_source" in steps
        assert "phase_2_merge" in steps
        assert "phase_4_finalize" in steps


# ═══════════════════════════════════════════════════════════════════════
# Product slug → effective_slug routing
# ═══════════════════════════════════════════════════════════════════════


class TestProductSlug:

    @pytest.mark.asyncio
    async def test_effective_slug_with_product(self, tmp_path):
        td_input = TopicDiscoveryInput(
            company_name="Test Co",
            domain="test.com",
            company_slug="test-co",
            product_slug="cards",
            auto_approve_checkpoints=[1, 2],
            max_expansion_rounds=2,
        )

        # Company context at company level (fallback)
        ctx_dir = tmp_path / "company_context"
        ctx_dir.mkdir()
        (ctx_dir / "test-co.md").write_text("# Test Co\nCompany context.")

        with _pipeline_patches():
            from core.topic_discovery.pipeline import run_topic_discovery_pipeline
            output = await run_topic_discovery_pipeline(
                td_input, artifacts_root=tmp_path,
            )

        assert output.effective_slug == "test-co__cards"
        assert (tmp_path / "topic_discovery" / "test-co__cards" / "_manifest.json").exists()


# ═══════════════════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════════════════


class TestHelpers:

    def test_flatten_subdomain_names(self):
        from core.topic_discovery.pipeline import _flatten_subdomain_names
        nodes = [
            SubdomainNode(
                name="Parent",
                children=[SubdomainNode(name="Child 1"), SubdomainNode(name="Child 2")],
            ),
            SubdomainNode(name="Root 2"),
        ]
        assert _flatten_subdomain_names(nodes) == ["Parent", "Child 1", "Child 2", "Root 2"]

    def test_flatten_empty(self):
        from core.topic_discovery.pipeline import _flatten_subdomain_names
        assert _flatten_subdomain_names([]) == []

    def test_compute_distributions(self):
        from core.topic_discovery.pipeline import _compute_distributions
        assignments = [
            TopicAssignment(buyer_stage=BuyerStage.TOFU, intent_type=IntentType.informational, audience_segment="CFO"),
            TopicAssignment(buyer_stage=BuyerStage.MOFU, intent_type=IntentType.commercial, audience_segment="CFO"),
            TopicAssignment(buyer_stage=BuyerStage.TOFU, intent_type=IntentType.informational, audience_segment="VP Eng"),
        ]
        d = _compute_distributions(assignments)
        assert d["buyer_stage"]["tofu"] == 2
        assert d["buyer_stage"]["mofu"] == 1
        assert d["intent"]["informational"] == 2
        assert d["audience"]["CFO"] == 2

    def test_build_persona_summaries(self):
        from core.topic_discovery.pipeline import _build_persona_summaries
        result = _build_persona_summaries(["Persona A content", "Persona B content"])
        assert "Persona 1" in result
        assert "Persona 2" in result

    def test_build_persona_summaries_empty(self):
        from core.topic_discovery.pipeline import _build_persona_summaries
        assert _build_persona_summaries([]) == ""

    def test_emit_null_safe(self):
        from core.topic_discovery.pipeline import _emit
        _emit(None, None, "test", {})  # should not raise

    def test_update_task_null_safe(self):
        from core.topic_discovery.pipeline import _update_task
        _update_task(None, None)  # should not raise
