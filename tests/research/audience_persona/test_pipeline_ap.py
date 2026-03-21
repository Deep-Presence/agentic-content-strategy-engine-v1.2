"""Tests for Audience Persona pipeline orchestrator.

TDD: tests written FIRST, implementation follows.
Phase D of the Audience Persona Research Pipeline.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.audience_persona import (
    AudiencePersonaInput,
    AudiencePersonaOutput,
    PersonaAgentResult,
    PersonaBrief,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PIPE = "core.research.audience_persona.pipeline"


# ---------------------------------------------------------------------------
# Sample data factories
# ---------------------------------------------------------------------------


def _make_input(**overrides: Any) -> AudiencePersonaInput:
    """Create a standard pipeline input."""
    defaults = {
        "company_name": "Test Co",
        "company_slug": "test-co",
        "domain": "testco.com",
        "max_personas": 3,
        "auto_approve_checkpoints": [1, 2],
    }
    defaults.update(overrides)
    return AudiencePersonaInput(**defaults)


def _make_brief(
    brief_id: str = "pb-001",
    name: str = "Sarah",
    tagline: str = "VP of Finance at mid-market SaaS",
) -> PersonaBrief:
    """Create a sample PersonaBrief."""
    return PersonaBrief(
        brief_id=brief_id,
        persona_name=name,
        tagline=tagline,
        description=f"{name} manages ops.",
        rationale=["Evidence A", "Evidence B"],
        source="agent",
    )


def _make_briefs(count: int = 3) -> List[PersonaBrief]:
    """Create N sample briefs."""
    names = ["Sarah", "Marcus", "Priya", "James", "Anika"]
    taglines = [
        "VP of Finance at mid-market SaaS",
        "Head of Product at B2B startup",
        "Director of Marketing at mid-market",
        "CTO at enterprise fintech",
        "Head of Ops at growth-stage",
    ]
    return [
        _make_brief(brief_id=f"pb-{i:03d}", name=names[i], tagline=taglines[i])
        for i in range(count)
    ]


def _make_result(
    brief: PersonaBrief,
    content: str = "# Persona Profile\n\nDetailed persona content here.",
    error: Optional[str] = None,
) -> PersonaAgentResult:
    """Create a sample PersonaAgentResult."""
    return PersonaAgentResult(
        brief_id=brief.brief_id,
        persona_name=brief.persona_name,
        content_md=content if not error else "",
        word_count=len(content.split()) if not error else 0,
        execution_time_s=2.5,
        error=error,
    )


_COMPANY_CONTEXT_MD = "# Test Co\n\nTest company overview with enough content for testing."
_CUSTOMER_REVIEWS_MD = "# Customer Reviews\n\nPositive feedback from customers."


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ap_input() -> AudiencePersonaInput:
    """Standard auto-approve input."""
    return _make_input()


@pytest.fixture()
def ap_input_manual() -> AudiencePersonaInput:
    """Input WITHOUT auto-approve (requires HITL)."""
    return _make_input(auto_approve_checkpoints=[])


@pytest.fixture()
def setup_preflight(tmp_path: Path) -> Path:
    """Create preflight artifacts: company_context + KB customer_reviews."""
    # company_context
    ctx_dir = tmp_path / "company_context"
    ctx_dir.mkdir()
    (ctx_dir / "test-co.md").write_text(_COMPANY_CONTEXT_MD, encoding="utf-8")

    # KB storage with customer_reviews v1
    kb_dir = tmp_path / "knowledge_base" / "test-co" / "customer_reviews"
    kb_dir.mkdir(parents=True)
    (kb_dir / "v1.md").write_text(_CUSTOMER_REVIEWS_MD, encoding="utf-8")

    # KB manifest with customer_reviews entry + synthesis_version
    manifest_dir = tmp_path / "knowledge_base" / "test-co"
    manifest = {
        "slug": "test-co",
        "company_name": "Test Co",
        "created_at": "2026-03-01T00:00:00Z",
        "documents": {
            "customer_reviews": {
                "doc_type": "customer_reviews",
                "current_version": 1,
                "status": "fresh",
                "last_updated": "2026-03-01T00:00:00Z",
                "word_count": 10,
                "sha256": "abc123",
            }
        },
        "synthesis_version": 2,
    }
    (manifest_dir / "_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8",
    )

    return tmp_path


@pytest.fixture(autouse=True)
def _mock_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable all tracing functions."""
    for fn in ("create_session", "create_span", "end_span", "flush", "log_generation"):
        monkeypatch.setattr(f"{_PIPE}.{fn}", MagicMock())


@pytest.fixture()
def _mock_load_kdocs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock _load_knowledge_docs to return empty string."""
    monkeypatch.setattr(
        f"{_PIPE}._load_knowledge_docs",
        AsyncMock(return_value=""),
    )


def _mock_suggester(briefs: List[PersonaBrief], time_s: float = 1.0):
    """Create a mock for run_persona_suggester."""
    return AsyncMock(return_value=(briefs, time_s))


def _mock_generator(results_map: Dict[str, PersonaAgentResult]):
    """Create a mock for run_persona_profile_generator that returns per-brief results."""
    async def _gen(brief, **kwargs):
        # Look up by brief_id
        return results_map.get(
            brief.brief_id,
            _make_result(brief),
        )
    return _gen


def _mock_hitl_auto_approve():
    """Mock run_ap_hitl_checkpoint to auto-approve."""
    async def _hitl(graph, initial_state, thread_id, **kwargs):
        # Mimic auto-approve: return all briefs approved / all profiles approved
        if initial_state.get("checkpoint") == 1:
            return {
                "batch_decision": "approve_all",
                "approved_briefs": initial_state.get("briefs", []),
            }
        elif initial_state.get("checkpoint") == 2:
            summaries = initial_state.get("profile_summaries", {})
            return {
                "approved_profiles": list(summaries.keys()),
                "revision_requests": {},
                "rejected_profiles": [],
            }
        return initial_state
    return _hitl


# ═══════════════════════════════════════════════════════════════════════
# A. Helper Tests
# ═══════════════════════════════════════════════════════════════════════


class TestResolveSlug:
    """Test _resolve_slug helper."""

    def test_uses_company_slug_when_set(self):
        from core.research.audience_persona.pipeline import _resolve_slug

        inp = _make_input(company_slug="custom-slug")
        assert _resolve_slug(inp) == "custom-slug"

    def test_derives_from_company_name(self):
        from core.research.audience_persona.pipeline import _resolve_slug

        inp = _make_input(company_slug=None, company_name="Acme Corp")
        assert _resolve_slug(inp) == "acme-corp"

    def test_strips_special_chars(self):
        from core.research.audience_persona.pipeline import _resolve_slug

        inp = _make_input(company_slug=None, company_name="Test & Co. (Inc)")
        result = _resolve_slug(inp)
        assert "&" not in result
        assert "." not in result
        assert "(" not in result


class TestResolveEffectiveSlug:
    """Test _resolve_effective_slug correctly appends product_slug."""

    def test_company_only(self):
        from core.research.audience_persona.pipeline import _resolve_effective_slug

        inp = _make_input(company_slug="ramp", product_slug=None)
        assert _resolve_effective_slug(inp) == "ramp"

    def test_with_product_slug(self):
        from core.research.audience_persona.pipeline import _resolve_effective_slug

        inp = _make_input(company_slug="ramp", product_slug="treasury")
        assert _resolve_effective_slug(inp) == "ramp__treasury"

    def test_no_double_append_when_slug_is_base(self):
        """Regression: runner must pass company_slug (not effective_slug) to input_data."""
        from core.research.audience_persona.pipeline import _resolve_effective_slug

        # If runner correctly passes company_slug="ramp" (not "ramp__treasury"):
        inp = _make_input(company_slug="ramp", product_slug="treasury")
        result = _resolve_effective_slug(inp)
        assert result == "ramp__treasury"
        assert "__treasury__treasury" not in result


class TestSlugifyPersonaName:
    """Test _slugify_persona_name helper."""

    def test_basic_name(self):
        from core.research.audience_persona.pipeline import _slugify_persona_name

        assert _slugify_persona_name("Sarah Chen") == "sarah-chen"

    def test_special_chars_removed(self):
        from core.research.audience_persona.pipeline import _slugify_persona_name

        result = _slugify_persona_name("VP (Finance) & Ops")
        assert "(" not in result
        assert "&" not in result
        assert result  # not empty


class TestBuildIdMap:
    """Test _build_id_map collision handling."""

    def test_unique_names(self):
        from core.research.audience_persona.pipeline import _build_id_map

        briefs = _make_briefs(3)
        id_map = _build_id_map(briefs)
        assert len(id_map) == 3
        assert id_map["pb-000"] == "sarah"
        assert id_map["pb-001"] == "marcus"
        assert id_map["pb-002"] == "priya"

    def test_collision_suffixing(self):
        from core.research.audience_persona.pipeline import _build_id_map

        briefs = [
            _make_brief("pb-001", "James"),
            _make_brief("pb-002", "James"),
            _make_brief("pb-003", "James"),
        ]
        id_map = _build_id_map(briefs)
        values = sorted(id_map.values())
        assert "james" in values
        assert "james-2" in values
        assert "james-3" in values


# ═══════════════════════════════════════════════════════════════════════
# B. Preflight Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPreflightCheck:
    """Test _preflight_check validation."""

    @pytest.mark.asyncio
    async def test_missing_company_context_raises(self, tmp_path: Path):
        from core.research.audience_persona.pipeline import _preflight_check

        with pytest.raises(RuntimeError, match="[Cc]ompany context"):
            await _preflight_check(tmp_path, "test-co", "test-co")

    @pytest.mark.asyncio
    async def test_empty_company_context_raises(self, tmp_path: Path):
        from core.research.audience_persona.pipeline import _preflight_check

        ctx_dir = tmp_path / "company_context"
        ctx_dir.mkdir()
        (ctx_dir / "test-co.md").write_text("", encoding="utf-8")

        with pytest.raises(RuntimeError, match="[Cc]ompany context"):
            await _preflight_check(tmp_path, "test-co", "test-co")

    @pytest.mark.asyncio
    async def test_reads_and_truncates_company_context(self, tmp_path: Path):
        from core.research.audience_persona.pipeline import _preflight_check

        ctx_dir = tmp_path / "company_context"
        ctx_dir.mkdir()
        long_content = "x" * 20_000
        (ctx_dir / "test-co.md").write_text(long_content, encoding="utf-8")

        company_md, _, _, _ = await _preflight_check(tmp_path, "test-co", "test-co")
        assert len(company_md) == 20_000

    @pytest.mark.asyncio
    async def test_effective_slug_fallback(self, tmp_path: Path):
        """Check effective_slug first, fallback to company_slug."""
        from core.research.audience_persona.pipeline import _preflight_check

        ctx_dir = tmp_path / "company_context"
        ctx_dir.mkdir()
        # Only company slug file exists (not effective slug)
        (ctx_dir / "test-co.md").write_text("Company context", encoding="utf-8")

        company_md, _, _, _ = await _preflight_check(
            tmp_path, "test-co__product", "test-co",
        )
        assert company_md == "Company context"

    @pytest.mark.asyncio
    async def test_missing_customer_reviews_warns(self, tmp_path: Path, caplog):
        from core.research.audience_persona.pipeline import _preflight_check

        ctx_dir = tmp_path / "company_context"
        ctx_dir.mkdir()
        (ctx_dir / "test-co.md").write_text("Company context", encoding="utf-8")

        _, reviews_md, _, _ = await _preflight_check(tmp_path, "test-co", "test-co")
        assert reviews_md == ""

    @pytest.mark.asyncio
    async def test_reads_kb_synthesis_version(self, setup_preflight: Path):
        from core.research.audience_persona.pipeline import _preflight_check

        _, _, _, kb_version = await _preflight_check(
            setup_preflight, "test-co", "test-co",
        )
        assert kb_version == 2


# ═══════════════════════════════════════════════════════════════════════
# C. Phase 1 — Suggester Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPhase1Suggester:
    """Test Phase 1: Persona Suggester."""

    @pytest.mark.asyncio
    async def test_calls_suggester_with_correct_args(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        briefs = _make_briefs(3)
        mock_suggest = _mock_suggester(briefs)
        monkeypatch.setattr(f"{_PIPE}.run_persona_suggester", mock_suggest)
        monkeypatch.setattr(f"{_PIPE}.run_persona_profile_generator", AsyncMock(side_effect=_mock_generator({})))
        monkeypatch.setattr(f"{_PIPE}.run_ap_hitl_checkpoint", _mock_hitl_auto_approve())
        monkeypatch.setattr(f"{_PIPE}._load_knowledge_docs", AsyncMock(return_value=""))
        monkeypatch.setattr(f"{_PIPE}.build_ap_brief_review_graph", MagicMock())
        monkeypatch.setattr(f"{_PIPE}.build_ap_profile_review_graph", MagicMock())

        await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )

        mock_suggest.assert_called_once()
        call_kwargs = mock_suggest.call_args
        assert call_kwargs[1].get("input_data") or call_kwargs[0][0]

    @pytest.mark.asyncio
    async def test_zero_briefs_raises(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        monkeypatch.setattr(f"{_PIPE}.run_persona_suggester", _mock_suggester([]))
        monkeypatch.setattr(f"{_PIPE}._load_knowledge_docs", AsyncMock(return_value=""))

        with pytest.raises(RuntimeError, match="0 valid briefs"):
            await run_audience_persona_pipeline(
                _make_input(), artifacts_root=setup_preflight,
            )

    @pytest.mark.asyncio
    async def test_emits_agent_complete(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        briefs = _make_briefs(3)
        monkeypatch.setattr(f"{_PIPE}.run_persona_suggester", _mock_suggester(briefs))
        monkeypatch.setattr(f"{_PIPE}.run_persona_profile_generator", AsyncMock(side_effect=_mock_generator({})))
        monkeypatch.setattr(f"{_PIPE}.run_ap_hitl_checkpoint", _mock_hitl_auto_approve())
        monkeypatch.setattr(f"{_PIPE}._load_knowledge_docs", AsyncMock(return_value=""))
        monkeypatch.setattr(f"{_PIPE}.build_ap_brief_review_graph", MagicMock())
        monkeypatch.setattr(f"{_PIPE}.build_ap_profile_review_graph", MagicMock())

        event_bus = MagicMock()
        await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
            task_id="t-1", event_bus=event_bus,
        )

        # Check ap_agent_complete event was emitted for suggester
        calls = [c for c in event_bus.publish.call_args_list if c[0][1] == "ap_agent_complete"]
        assert len(calls) >= 1
        assert calls[0][0][2]["agent"] == "persona_suggester"


# ═══════════════════════════════════════════════════════════════════════
# D. HITL-1 Tests
# ═══════════════════════════════════════════════════════════════════════


class TestHITL1BriefApproval:
    """Test HITL-1: Brief approval flow."""

    def _setup_mocks(self, monkeypatch, briefs, hitl_fn):
        monkeypatch.setattr(f"{_PIPE}.run_persona_suggester", _mock_suggester(briefs))
        monkeypatch.setattr(f"{_PIPE}.run_persona_profile_generator", AsyncMock(side_effect=_mock_generator({})))
        monkeypatch.setattr(f"{_PIPE}.run_ap_hitl_checkpoint", hitl_fn)
        monkeypatch.setattr(f"{_PIPE}._load_knowledge_docs", AsyncMock(return_value=""))
        monkeypatch.setattr(f"{_PIPE}.build_ap_brief_review_graph", MagicMock())
        monkeypatch.setattr(f"{_PIPE}.build_ap_profile_review_graph", MagicMock())

    @pytest.mark.asyncio
    async def test_auto_approve_passes_all(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        briefs = _make_briefs(3)
        self._setup_mocks(monkeypatch, briefs, _mock_hitl_auto_approve())

        output = await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        assert output.briefs_approved == 3

    @pytest.mark.asyncio
    async def test_all_rejected_ends_gracefully(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        briefs = _make_briefs(3)

        async def _hitl_reject_all(graph, state, thread_id, **kw):
            if state.get("checkpoint") == 1:
                return {"batch_decision": "reject_all", "approved_briefs": []}
            return state

        self._setup_mocks(monkeypatch, briefs, _hitl_reject_all)

        output = await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        assert output.briefs_approved == 0
        assert output.profiles_generated == 0

    @pytest.mark.asyncio
    async def test_partial_approval(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        briefs = _make_briefs(3)

        async def _hitl_partial(graph, state, thread_id, **kw):
            if state.get("checkpoint") == 1:
                # Only approve first 2 briefs
                return {
                    "batch_decision": "partial",
                    "approved_briefs": state["briefs"][:2],
                }
            elif state.get("checkpoint") == 2:
                return {
                    "approved_profiles": list(state.get("profile_summaries", {}).keys()),
                    "revision_requests": {},
                    "rejected_profiles": [],
                }
            return state

        self._setup_mocks(monkeypatch, briefs, _hitl_partial)

        output = await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        assert output.briefs_approved == 2

    @pytest.mark.asyncio
    async def test_manual_briefs_included(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        briefs = _make_briefs(2)
        manual_brief = {
            "brief_id": "pb-manual-001",
            "persona_name": "CustomPerson",
            "tagline": "Custom role",
            "description": "Manual entry",
            "rationale": ["Custom reason"],
            "source": "manual",
        }

        async def _hitl_with_manual(graph, state, thread_id, **kw):
            if state.get("checkpoint") == 1:
                return {
                    "batch_decision": "approve_all",
                    "approved_briefs": state["briefs"] + [manual_brief],
                }
            elif state.get("checkpoint") == 2:
                return {
                    "approved_profiles": list(state.get("profile_summaries", {}).keys()),
                    "revision_requests": {},
                    "rejected_profiles": [],
                }
            return state

        self._setup_mocks(monkeypatch, briefs, _hitl_with_manual)

        output = await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        assert output.briefs_approved == 3  # 2 original + 1 manual

    @pytest.mark.asyncio
    async def test_modified_brief_passes_through(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        briefs = _make_briefs(1)
        modified = briefs[0].model_dump(mode="json")
        modified["persona_name"] = "Modified Sarah"
        modified["source"] = "hybrid"

        async def _hitl_modify(graph, state, thread_id, **kw):
            if state.get("checkpoint") == 1:
                return {
                    "batch_decision": "partial",
                    "approved_briefs": [modified],
                }
            elif state.get("checkpoint") == 2:
                return {
                    "approved_profiles": list(state.get("profile_summaries", {}).keys()),
                    "revision_requests": {},
                    "rejected_profiles": [],
                }
            return state

        self._setup_mocks(monkeypatch, briefs, _hitl_modify)

        output = await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        assert output.briefs_approved == 1


# ═══════════════════════════════════════════════════════════════════════
# E. Phase 2 — Generator Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPhase2Generators:
    """Test Phase 2: Parallel profile generators."""

    def _setup_full(self, monkeypatch, briefs, gen_fn=None):
        monkeypatch.setattr(f"{_PIPE}.run_persona_suggester", _mock_suggester(briefs))
        if gen_fn:
            monkeypatch.setattr(f"{_PIPE}.run_persona_profile_generator", gen_fn)
        else:
            monkeypatch.setattr(f"{_PIPE}.run_persona_profile_generator", AsyncMock(side_effect=_mock_generator({})))
        monkeypatch.setattr(f"{_PIPE}.run_ap_hitl_checkpoint", _mock_hitl_auto_approve())
        monkeypatch.setattr(f"{_PIPE}._load_knowledge_docs", AsyncMock(return_value=""))
        monkeypatch.setattr(f"{_PIPE}.build_ap_brief_review_graph", MagicMock())
        monkeypatch.setattr(f"{_PIPE}.build_ap_profile_review_graph", MagicMock())

    @pytest.mark.asyncio
    async def test_calls_generator_per_brief(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        briefs = _make_briefs(3)
        gen_mock = AsyncMock(side_effect=_mock_generator({}))
        self._setup_full(monkeypatch, briefs, gen_mock)

        await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        assert gen_mock.call_count == 3

    @pytest.mark.asyncio
    async def test_per_persona_error_non_fatal(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        briefs = _make_briefs(3)
        # Second brief returns an error
        results_map = {
            briefs[1].brief_id: _make_result(briefs[1], error="LLM timeout"),
        }

        async def _gen(brief, **kwargs):
            if brief.brief_id in results_map:
                return results_map[brief.brief_id]
            return _make_result(brief)

        self._setup_full(monkeypatch, briefs, _gen)

        output = await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        # Pipeline should still complete
        assert output.profiles_generated >= 2
        # Error persona should be in results
        error_results = [r for r in output.persona_results.values() if r.error]
        assert len(error_results) == 1

    @pytest.mark.asyncio
    async def test_exception_captured_as_error(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        briefs = _make_briefs(2)
        call_count = 0

        async def _gen_with_exception(brief, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Perplexity API down")
            return _make_result(brief)

        self._setup_full(monkeypatch, briefs, _gen_with_exception)

        output = await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        error_results = [r for r in output.persona_results.values() if r.error]
        assert len(error_results) == 1
        assert "Perplexity API down" in error_results[0].error

    @pytest.mark.asyncio
    async def test_writes_to_storage(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        briefs = _make_briefs(2)
        self._setup_full(monkeypatch, briefs)

        output = await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        # Verify persona dirs exist
        persona_dir = setup_preflight / "audience_personas" / "test-co"
        assert persona_dir.exists()
        manifest_path = persona_dir / "_manifest.json"
        assert manifest_path.exists()

    @pytest.mark.asyncio
    async def test_first_persona_is_icp(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        briefs = _make_briefs(3)
        self._setup_full(monkeypatch, briefs)

        output = await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        # Read manifest to check first persona is ICP
        manifest_path = setup_preflight / "audience_personas" / "test-co" / "_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        # First persona (Sarah) should be ICP
        sarah_entry = manifest["personas"].get("sarah")
        assert sarah_entry is not None
        assert sarah_entry["kind"] == "icp"

    @pytest.mark.asyncio
    async def test_parallel_execution(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        """Verify generators run concurrently (not sequentially)."""
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        briefs = _make_briefs(3)
        timestamps: List[float] = []

        async def _timed_gen(brief, **kwargs):
            import time
            timestamps.append(time.time())
            await asyncio.sleep(0.05)
            return _make_result(brief)

        self._setup_full(monkeypatch, briefs, _timed_gen)

        await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        # All 3 should start within ~50ms of each other (parallel, not 150ms sequential)
        assert len(timestamps) == 3
        assert max(timestamps) - min(timestamps) < 0.1

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        briefs = _make_briefs(3)
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def _tracked_gen(brief, **kwargs):
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent:
                    max_concurrent = current_concurrent
            await asyncio.sleep(0.05)
            async with lock:
                current_concurrent -= 1
            return _make_result(brief)

        self._setup_full(monkeypatch, briefs, _tracked_gen)
        monkeypatch.setattr(
            "core.config.settings.settings.audience_persona_max_concurrent_generators", 1,
        )

        await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        assert max_concurrent == 1


# ═══════════════════════════════════════════════════════════════════════
# F. HITL-2 Tests
# ═══════════════════════════════════════════════════════════════════════


class TestHITL2ProfileReview:
    """Test HITL-2: Profile review flow."""

    def _setup_full(self, monkeypatch, briefs, hitl_fn, gen_fn=None):
        monkeypatch.setattr(f"{_PIPE}.run_persona_suggester", _mock_suggester(briefs))
        if gen_fn:
            monkeypatch.setattr(f"{_PIPE}.run_persona_profile_generator", gen_fn)
        else:
            monkeypatch.setattr(f"{_PIPE}.run_persona_profile_generator", AsyncMock(side_effect=_mock_generator({})))
        monkeypatch.setattr(f"{_PIPE}.run_ap_hitl_checkpoint", hitl_fn)
        monkeypatch.setattr(f"{_PIPE}._load_knowledge_docs", AsyncMock(return_value=""))
        monkeypatch.setattr(f"{_PIPE}.build_ap_brief_review_graph", MagicMock())
        monkeypatch.setattr(f"{_PIPE}.build_ap_profile_review_graph", MagicMock())

    @pytest.mark.asyncio
    async def test_auto_approve_all_profiles(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        briefs = _make_briefs(2)
        self._setup_full(monkeypatch, briefs, _mock_hitl_auto_approve())

        output = await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        assert output.profiles_generated == 2

    @pytest.mark.asyncio
    async def test_revision_reruns_agent(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        briefs = _make_briefs(2)
        gen_call_count = 0

        async def _counting_gen(brief, **kwargs):
            nonlocal gen_call_count
            gen_call_count += 1
            return _make_result(brief, content=f"# Profile v{gen_call_count}")

        checkpoint_calls = 0

        async def _hitl_with_revision(graph, state, thread_id, **kw):
            nonlocal checkpoint_calls
            checkpoint_calls += 1
            if state.get("checkpoint") == 1:
                return {
                    "batch_decision": "approve_all",
                    "approved_briefs": state["briefs"],
                }
            elif state.get("checkpoint") == 2:
                summaries = state.get("profile_summaries", {})
                pids = list(summaries.keys())
                return {
                    "approved_profiles": pids[1:],  # approve second
                    "revision_requests": {pids[0]: "Add more buying triggers"},
                    "rejected_profiles": [],
                }
            return state

        self._setup_full(monkeypatch, briefs, _hitl_with_revision, _counting_gen)

        output = await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        # 2 initial + 1 revision = 3 generator calls
        assert gen_call_count == 3

    @pytest.mark.asyncio
    async def test_revision_writes_new_version(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        briefs = _make_briefs(1)

        async def _hitl_revise(graph, state, thread_id, **kw):
            if state.get("checkpoint") == 1:
                return {"batch_decision": "approve_all", "approved_briefs": state["briefs"]}
            elif state.get("checkpoint") == 2:
                pids = list(state.get("profile_summaries", {}).keys())
                return {
                    "approved_profiles": [],
                    "revision_requests": {pids[0]: "Improve pain points"},
                    "rejected_profiles": [],
                }
            return state

        self._setup_full(monkeypatch, briefs, _hitl_revise)

        await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        # Should have v1 and v2
        persona_dir = setup_preflight / "audience_personas" / "test-co" / "sarah"
        assert (persona_dir / "v1.md").exists()
        assert (persona_dir / "v2.md").exists()

    @pytest.mark.asyncio
    async def test_reject_marks_archived(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        briefs = _make_briefs(2)

        async def _hitl_reject(graph, state, thread_id, **kw):
            if state.get("checkpoint") == 1:
                return {"batch_decision": "approve_all", "approved_briefs": state["briefs"]}
            elif state.get("checkpoint") == 2:
                pids = list(state.get("profile_summaries", {}).keys())
                return {
                    "approved_profiles": [pids[0]],
                    "revision_requests": {},
                    "rejected_profiles": [pids[1]],
                }
            return state

        self._setup_full(monkeypatch, briefs, _hitl_reject)

        output = await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        # Check manifest for archived status
        manifest_path = setup_preflight / "audience_personas" / "test-co" / "_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        statuses = {pid: e["status"] for pid, e in manifest["personas"].items()}
        assert "archived" in statuses.values()

    @pytest.mark.asyncio
    async def test_skipped_when_all_generators_failed(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        briefs = _make_briefs(2)

        async def _failing_gen(brief, **kwargs):
            return _make_result(brief, error="API failure")

        hitl_call_count = 0

        async def _counting_hitl(graph, state, thread_id, **kw):
            nonlocal hitl_call_count
            hitl_call_count += 1
            if state.get("checkpoint") == 1:
                return {"batch_decision": "approve_all", "approved_briefs": state["briefs"]}
            return state

        self._setup_full(monkeypatch, briefs, _counting_hitl, _failing_gen)

        output = await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        # HITL-2 should not be called (only HITL-1 called)
        assert hitl_call_count == 1
        assert output.profiles_generated == 0

    @pytest.mark.asyncio
    async def test_unknown_persona_in_revision_skipped(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        briefs = _make_briefs(1)

        async def _hitl_bad_revision(graph, state, thread_id, **kw):
            if state.get("checkpoint") == 1:
                return {"batch_decision": "approve_all", "approved_briefs": state["briefs"]}
            elif state.get("checkpoint") == 2:
                return {
                    "approved_profiles": list(state.get("profile_summaries", {}).keys()),
                    "revision_requests": {"nonexistent-persona": "Fix it"},
                    "rejected_profiles": [],
                }
            return state

        self._setup_full(monkeypatch, briefs, _hitl_bad_revision)

        # Should not crash
        output = await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        assert output.profiles_generated >= 1

    @pytest.mark.asyncio
    async def test_sends_trimmed_previews(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        briefs = _make_briefs(1)
        long_content = "x " * 1000  # 2000 chars

        async def _long_gen(brief, **kwargs):
            return _make_result(brief, content=long_content)

        hitl2_state_captured = {}

        async def _capturing_hitl(graph, state, thread_id, **kw):
            if state.get("checkpoint") == 1:
                return {"batch_decision": "approve_all", "approved_briefs": state["briefs"]}
            elif state.get("checkpoint") == 2:
                hitl2_state_captured.update(state)
                return {
                    "approved_profiles": list(state.get("profile_summaries", {}).keys()),
                    "revision_requests": {},
                    "rejected_profiles": [],
                }
            return state

        self._setup_full(monkeypatch, briefs, _capturing_hitl, _long_gen)

        await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        # Check that preview is trimmed to 500 chars
        for pid, summary in hitl2_state_captured.get("profile_summaries", {}).items():
            assert len(summary["content_preview"]) <= 500


# ═══════════════════════════════════════════════════════════════════════
# G. Phase 3 — Finalize Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPhase3Finalize:
    """Test Phase 3: Finalize manifest updates."""

    def _setup_full(self, monkeypatch, briefs):
        monkeypatch.setattr(f"{_PIPE}.run_persona_suggester", _mock_suggester(briefs))
        monkeypatch.setattr(f"{_PIPE}.run_persona_profile_generator", AsyncMock(side_effect=_mock_generator({})))
        monkeypatch.setattr(f"{_PIPE}.run_ap_hitl_checkpoint", _mock_hitl_auto_approve())
        monkeypatch.setattr(f"{_PIPE}._load_knowledge_docs", AsyncMock(return_value=""))
        monkeypatch.setattr(f"{_PIPE}.build_ap_brief_review_graph", MagicMock())
        monkeypatch.setattr(f"{_PIPE}.build_ap_profile_review_graph", MagicMock())

    @pytest.mark.asyncio
    async def test_updates_last_full_run(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        self._setup_full(monkeypatch, _make_briefs(2))

        await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        manifest_path = setup_preflight / "audience_personas" / "test-co" / "_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        assert manifest.get("last_full_run") is not None

    @pytest.mark.asyncio
    async def test_records_kb_synthesis_version(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        self._setup_full(monkeypatch, _make_briefs(2))

        await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        manifest_path = setup_preflight / "audience_personas" / "test-co" / "_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        assert manifest.get("kb_synthesis_version") == 2

    @pytest.mark.asyncio
    async def test_updates_company_name(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        self._setup_full(monkeypatch, _make_briefs(1))

        await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        manifest_path = setup_preflight / "audience_personas" / "test-co" / "_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        assert manifest["company_name"] == "Test Co"


# ═══════════════════════════════════════════════════════════════════════
# H. Full Flow Tests
# ═══════════════════════════════════════════════════════════════════════


class TestFullPipelineFlow:
    """Test full pipeline end-to-end."""

    def _setup_full(self, monkeypatch, briefs):
        monkeypatch.setattr(f"{_PIPE}.run_persona_suggester", _mock_suggester(briefs))
        monkeypatch.setattr(f"{_PIPE}.run_persona_profile_generator", AsyncMock(side_effect=_mock_generator({})))
        monkeypatch.setattr(f"{_PIPE}.run_ap_hitl_checkpoint", _mock_hitl_auto_approve())
        monkeypatch.setattr(f"{_PIPE}._load_knowledge_docs", AsyncMock(return_value=""))
        monkeypatch.setattr(f"{_PIPE}.build_ap_brief_review_graph", MagicMock())
        monkeypatch.setattr(f"{_PIPE}.build_ap_profile_review_graph", MagicMock())

    @pytest.mark.asyncio
    async def test_happy_path(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        briefs = _make_briefs(3)
        self._setup_full(monkeypatch, briefs)

        output = await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        assert isinstance(output, AudiencePersonaOutput)
        assert output.slug == "test-co"
        assert output.briefs_suggested == 3
        assert output.briefs_approved == 3
        assert output.profiles_generated == 3

    @pytest.mark.asyncio
    async def test_output_fields_populated(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        self._setup_full(monkeypatch, _make_briefs(2))

        output = await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        assert output.company_name == "Test Co"
        assert output.manifest is not None
        assert output.total_execution_time_s > 0
        assert output.persona_dir
        assert len(output.persona_results) == 2

    @pytest.mark.asyncio
    async def test_storage_dir_exists(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        self._setup_full(monkeypatch, _make_briefs(2))

        await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
        )
        persona_dir = setup_preflight / "audience_personas" / "test-co"
        assert persona_dir.exists()
        assert (persona_dir / "_manifest.json").exists()


# ═══════════════════════════════════════════════════════════════════════
# I. SSE + TaskStore Tests
# ═══════════════════════════════════════════════════════════════════════


class TestSSEAndTaskStore:
    """Test SSE event emission and task store updates."""

    def _setup_full(self, monkeypatch, briefs):
        monkeypatch.setattr(f"{_PIPE}.run_persona_suggester", _mock_suggester(briefs))
        monkeypatch.setattr(f"{_PIPE}.run_persona_profile_generator", AsyncMock(side_effect=_mock_generator({})))
        monkeypatch.setattr(f"{_PIPE}.run_ap_hitl_checkpoint", _mock_hitl_auto_approve())
        monkeypatch.setattr(f"{_PIPE}._load_knowledge_docs", AsyncMock(return_value=""))
        monkeypatch.setattr(f"{_PIPE}.build_ap_brief_review_graph", MagicMock())
        monkeypatch.setattr(f"{_PIPE}.build_ap_profile_review_graph", MagicMock())

    @pytest.mark.asyncio
    async def test_sse_events_emitted(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        self._setup_full(monkeypatch, _make_briefs(2))
        event_bus = MagicMock()

        await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
            task_id="t-1", event_bus=event_bus,
        )

        event_types = [c[0][1] for c in event_bus.publish.call_args_list]
        assert "pipeline_start" in event_types
        assert "ap_phase_start" in event_types
        assert "ap_agent_complete" in event_types
        assert "completed" in event_types

    @pytest.mark.asyncio
    async def test_task_store_updated(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        self._setup_full(monkeypatch, _make_briefs(2))
        task_store = MagicMock()

        await run_audience_persona_pipeline(
            _make_input(), artifacts_root=setup_preflight,
            task_id="t-1", task_store=task_store,
        )

        assert task_store.update_task.called
        steps = [c[1].get("current_step") for c in task_store.update_task.call_args_list if c[1].get("current_step")]
        assert len(steps) >= 2  # At least preflight + phase_1


# ═══════════════════════════════════════════════════════════════════════
# J. Error Handling Tests
# ═══════════════════════════════════════════════════════════════════════


class TestErrorHandling:
    """Test pipeline error handling."""

    @pytest.mark.asyncio
    async def test_error_emits_failed_event(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        monkeypatch.setattr(f"{_PIPE}.run_persona_suggester", _mock_suggester([]))
        monkeypatch.setattr(f"{_PIPE}._load_knowledge_docs", AsyncMock(return_value=""))

        event_bus = MagicMock()
        with pytest.raises(RuntimeError):
            await run_audience_persona_pipeline(
                _make_input(), artifacts_root=setup_preflight,
                task_id="t-1", event_bus=event_bus,
            )

        event_types = [c[0][1] for c in event_bus.publish.call_args_list]
        assert "failed" in event_types

    @pytest.mark.asyncio
    async def test_error_flushes_tracing(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        flush_mock = MagicMock()
        monkeypatch.setattr(f"{_PIPE}.flush", flush_mock)
        monkeypatch.setattr(f"{_PIPE}.run_persona_suggester", _mock_suggester([]))
        monkeypatch.setattr(f"{_PIPE}._load_knowledge_docs", AsyncMock(return_value=""))

        with pytest.raises(RuntimeError):
            await run_audience_persona_pipeline(
                _make_input(), artifacts_root=setup_preflight,
            )

        flush_mock.assert_called()
