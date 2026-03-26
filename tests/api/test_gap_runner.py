"""Tests for gap analysis runner background task logic."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from api.tasks.event_bus import EventBus
from api.tasks.models import TaskStatus
from api.tasks.runner import resolve_artifacts, run_gap_pipeline_task, run_content_v13_pipeline_task
from api.tasks.store import TaskStore
from core.models.gap_analysis import GapReport


def _write_persona_storage(
    artifacts_root: Path,
    slug: str,
    persona_id: str,
    *,
    version: int = 1,
    status: str = "fresh",
    kind: str = "icp",
    content: str = "# Persona",
) -> None:
    """Write a persona via the audience_personas manifest + versioned file."""
    base = artifacts_root / "audience_personas" / slug
    base.mkdir(parents=True, exist_ok=True)
    persona_dir = base / persona_id
    persona_dir.mkdir(parents=True, exist_ok=True)
    (persona_dir / f"v{version}.md").write_text(content, encoding="utf-8")
    manifest_path = base / "_manifest.json"
    manifest: dict = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    personas = manifest.get("personas", {})
    personas[persona_id] = {
        "persona_name": persona_id.replace("-", " ").title(),
        "kind": kind,
        "status": status,
        "current_version": version,
        "last_updated": None,
    }
    manifest["personas"] = personas
    manifest.setdefault("slug", slug)
    manifest.setdefault("kb_synthesis_version", 0)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


@pytest.fixture
def gap_request() -> SimpleNamespace:
    """Mimics a simplified GapAnalysisStartRequest."""
    return SimpleNamespace(
        company_name="Ramp",
        domain="ramp.com",
        seed_urls=[],
        skip_steps=[],
        max_queries=150,
        platforms=["perplexity", "openai", "gemini", "claude"],
        language="en",
        region=None,
        additional_constraints=None,
        max_crawl_pages=None,
        max_crawl_depth=None,
    )


@pytest.fixture
def mock_report() -> GapReport:
    return GapReport(
        report_md="# Test Report",
        report_json={"executive_summary": "test"},
        generation_spec_md="# Spec",
        generation_spec_json={},
        visualization_paths=[],
    )


@pytest.fixture
def empty_artifacts(tmp_path: Path) -> Path:
    """Artifacts root with no research artifacts."""
    root = tmp_path / "artifacts"
    root.mkdir()
    return root


class TestResolveArtifacts:
    def test_resolves_nothing_when_empty(self, tmp_path: Path) -> None:
        root = tmp_path / "artifacts"
        root.mkdir()
        resolved = resolve_artifacts("ramp", root)
        assert resolved["company_context_path"] is None
        assert resolved["persona_paths"] == []
        assert resolved["style_guide_path"] is None

    def test_resolves_company_context(self, tmp_path: Path) -> None:
        root = tmp_path / "artifacts"
        (root / "company_context").mkdir(parents=True)
        (root / "company_context" / "ramp.md").write_text("# Ramp context")
        resolved = resolve_artifacts("ramp", root)
        assert resolved["company_context_path"] is not None
        assert resolved["company_context_path"].endswith("ramp.md")

    def test_ignores_draft_company_context(self, tmp_path: Path) -> None:
        root = tmp_path / "artifacts"
        (root / "company_context").mkdir(parents=True)
        (root / "company_context" / "ramp.draft.md").write_text("draft")
        resolved = resolve_artifacts("ramp", root)
        assert resolved["company_context_path"] is None

    def test_resolves_personas(self, tmp_path: Path) -> None:
        root = tmp_path / "artifacts"
        root.mkdir(parents=True, exist_ok=True)
        _write_persona_storage(root, "ramp", "persona-icp", content="# ICP")
        _write_persona_storage(root, "ramp", "persona-cfo", content="# CFO")
        resolved = resolve_artifacts("ramp", root)
        assert len(resolved["persona_paths"]) == 2

    def test_ignores_inactive_personas(self, tmp_path: Path) -> None:
        root = tmp_path / "artifacts"
        root.mkdir(parents=True, exist_ok=True)
        _write_persona_storage(root, "ramp", "persona-icp", content="# ICP", status="fresh")
        _write_persona_storage(root, "ramp", "persona-old", content="# Old", status="archived")
        resolved = resolve_artifacts("ramp", root)
        assert len(resolved["persona_paths"]) == 1

    def test_ignores_other_company_personas(self, tmp_path: Path) -> None:
        root = tmp_path / "artifacts"
        root.mkdir(parents=True, exist_ok=True)
        _write_persona_storage(root, "ramp", "persona-icp", content="# ICP")
        _write_persona_storage(root, "carta", "persona-icp", content="# Carta ICP")
        resolved = resolve_artifacts("ramp", root)
        assert len(resolved["persona_paths"]) == 1

    def test_resolves_style_guide(self, tmp_path: Path) -> None:
        root = tmp_path / "artifacts"
        (root / "style_guides").mkdir(parents=True)
        (root / "style_guides" / "ramp.md").write_text("# Style")
        resolved = resolve_artifacts("ramp", root)
        assert resolved["style_guide_path"] is not None

    def test_ignores_draft_style_guide(self, tmp_path: Path) -> None:
        root = tmp_path / "artifacts"
        (root / "style_guides").mkdir(parents=True)
        (root / "style_guides" / "ramp.draft.md").write_text("draft")
        resolved = resolve_artifacts("ramp", root)
        assert resolved["style_guide_path"] is None

    def test_resolves_all_artifacts(self, tmp_path: Path) -> None:
        root = tmp_path / "artifacts"
        (root / "company_context").mkdir(parents=True)
        (root / "style_guides").mkdir(parents=True)
        (root / "company_context" / "ramp.md").write_text("# Context")
        _write_persona_storage(root, "ramp", "persona-icp", content="# ICP")
        (root / "style_guides" / "ramp.md").write_text("# Style")
        resolved = resolve_artifacts("ramp", root)
        assert resolved["company_context_path"] is not None
        assert len(resolved["persona_paths"]) == 1
        assert resolved["style_guide_path"] is not None


class TestRunGapPipelineTask:
    @pytest.mark.asyncio
    async def test_successful_run_updates_status(
        self, task_store: TaskStore, event_bus: EventBus,
        gap_request, mock_report: GapReport, empty_artifacts: Path,
    ) -> None:
        task = task_store.create_task("gap_analysis", "ramp")
        with patch(
            "api.tasks.runner.run_gap_analysis",
            new_callable=AsyncMock,
            return_value=mock_report,
        ):
            await run_gap_pipeline_task(
                task_id=task.task_id,
                request=gap_request,
                artifacts_root=empty_artifacts,
                task_store=task_store,
                event_bus=event_bus,
            )

        updated = task_store.get_task(task.task_id)
        assert updated.status == TaskStatus.COMPLETED
        assert updated.result is not None
        assert updated.result["report_json"]["executive_summary"] == "test"
        assert updated.result["produced_artifacts"] == [
            {"type": "gap_analysis", "slug": "ramp"},
        ]

    @pytest.mark.asyncio
    async def test_result_includes_resolved_artifacts(
        self, task_store: TaskStore, event_bus: EventBus,
        gap_request, mock_report: GapReport, empty_artifacts: Path,
    ) -> None:
        task = task_store.create_task("gap_analysis", "ramp")
        with patch(
            "api.tasks.runner.run_gap_analysis",
            new_callable=AsyncMock,
            return_value=mock_report,
        ):
            await run_gap_pipeline_task(
                task_id=task.task_id,
                request=gap_request,
                artifacts_root=empty_artifacts,
                task_store=task_store,
                event_bus=event_bus,
            )

        updated = task_store.get_task(task.task_id)
        assert "resolved_artifacts" in updated.result
        resolved = updated.result["resolved_artifacts"]
        assert resolved["company_context_path"] is None
        assert resolved["persona_paths"] == []
        assert resolved["style_guide_path"] is None

    @pytest.mark.asyncio
    async def test_resolves_existing_artifacts(
        self, task_store: TaskStore, event_bus: EventBus,
        gap_request, mock_report: GapReport, tmp_path: Path,
    ) -> None:
        # Set up artifacts on disk
        root = tmp_path / "test_artifacts"
        (root / "company_context").mkdir(parents=True)
        (root / "company_context" / "ramp.md").write_text("# Ramp")
        _write_persona_storage(root, "ramp", "persona-icp", content="# ICP")

        task = task_store.create_task("gap_analysis", "ramp")
        with patch(
            "api.tasks.runner.run_gap_analysis",
            new_callable=AsyncMock,
            return_value=mock_report,
        ):
            await run_gap_pipeline_task(
                task_id=task.task_id,
                request=gap_request,
                artifacts_root=root,
                task_store=task_store,
                event_bus=event_bus,
            )

        updated = task_store.get_task(task.task_id)
        resolved = updated.result["resolved_artifacts"]
        assert resolved["company_context_path"] is not None
        assert len(resolved["persona_paths"]) == 1
        assert resolved["style_guide_path"] is None

    @pytest.mark.asyncio
    async def test_failed_run_updates_status(
        self, task_store: TaskStore, event_bus: EventBus,
        gap_request, empty_artifacts: Path,
    ) -> None:
        task = task_store.create_task("gap_analysis", "ramp")
        with patch(
            "api.tasks.runner.run_gap_analysis",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Pipeline exploded"),
        ):
            await run_gap_pipeline_task(
                task_id=task.task_id,
                request=gap_request,
                artifacts_root=empty_artifacts,
                task_store=task_store,
                event_bus=event_bus,
            )

        updated = task_store.get_task(task.task_id)
        assert updated.status == TaskStatus.FAILED
        assert "Pipeline exploded" in updated.error

    @pytest.mark.asyncio
    async def test_publishes_pipeline_start_event(
        self, task_store: TaskStore, event_bus: EventBus,
        gap_request, mock_report: GapReport, empty_artifacts: Path,
    ) -> None:
        task = task_store.create_task("gap_analysis", "ramp")
        with patch(
            "api.tasks.runner.run_gap_analysis",
            new_callable=AsyncMock,
            return_value=mock_report,
        ):
            await run_gap_pipeline_task(
                task_id=task.task_id,
                request=gap_request,
                artifacts_root=empty_artifacts,
                task_store=task_store,
                event_bus=event_bus,
            )

        history = event_bus.get_history(task.task_id)
        types = [e["type"] for e in history]
        assert "pipeline_start" in types
        assert "completed" in types

    @pytest.mark.asyncio
    async def test_publishes_failed_event_on_error(
        self, task_store: TaskStore, event_bus: EventBus,
        gap_request, empty_artifacts: Path,
    ) -> None:
        task = task_store.create_task("gap_analysis", "ramp")
        with patch(
            "api.tasks.runner.run_gap_analysis",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ):
            await run_gap_pipeline_task(
                task_id=task.task_id,
                request=gap_request,
                artifacts_root=empty_artifacts,
                task_store=task_store,
                event_bus=event_bus,
            )

        history = event_bus.get_history(task.task_id)
        types = [e["type"] for e in history]
        assert "pipeline_start" in types
        assert "failed" in types

    @pytest.mark.asyncio
    async def test_releases_slug_lock_on_success(
        self, task_store: TaskStore, event_bus: EventBus,
        gap_request, mock_report: GapReport, empty_artifacts: Path,
    ) -> None:
        task = task_store.create_task("gap_analysis", "ramp")
        with patch(
            "api.tasks.runner.run_gap_analysis",
            new_callable=AsyncMock,
            return_value=mock_report,
        ):
            await run_gap_pipeline_task(
                task_id=task.task_id,
                request=gap_request,
                artifacts_root=empty_artifacts,
                task_store=task_store,
                event_bus=event_bus,
            )

        task2 = task_store.create_task("gap_analysis", "ramp")
        assert task2.task_id != task.task_id

    @pytest.mark.asyncio
    async def test_releases_slug_lock_on_failure(
        self, task_store: TaskStore, event_bus: EventBus,
        gap_request, empty_artifacts: Path,
    ) -> None:
        task = task_store.create_task("gap_analysis", "ramp")
        with patch(
            "api.tasks.runner.run_gap_analysis",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ):
            await run_gap_pipeline_task(
                task_id=task.task_id,
                request=gap_request,
                artifacts_root=empty_artifacts,
                task_store=task_store,
                event_bus=event_bus,
            )

        task2 = task_store.create_task("gap_analysis", "ramp")
        assert task2.task_id != task.task_id

    @pytest.mark.asyncio
    async def test_skip_steps_forwarded_to_pipeline(
        self, task_store: TaskStore, event_bus: EventBus,
        mock_report: GapReport, empty_artifacts: Path,
    ) -> None:
        request = SimpleNamespace(
            company_name="Ramp",
            domain="ramp.com",
            seed_urls=[],
            skip_steps=[1, 2, 3],
            max_queries=150,
            platforms=["perplexity", "openai", "gemini", "claude"],
            language="en",
            region=None,
            additional_constraints=None,
            max_crawl_pages=None,
            max_crawl_depth=None,
        )
        task = task_store.create_task("gap_analysis", "ramp")
        with patch(
            "api.tasks.runner.run_gap_analysis",
            new_callable=AsyncMock,
            return_value=mock_report,
        ) as mock_fn:
            await run_gap_pipeline_task(
                task_id=task.task_id,
                request=request,
                artifacts_root=empty_artifacts,
                task_store=task_store,
                event_bus=event_bus,
            )

        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["skip_steps"] == [1, 2, 3]


# ---------------------------------------------------------------------------
# C1: resolve_artifacts uses configured StorageBackend (not hardcoded local)
# ---------------------------------------------------------------------------


class TestResolveArtifactsWithNonLocalBackend:
    """C1: When a non-LocalStorageBackend is passed, resolve_artifacts
    returns logical keys (not absolute filesystem paths)."""

    def test_returns_keys_for_nonlocal_backend(self, tmp_path: Path) -> None:
        """Non-local backend returns logical keys, not absolute paths."""
        from unittest.mock import MagicMock

        mock_backend = MagicMock()
        mock_backend.exists.side_effect = lambda key: key == "company_context/ramp.md"

        resolved = resolve_artifacts("ramp", tmp_path, backend=mock_backend)
        # Should be a logical key, not an absolute path
        assert resolved["company_context_path"] == "company_context/ramp.md"
        assert not resolved["company_context_path"].startswith("/")

    def test_returns_absolute_paths_for_local_backend(self, tmp_path: Path) -> None:
        """LocalStorageBackend returns absolute filesystem paths (backward compat)."""
        root = tmp_path / "artifacts"
        (root / "company_context").mkdir(parents=True)
        (root / "company_context" / "ramp.md").write_text("# Context")
        resolved = resolve_artifacts("ramp", root)
        assert resolved["company_context_path"].startswith("/")


class TestGapRunnerUsesFactoryBackend:
    """C1: run_gap_pipeline_task uses get_storage_backend() for resolve_artifacts."""

    @pytest.mark.asyncio
    async def test_gap_runner_passes_factory_backend_to_resolve(
        self, task_store: TaskStore, event_bus: EventBus,
        gap_request, mock_report: GapReport, empty_artifacts: Path,
    ) -> None:
        from unittest.mock import MagicMock, call

        task = task_store.create_task("gap_analysis", "ramp")
        mock_backend = MagicMock()
        mock_backend.exists.return_value = False

        with patch(
            "api.tasks.runner.run_gap_analysis",
            new_callable=AsyncMock,
            return_value=mock_report,
        ), patch(
            "core.storage.get_storage_backend",
            return_value=mock_backend,
        ) as mock_gsb, patch(
            "api.tasks.runner.resolve_artifacts",
            wraps=resolve_artifacts,
        ) as mock_resolve:
            await run_gap_pipeline_task(
                task_id=task.task_id,
                request=gap_request,
                artifacts_root=empty_artifacts,
                task_store=task_store,
                event_bus=event_bus,
            )

        # Verify factory was called
        mock_gsb.assert_called_once_with(empty_artifacts)
        # Verify resolve_artifacts received the factory backend
        mock_resolve.assert_called_once()
        call_kwargs = mock_resolve.call_args
        assert call_kwargs.kwargs.get("backend") is mock_backend
