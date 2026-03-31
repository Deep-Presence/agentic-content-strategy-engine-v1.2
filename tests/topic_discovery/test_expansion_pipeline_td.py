"""Tests for Topic Expansion pipeline (Pipeline B).

Covers:
- Preflight: validates Pipeline A artifacts exist
- Happy path: expand selected subdomains → matrix output
- Subdomain validation: empty IDs, unknown IDs
- Partial failure: one subdomain fails, rest succeed
- HITL-2: matrix approval with edits
- Re-entrant: multiple expansion runs accumulate expanded_subdomain_ids
- expansion_status updated on taxonomy nodes
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from core.models.topic_discovery import (
    BuyerStage,
    IntentType,
    PersonaAffinityIndex,
    RelevanceCell,
    ScoredSubdomainList,
    SubdomainNode,
    SubdomainScore,
    TaxonomyTree,
    TopicAssignment,
    TopicAssignmentMatrix,
    TopicDiscoveryStatus,
    TopicExpansionInput,
    TopicExpansionOutput,
)

# Patch targets
_P = "core.topic_discovery.pipeline"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def expansion_input() -> TopicExpansionInput:
    return TopicExpansionInput(
        company_name="Test Co",
        domain="test.com",
        company_slug="test-co",
        effective_slug="test-co",
        subdomain_ids=["sd-1", "sd-2"],
        auto_approve_checkpoints=[2],
    )


@pytest.fixture
def artifacts_dir(tmp_path: Path) -> Path:
    """Artifacts dir with company context, personas, and Pipeline A outputs."""
    # Company context
    ctx_dir = tmp_path / "company_context"
    ctx_dir.mkdir()
    (ctx_dir / "test-co.md").write_text(
        "# Test Co\nA fintech company specializing in expense management.",
        encoding="utf-8",
    )

    # Write Pipeline A artifacts via storage
    from core.topic_discovery.storage import TopicDiscoveryStorage
    from core.models.topic_discovery import TopicDiscoveryManifest

    storage = TopicDiscoveryStorage(tmp_path, "test-co")

    # Taxonomy
    taxonomy = _make_taxonomy()
    taxonomy.status = TopicDiscoveryStatus.approved
    storage.write_taxonomy(taxonomy, version=1)

    # Scored subdomains
    storage.write_scoring(_make_scored_subdomains(), version=1)

    # Persona affinity
    storage.write_persona_affinity(_make_persona_affinity(), version=1)

    # Manifest
    manifest = TopicDiscoveryManifest(
        slug="test-co",
        company_name="Test Co",
        domain_name="test.com",
        status=TopicDiscoveryStatus.discovery_complete,
        taxonomy_version=1,
        scoring_version=1,
        persona_affinity_version=1,
        matrix_version=0,
    )
    storage.write_manifest(manifest)

    return tmp_path


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _make_taxonomy() -> TaxonomyTree:
    return TaxonomyTree(
        domain_name="test.com",
        version=1,
        root_nodes=[
            SubdomainNode(
                id="sd-1", name="Expense Management", description="Managing expenses",
                depth=0, confidence=0.9,
                source_provenance={"source_a": True, "source_b": True},
                priority_score=0.9,
            ),
            SubdomainNode(
                id="sd-2", name="Corporate Cards", description="Corp card programs",
                depth=0, confidence=0.8,
                source_provenance={"source_a": True},
                priority_score=0.7,
            ),
            SubdomainNode(
                id="sd-3", name="Travel Reimbursement", description="Travel expense reimbursement",
                depth=0, confidence=0.7,
                source_provenance={"source_b": True},
                priority_score=0.5,
            ),
        ],
        total_subdomains=3,
        max_depth=0,
    )


def _make_scored_subdomains() -> ScoredSubdomainList:
    return ScoredSubdomainList(
        version=1,
        scores=[
            SubdomainScore(
                subdomain_id="sd-1", subdomain_name="Expense Management",
                composite_score=0.9, rank=1,
            ),
            SubdomainScore(
                subdomain_id="sd-2", subdomain_name="Corporate Cards",
                composite_score=0.7, rank=2,
            ),
            SubdomainScore(
                subdomain_id="sd-3", subdomain_name="Travel Reimbursement",
                composite_score=0.5, rank=3,
            ),
        ],
        total_scored=3,
        signals_used=["source_confidence", "persona_breadth"],
    )


def _make_persona_affinity() -> PersonaAffinityIndex:
    return PersonaAffinityIndex(version=1, total_personas=1, total_subdomains=3)


def _make_topics(count: int = 2) -> List[TopicAssignment]:
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


def _expansion_patches():
    """Context manager patching Pipeline B externals."""
    from contextlib import contextmanager

    @contextmanager
    def _ctx():
        with (
            patch(f"{_P}.configure_openrouter"),
            patch(f"{_P}.create_session", return_value="s"),
            patch(f"{_P}.create_trace", return_value=MagicMock()),
            patch(f"{_P}.end_span"),
            patch(f"{_P}.flush"),
            patch(f"{_P}.load_persona_profiles", return_value=["## Persona 1\nCFO persona."]),
            patch(f"{_P}._load_persona_entries", return_value=[("p1", "CFO")]),
            patch(f"{_P}.run_subdomain_expansion", return_value=_make_topics()),
        ):
            yield

    return _ctx()


# ═══════════════════════════════════════════════════════════════════════
# Preflight errors
# ═══════════════════════════════════════════════════════════════════════


class TestExpansionPreflight:

    @pytest.mark.asyncio
    async def test_missing_discovery_artifacts(self, tmp_path):
        """Pipeline B fails if Pipeline A hasn't run."""
        # Company context exists but no taxonomy/manifest
        ctx_dir = tmp_path / "company_context"
        ctx_dir.mkdir()
        (ctx_dir / "test-co.md").write_text("# Test Co")

        inp = TopicExpansionInput(
            company_name="Test Co",
            domain="test.com",
            company_slug="test-co",
            effective_slug="test-co",
            subdomain_ids=["sd-1"],
        )

        with _expansion_patches():
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            with pytest.raises(RuntimeError, match="not completed"):
                await run_topic_expansion_pipeline(inp, artifacts_root=tmp_path)

    @pytest.mark.asyncio
    async def test_missing_taxonomy_version(self, tmp_path):
        """Pipeline B fails if requested taxonomy version doesn't exist."""
        from core.topic_discovery.storage import TopicDiscoveryStorage
        from core.models.topic_discovery import TopicDiscoveryManifest

        ctx_dir = tmp_path / "company_context"
        ctx_dir.mkdir()
        (ctx_dir / "test-co.md").write_text("# Test Co")

        storage = TopicDiscoveryStorage(tmp_path, "test-co")
        # Write manifest referencing version 1, but don't write taxonomy
        manifest = TopicDiscoveryManifest(
            slug="test-co",
            status=TopicDiscoveryStatus.discovery_complete,
            taxonomy_version=1,
            scoring_version=1,
        )
        storage.write_manifest(manifest)
        storage.write_scoring(_make_scored_subdomains(), version=1)

        inp = TopicExpansionInput(
            company_name="Test Co",
            company_slug="test-co",
            effective_slug="test-co",
            subdomain_ids=["sd-1"],
        )

        with _expansion_patches():
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            with pytest.raises(RuntimeError, match="not found"):
                await run_topic_expansion_pipeline(inp, artifacts_root=tmp_path)


# ═══════════════════════════════════════════════════════════════════════
# Subdomain validation
# ═══════════════════════════════════════════════════════════════════════


class TestExpansionSubdomainValidation:

    @pytest.mark.asyncio
    async def test_empty_subdomain_ids(self, artifacts_dir):
        """Empty subdomain_ids raises ValueError."""
        inp = TopicExpansionInput(
            company_name="Test Co",
            company_slug="test-co",
            effective_slug="test-co",
            subdomain_ids=[],
        )

        with _expansion_patches():
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            with pytest.raises(ValueError, match="non-empty"):
                await run_topic_expansion_pipeline(inp, artifacts_root=artifacts_dir)

    @pytest.mark.asyncio
    async def test_all_unknown_ids(self, artifacts_dir):
        """All unknown IDs raises ValueError."""
        inp = TopicExpansionInput(
            company_name="Test Co",
            company_slug="test-co",
            effective_slug="test-co",
            subdomain_ids=["nonexistent-1", "nonexistent-2"],
        )

        with _expansion_patches():
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            with pytest.raises(ValueError, match="No valid subdomain"):
                await run_topic_expansion_pipeline(inp, artifacts_root=artifacts_dir)

    @pytest.mark.asyncio
    async def test_partial_unknown_ids_continues(self, expansion_input, artifacts_dir):
        """Unknown IDs are skipped, valid ones are expanded."""
        expansion_input.subdomain_ids = ["sd-1", "nonexistent-1"]

        with _expansion_patches():
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            output = await run_topic_expansion_pipeline(
                expansion_input, artifacts_root=artifacts_dir,
            )

        assert output.subdomains_expanded == 1


# ═══════════════════════════════════════════════════════════════════════
# Happy path
# ═══════════════════════════════════════════════════════════════════════


class TestExpansionHappyPath:

    @pytest.mark.asyncio
    async def test_basic_expansion(self, expansion_input, artifacts_dir):
        """Expand two subdomains → matrix output with auto-approved HITL-2."""
        with _expansion_patches():
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            output = await run_topic_expansion_pipeline(
                expansion_input, artifacts_root=artifacts_dir,
            )

        assert isinstance(output, TopicExpansionOutput)
        assert output.slug == "test-co"
        assert output.effective_slug == "test-co"
        assert output.matrix is not None
        assert output.subdomains_expanded == 2
        assert output.subdomains_failed == 0
        assert output.total_assignments > 0
        assert output.total_execution_time_s > 0
        assert output.status == TopicDiscoveryStatus.approved

    @pytest.mark.asyncio
    async def test_expansion_writes_matrix(self, expansion_input, artifacts_dir):
        """Pipeline B writes matrix to storage."""
        with _expansion_patches():
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            await run_topic_expansion_pipeline(
                expansion_input, artifacts_root=artifacts_dir,
            )

        from core.topic_discovery.storage import TopicDiscoveryStorage
        storage = TopicDiscoveryStorage(artifacts_dir, "test-co")
        mat = storage.get_latest_matrix()
        assert mat is not None
        assert mat.total_assignments > 0

    @pytest.mark.asyncio
    async def test_expansion_updates_manifest(self, expansion_input, artifacts_dir):
        """Pipeline B updates manifest with matrix version and expanded IDs."""
        with _expansion_patches():
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            await run_topic_expansion_pipeline(
                expansion_input, artifacts_root=artifacts_dir,
            )

        from core.topic_discovery.storage import TopicDiscoveryStorage
        storage = TopicDiscoveryStorage(artifacts_dir, "test-co")
        manifest = storage.read_manifest()
        assert manifest.matrix_version > 0
        assert manifest.status == TopicDiscoveryStatus.approved
        assert set(manifest.expanded_subdomain_ids) == {"sd-1", "sd-2"}
        assert manifest.last_expansion_task_id is not None


# ═══════════════════════════════════════════════════════════════════════
# Partial failure
# ═══════════════════════════════════════════════════════════════════════


class TestExpansionPartialFailure:

    @pytest.mark.asyncio
    async def test_one_subdomain_fails(self, artifacts_dir):
        """One subdomain fails, rest succeed. Counters reflect only successes."""
        inp = TopicExpansionInput(
            company_name="Test Co",
            company_slug="test-co",
            effective_slug="test-co",
            subdomain_ids=["sd-1", "sd-2"],
            auto_approve_checkpoints=[2],
        )

        async def _expansion_with_failure(subdomain_name, **kwargs):
            if subdomain_name == "Corporate Cards":
                raise RuntimeError("Simulated LLM failure")
            return _make_topics(2)

        with (
            patch(f"{_P}.configure_openrouter"),
            patch(f"{_P}.create_session", return_value="s"),
            patch(f"{_P}.create_trace", return_value=MagicMock()),
            patch(f"{_P}.end_span"),
            patch(f"{_P}.flush"),
            patch(f"{_P}.load_persona_profiles", return_value=["persona md"]),
            patch(f"{_P}._load_persona_entries", return_value=[("p1", "CFO")]),
            patch(f"{_P}.run_subdomain_expansion", side_effect=_expansion_with_failure),
        ):
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            output = await run_topic_expansion_pipeline(
                inp, artifacts_root=artifacts_dir,
            )

        assert output.subdomains_expanded == 1
        assert output.subdomains_failed == 1
        assert output.total_assignments == len(output.matrix.assignments)
        assert output.total_assignments > 0

    @pytest.mark.asyncio
    async def test_expansion_status_updated(self, artifacts_dir):
        """expansion_status on taxonomy nodes updates after expansion."""
        inp = TopicExpansionInput(
            company_name="Test Co",
            company_slug="test-co",
            effective_slug="test-co",
            subdomain_ids=["sd-1", "sd-2"],
            auto_approve_checkpoints=[2],
        )

        async def _expansion_with_failure(subdomain_name, **kwargs):
            if subdomain_name == "Corporate Cards":
                raise RuntimeError("fail")
            return _make_topics(2)

        with (
            patch(f"{_P}.configure_openrouter"),
            patch(f"{_P}.create_session", return_value="s"),
            patch(f"{_P}.create_trace", return_value=MagicMock()),
            patch(f"{_P}.end_span"),
            patch(f"{_P}.flush"),
            patch(f"{_P}.load_persona_profiles", return_value=["persona md"]),
            patch(f"{_P}._load_persona_entries", return_value=[("p1", "CFO")]),
            patch(f"{_P}.run_subdomain_expansion", side_effect=_expansion_with_failure),
        ):
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            await run_topic_expansion_pipeline(inp, artifacts_root=artifacts_dir)

        from core.topic_discovery.storage import TopicDiscoveryStorage
        storage = TopicDiscoveryStorage(artifacts_dir, "test-co")
        tax = storage.get_latest_taxonomy()
        assert tax is not None

        node_map = {n.id: n for n in tax.root_nodes}
        assert node_map["sd-1"].expansion_status == "expanded"
        assert node_map["sd-2"].expansion_status == "failed"
        assert node_map["sd-3"].expansion_status == "not_expanded"


# ═══════════════════════════════════════════════════════════════════════
# Re-entrant expansion
# ═══════════════════════════════════════════════════════════════════════


class TestExpansionReentrant:

    @pytest.mark.asyncio
    async def test_two_expansions_accumulate(self, artifacts_dir):
        """Running Pipeline B twice with different subdomains accumulates
        expanded_subdomain_ids AND merges assignments from both runs."""
        # First expansion: sd-1
        inp1 = TopicExpansionInput(
            company_name="Test Co",
            company_slug="test-co",
            effective_slug="test-co",
            subdomain_ids=["sd-1"],
            auto_approve_checkpoints=[2],
        )

        with _expansion_patches():
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            output1 = await run_topic_expansion_pipeline(
                inp1, artifacts_root=artifacts_dir, task_id="task-1",
            )

        from core.topic_discovery.storage import TopicDiscoveryStorage
        storage = TopicDiscoveryStorage(artifacts_dir, "test-co")
        manifest1 = storage.read_manifest()
        assert manifest1.expanded_subdomain_ids == ["sd-1"]
        v1 = manifest1.matrix_version

        mat1 = storage.get_latest_matrix()
        assert mat1 is not None
        sd1_count = len([a for a in mat1.assignments if a.subdomain_id == "sd-1"])
        assert sd1_count > 0

        # Second expansion: sd-2
        inp2 = TopicExpansionInput(
            company_name="Test Co",
            company_slug="test-co",
            effective_slug="test-co",
            subdomain_ids=["sd-2"],
            auto_approve_checkpoints=[2],
        )

        with _expansion_patches():
            output2 = await run_topic_expansion_pipeline(
                inp2, artifacts_root=artifacts_dir, task_id="task-2",
            )

        manifest2 = storage.read_manifest()
        assert sorted(manifest2.expanded_subdomain_ids) == ["sd-1", "sd-2"]
        assert manifest2.matrix_version > v1
        assert manifest2.last_expansion_task_id == "task-2"

        # Verify assignments from BOTH runs are in the latest matrix
        mat2 = storage.get_latest_matrix()
        assert mat2 is not None
        sd1_assignments = [a for a in mat2.assignments if a.subdomain_id == "sd-1"]
        sd2_assignments = [a for a in mat2.assignments if a.subdomain_id == "sd-2"]
        assert len(sd1_assignments) == sd1_count, "sd-1 assignments must be preserved"
        assert len(sd2_assignments) > 0, "sd-2 assignments must be added"
        assert mat2.total_assignments == len(sd1_assignments) + len(sd2_assignments)

    @pytest.mark.asyncio
    async def test_reexpand_replaces_old_assignments(self, artifacts_dir):
        """Re-expanding the same subdomain replaces its old assignments."""
        inp = TopicExpansionInput(
            company_name="Test Co",
            company_slug="test-co",
            effective_slug="test-co",
            subdomain_ids=["sd-1"],
            auto_approve_checkpoints=[2],
        )

        # First expansion: 2 topics
        with _expansion_patches():
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            await run_topic_expansion_pipeline(inp, artifacts_root=artifacts_dir)

        from core.topic_discovery.storage import TopicDiscoveryStorage
        storage = TopicDiscoveryStorage(artifacts_dir, "test-co")
        mat1 = storage.get_latest_matrix()
        assert mat1 is not None
        first_count = len([a for a in mat1.assignments if a.subdomain_id == "sd-1"])

        # Second expansion of sd-1: returns 3 topics this time
        with (
            patch(f"{_P}.configure_openrouter"),
            patch(f"{_P}.create_session", return_value="s"),
            patch(f"{_P}.create_trace", return_value=MagicMock()),
            patch(f"{_P}.end_span"),
            patch(f"{_P}.flush"),
            patch(f"{_P}.load_persona_profiles", return_value=["persona md"]),
            patch(f"{_P}._load_persona_entries", return_value=[("p1", "CFO")]),
            patch(f"{_P}.run_subdomain_expansion", return_value=_make_topics(3)),
        ):
            await run_topic_expansion_pipeline(inp, artifacts_root=artifacts_dir)

        mat2 = storage.get_latest_matrix()
        assert mat2 is not None
        sd1_assignments = [a for a in mat2.assignments if a.subdomain_id == "sd-1"]
        assert len(sd1_assignments) == 3, "Re-expansion should replace with fresh topics"

    @pytest.mark.asyncio
    async def test_failed_expansion_preserves_previous(self, artifacts_dir):
        """If a subdomain fails during re-expansion, its previous assignments are kept."""
        # First: successfully expand sd-1 and sd-2
        # Use side_effect to return fresh objects per call (avoid shared mutation)
        inp1 = TopicExpansionInput(
            company_name="Test Co",
            company_slug="test-co",
            effective_slug="test-co",
            subdomain_ids=["sd-1", "sd-2"],
            auto_approve_checkpoints=[2],
        )

        with (
            patch(f"{_P}.configure_openrouter"),
            patch(f"{_P}.create_session", return_value="s"),
            patch(f"{_P}.create_trace", return_value=MagicMock()),
            patch(f"{_P}.end_span"),
            patch(f"{_P}.flush"),
            patch(f"{_P}.load_persona_profiles", return_value=["persona md"]),
            patch(f"{_P}._load_persona_entries", return_value=[("p1", "CFO")]),
            patch(f"{_P}.run_subdomain_expansion", side_effect=lambda **kw: _make_topics(2)),
        ):
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline  # noqa: F811
            await run_topic_expansion_pipeline(inp1, artifacts_root=artifacts_dir)

        from core.topic_discovery.storage import TopicDiscoveryStorage
        storage = TopicDiscoveryStorage(artifacts_dir, "test-co")
        mat1 = storage.get_latest_matrix()
        assert mat1 is not None
        sd2_original = [a for a in mat1.assignments if a.subdomain_id == "sd-2"]
        assert len(sd2_original) > 0

        # Second: re-expand sd-2 but it FAILS
        inp2 = TopicExpansionInput(
            company_name="Test Co",
            company_slug="test-co",
            effective_slug="test-co",
            subdomain_ids=["sd-2"],
            auto_approve_checkpoints=[2],
        )

        async def _fail_expansion(subdomain_name, **kwargs):
            raise RuntimeError("Simulated failure")

        with (
            patch(f"{_P}.configure_openrouter"),
            patch(f"{_P}.create_session", return_value="s"),
            patch(f"{_P}.create_trace", return_value=MagicMock()),
            patch(f"{_P}.end_span"),
            patch(f"{_P}.flush"),
            patch(f"{_P}.load_persona_profiles", return_value=["persona md"]),
            patch(f"{_P}._load_persona_entries", return_value=[("p1", "CFO")]),
            patch(f"{_P}.run_subdomain_expansion", side_effect=_fail_expansion),
        ):
            # All subdomains fail → pipeline should still produce a matrix
            # with previous assignments preserved
            output = await run_topic_expansion_pipeline(inp2, artifacts_root=artifacts_dir)

        assert output.subdomains_failed == 1
        assert output.subdomains_expanded == 0

        mat2 = storage.get_latest_matrix()
        assert mat2 is not None
        # sd-1 assignments preserved (not touched)
        sd1_kept = [a for a in mat2.assignments if a.subdomain_id == "sd-1"]
        assert len(sd1_kept) > 0, "sd-1 assignments must be preserved"
        # sd-2 assignments also preserved (failed, not in expanded_ids)
        sd2_kept = [a for a in mat2.assignments if a.subdomain_id == "sd-2"]
        assert len(sd2_kept) == len(sd2_original), "sd-2 assignments must be preserved on failure"


# ═══════════════════════════════════════════════════════════════════════
# SSE events
# ═══════════════════════════════════════════════════════════════════════


class TestExpansionSSEEvents:

    @pytest.mark.asyncio
    async def test_events_emitted(self, expansion_input, artifacts_dir):
        """Pipeline B emits expected SSE events."""
        event_bus = MagicMock()

        with _expansion_patches():
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            await run_topic_expansion_pipeline(
                expansion_input, artifacts_root=artifacts_dir,
                task_id="task-sse", event_bus=event_bus,
            )

        event_types = [call[0][1] for call in event_bus.publish.call_args_list]
        assert "pipeline_start" in event_types
        assert "completed" in event_types
        assert "td_phase_start" in event_types
        assert "td_phase_complete" in event_types


# ═══════════════════════════════════════════════════════════════════════
# Task store transitions
# ═══════════════════════════════════════════════════════════════════════


class TestExpansionTaskStore:

    @pytest.mark.asyncio
    async def test_step_progression(self, expansion_input, artifacts_dir):
        """Pipeline B reports correct step names to task store."""
        task_store = MagicMock()

        with _expansion_patches():
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            await run_topic_expansion_pipeline(
                expansion_input, artifacts_root=artifacts_dir,
                task_id="task-steps", task_store=task_store,
            )

        steps = [
            c.kwargs.get("current_step")
            for c in task_store.update_task.call_args_list
            if c.kwargs.get("current_step")
        ]
        assert "expansion_preflight" in steps
        assert "phase_3_expansion" in steps
        assert "finalize_expansion" in steps


# ═══════════════════════════════════════════════════════════════════════
# Helper: _update_expansion_status
# ═══════════════════════════════════════════════════════════════════════


class TestUpdateExpansionStatus:

    def test_marks_expanded_and_failed(self):
        from core.topic_discovery.pipeline import _update_expansion_status

        nodes = [
            SubdomainNode(id="sd-a", name="A"),
            SubdomainNode(id="sd-b", name="B"),
            SubdomainNode(
                id="sd-c", name="C",
                children=[SubdomainNode(id="sd-d", name="D")],
            ),
        ]

        _update_expansion_status(nodes, expanded_ids={"sd-a", "sd-d"}, failed_ids={"sd-b"})

        assert nodes[0].expansion_status == "expanded"
        assert nodes[1].expansion_status == "failed"
        assert nodes[2].expansion_status == "not_expanded"
        assert nodes[2].children[0].expansion_status == "expanded"

    def test_no_changes_on_empty_sets(self):
        from core.topic_discovery.pipeline import _update_expansion_status

        nodes = [SubdomainNode(id="sd-x", name="X")]
        _update_expansion_status(nodes, expanded_ids=set(), failed_ids=set())
        assert nodes[0].expansion_status == "not_expanded"
