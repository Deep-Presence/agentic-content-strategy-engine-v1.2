"""Tests for Knowledge Base pipeline orchestrator.

Tests the DAG execution: Phase 1 (parallel) → Phase 2 (sequential) →
HITL-1 → Phase 3 (parallel) → HITL-2 → Phase 4 (synthesis) → HITL-3.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.knowledge_base import (
    KBAgentResult,
    KBDocType,
    KnowledgeBaseInput,
    KnowledgeBaseOutput,
)

# ---------------------------------------------------------------------------
# Patch targets
# ---------------------------------------------------------------------------

_PIPE = "core.research.knowledge_base.pipeline"
_AGENTS = f"{_PIPE}.agents"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def kb_input() -> KnowledgeBaseInput:
    return KnowledgeBaseInput(
        company_name="Test Co",
        domain="test.co",
        company_slug="test-co",
    )


@pytest.fixture()
def kb_input_auto_approve() -> KnowledgeBaseInput:
    return KnowledgeBaseInput(
        company_name="Test Co",
        domain="test.co",
        company_slug="test-co",
        auto_approve_checkpoints=[1, 2, 3],
    )


def _make_result(
    doc_type: KBDocType,
    content: str = "# Result\n\nContent.",
    error: Optional[str] = None,
) -> KBAgentResult:
    """Build a mock KBAgentResult."""
    return KBAgentResult(
        doc_type=doc_type,
        content_md=content if not error else "",
        word_count=len(content.split()) if not error else 0,
        execution_time_s=1.0,
        error=error,
    )


@pytest.fixture(autouse=True)
def _mock_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable tracing for all pipeline tests."""
    for fn_name in ("create_session", "create_span", "end_span", "log_generation", "flush"):
        monkeypatch.setattr(f"{_PIPE}.{fn_name}", lambda *a, **kw: None)


@pytest.fixture(autouse=True)
def _mock_agents(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock all 6 agent functions to return preset results."""
    async def _co(input_data, **kw):
        return _make_result(KBDocType.COMPANY_OVERVIEW, "# Company Overview\n\nOverview content.")

    async def _cr(input_data, **kw):
        return _make_result(KBDocType.CUSTOMER_REVIEWS, "# Customer Reviews\n\nReview content.")

    async def _cs(input_data, company_overview_md, **kw):
        return _make_result(KBDocType.COMPETITOR_REGISTRY, "# Competitor Registry\n\nCompetitor content.")

    async def _wa(input_data, company_overview_md, competitor_registry_md, **kw):
        return _make_result(KBDocType.WEAKNESS_ANALYSIS, "# Weakness Analysis\n\nWeakness content.")

    async def _bp(input_data, upstream_docs, **kw):
        return _make_result(KBDocType.BRAND_PERCEPTION, "# Brand Perception\n\nBrand content.")

    async def _synth(input_data, kb_base_dir, available_docs, missing_docs, **kw):
        return _make_result(KBDocType.SYNTHESIS, "# Company Profile\n\nSynthesized profile.")

    monkeypatch.setattr(f"{_PIPE}.run_company_overview_agent", _co)
    monkeypatch.setattr(f"{_PIPE}.run_customer_reviews_agent", _cr)
    monkeypatch.setattr(f"{_PIPE}.run_competitor_scanner_agent", _cs)
    monkeypatch.setattr(f"{_PIPE}.run_weakness_analyst_agent", _wa)
    monkeypatch.setattr(f"{_PIPE}.run_brand_perception_agent", _bp)
    monkeypatch.setattr(f"{_PIPE}.run_synthesis_agent", _synth)


@pytest.fixture(autouse=True)
def _mock_hitl(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock HITL checkpoint to auto-approve by default."""
    async def _auto_hitl(graph, initial_state, thread_id, **kw):
        # Return the state with approve decision
        return {**initial_state, "decision": "approve", "approved_docs": list(initial_state.get("doc_summaries", {}).keys())}

    monkeypatch.setattr(f"{_PIPE}.run_kb_hitl_checkpoint", _auto_hitl)


# ---------------------------------------------------------------------------
# Helper Tests
# ---------------------------------------------------------------------------


class TestResolveSlug:
    """Tests for _resolve_slug helper."""

    def test_uses_company_slug(self) -> None:
        from core.research.knowledge_base.pipeline import _resolve_slug

        inp = KnowledgeBaseInput(company_name="Test Co", company_slug="test-co")
        assert _resolve_slug(inp) == "test-co"

    def test_derives_from_name(self) -> None:
        from core.research.knowledge_base.pipeline import _resolve_slug

        inp = KnowledgeBaseInput(company_name="My Great Company")
        slug = _resolve_slug(inp)
        assert slug == "my-great-company"

    def test_strips_special_chars(self) -> None:
        from core.research.knowledge_base.pipeline import _resolve_slug

        inp = KnowledgeBaseInput(company_name="Test Co. (Inc)")
        slug = _resolve_slug(inp)
        assert " " not in slug
        assert slug.islower() or "-" in slug


class TestResolveMode:
    """Tests for _resolve_mode helper."""

    def test_full_mode_default(self, tmp_path: Path) -> None:
        from core.research.knowledge_base.pipeline import _resolve_mode
        from core.research.knowledge_base.storage import KBStorage

        inp = KnowledgeBaseInput(company_name="Test Co", company_slug="test-co")
        storage = KBStorage(tmp_path, "test-co")
        mode, target_docs = _resolve_mode(inp, storage)
        assert mode == "full"
        assert len(target_docs) == 5  # All 5 doc types

    def test_single_with_one_doc(self, tmp_path: Path) -> None:
        from core.research.knowledge_base.pipeline import _resolve_mode
        from core.research.knowledge_base.storage import KBStorage

        inp = KnowledgeBaseInput(
            company_name="Test Co",
            company_slug="test-co",
            refresh_docs=[KBDocType.COMPANY_OVERVIEW],
        )
        storage = KBStorage(tmp_path, "test-co")
        mode, target_docs = _resolve_mode(inp, storage)
        assert mode == "single"
        assert target_docs == [KBDocType.COMPANY_OVERVIEW]

    def test_refresh_with_multiple_docs(self, tmp_path: Path) -> None:
        from core.research.knowledge_base.pipeline import _resolve_mode
        from core.research.knowledge_base.storage import KBStorage

        inp = KnowledgeBaseInput(
            company_name="Test Co",
            company_slug="test-co",
            refresh_docs=[KBDocType.COMPANY_OVERVIEW, KBDocType.CUSTOMER_REVIEWS],
        )
        storage = KBStorage(tmp_path, "test-co")
        mode, target_docs = _resolve_mode(inp, storage)
        assert mode == "refresh"
        assert len(target_docs) == 2


class TestGetDocMd:
    """Tests for _get_doc_md helper."""

    def test_from_results(self, tmp_path: Path) -> None:
        from core.research.knowledge_base.pipeline import _get_doc_md
        from core.research.knowledge_base.storage import KBStorage

        storage = KBStorage(tmp_path, "test-co")
        results = {
            KBDocType.COMPANY_OVERVIEW: _make_result(
                KBDocType.COMPANY_OVERVIEW, "# Fresh Overview"
            ),
        }
        md = _get_doc_md(results, KBDocType.COMPANY_OVERVIEW, storage)
        assert "Fresh Overview" in md

    def test_fallback_to_storage(self, tmp_path: Path) -> None:
        from core.research.knowledge_base.pipeline import _get_doc_md
        from core.research.knowledge_base.storage import KBStorage

        storage = KBStorage(tmp_path, "test-co")
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "# Stored Overview")

        results: Dict[KBDocType, KBAgentResult] = {}
        md = _get_doc_md(results, KBDocType.COMPANY_OVERVIEW, storage)
        assert "Stored Overview" in md

    def test_empty_when_missing(self, tmp_path: Path) -> None:
        from core.research.knowledge_base.pipeline import _get_doc_md
        from core.research.knowledge_base.storage import KBStorage

        storage = KBStorage(tmp_path, "test-co")
        results: Dict[KBDocType, KBAgentResult] = {}
        md = _get_doc_md(results, KBDocType.COMPANY_OVERVIEW, storage)
        assert md == ""


class TestBuildUpstreamDocs:
    """Tests for _build_upstream_docs helper."""

    def test_includes_available(self, tmp_path: Path) -> None:
        from core.research.knowledge_base.pipeline import _build_upstream_docs
        from core.research.knowledge_base.storage import KBStorage

        storage = KBStorage(tmp_path, "test-co")
        results = {
            KBDocType.COMPANY_OVERVIEW: _make_result(KBDocType.COMPANY_OVERVIEW, "# Overview"),
            KBDocType.CUSTOMER_REVIEWS: _make_result(KBDocType.CUSTOMER_REVIEWS, "# Reviews"),
            KBDocType.COMPETITOR_REGISTRY: _make_result(KBDocType.COMPETITOR_REGISTRY, "# Competitors"),
        }
        docs = _build_upstream_docs(results, storage)
        assert "company_overview" in docs
        assert "customer_reviews" in docs
        assert "competitor_registry" in docs

    def test_fallback_for_missing(self, tmp_path: Path) -> None:
        from core.research.knowledge_base.pipeline import _build_upstream_docs
        from core.research.knowledge_base.storage import KBStorage

        storage = KBStorage(tmp_path, "test-co")
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "# Stored Overview")

        results: Dict[KBDocType, KBAgentResult] = {}
        docs = _build_upstream_docs(results, storage)
        assert "Stored Overview" in docs.get("company_overview", "")


class TestCollectSynthesisInputs:
    """Tests for _collect_synthesis_inputs helper."""

    def test_available_and_missing(self, tmp_path: Path) -> None:
        from core.research.knowledge_base.pipeline import _collect_synthesis_inputs
        from core.research.knowledge_base.storage import KBStorage

        storage = KBStorage(tmp_path, "test-co")
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "# Overview")
        storage.write_version(KBDocType.CUSTOMER_REVIEWS, "# Reviews")
        storage.write_version(KBDocType.COMPETITOR_REGISTRY, "# Competitors")

        available, missing = _collect_synthesis_inputs(storage)
        assert len(available) == 3
        assert "weakness_analysis" in missing
        assert "brand_perception" in missing


# ---------------------------------------------------------------------------
# Full Pipeline Tests
# ---------------------------------------------------------------------------


class TestRunKnowledgeBasePipeline:
    """Tests for run_knowledge_base_pipeline orchestrator."""

    @pytest.mark.asyncio
    async def test_full_mode_all_agents(
        self, kb_input_auto_approve: KnowledgeBaseInput, tmp_path: Path,
    ) -> None:
        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        output = await run_knowledge_base_pipeline(
            kb_input_auto_approve, artifacts_root=tmp_path,
        )
        assert isinstance(output, KnowledgeBaseOutput)
        assert output.slug == "test-co"
        assert output.synthesis_md != ""
        assert output.total_execution_time_s > 0

    @pytest.mark.asyncio
    async def test_returns_output(
        self, kb_input_auto_approve: KnowledgeBaseInput, tmp_path: Path,
    ) -> None:
        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        output = await run_knowledge_base_pipeline(
            kb_input_auto_approve, artifacts_root=tmp_path,
        )
        assert isinstance(output, KnowledgeBaseOutput)
        assert output.company_name == "Test Co"

    @pytest.mark.asyncio
    async def test_writes_l3_company_profile(
        self, kb_input_auto_approve: KnowledgeBaseInput, tmp_path: Path,
    ) -> None:
        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        output = await run_knowledge_base_pipeline(
            kb_input_auto_approve, artifacts_root=tmp_path,
        )
        # Should write company_context/{slug}.md
        profile_path = tmp_path / "company_context" / "test-co.md"
        assert profile_path.exists()
        assert "Synthesized profile" in profile_path.read_text()

    @pytest.mark.asyncio
    async def test_persists_versions_to_storage(
        self, kb_input_auto_approve: KnowledgeBaseInput, tmp_path: Path,
    ) -> None:
        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline
        from core.research.knowledge_base.storage import KBStorage

        await run_knowledge_base_pipeline(
            kb_input_auto_approve, artifacts_root=tmp_path,
        )
        storage = KBStorage(tmp_path, "test-co")
        manifest = storage.read_manifest()
        # All 5 doc types should be in manifest
        assert len(manifest.documents) == 5

    @pytest.mark.asyncio
    async def test_agent_error_continues(
        self, kb_input_auto_approve: KnowledgeBaseInput, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Pipeline continues with partial results when an agent errors."""
        async def _failing_cr(input_data, **kw):
            return _make_result(KBDocType.CUSTOMER_REVIEWS, error="Perplexity rate limit")

        monkeypatch.setattr(f"{_PIPE}.run_customer_reviews_agent", _failing_cr)

        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        output = await run_knowledge_base_pipeline(
            kb_input_auto_approve, artifacts_root=tmp_path,
        )
        # Pipeline completes despite one agent error
        assert isinstance(output, KnowledgeBaseOutput)

    @pytest.mark.asyncio
    async def test_single_mode_runs_one_agent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Single mode only runs the specified agent."""
        inp = KnowledgeBaseInput(
            company_name="Test Co",
            company_slug="test-co",
            refresh_docs=[KBDocType.COMPANY_OVERVIEW],
            auto_approve_checkpoints=[1, 2, 3],
        )

        call_log: List[str] = []

        async def _co_tracked(input_data, **kw):
            call_log.append("company_overview")
            return _make_result(KBDocType.COMPANY_OVERVIEW)

        async def _cr_tracked(input_data, **kw):
            call_log.append("customer_reviews")
            return _make_result(KBDocType.CUSTOMER_REVIEWS)

        monkeypatch.setattr(f"{_PIPE}.run_company_overview_agent", _co_tracked)
        monkeypatch.setattr(f"{_PIPE}.run_customer_reviews_agent", _cr_tracked)

        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        await run_knowledge_base_pipeline(inp, artifacts_root=tmp_path)
        assert "company_overview" in call_log
        assert "customer_reviews" not in call_log

    @pytest.mark.asyncio
    async def test_hitl_auto_approve(
        self, kb_input_auto_approve: KnowledgeBaseInput, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Auto-approve checkpoints pass through without interrupt."""
        hitl_calls: List[Dict[str, Any]] = []

        async def _track_hitl(graph, initial_state, thread_id, **kw):
            hitl_calls.append(initial_state)
            return {
                **initial_state,
                "decision": "approve",
                "approved_docs": list(initial_state.get("doc_summaries", {}).keys()),
            }

        monkeypatch.setattr(f"{_PIPE}.run_kb_hitl_checkpoint", _track_hitl)

        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        await run_knowledge_base_pipeline(
            kb_input_auto_approve, artifacts_root=tmp_path,
        )
        # Should have called HITL 3 times (cp1, cp2, cp3)
        assert len(hitl_calls) == 3

    @pytest.mark.asyncio
    async def test_hitl_reject_at_cp1_stops(
        self, kb_input: KnowledgeBaseInput, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Reject at checkpoint 1 stops the pipeline."""
        call_count = {"hitl": 0}

        async def _reject_hitl(graph, initial_state, thread_id, **kw):
            call_count["hitl"] += 1
            return {**initial_state, "decision": "reject"}

        monkeypatch.setattr(f"{_PIPE}.run_kb_hitl_checkpoint", _reject_hitl)

        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        output = await run_knowledge_base_pipeline(
            kb_input, artifacts_root=tmp_path,
        )
        # Should stop after first HITL rejection
        assert call_count["hitl"] == 1
        # No synthesis since we rejected
        assert output.synthesis_md == ""

    @pytest.mark.asyncio
    async def test_hitl_revise_reruns_agent(
        self, kb_input: KnowledgeBaseInput, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Revise at checkpoint reruns the specified agents with feedback."""
        revision_calls: List[Dict[str, Any]] = []
        hitl_count = {"count": 0}

        async def _co_track(input_data, revision_note=None, **kw):
            if revision_note:
                revision_calls.append({"doc": "company_overview", "note": revision_note})
            return _make_result(KBDocType.COMPANY_OVERVIEW)

        monkeypatch.setattr(f"{_PIPE}.run_company_overview_agent", _co_track)

        async def _revise_then_approve(graph, initial_state, thread_id, **kw):
            hitl_count["count"] += 1
            if hitl_count["count"] == 1:
                # First HITL at cp1 — revise company_overview
                return {
                    **initial_state,
                    "decision": "revise",
                    "revision_notes": {"company_overview": "Add more funding data"},
                }
            # All subsequent — approve
            return {
                **initial_state,
                "decision": "approve",
                "approved_docs": list(initial_state.get("doc_summaries", {}).keys()),
            }

        monkeypatch.setattr(f"{_PIPE}.run_kb_hitl_checkpoint", _revise_then_approve)

        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        await run_knowledge_base_pipeline(kb_input, artifacts_root=tmp_path)
        assert len(revision_calls) >= 1
        assert revision_calls[0]["note"] == "Add more funding data"

    @pytest.mark.asyncio
    async def test_sse_events(
        self, kb_input_auto_approve: KnowledgeBaseInput, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Pipeline emits SSE events via event_bus."""
        event_bus = MagicMock()

        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        await run_knowledge_base_pipeline(
            kb_input_auto_approve,
            artifacts_root=tmp_path,
            task_id="task-sse-1",
            event_bus=event_bus,
        )

        # Should have published events
        assert event_bus.publish.call_count > 0
        event_types = [c[0][1] for c in event_bus.publish.call_args_list]
        assert "pipeline_start" in event_types
        assert "completed" in event_types

    @pytest.mark.asyncio
    async def test_task_store_updates(
        self, kb_input_auto_approve: KnowledgeBaseInput, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Pipeline updates task_store with progress."""
        task_store = MagicMock()

        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        await run_knowledge_base_pipeline(
            kb_input_auto_approve,
            artifacts_root=tmp_path,
            task_id="task-ts-1",
            task_store=task_store,
        )

        assert task_store.update_task.call_count > 0

    @pytest.mark.asyncio
    async def test_phase1_parallel(
        self, kb_input_auto_approve: KnowledgeBaseInput, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Phase 1 runs company_overview and customer_reviews in parallel."""
        start_times: Dict[str, float] = {}

        async def _co_timed(input_data, **kw):
            import time
            start_times["co"] = time.time()
            await asyncio.sleep(0.01)
            return _make_result(KBDocType.COMPANY_OVERVIEW)

        async def _cr_timed(input_data, **kw):
            import time
            start_times["cr"] = time.time()
            await asyncio.sleep(0.01)
            return _make_result(KBDocType.CUSTOMER_REVIEWS)

        monkeypatch.setattr(f"{_PIPE}.run_company_overview_agent", _co_timed)
        monkeypatch.setattr(f"{_PIPE}.run_customer_reviews_agent", _cr_timed)

        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        await run_knowledge_base_pipeline(
            kb_input_auto_approve, artifacts_root=tmp_path,
        )
        # Both should have started within 50ms of each other (parallel)
        assert abs(start_times["co"] - start_times["cr"]) < 0.05

    @pytest.mark.asyncio
    async def test_phase3_parallel(
        self, kb_input_auto_approve: KnowledgeBaseInput, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Phase 3 runs weakness_analyst and brand_perception in parallel."""
        start_times: Dict[str, float] = {}

        async def _wa_timed(input_data, company_overview_md, competitor_registry_md, **kw):
            import time
            start_times["wa"] = time.time()
            await asyncio.sleep(0.01)
            return _make_result(KBDocType.WEAKNESS_ANALYSIS)

        async def _bp_timed(input_data, upstream_docs, **kw):
            import time
            start_times["bp"] = time.time()
            await asyncio.sleep(0.01)
            return _make_result(KBDocType.BRAND_PERCEPTION)

        monkeypatch.setattr(f"{_PIPE}.run_weakness_analyst_agent", _wa_timed)
        monkeypatch.setattr(f"{_PIPE}.run_brand_perception_agent", _bp_timed)

        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        await run_knowledge_base_pipeline(
            kb_input_auto_approve, artifacts_root=tmp_path,
        )
        assert abs(start_times["wa"] - start_times["bp"]) < 0.05

    @pytest.mark.asyncio
    async def test_phase2_gets_overview_upstream(
        self, kb_input_auto_approve: KnowledgeBaseInput, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Phase 2 competitor_scanner receives company_overview_md."""
        captured_upstream = {}

        async def _cs_capture(input_data, company_overview_md, **kw):
            captured_upstream["overview"] = company_overview_md
            return _make_result(KBDocType.COMPETITOR_REGISTRY)

        monkeypatch.setattr(f"{_PIPE}.run_competitor_scanner_agent", _cs_capture)

        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        await run_knowledge_base_pipeline(
            kb_input_auto_approve, artifacts_root=tmp_path,
        )
        assert "Overview content" in captured_upstream["overview"]

    @pytest.mark.asyncio
    async def test_synthesis_skipped_single_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Single mode skips synthesis and HITL."""
        inp = KnowledgeBaseInput(
            company_name="Test Co",
            company_slug="test-co",
            refresh_docs=[KBDocType.COMPANY_OVERVIEW],
            auto_approve_checkpoints=[1, 2, 3],
        )

        synth_called = {"called": False}

        async def _synth_track(input_data, kb_base_dir, available_docs, missing_docs, **kw):
            synth_called["called"] = True
            return _make_result(KBDocType.SYNTHESIS)

        monkeypatch.setattr(f"{_PIPE}.run_synthesis_agent", _synth_track)

        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        await run_knowledge_base_pipeline(inp, artifacts_root=tmp_path)
        assert not synth_called["called"]

    @pytest.mark.asyncio
    async def test_hitl_reject_at_cp3_stops(
        self, kb_input: KnowledgeBaseInput, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CX-2: Reject at checkpoint 3 returns output WITHOUT synthesis_md."""
        hitl_count = {"count": 0}

        async def _approve_then_reject(graph, initial_state, thread_id, **kw):
            hitl_count["count"] += 1
            if hitl_count["count"] <= 2:
                # Approve cp1 and cp2
                return {
                    **initial_state,
                    "decision": "approve",
                    "approved_docs": list(initial_state.get("doc_summaries", {}).keys()),
                }
            # Reject at cp3 (synthesis)
            return {**initial_state, "decision": "reject"}

        monkeypatch.setattr(f"{_PIPE}.run_kb_hitl_checkpoint", _approve_then_reject)

        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        output = await run_knowledge_base_pipeline(kb_input, artifacts_root=tmp_path)
        assert hitl_count["count"] == 3
        # Synthesis was rejected — output should NOT contain synthesis_md
        assert output.synthesis_md == ""

    @pytest.mark.asyncio
    async def test_empty_cp1_skips_hitl1_in_refresh_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CX-5: Refresh targeting only Phase 3 agents skips HITL-1."""
        inp = KnowledgeBaseInput(
            company_name="Test Co",
            company_slug="test-co",
            refresh_docs=[KBDocType.WEAKNESS_ANALYSIS, KBDocType.BRAND_PERCEPTION],
        )

        hitl_checkpoints: List[int] = []

        async def _track_hitl(graph, initial_state, thread_id, **kw):
            hitl_checkpoints.append(initial_state["checkpoint"])
            return {
                **initial_state,
                "decision": "approve",
                "approved_docs": list(initial_state.get("doc_summaries", {}).keys()),
            }

        monkeypatch.setattr(f"{_PIPE}.run_kb_hitl_checkpoint", _track_hitl)

        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        await run_knowledge_base_pipeline(inp, artifacts_root=tmp_path)
        # HITL-1 should be skipped (no Phase 1+2 docs in results)
        assert 1 not in hitl_checkpoints
        # HITL-2 and HITL-3 should still fire
        assert 2 in hitl_checkpoints
        assert 3 in hitl_checkpoints

    @pytest.mark.asyncio
    async def test_malformed_revision_doc_type_skipped(
        self, kb_input: KnowledgeBaseInput, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CX-4: Invalid doc_type key in revision_notes is skipped gracefully."""
        hitl_count = {"count": 0}

        async def _revise_with_bad_key(graph, initial_state, thread_id, **kw):
            hitl_count["count"] += 1
            if hitl_count["count"] == 1:
                return {
                    **initial_state,
                    "decision": "revise",
                    "revision_notes": {"nonexistent_type": "Fix this"},
                }
            return {
                **initial_state,
                "decision": "approve",
                "approved_docs": list(initial_state.get("doc_summaries", {}).keys()),
            }

        monkeypatch.setattr(f"{_PIPE}.run_kb_hitl_checkpoint", _revise_with_bad_key)

        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        # Should NOT raise ValueError — malformed key skipped
        output = await run_knowledge_base_pipeline(kb_input, artifacts_root=tmp_path)
        assert isinstance(output, KnowledgeBaseOutput)

    @pytest.mark.asyncio
    async def test_revision_doc_outside_checkpoint_scope_skipped(
        self, kb_input: KnowledgeBaseInput, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CX-4: Valid doc_type but not in checkpoint scope is skipped."""
        hitl_count = {"count": 0}

        async def _revise_wrong_scope(graph, initial_state, thread_id, **kw):
            hitl_count["count"] += 1
            if hitl_count["count"] == 1:
                # cp1 covers overview/reviews/competitor — send brand_perception (Phase 3)
                return {
                    **initial_state,
                    "decision": "revise",
                    "revision_notes": {"brand_perception": "Out of scope for cp1"},
                }
            return {
                **initial_state,
                "decision": "approve",
                "approved_docs": list(initial_state.get("doc_summaries", {}).keys()),
            }

        monkeypatch.setattr(f"{_PIPE}.run_kb_hitl_checkpoint", _revise_wrong_scope)

        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        # Should complete without error — out-of-scope doc skipped
        output = await run_knowledge_base_pipeline(kb_input, artifacts_root=tmp_path)
        assert isinstance(output, KnowledgeBaseOutput)

    @pytest.mark.asyncio
    async def test_collect_synthesis_reads_manifest_once(
        self, tmp_path: Path,
    ) -> None:
        """CX-6: _collect_synthesis_inputs reads manifest exactly once."""
        from unittest.mock import MagicMock as MM

        from core.models.knowledge_base import KBDocEntry, KBManifest
        from core.research.knowledge_base.pipeline import _collect_synthesis_inputs

        manifest = KBManifest(
            slug="test",
            documents={
                "company_overview": KBDocEntry(current_version=1, status="fresh"),
                "customer_reviews": KBDocEntry(current_version=2, status="fresh"),
            },
        )
        storage = MM()
        storage.read_manifest.return_value = manifest

        available, missing = _collect_synthesis_inputs(storage)
        assert storage.read_manifest.call_count == 1
        assert "company_overview" in available
        assert "customer_reviews" in available

    @pytest.mark.asyncio
    async def test_company_profile_path_when_synthesis_fails(
        self, kb_input_auto_approve: KnowledgeBaseInput, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CX-10: When synthesis errors, output has empty synthesis_md."""
        async def _failing_synth(input_data, kb_base_dir, available_docs, missing_docs, **kw):
            return _make_result(KBDocType.SYNTHESIS, error="LLM error")

        monkeypatch.setattr(f"{_PIPE}.run_synthesis_agent", _failing_synth)

        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        output = await run_knowledge_base_pipeline(
            kb_input_auto_approve, artifacts_root=tmp_path,
        )
        assert output.synthesis_md == ""


# ---------------------------------------------------------------------------
# Phase 5: Delta Synthesis, Staleness Propagation, Write-Before-Approve Fix
# ---------------------------------------------------------------------------


class TestDeltaSynthesisIntegration:
    """Pipeline routes to delta synthesis mode when refresh + existing synthesis."""

    @pytest.mark.asyncio
    async def test_refresh_mode_with_existing_synthesis_uses_delta(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Refresh mode + prior synthesis → run_synthesis_agent called with delta_mode=True."""
        from core.research.knowledge_base.storage import KBStorage

        # Pre-populate storage with all 5 L2 docs + synthesis
        storage = KBStorage(tmp_path, "test-co")
        for dt in [KBDocType.COMPANY_OVERVIEW, KBDocType.CUSTOMER_REVIEWS,
                    KBDocType.COMPETITOR_REGISTRY, KBDocType.WEAKNESS_ANALYSIS,
                    KBDocType.BRAND_PERCEPTION]:
            storage.write_version(dt, f"# {dt.value}\n\nExisting content.")
        storage.write_synthesis("# Existing Synthesis\n\nPrior content.")

        captured_synth: Dict[str, Any] = {}

        async def _track_synth(input_data, kb_base_dir, available_docs, missing_docs, **kw):
            captured_synth.update(kw)
            captured_synth["available_docs"] = available_docs
            return _make_result(KBDocType.SYNTHESIS, "# Updated Profile")

        monkeypatch.setattr(f"{_PIPE}.run_synthesis_agent", _track_synth)

        inp = KnowledgeBaseInput(
            company_name="Test Co",
            company_slug="test-co",
            refresh_docs=[KBDocType.CUSTOMER_REVIEWS, KBDocType.BRAND_PERCEPTION],
            auto_approve_checkpoints=[1, 2, 3],
        )

        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        await run_knowledge_base_pipeline(inp, artifacts_root=tmp_path)

        assert captured_synth.get("delta_mode") is True
        assert captured_synth.get("previous_synthesis_path") is not None
        assert "synthesis/v1.md" in captured_synth["previous_synthesis_path"]

    @pytest.mark.asyncio
    async def test_full_mode_uses_full_synthesis(
        self, kb_input_auto_approve: KnowledgeBaseInput, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Full mode → delta_mode=False."""
        captured_synth: Dict[str, Any] = {}

        async def _track_synth(input_data, kb_base_dir, available_docs, missing_docs, **kw):
            captured_synth.update(kw)
            return _make_result(KBDocType.SYNTHESIS, "# Profile")

        monkeypatch.setattr(f"{_PIPE}.run_synthesis_agent", _track_synth)

        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        await run_knowledge_base_pipeline(kb_input_auto_approve, artifacts_root=tmp_path)

        assert captured_synth.get("delta_mode") is False

    @pytest.mark.asyncio
    async def test_refresh_without_prior_synthesis_falls_back_to_full(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Refresh mode without prior synthesis → delta_mode=False."""
        captured_synth: Dict[str, Any] = {}

        async def _track_synth(input_data, kb_base_dir, available_docs, missing_docs, **kw):
            captured_synth.update(kw)
            return _make_result(KBDocType.SYNTHESIS, "# Profile")

        monkeypatch.setattr(f"{_PIPE}.run_synthesis_agent", _track_synth)

        inp = KnowledgeBaseInput(
            company_name="Test Co",
            company_slug="test-co",
            refresh_docs=[KBDocType.CUSTOMER_REVIEWS, KBDocType.BRAND_PERCEPTION],
            auto_approve_checkpoints=[1, 2, 3],
        )

        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        await run_knowledge_base_pipeline(inp, artifacts_root=tmp_path)

        assert captured_synth.get("delta_mode") is False


class TestStalenessAndChangedDocs:
    """Pipeline propagates staleness and tracks changed_docs."""

    @pytest.mark.asyncio
    async def test_propagate_staleness_called(
        self, kb_input_auto_approve: KnowledgeBaseInput, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """propagate_staleness is called with changed doc types before synthesis."""
        propagated: List[Any] = []

        from core.research.knowledge_base.storage import KBStorage

        original_propagate = KBStorage.propagate_staleness

        def _track_propagate(self_storage, refreshed_doc_types):
            propagated.append(list(refreshed_doc_types))
            return original_propagate(self_storage, refreshed_doc_types)

        monkeypatch.setattr(
            "core.research.knowledge_base.pipeline.KBStorage.propagate_staleness",
            _track_propagate,
        )

        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        await run_knowledge_base_pipeline(kb_input_auto_approve, artifacts_root=tmp_path)

        assert len(propagated) == 1
        assert len(propagated[0]) == 5  # All 5 docs changed in full mode

    @pytest.mark.asyncio
    async def test_full_mode_updates_last_full_refresh(
        self, kb_input_auto_approve: KnowledgeBaseInput, tmp_path: Path,
    ) -> None:
        """Full mode sets last_full_refresh in manifest after synthesis approved."""
        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline
        from core.research.knowledge_base.storage import KBStorage

        await run_knowledge_base_pipeline(kb_input_auto_approve, artifacts_root=tmp_path)

        storage = KBStorage(tmp_path, "test-co")
        manifest = storage.read_manifest()
        assert manifest.last_full_refresh is not None

    @pytest.mark.asyncio
    async def test_reject_at_cp3_does_not_write_company_context(
        self, kb_input: KnowledgeBaseInput, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CRITICAL: Reject at HITL-3 must NOT write company_context/{slug}.md."""
        hitl_count = {"count": 0}

        async def _approve_then_reject(graph, initial_state, thread_id, **kw):
            hitl_count["count"] += 1
            if hitl_count["count"] <= 2:
                return {
                    **initial_state,
                    "decision": "approve",
                    "approved_docs": list(initial_state.get("doc_summaries", {}).keys()),
                }
            return {**initial_state, "decision": "reject"}

        monkeypatch.setattr(f"{_PIPE}.run_kb_hitl_checkpoint", _approve_then_reject)

        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        output = await run_knowledge_base_pipeline(kb_input, artifacts_root=tmp_path)

        profile_path = tmp_path / "company_context" / "test-co.md"
        assert not profile_path.exists(), "company_context must NOT be written when HITL-3 rejects"

    @pytest.mark.asyncio
    async def test_changed_docs_populated_in_output(
        self, kb_input_auto_approve: KnowledgeBaseInput, tmp_path: Path,
    ) -> None:
        """Output.changed_docs lists all doc types that were written."""
        from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

        output = await run_knowledge_base_pipeline(
            kb_input_auto_approve, artifacts_root=tmp_path,
        )
        # Full mode: all 5 L2 docs should be in changed_docs
        assert len(output.changed_docs) == 5
        assert "company_overview" in output.changed_docs
        assert "customer_reviews" in output.changed_docs
