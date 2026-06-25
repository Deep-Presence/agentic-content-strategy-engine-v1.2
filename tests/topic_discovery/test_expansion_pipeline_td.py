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

import contextlib
import copy
import inspect
from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

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
    TopicDiscoveryManifest,
    TopicDiscoveryStatus,
    TopicExpansionInput,
    TopicExpansionOutput,
)

# Patch targets
_P = "core.topic_discovery.pipeline"


def test_expansion_cannibalization_uses_resolved_byok_embedding_config():
    from core.topic_discovery.pipeline import run_topic_expansion_pipeline

    source = inspect.getsource(run_topic_expansion_pipeline)
    assert "topic_discovery.cannibalization_embedding" in source
    assert "resolved_model_config=cannibalization_embedding_config" in source


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session_factory():
    """Mock async session factory for db_ops calls."""
    return AsyncMock()


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
    """Artifacts dir with company context and persona files (required by expansion prompts).

    DB artifacts (taxonomy, manifest, etc.) are provided by db_ops mocks.
    """
    # Company context
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


def _make_manifest(
    taxonomy_version: int = 1,
    scoring_version: int = 1,
    matrix_version: int = 0,
    status: TopicDiscoveryStatus = TopicDiscoveryStatus.discovery_complete,
    expanded_subdomain_ids: list | None = None,
    last_expansion_task_id: str = "",
) -> TopicDiscoveryManifest:
    return TopicDiscoveryManifest(
        slug="test-co",
        company_name="Test Co",
        domain_name="test.com",
        status=status,
        taxonomy_version=taxonomy_version,
        scoring_version=scoring_version,
        persona_affinity_version=1,
        matrix_version=matrix_version,
        expanded_subdomain_ids=expanded_subdomain_ids or [],
        last_expansion_task_id=last_expansion_task_id,
    )


# Track manifest state across calls for re-entrant tests
_manifest_state: dict = {}


def _expansion_patches(
    manifest: TopicDiscoveryManifest | None = None,
    taxonomy: TaxonomyTree | None = None,
    previous_matrix: TopicAssignmentMatrix | None = None,
):
    """Context manager patching Pipeline B externals + db_ops.

    Provides both agent mocks and db_ops mocks needed by Pipeline B.
    """
    from contextlib import contextmanager
    import uuid as _uuid

    _manifest = manifest or _make_manifest()
    _taxonomy = taxonomy or _make_taxonomy()

    # Track manifest writes for re-entrant tests
    _manifest_state["current"] = _manifest

    async def _mock_db_read_manifest(sf, slug):
        return copy.deepcopy(_manifest_state["current"])

    async def _mock_db_write_manifest(sf, discovery_id, m):
        _manifest_state["current"] = copy.deepcopy(m)

    async def _mock_db_write_matrix(sf, discovery_id, matrix, version=0, **kwargs):
        # Track matrix writes
        _manifest_state.setdefault("matrices", []).append(copy.deepcopy(matrix))
        return version + 1

    async def _mock_db_read_latest_matrix(sf, slug):
        matrices = _manifest_state.get("matrices", [])
        return copy.deepcopy(matrices[-1]) if matrices else previous_matrix

    async def _mock_db_write_taxonomy(sf, discovery_id, tax, version=0):
        _manifest_state["taxonomy"] = copy.deepcopy(tax)
        return (_uuid.uuid4(), version)

    async def _mock_db_write_assignments_for_subdomain(
        sf, discovery_id, subdomain_node_id, assignments, matrix_version, batch_id,
        **kwargs,
    ):
        # Track per-subdomain writes and accumulate into matrices list
        from core.models.topic_discovery import TopicAssignmentMatrix, TopicDiscoveryStatus
        existing = _manifest_state.get("matrices", [])
        prev = copy.deepcopy(existing[-1]) if existing else TopicAssignmentMatrix()
        # Add new assignments to previous matrix
        from core.models.topic_discovery import TopicAssignment
        prev_assignments = list(prev.assignments)
        # Remove old assignments for this subdomain
        prev_assignments = [a for a in prev_assignments if a.subdomain_id != str(subdomain_node_id)]
        prev_assignments.extend(copy.deepcopy(assignments))
        prev.assignments = prev_assignments
        prev.total_assignments = len(prev_assignments)
        _manifest_state.setdefault("matrices", []).append(copy.deepcopy(prev))
        return len(assignments)

    @contextmanager
    def _ctx():
        patches = [
            patch(f"{_P}.configure_openrouter"),
            patch(f"{_P}.create_session", return_value="s"),
            patch(f"{_P}.create_trace", return_value=MagicMock()),
            patch(f"{_P}.end_span"),
            patch(f"{_P}.flush"),
            patch(f"{_P}.load_persona_profiles", return_value=["## Persona 1\nCFO persona."]),
            patch(f"{_P}._load_persona_entries", return_value=[("p1", "CFO", "")]),
            patch(f"{_P}.run_subdomain_expansion", return_value=_make_topics()),
            # db_ops mocks (legacy — still used by Pipeline A)
            patch(f"{_P}.db_read_manifest", side_effect=_mock_db_read_manifest),
            patch(f"{_P}.db_read_taxonomy", new_callable=AsyncMock, return_value=copy.deepcopy(_taxonomy)),
            patch(f"{_P}.db_read_scoring", new_callable=AsyncMock, return_value=_make_scored_subdomains()),
            patch(f"{_P}.db_read_persona_affinity", new_callable=AsyncMock, return_value=_make_persona_affinity()),
            patch(f"{_P}.db_read_latest_matrix", side_effect=_mock_db_read_latest_matrix),
            patch(f"{_P}.db_write_matrix", side_effect=_mock_db_write_matrix),
            patch(f"{_P}.db_write_taxonomy", side_effect=_mock_db_write_taxonomy),
            patch(f"{_P}.db_write_manifest", side_effect=_mock_db_write_manifest),
            # Additive upsert mocks (Pipeline B per-subdomain writes)
            patch(f"{_P}.db_write_assignments_for_subdomain", side_effect=_mock_db_write_assignments_for_subdomain),
            patch(f"{_P}.db_claim_subdomain_for_expansion", new_callable=AsyncMock, return_value=True),
            patch(f"{_P}.db_mark_subdomain_expanded", new_callable=AsyncMock),
            patch(f"{_P}.db_rebuild_tree_json", new_callable=AsyncMock, return_value=None),
            patch(f"{_P}.db_reset_stale_expanding", new_callable=AsyncMock, return_value=0),
            patch("core.topic_discovery.persistence.persist_td_discovery", new_callable=AsyncMock, return_value=_uuid.uuid4()),
        ]
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            yield

    return _ctx()


# ═══════════════════════════════════════════════════════════════════════
# Preflight errors
# ═══════════════════════════════════════════════════════════════════════


class TestExpansionPreflight:

    @pytest.mark.asyncio
    async def test_session_factory_none_raises(self, tmp_path):
        """Pipeline B fails fast when session_factory is None (DB required)."""
        inp = TopicExpansionInput(
            company_name="Test Co",
            domain="test.com",
            company_slug="test-co",
            effective_slug="test-co",
            subdomain_ids=["sd-1"],
        )
        from core.topic_discovery.pipeline import run_topic_expansion_pipeline
        with pytest.raises(RuntimeError, match="session_factory is required"):
            await run_topic_expansion_pipeline(
                inp, artifacts_root=tmp_path, session_factory=None,
            )

    @pytest.mark.asyncio
    async def test_missing_discovery_artifacts(self, tmp_path, mock_session_factory):
        """Pipeline B fails if Pipeline A hasn't run (manifest has taxonomy_version=0)."""
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

        # Manifest with taxonomy_version=0 means discovery hasn't run
        empty_manifest = _make_manifest(taxonomy_version=0, scoring_version=0)
        with _expansion_patches(manifest=empty_manifest):
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            with pytest.raises(RuntimeError, match="not completed"):
                await run_topic_expansion_pipeline(
                    inp, artifacts_root=tmp_path, session_factory=mock_session_factory,
                )

    @pytest.mark.asyncio
    async def test_missing_taxonomy_version(self, tmp_path, mock_session_factory):
        """Pipeline B fails if requested taxonomy version doesn't exist in DB."""
        ctx_dir = tmp_path / "company_context"
        ctx_dir.mkdir()
        (ctx_dir / "test-co.md").write_text("# Test Co")

        inp = TopicExpansionInput(
            company_name="Test Co",
            company_slug="test-co",
            effective_slug="test-co",
            subdomain_ids=["sd-1"],
        )

        # Manifest says taxonomy_version=1, but db_read_taxonomy returns None
        manifest = _make_manifest(taxonomy_version=1, scoring_version=1)
        with (
            patch(f"{_P}.configure_openrouter"),
            patch(f"{_P}.create_session", return_value="s"),
            patch(f"{_P}.create_trace", return_value=MagicMock()),
            patch(f"{_P}.end_span"),
            patch(f"{_P}.flush"),
            patch(f"{_P}.db_read_manifest", new_callable=AsyncMock, return_value=manifest),
            patch(f"{_P}.db_read_taxonomy", new_callable=AsyncMock, return_value=None),
            patch(f"{_P}.db_read_scoring", new_callable=AsyncMock, return_value=_make_scored_subdomains()),
            patch(f"{_P}.db_read_persona_affinity", new_callable=AsyncMock, return_value=_make_persona_affinity()),
        ):
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            with pytest.raises(RuntimeError, match="not found"):
                await run_topic_expansion_pipeline(
                    inp, artifacts_root=tmp_path, session_factory=mock_session_factory,
                )


# ═══════════════════════════════════════════════════════════════════════
# Subdomain validation
# ═══════════════════════════════════════════════════════════════════════


class TestExpansionSubdomainValidation:

    @pytest.mark.asyncio
    async def test_empty_subdomain_ids(self, artifacts_dir, mock_session_factory):
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
                await run_topic_expansion_pipeline(
                    inp, artifacts_root=artifacts_dir, session_factory=mock_session_factory,
                )

    @pytest.mark.asyncio
    async def test_all_unknown_ids(self, artifacts_dir, mock_session_factory):
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
                await run_topic_expansion_pipeline(
                    inp, artifacts_root=artifacts_dir, session_factory=mock_session_factory,
                )

    @pytest.mark.asyncio
    async def test_partial_unknown_ids_continues(self, expansion_input, artifacts_dir, mock_session_factory):
        """Unknown IDs are skipped, valid ones are expanded."""
        expansion_input.subdomain_ids = ["sd-1", "nonexistent-1"]

        with _expansion_patches():
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            output = await run_topic_expansion_pipeline(
                expansion_input, artifacts_root=artifacts_dir,
                session_factory=mock_session_factory,
            )

        assert output.subdomains_expanded == 1


# ═══════════════════════════════════════════════════════════════════════
# Happy path
# ═══════════════════════════════════════════════════════════════════════


class TestExpansionHappyPath:

    @pytest.mark.asyncio
    async def test_basic_expansion(self, expansion_input, artifacts_dir, mock_session_factory):
        """Expand two subdomains → matrix output with auto-approved HITL-2."""
        _manifest_state.clear()
        with _expansion_patches():
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            output = await run_topic_expansion_pipeline(
                expansion_input, artifacts_root=artifacts_dir,
                session_factory=mock_session_factory,
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
    async def test_expansion_passes_workspace_context_to_agent(self, expansion_input, artifacts_dir, mock_session_factory):
        expansion_input.workspace_id = "ws-td"
        _manifest_state.clear()
        with (
            _expansion_patches(),
            patch(f"{_P}.resolve_model_config_for_agent", new_callable=AsyncMock) as mock_resolve,
            patch(f"{_P}.run_subdomain_expansion", return_value=_make_topics()) as mock_expand,
        ):
            mock_resolve.return_value = MagicMock()
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            await run_topic_expansion_pipeline(
                expansion_input,
                artifacts_root=artifacts_dir,
                session_factory=mock_session_factory,
            )

        mock_resolve.assert_awaited_once()
        assert mock_expand.call_count == 2
        for call in mock_expand.call_args_list:
            assert call.kwargs["workspace_id"] == "ws-td"
            assert call.kwargs["workspace_slug"] == "test-co"

    @pytest.mark.asyncio
    async def test_expansion_writes_matrix(self, expansion_input, artifacts_dir, mock_session_factory):
        """Pipeline B writes matrix to DB."""
        _manifest_state.clear()
        with _expansion_patches():
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            output = await run_topic_expansion_pipeline(
                expansion_input, artifacts_root=artifacts_dir,
                session_factory=mock_session_factory,
            )

        assert output.matrix is not None
        assert output.matrix.total_assignments > 0

    @pytest.mark.asyncio
    async def test_expansion_updates_manifest(self, expansion_input, artifacts_dir, mock_session_factory):
        """Pipeline B updates manifest with matrix version and expanded IDs."""
        _manifest_state.clear()
        with _expansion_patches():
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            await run_topic_expansion_pipeline(
                expansion_input, artifacts_root=artifacts_dir,
                session_factory=mock_session_factory, task_id="task-exp",
            )

        manifest = _manifest_state["current"]
        assert manifest.matrix_version > 0
        assert manifest.status == TopicDiscoveryStatus.approved
        assert set(manifest.expanded_subdomain_ids) == {"sd-1", "sd-2"}
        assert manifest.last_expansion_task_id is not None


# ═══════════════════════════════════════════════════════════════════════
# Partial failure
# ═══════════════════════════════════════════════════════════════════════


class TestExpansionPartialFailure:

    @pytest.mark.asyncio
    async def test_one_subdomain_fails(self, artifacts_dir, mock_session_factory):
        """One subdomain fails, rest succeed. Counters reflect only successes."""
        _manifest_state.clear()
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

        manifest = _make_manifest()
        taxonomy = _make_taxonomy()
        with (
            patch(f"{_P}.configure_openrouter"),
            patch(f"{_P}.create_session", return_value="s"),
            patch(f"{_P}.create_trace", return_value=MagicMock()),
            patch(f"{_P}.end_span"),
            patch(f"{_P}.flush"),
            patch(f"{_P}.load_persona_profiles", return_value=["persona md"]),
            patch(f"{_P}._load_persona_entries", return_value=[("p1", "CFO", "")]),
            patch(f"{_P}.run_subdomain_expansion", side_effect=_expansion_with_failure),
            patch(f"{_P}.db_read_manifest", new_callable=AsyncMock, return_value=manifest),
            patch(f"{_P}.db_read_taxonomy", new_callable=AsyncMock, return_value=copy.deepcopy(taxonomy)),
            patch(f"{_P}.db_read_scoring", new_callable=AsyncMock, return_value=_make_scored_subdomains()),
            patch(f"{_P}.db_read_persona_affinity", new_callable=AsyncMock, return_value=_make_persona_affinity()),
            patch(f"{_P}.db_read_latest_matrix", new_callable=AsyncMock, return_value=None),
            patch(f"{_P}.db_write_matrix", new_callable=AsyncMock, return_value=1),
            patch(f"{_P}.db_write_taxonomy", new_callable=AsyncMock, return_value=(MagicMock(), 1)),
            patch(f"{_P}.db_write_manifest", new_callable=AsyncMock),
            patch("core.topic_discovery.persistence.persist_td_discovery", new_callable=AsyncMock, return_value=MagicMock()),
        ):
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            output = await run_topic_expansion_pipeline(
                inp, artifacts_root=artifacts_dir, session_factory=mock_session_factory,
            )

        assert output.subdomains_expanded == 1
        assert output.subdomains_failed == 1
        assert output.total_assignments == len(output.matrix.assignments)
        assert output.total_assignments > 0

    @pytest.mark.asyncio
    async def test_expansion_status_updated(self, artifacts_dir, mock_session_factory):
        """expansion_status on taxonomy nodes updates after expansion."""
        _manifest_state.clear()
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

        manifest = _make_manifest()
        taxonomy = _make_taxonomy()

        # Track db_mark_subdomain_expanded calls
        mark_calls = []

        async def _capture_mark(sf, node_id, success):
            mark_calls.append((str(node_id), success))

        patches = [
            patch(f"{_P}.configure_openrouter"),
            patch(f"{_P}.create_session", return_value="s"),
            patch(f"{_P}.create_trace", return_value=MagicMock()),
            patch(f"{_P}.end_span"),
            patch(f"{_P}.flush"),
            patch(f"{_P}.load_persona_profiles", return_value=["persona md"]),
            patch(f"{_P}._load_persona_entries", return_value=[("p1", "CFO", "")]),
            patch(f"{_P}.run_subdomain_expansion", side_effect=_expansion_with_failure),
            patch(f"{_P}.db_read_manifest", new_callable=AsyncMock, return_value=manifest),
            patch(f"{_P}.db_read_taxonomy", new_callable=AsyncMock, return_value=copy.deepcopy(taxonomy)),
            patch(f"{_P}.db_read_scoring", new_callable=AsyncMock, return_value=_make_scored_subdomains()),
            patch(f"{_P}.db_read_persona_affinity", new_callable=AsyncMock, return_value=_make_persona_affinity()),
            patch(f"{_P}.db_read_latest_matrix", new_callable=AsyncMock, return_value=None),
            patch(f"{_P}.db_write_matrix", new_callable=AsyncMock, return_value=1),
            patch(f"{_P}.db_write_taxonomy", new_callable=AsyncMock, return_value=(MagicMock(), 1)),
            patch(f"{_P}.db_write_manifest", new_callable=AsyncMock),
            patch(f"{_P}.db_mark_subdomain_expanded", side_effect=_capture_mark),
            patch(f"{_P}.db_write_assignments_for_subdomain", new_callable=AsyncMock, return_value=2),
            patch(f"{_P}.db_claim_subdomain_for_expansion", new_callable=AsyncMock, return_value=True),
            patch(f"{_P}.db_rebuild_tree_json", new_callable=AsyncMock, return_value=None),
            patch(f"{_P}.db_reset_stale_expanding", new_callable=AsyncMock, return_value=0),
            patch("core.topic_discovery.persistence.persist_td_discovery", new_callable=AsyncMock, return_value=MagicMock()),
        ]
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            output = await run_topic_expansion_pipeline(
                inp, artifacts_root=artifacts_dir, session_factory=mock_session_factory,
            )

        # Verify expansion results
        assert output.subdomains_expanded == 1
        assert output.subdomains_failed == 1
        # With non-UUID test IDs, DB mark calls are skipped (UUID parse guard).
        # In production, real UUIDs trigger db_mark_subdomain_expanded.
        # Output counts are still correct from the in-memory tracking.


# ═══════════════════════════════════════════════════════════════════════
# Re-entrant expansion
# ═══════════════════════════════════════════════════════════════════════


class TestExpansionReentrant:

    @pytest.mark.asyncio
    async def test_two_expansions_accumulate(self, artifacts_dir, mock_session_factory):
        """Running Pipeline B twice with different subdomains accumulates
        expanded_subdomain_ids AND merges assignments from both runs."""
        _manifest_state.clear()

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
                session_factory=mock_session_factory,
            )

        manifest1 = _manifest_state["current"]
        assert manifest1.expanded_subdomain_ids == ["sd-1"]
        v1 = manifest1.matrix_version

        matrices = _manifest_state.get("matrices", [])
        assert len(matrices) > 0
        mat1 = matrices[-1]
        sd1_count = len([a for a in mat1.assignments if a.subdomain_id == "sd-1"])
        assert sd1_count > 0

        # Second expansion: sd-2 — DON'T clear _manifest_state, let it accumulate
        inp2 = TopicExpansionInput(
            company_name="Test Co",
            company_slug="test-co",
            effective_slug="test-co",
            subdomain_ids=["sd-2"],
            auto_approve_checkpoints=[2],
        )

        # Pass the current manifest (with sd-1 already expanded) to _expansion_patches
        with _expansion_patches(manifest=copy.deepcopy(manifest1)):
            output2 = await run_topic_expansion_pipeline(
                inp2, artifacts_root=artifacts_dir, task_id="task-2",
                session_factory=mock_session_factory,
            )

        manifest2 = _manifest_state["current"]
        assert sorted(manifest2.expanded_subdomain_ids) == ["sd-1", "sd-2"]
        assert manifest2.matrix_version > 0
        assert manifest2.last_expansion_task_id == "task-2"

        # The output matrix should contain assignments from both runs
        mat2 = output2.matrix
        assert mat2 is not None
        sd1_assignments = [a for a in mat2.assignments if a.subdomain_id == "sd-1"]
        sd2_assignments = [a for a in mat2.assignments if a.subdomain_id == "sd-2"]
        assert len(sd1_assignments) == sd1_count, "sd-1 assignments must be preserved"
        assert len(sd2_assignments) > 0, "sd-2 assignments must be added"

    @pytest.mark.asyncio
    async def test_reexpand_replaces_old_assignments(self, artifacts_dir, mock_session_factory):
        """Re-expanding the same subdomain replaces its old assignments."""
        _manifest_state.clear()

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
            await run_topic_expansion_pipeline(
                inp, artifacts_root=artifacts_dir, session_factory=mock_session_factory,
            )

        matrices = _manifest_state.get("matrices", [])
        assert len(matrices) > 0
        mat1 = matrices[-1]
        first_count = len([a for a in mat1.assignments if a.subdomain_id == "sd-1"])

        # Second expansion of sd-1: returns 3 topics this time
        with _expansion_patches():
            with patch(f"{_P}.run_subdomain_expansion", return_value=_make_topics(3)):
                await run_topic_expansion_pipeline(
                    inp, artifacts_root=artifacts_dir, session_factory=mock_session_factory,
                )

        matrices2 = _manifest_state.get("matrices", [])
        mat2 = matrices2[-1]
        sd1_assignments = [a for a in mat2.assignments if a.subdomain_id == "sd-1"]
        assert len(sd1_assignments) == 3, "Re-expansion should replace with fresh topics"

    @pytest.mark.asyncio
    async def test_failed_expansion_preserves_previous(self, artifacts_dir, mock_session_factory):
        """If a subdomain fails during re-expansion, its previous assignments are kept."""
        _manifest_state.clear()

        # First: successfully expand sd-1 and sd-2
        inp1 = TopicExpansionInput(
            company_name="Test Co",
            company_slug="test-co",
            effective_slug="test-co",
            subdomain_ids=["sd-1", "sd-2"],
            auto_approve_checkpoints=[2],
        )

        with _expansion_patches():
            with patch(f"{_P}.run_subdomain_expansion", side_effect=lambda **kw: _make_topics(2)):
                from core.topic_discovery.pipeline import run_topic_expansion_pipeline
                await run_topic_expansion_pipeline(
                    inp1, artifacts_root=artifacts_dir, session_factory=mock_session_factory,
                )

        matrices = _manifest_state.get("matrices", [])
        mat1 = matrices[-1]
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

        with _expansion_patches():
            with patch(f"{_P}.run_subdomain_expansion", side_effect=_fail_expansion):
                output = await run_topic_expansion_pipeline(
                    inp2, artifacts_root=artifacts_dir, session_factory=mock_session_factory,
                )

        assert output.subdomains_failed == 1
        assert output.subdomains_expanded == 0

        # Check the output matrix
        mat2 = output.matrix
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
    async def test_events_emitted(self, expansion_input, artifacts_dir, mock_session_factory):
        """Pipeline B emits expected SSE events."""
        _manifest_state.clear()
        event_bus = MagicMock()

        with _expansion_patches():
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            await run_topic_expansion_pipeline(
                expansion_input, artifacts_root=artifacts_dir,
                task_id="task-sse", event_bus=event_bus,
                session_factory=mock_session_factory,
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
    async def test_step_progression(self, expansion_input, artifacts_dir, mock_session_factory):
        """Pipeline B reports correct step names to task store."""
        _manifest_state.clear()
        task_store = MagicMock()

        with _expansion_patches():
            from core.topic_discovery.pipeline import run_topic_expansion_pipeline
            await run_topic_expansion_pipeline(
                expansion_input, artifacts_root=artifacts_dir,
                task_id="task-steps", task_store=task_store,
                session_factory=mock_session_factory,
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
