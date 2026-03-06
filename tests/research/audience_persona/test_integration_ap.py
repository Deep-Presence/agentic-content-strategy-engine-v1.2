"""Phase F integration tests for Audience Persona pipeline.

Tests: resolve_artifacts() integration, concurrent write safety,
delayed HITL approval, and KB -> AP -> content engine artifact chain.

TDD: tests written FIRST, implementation follows.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.tasks.runner import resolve_artifacts
from core.models.audience_persona import (
    AudiencePersonaInput,
    AudiencePersonaOutput,
    PersonaAgentResult,
    PersonaBrief,
    PersonaManifest,
    PersonaProfileEntry,
)
from core.research.audience_persona.storage import PersonaStorage


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PIPE = "core.research.audience_persona.pipeline"


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _create_ap_persona(
    root: Path,
    slug: str,
    persona_id: str,
    *,
    status: str = "fresh",
    version: int = 1,
    content: str = "# Persona Profile\n\nDetailed profile content.",
    kind: str = "secondary",
) -> str:
    """Create AP persona artifacts on disk via PersonaStorage.

    Returns the path to the v{N}.md file.
    """
    storage = PersonaStorage(root, slug)
    for v in range(1, version + 1):
        storage.write_version(
            persona_id,
            persona_name=persona_id.replace("-", " ").title(),
            content_md=f"{content} (v{v})",
            kind=kind,
            created_by="agent",
            tagline=f"Test {persona_id}",
            status=status,
        )
    return str(storage._version_md_path(persona_id, version))


def _create_legacy_persona(root: Path, slug: str, name: str = "icp") -> str:
    """Create a legacy persona file at artifacts/personas/{slug}__persona-{name}.md."""
    personas_dir = root / "personas"
    personas_dir.mkdir(parents=True, exist_ok=True)
    path = personas_dir / f"{slug}__persona-{name}.md"
    path.write_text(f"# Legacy Persona {name}\n\nLegacy content.", encoding="utf-8")
    return str(path)


def _create_kb_artifacts(
    root: Path,
    slug: str,
    *,
    synthesis_version: int = 2,
) -> None:
    """Create minimal KB artifacts for preflight validation."""
    # Company context
    ctx_dir = root / "company_context"
    ctx_dir.mkdir(parents=True, exist_ok=True)
    (ctx_dir / f"{slug}.md").write_text(
        f"# {slug} Company Context\n\nOverview.", encoding="utf-8",
    )

    # KB manifest with customer_reviews + synthesis_version
    kb_dir = root / "knowledge_base" / slug
    kb_dir.mkdir(parents=True, exist_ok=True)

    # Customer reviews
    reviews_dir = kb_dir / "customer_reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    (reviews_dir / "v1.md").write_text(
        "# Customer Reviews\n\nPositive feedback.", encoding="utf-8",
    )

    # KB manifest
    manifest = {
        "slug": slug,
        "company_name": slug.replace("-", " ").title(),
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
        "synthesis_version": synthesis_version,
    }
    (kb_dir / "_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8",
    )


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


# ═══════════════════════════════════════════════════════════════════════
# CLASS 1: resolve_artifacts() + Audience Persona integration (10 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestResolveArtifactsAudiencePersona:
    """Test that resolve_artifacts() correctly discovers AP persona paths."""

    def test_resolve_picks_up_new_ap_paths(self, tmp_path: Path) -> None:
        """New AP personas with fresh status are picked up."""
        root = tmp_path / "artifacts"
        root.mkdir()
        _create_ap_persona(root, "test-co", "vp-finance")
        _create_ap_persona(root, "test-co", "head-ops")

        resolved = resolve_artifacts("test-co", root)
        assert len(resolved["persona_paths"]) == 2
        assert all(p.endswith("v1.md") for p in resolved["persona_paths"])

    def test_resolve_ignores_archived_personas(self, tmp_path: Path) -> None:
        """Archived personas are excluded from resolve_artifacts."""
        root = tmp_path / "artifacts"
        root.mkdir()
        _create_ap_persona(root, "test-co", "vp-finance", status="fresh")
        _create_ap_persona(root, "test-co", "old-persona", status="archived")

        resolved = resolve_artifacts("test-co", root)
        assert len(resolved["persona_paths"]) == 1
        assert "vp-finance" in resolved["persona_paths"][0]

    def test_resolve_ignores_pending_review(self, tmp_path: Path) -> None:
        """pending_review personas are not visible to content engine."""
        root = tmp_path / "artifacts"
        root.mkdir()
        _create_ap_persona(root, "test-co", "manual-persona", status="pending_review")

        resolved = resolve_artifacts("test-co", root)
        assert resolved["persona_paths"] == []

    def test_resolve_falls_back_to_legacy(self, tmp_path: Path) -> None:
        """Falls back to legacy persona path when no AP directory exists."""
        root = tmp_path / "artifacts"
        root.mkdir()
        _create_legacy_persona(root, "test-co", "icp")

        resolved = resolve_artifacts("test-co", root)
        assert len(resolved["persona_paths"]) == 1
        assert "personas" in resolved["persona_paths"][0]
        assert "test-co__persona-icp.md" in resolved["persona_paths"][0]

    def test_resolve_falls_back_when_manifest_empty(self, tmp_path: Path) -> None:
        """Falls back to legacy when AP manifest exists but has zero personas."""
        root = tmp_path / "artifacts"
        root.mkdir()

        # Create empty AP manifest
        ap_dir = root / "audience_personas" / "test-co"
        ap_dir.mkdir(parents=True)
        manifest = PersonaManifest(slug="test-co")
        (ap_dir / "_manifest.json").write_text(
            manifest.model_dump_json(indent=2), encoding="utf-8",
        )

        # Create legacy fallback
        _create_legacy_persona(root, "test-co", "icp")

        resolved = resolve_artifacts("test-co", root)
        assert len(resolved["persona_paths"]) == 1
        assert "personas" in resolved["persona_paths"][0]

    def test_resolve_falls_back_when_only_archived(self, tmp_path: Path) -> None:
        """Falls back to legacy when AP has only archived personas (Codex finding #1)."""
        root = tmp_path / "artifacts"
        root.mkdir()
        _create_ap_persona(root, "test-co", "old-persona", status="archived")

        # Create legacy fallback
        _create_legacy_persona(root, "test-co", "icp")

        resolved = resolve_artifacts("test-co", root)
        # list_persona_paths() returns empty for archived-only,
        # so should fall back to legacy
        assert len(resolved["persona_paths"]) == 1
        assert "personas" in resolved["persona_paths"][0]

    def test_resolve_prefers_new_over_legacy(self, tmp_path: Path) -> None:
        """When both AP and legacy exist, AP takes precedence."""
        root = tmp_path / "artifacts"
        root.mkdir()
        _create_ap_persona(root, "test-co", "vp-finance")
        _create_legacy_persona(root, "test-co", "icp")

        resolved = resolve_artifacts("test-co", root)
        assert len(resolved["persona_paths"]) == 1
        assert "audience_personas" in resolved["persona_paths"][0]
        assert "vp-finance" in resolved["persona_paths"][0]

    def test_resolve_effective_slug_product_level(self, tmp_path: Path) -> None:
        """Product-level effective_slug finds AP personas at product path."""
        root = tmp_path / "artifacts"
        root.mkdir()
        _create_ap_persona(root, "test-co__product", "vp-finance")

        resolved = resolve_artifacts(
            "test-co", root, effective_slug="test-co__product",
        )
        assert len(resolved["persona_paths"]) == 1
        assert "test-co__product" in resolved["persona_paths"][0]

    def test_resolve_effective_slug_falls_back_to_company(self, tmp_path: Path) -> None:
        """Product-level lookup falls back to company-level AP storage."""
        root = tmp_path / "artifacts"
        root.mkdir()
        # Only company-level AP exists, no product-level
        _create_ap_persona(root, "test-co", "vp-finance")

        resolved = resolve_artifacts(
            "test-co", root, effective_slug="test-co__product",
        )
        assert len(resolved["persona_paths"]) == 1
        assert "audience_personas/test-co/" in resolved["persona_paths"][0]

    def test_resolve_corrupt_manifest_falls_back(self, tmp_path: Path) -> None:
        """Corrupt AP manifest falls back to legacy gracefully (Codex finding #3)."""
        root = tmp_path / "artifacts"
        root.mkdir()

        # Create corrupt AP manifest
        ap_dir = root / "audience_personas" / "test-co"
        ap_dir.mkdir(parents=True)
        (ap_dir / "_manifest.json").write_text(
            "{corrupt json data!!", encoding="utf-8",
        )

        # Create legacy fallback
        _create_legacy_persona(root, "test-co", "icp")

        resolved = resolve_artifacts("test-co", root)
        # Should fall back to legacy due to corrupt manifest
        assert len(resolved["persona_paths"]) == 1
        assert "personas" in resolved["persona_paths"][0]


# ═══════════════════════════════════════════════════════════════════════
# CLASS 2: Concurrent write_version safety (4 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestConcurrentWriteVersion:
    """Verify asyncio.Lock prevents manifest corruption under parallel writes."""

    @pytest.mark.asyncio
    async def test_parallel_writes_no_lost_updates(self, tmp_path: Path) -> None:
        """5 concurrent writers for different personas — none should be lost."""
        root = tmp_path / "artifacts"
        root.mkdir()
        storage = PersonaStorage(root, "test-co")
        lock = asyncio.Lock()

        async def _write(persona_id: str) -> None:
            async with lock:
                storage.write_version(
                    persona_id,
                    persona_name=persona_id.replace("-", " ").title(),
                    content_md=f"# Profile for {persona_id}",
                    kind="secondary",
                    created_by="agent",
                    tagline=f"Test {persona_id}",
                )

        await asyncio.gather(*[
            _write(f"persona-{i}") for i in range(5)
        ])

        manifest = storage.read_manifest()
        assert len(manifest.personas) == 5
        for i in range(5):
            pid = f"persona-{i}"
            assert pid in manifest.personas
            assert manifest.personas[pid].current_version == 1

    @pytest.mark.asyncio
    async def test_parallel_writes_same_persona_increments(self, tmp_path: Path) -> None:
        """3 concurrent writes to SAME persona — versions increment correctly."""
        root = tmp_path / "artifacts"
        root.mkdir()
        storage = PersonaStorage(root, "test-co")
        lock = asyncio.Lock()

        async def _write(version_hint: int) -> None:
            async with lock:
                storage.write_version(
                    "vp-finance",
                    persona_name="VP Finance",
                    content_md=f"# Profile version {version_hint}",
                    kind="icp",
                    created_by="agent",
                    tagline="VP Finance",
                )

        await asyncio.gather(*[_write(i) for i in range(3)])

        manifest = storage.read_manifest()
        assert manifest.personas["vp-finance"].current_version == 3

        # All version files should exist
        for v in range(1, 4):
            md_path = storage._version_md_path("vp-finance", v)
            assert md_path.exists(), f"v{v}.md missing"

    @pytest.mark.asyncio
    async def test_parallel_writes_interleaved_with_reads(self, tmp_path: Path) -> None:
        """5 writers + 5 readers concurrent — readers never crash on partial manifest."""
        root = tmp_path / "artifacts"
        root.mkdir()
        storage = PersonaStorage(root, "test-co")
        lock = asyncio.Lock()
        reader_errors: List[str] = []

        async def _write(persona_id: str) -> None:
            async with lock:
                storage.write_version(
                    persona_id,
                    persona_name=persona_id,
                    content_md=f"# {persona_id}",
                )

        async def _read() -> None:
            try:
                # Allow writers to start first
                await asyncio.sleep(0)
                storage.list_persona_paths()
                storage.read_manifest()
            except Exception as exc:
                reader_errors.append(str(exc))

        writers = [_write(f"p-{i}") for i in range(5)]
        readers = [_read() for _ in range(5)]
        await asyncio.gather(*writers, *readers)

        assert reader_errors == [], f"Readers hit errors: {reader_errors}"
        manifest = storage.read_manifest()
        assert len(manifest.personas) == 5

    @pytest.mark.asyncio
    async def test_lock_serializes_brief_and_version(self, tmp_path: Path) -> None:
        """Lock ensures write_brief() + write_version() are atomic together."""
        root = tmp_path / "artifacts"
        root.mkdir()
        storage = PersonaStorage(root, "test-co")
        lock = asyncio.Lock()
        briefs = _make_briefs(3)

        async def _write_both(brief: PersonaBrief, persona_id: str) -> None:
            async with lock:
                storage.write_brief(persona_id, brief)
                storage.write_version(
                    persona_id,
                    persona_name=brief.persona_name,
                    content_md=f"# Profile for {brief.persona_name}",
                    kind="secondary",
                    created_by=brief.source,
                    tagline=brief.tagline,
                )

        persona_ids = ["sarah", "marcus", "priya"]
        await asyncio.gather(*[
            _write_both(b, pid) for b, pid in zip(briefs, persona_ids)
        ])

        manifest = storage.read_manifest()
        assert len(manifest.personas) == 3

        for pid in persona_ids:
            assert storage.read_brief(pid) is not None
            assert storage._version_md_path(pid, 1).exists()


# ═══════════════════════════════════════════════════════════════════════
# CLASS 3: Delayed HITL approval (4 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestDelayedApproval:
    """Verify pipeline works when HITL approval arrives after arbitrary delay."""

    @pytest.fixture(autouse=True)
    def _mock_tracing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Disable all tracing functions."""
        for fn in ("create_session", "create_span", "end_span", "flush", "log_generation"):
            monkeypatch.setattr(f"{_PIPE}.{fn}", MagicMock())

    @pytest.fixture()
    def setup_preflight(self, tmp_path: Path) -> Path:
        """Create preflight artifacts."""
        _create_kb_artifacts(tmp_path, "test-co", synthesis_version=2)
        return tmp_path

    @pytest.mark.asyncio
    async def test_delayed_hitl1_resumes_correctly(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Pipeline completes after delayed HITL-1 approval."""
        briefs = _make_briefs(3)
        results_map = {b.brief_id: _make_result(b) for b in briefs}

        # Mock agents
        monkeypatch.setattr(
            f"{_PIPE}.run_persona_suggester",
            AsyncMock(return_value=(briefs, 1.0)),
        )

        async def _gen(brief, **kwargs):
            return results_map[brief.brief_id]

        monkeypatch.setattr(f"{_PIPE}.run_persona_profile_generator", _gen)
        monkeypatch.setattr(f"{_PIPE}._load_knowledge_docs", AsyncMock(return_value=""))

        # Mock HITL — simulates delayed approval by returning approve_all
        async def _hitl(graph, initial_state, thread_id, **kwargs):
            if initial_state.get("checkpoint") == 1:
                return {
                    "batch_decision": "approve_all",
                    "approved_briefs": initial_state["briefs"],
                }
            elif initial_state.get("checkpoint") == 2:
                summaries = initial_state.get("profile_summaries", {})
                return {
                    "approved_profiles": list(summaries.keys()),
                    "revision_requests": {},
                    "rejected_profiles": [],
                }
            return initial_state

        monkeypatch.setattr(f"{_PIPE}.run_ap_hitl_checkpoint", _hitl)

        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        inp = _make_input(auto_approve_checkpoints=[])
        output = await run_audience_persona_pipeline(
            inp, artifacts_root=setup_preflight,
        )

        assert output.profiles_generated == 3
        assert output.briefs_approved == 3

    @pytest.mark.asyncio
    async def test_delayed_hitl2_with_revision(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Delayed HITL-2 revision triggers re-generation for one persona."""
        briefs = _make_briefs(3)
        call_count: Dict[str, int] = {}

        monkeypatch.setattr(
            f"{_PIPE}.run_persona_suggester",
            AsyncMock(return_value=(briefs, 1.0)),
        )

        async def _gen(brief, revision_note=None, **kwargs):
            call_count[brief.brief_id] = call_count.get(brief.brief_id, 0) + 1
            suffix = " (revised)" if revision_note else ""
            return _make_result(brief, content=f"# Profile{suffix}")

        monkeypatch.setattr(f"{_PIPE}.run_persona_profile_generator", _gen)
        monkeypatch.setattr(f"{_PIPE}._load_knowledge_docs", AsyncMock(return_value=""))

        async def _hitl(graph, initial_state, thread_id, **kwargs):
            if initial_state.get("checkpoint") == 1:
                return {
                    "batch_decision": "approve_all",
                    "approved_briefs": initial_state["briefs"],
                }
            elif initial_state.get("checkpoint") == 2:
                summaries = initial_state.get("profile_summaries", {})
                pids = list(summaries.keys())
                # Revise the first persona
                return {
                    "approved_profiles": pids[1:],
                    "revision_requests": {pids[0]: "Add more detail about KPIs"},
                    "rejected_profiles": [],
                }
            return initial_state

        monkeypatch.setattr(f"{_PIPE}.run_ap_hitl_checkpoint", _hitl)

        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        inp = _make_input(auto_approve_checkpoints=[1])
        output = await run_audience_persona_pipeline(
            inp, artifacts_root=setup_preflight,
        )

        # The revised persona should be at v2
        storage = PersonaStorage(setup_preflight, "test-co")
        manifest = storage.read_manifest()
        revised_pids = [
            pid for pid, entry in manifest.personas.items()
            if entry.current_version == 2
        ]
        assert len(revised_pids) == 1
        # Others at v1
        non_revised = [
            pid for pid, entry in manifest.personas.items()
            if entry.current_version == 1
        ]
        assert len(non_revised) == 2

    @pytest.mark.asyncio
    async def test_delayed_hitl2_with_rejection(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Delayed HITL-2 rejection marks persona as archived."""
        briefs = _make_briefs(3)

        monkeypatch.setattr(
            f"{_PIPE}.run_persona_suggester",
            AsyncMock(return_value=(briefs, 1.0)),
        )

        async def _gen(brief, **kwargs):
            return _make_result(brief)

        monkeypatch.setattr(f"{_PIPE}.run_persona_profile_generator", _gen)
        monkeypatch.setattr(f"{_PIPE}._load_knowledge_docs", AsyncMock(return_value=""))

        async def _hitl(graph, initial_state, thread_id, **kwargs):
            if initial_state.get("checkpoint") == 1:
                return {
                    "batch_decision": "approve_all",
                    "approved_briefs": initial_state["briefs"],
                }
            elif initial_state.get("checkpoint") == 2:
                summaries = initial_state.get("profile_summaries", {})
                pids = list(summaries.keys())
                # Reject the first persona
                return {
                    "approved_profiles": pids[1:],
                    "revision_requests": {},
                    "rejected_profiles": [pids[0]],
                }
            return initial_state

        monkeypatch.setattr(f"{_PIPE}.run_ap_hitl_checkpoint", _hitl)

        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        inp = _make_input(auto_approve_checkpoints=[1])
        output = await run_audience_persona_pipeline(
            inp, artifacts_root=setup_preflight,
        )

        storage = PersonaStorage(setup_preflight, "test-co")
        manifest = storage.read_manifest()
        archived = [
            pid for pid, entry in manifest.personas.items()
            if entry.status == "archived"
        ]
        assert len(archived) == 1
        fresh = [
            pid for pid, entry in manifest.personas.items()
            if entry.status == "fresh"
        ]
        assert len(fresh) == 2

    @pytest.mark.asyncio
    async def test_task_store_state_during_hitl_wait(
        self, setup_preflight: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Task store shows PENDING_APPROVAL during HITL wait, RUNNING after resume."""
        briefs = _make_briefs(3)
        task_store = MagicMock()
        event_bus = MagicMock()
        task_store.semaphore = asyncio.Semaphore(3)
        task_id = "test-task-123"

        monkeypatch.setattr(
            f"{_PIPE}.run_persona_suggester",
            AsyncMock(return_value=(briefs, 1.0)),
        )

        async def _gen(brief, **kwargs):
            return _make_result(brief)

        monkeypatch.setattr(f"{_PIPE}.run_persona_profile_generator", _gen)
        monkeypatch.setattr(f"{_PIPE}._load_knowledge_docs", AsyncMock(return_value=""))

        hitl_calls: List[Dict[str, Any]] = []

        async def _hitl(graph, initial_state, thread_id, **kwargs):
            hitl_calls.append({
                "checkpoint": initial_state.get("checkpoint"),
                "task_store": kwargs.get("task_store"),
                "event_bus": kwargs.get("event_bus"),
                "task_id": kwargs.get("task_id"),
            })
            if initial_state.get("checkpoint") == 1:
                return {
                    "batch_decision": "approve_all",
                    "approved_briefs": initial_state["briefs"],
                }
            elif initial_state.get("checkpoint") == 2:
                summaries = initial_state.get("profile_summaries", {})
                return {
                    "approved_profiles": list(summaries.keys()),
                    "revision_requests": {},
                    "rejected_profiles": [],
                }
            return initial_state

        monkeypatch.setattr(f"{_PIPE}.run_ap_hitl_checkpoint", _hitl)

        from core.research.audience_persona.pipeline import run_audience_persona_pipeline

        inp = _make_input(auto_approve_checkpoints=[])
        await run_audience_persona_pipeline(
            inp,
            task_id=task_id,
            task_store=task_store,
            event_bus=event_bus,
            artifacts_root=setup_preflight,
        )

        # Both HITL checkpoints should have received task_store and event_bus
        assert len(hitl_calls) == 2
        for call in hitl_calls:
            assert call["task_store"] is task_store
            assert call["event_bus"] is event_bus
            assert call["task_id"] == task_id

        # Verify task_store.update_task was called with step updates
        update_calls = task_store.update_task.call_args_list
        steps = [c.kwargs.get("current_step") for c in update_calls if c.kwargs.get("current_step")]
        assert "phase_1_suggester" in steps
        assert "phase_2_generators" in steps
        assert "phase_3_finalize" in steps


# ═══════════════════════════════════════════════════════════════════════
# CLASS 4: End-to-end KB -> AP -> content engine artifact chain (4 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestEndToEndArtifactChain:
    """Test full KB -> AP -> content engine artifact resolution chain."""

    def test_kb_to_ap_to_resolve_chain(self, tmp_path: Path) -> None:
        """KB artifacts + AP personas resolve correctly together."""
        root = tmp_path / "artifacts"
        root.mkdir()

        # Create KB artifacts (company context)
        _create_kb_artifacts(root, "test-co", synthesis_version=2)

        # Create AP personas
        _create_ap_persona(root, "test-co", "vp-finance")
        _create_ap_persona(root, "test-co", "head-ops")

        resolved = resolve_artifacts("test-co", root)

        # Persona paths from AP
        assert len(resolved["persona_paths"]) == 2
        assert all("audience_personas" in p for p in resolved["persona_paths"])

        # Company context from KB
        assert resolved["company_context_path"] is not None
        assert "test-co.md" in resolved["company_context_path"]

    def test_content_engine_input_from_resolved(self, tmp_path: Path) -> None:
        """Resolved AP paths are valid filesystem paths readable by content engine."""
        root = tmp_path / "artifacts"
        root.mkdir()
        _create_ap_persona(root, "test-co", "vp-finance")
        _create_ap_persona(root, "test-co", "head-ops")

        resolved = resolve_artifacts("test-co", root)
        persona_paths = resolved["persona_paths"]

        assert len(persona_paths) == 2
        # Each path should be a readable file
        for p in persona_paths:
            path = Path(p)
            assert path.exists(), f"File does not exist: {p}"
            content = path.read_text(encoding="utf-8")
            assert len(content) > 0, f"File is empty: {p}"
            assert "# Persona Profile" in content

    def test_kb_synthesis_version_tracked_in_ap(self, tmp_path: Path) -> None:
        """AP manifest records kb_synthesis_version from KB output."""
        root = tmp_path / "artifacts"
        root.mkdir()
        _create_kb_artifacts(root, "test-co", synthesis_version=3)

        # Create AP persona and manually set kb_synthesis_version
        storage = PersonaStorage(root, "test-co")
        storage.write_version(
            "vp-finance", "Sarah", "# Profile",
            kind="icp", created_by="agent", tagline="VP Finance",
        )

        # Update manifest with KB synthesis version
        manifest = storage.read_manifest()
        manifest.kb_synthesis_version = 3
        storage.write_manifest(manifest)

        # Verify it's tracked
        manifest = storage.read_manifest()
        assert manifest.kb_synthesis_version == 3
        assert not storage.check_kb_staleness(3)
        assert storage.check_kb_staleness(4)  # stale if KB advances

    def test_both_legacy_and_new_coexist(self, tmp_path: Path) -> None:
        """Different companies can use different persona storage formats."""
        root = tmp_path / "artifacts"
        root.mkdir()

        # Ramp uses legacy
        _create_legacy_persona(root, "ramp", "icp")

        # Carta uses new AP
        _create_ap_persona(root, "carta", "vp-finance")

        # Resolve each
        ramp_resolved = resolve_artifacts("ramp", root)
        carta_resolved = resolve_artifacts("carta", root)

        # Ramp gets legacy
        assert len(ramp_resolved["persona_paths"]) == 1
        assert "personas" in ramp_resolved["persona_paths"][0]
        assert "ramp__persona-icp.md" in ramp_resolved["persona_paths"][0]

        # Carta gets AP
        assert len(carta_resolved["persona_paths"]) == 1
        assert "audience_personas" in carta_resolved["persona_paths"][0]
        assert "carta" in carta_resolved["persona_paths"][0]
