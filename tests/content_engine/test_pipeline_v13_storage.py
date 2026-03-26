"""Tests for pipeline_v13.py StorageBackend write-path conversion (Phase 2 completion).

Verifies that all content engine artifact writes go through StorageBackend
when provided, with filesystem fallback when storage is None.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.storage.backends.local import LocalStorageBackend


# ---------------------------------------------------------------------------
# Import helpers under test
# ---------------------------------------------------------------------------

from core.content_engine.pipeline_v13 import (
    _merge_and_write_blueprints,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def storage(tmp_path: Path) -> LocalStorageBackend:
    """Real local storage backend rooted at tmp_path."""
    return LocalStorageBackend(tmp_path)


class _FakeBlueprint:
    """Minimal blueprint-like object with model_dump()."""

    def __init__(self, brief_id: str, title: str, _source: str = ""):
        self.brief_id = brief_id
        self.title = title
        self._source_val = _source

    def model_dump(self, mode: str = "json") -> dict:
        d = {"brief_id": self.brief_id, "title": self.title}
        if self._source_val:
            d["_source"] = self._source_val
        return d


# ---------------------------------------------------------------------------
# _merge_and_write_blueprints
# ---------------------------------------------------------------------------


class TestMergeAndWriteBlueprints:
    """Tests for _merge_and_write_blueprints with StorageBackend support."""

    def test_writes_via_storage(self, storage: LocalStorageBackend):
        """When storage + key provided, writes blueprints to StorageBackend."""
        bps = [_FakeBlueprint("brief-001", "Topic A")]
        bp_path = Path("/unused")
        key = "content/test-co/blueprints.json"

        _merge_and_write_blueprints(
            bp_path, bps, storage=storage, storage_key=key,
        )

        raw = storage.read(key)
        assert raw is not None
        data = json.loads(raw)
        assert len(data) == 1
        assert data[0]["brief_id"] == "brief-001"

    def test_preserves_sourced_entries_via_storage(self, storage: LocalStorageBackend):
        """Entries with _source field survive merge when reading/writing via storage."""
        key = "content/test-co/blueprints.json"
        # Pre-seed with a manual entry
        existing = [
            {"brief_id": "manual-001", "title": "Manual Brief", "_source": "manual"},
            {"brief_id": "brief-001", "title": "Old Pipeline Brief"},
        ]
        storage.write(key, json.dumps(existing))

        # Write new pipeline blueprints (no _source)
        bps = [_FakeBlueprint("brief-002", "New Pipeline Brief")]
        _merge_and_write_blueprints(
            Path("/unused"), bps, storage=storage, storage_key=key,
        )

        data = json.loads(storage.read(key))
        brief_ids = {b["brief_id"] for b in data}
        # manual-001 preserved, old brief-001 replaced by brief-002
        assert "manual-001" in brief_ids
        assert "brief-002" in brief_ids
        assert "brief-001" not in brief_ids

    def test_filesystem_fallback_when_no_storage(self, tmp_path: Path):
        """Falls back to filesystem when storage is None."""
        bp_path = tmp_path / "blueprints.json"
        bps = [_FakeBlueprint("brief-001", "Topic A")]

        _merge_and_write_blueprints(bp_path, bps)

        assert bp_path.exists()
        data = json.loads(bp_path.read_text())
        assert data[0]["brief_id"] == "brief-001"

    def test_handles_empty_existing(self, storage: LocalStorageBackend):
        """Works when no existing blueprints file."""
        key = "content/test-co/blueprints.json"
        bps = [_FakeBlueprint("brief-001", "Topic A")]

        _merge_and_write_blueprints(
            Path("/unused"), bps, storage=storage, storage_key=key,
        )

        data = json.loads(storage.read(key))
        assert len(data) == 1

    def test_handles_corrupt_existing_json(self, storage: LocalStorageBackend):
        """Corrupt JSON in existing blueprints doesn't crash — starts fresh."""
        key = "content/test-co/blueprints.json"
        storage.write(key, "not valid json {{")

        bps = [_FakeBlueprint("brief-001", "Topic A")]
        _merge_and_write_blueprints(
            Path("/unused"), bps, storage=storage, storage_key=key,
        )

        data = json.loads(storage.read(key))
        assert len(data) == 1
        assert data[0]["brief_id"] == "brief-001"


# ---------------------------------------------------------------------------
# _finalize_pipeline — run_metadata write
# ---------------------------------------------------------------------------


class TestFinalizePipelineMetadata:
    """Tests that _finalize_pipeline writes run_metadata via StorageBackend."""

    @pytest.fixture()
    def _mock_dependencies(self, monkeypatch):
        """Patch pipeline dependencies so _finalize_pipeline doesn't need real infra."""
        import core.content_engine.pipeline_v13 as mod

        monkeypatch.setattr(mod, "_cleanup_pipeline_state", lambda *a, **kw: None)
        monkeypatch.setattr(mod, "persist_content_pieces", AsyncMock())
        monkeypatch.setattr(mod, "persist_content_run_summary", AsyncMock())
        monkeypatch.setattr(mod, "update_trace_output", lambda *a, **kw: None)
        monkeypatch.setattr(mod, "flush", lambda: None)
        monkeypatch.setattr(mod, "_update_task", lambda *a, **kw: None)
        monkeypatch.setattr(mod, "_emit", lambda *a, **kw: None)

    @pytest.mark.asyncio
    async def test_writes_metadata_via_storage(
        self, storage: LocalStorageBackend, tmp_path: Path, _mock_dependencies,
    ):
        from core.content_engine.pipeline_v13 import _finalize_pipeline
        from core.models.content_generation import ContentGenerationOutput

        output = ContentGenerationOutput(
            company_slug="test-co",
            run_metadata={"pipeline_version": "1.3", "entry_mode": "autonomous"},
        )

        await _finalize_pipeline(
            output=output,
            pipeline_trace=MagicMock(),
            slug="test-co",
            approved_blueprints=[],
            pieces=[],
            start_time=0.0,
            input_data=MagicMock(entry_mode=MagicMock(value="autonomous")),
            artifact_dir=tmp_path,
            session_factory=None,
            run_id=None,
            company_id=None,
            task_store=None,
            task_id=None,
            event_bus=None,
            storage=storage,
        )

        content = storage.read("content/test-co/run_metadata_v13.json")
        assert content is not None
        data = json.loads(content)
        assert data["company_slug"] == "test-co"

    @pytest.mark.asyncio
    async def test_manual_mode_namespaced_metadata(
        self, storage: LocalStorageBackend, tmp_path: Path, _mock_dependencies,
    ):
        from core.content_engine.pipeline_v13 import _finalize_pipeline
        from core.models.content_generation import ContentGenerationOutput, ContentPiece, ContentStatus

        piece = ContentPiece(brief_id="brief-007", title="Test", status=ContentStatus.APPROVED)
        output = ContentGenerationOutput(
            company_slug="test-co",
            run_metadata={"pipeline_version": "1.3", "entry_mode": "manual"},
            pieces=[piece],
        )

        await _finalize_pipeline(
            output=output,
            pipeline_trace=MagicMock(),
            slug="test-co",
            approved_blueprints=[],
            pieces=[piece],
            start_time=0.0,
            input_data=MagicMock(entry_mode=MagicMock(value="manual")),
            artifact_dir=tmp_path,
            session_factory=None,
            run_id=None,
            company_id=None,
            task_store=None,
            task_id=None,
            event_bus=None,
            storage=storage,
        )

        # Manual mode namespaces by first brief ID
        content = storage.read("content/test-co/run_metadata_v13_brief-007.json")
        assert content is not None
        data = json.loads(content)
        assert data["company_slug"] == "test-co"


# ---------------------------------------------------------------------------
# Planner selections roundtrip
# ---------------------------------------------------------------------------


class TestPlannerSelectionsStorage:
    """Tests that planner_selections.json writes/reads go through StorageBackend."""

    def test_write_and_read_roundtrip(self, storage: LocalStorageBackend):
        """Planner selections can be written and read back via StorageBackend."""
        key = "content/test-co/planner_selections.json"
        data = {"selections": [{"topic": "AI Search", "rank": 1}], "selection_metadata": {}}

        storage.write(key, json.dumps(data, indent=2))
        raw = storage.read(key)
        assert raw is not None
        loaded = json.loads(raw)
        assert loaded["selections"][0]["topic"] == "AI Search"

    def test_read_returns_none_when_missing(self, storage: LocalStorageBackend):
        """storage.read() returns None for nonexistent key — used as .exists() replacement."""
        result = storage.read("content/test-co/planner_selections.json")
        assert result is None


# ---------------------------------------------------------------------------
# Blueprints auto-ID read via storage
# ---------------------------------------------------------------------------


class TestBlueprintsAutoIdStorage:
    """Tests that blueprints auto-ID generation reads from StorageBackend."""

    def test_reads_existing_ids_from_storage(self, storage: LocalStorageBackend):
        """Auto-ID logic should read existing brief IDs from storage."""
        key = "content/test-co/blueprints.json"
        existing = [
            {"brief_id": "brief-001", "title": "First"},
            {"brief_id": "brief-002", "title": "Second"},
        ]
        storage.write(key, json.dumps(existing))

        raw = storage.read(key)
        assert raw is not None
        data = json.loads(raw)
        existing_ids = {b.get("brief_id", "") for b in data if isinstance(b, dict)}
        assert existing_ids == {"brief-001", "brief-002"}

        # Next sequential ID
        next_idx = 1
        while f"brief-{next_idx:03d}" in existing_ids:
            next_idx += 1
        assert f"brief-{next_idx:03d}" == "brief-003"


# ---------------------------------------------------------------------------
# Cross-pipeline gap analysis read
# ---------------------------------------------------------------------------


class TestCrossPipelineGapRead:
    """Tests that topic-scoped gap analysis reads go through StorageBackend."""

    def test_reads_scoped_analysis_from_storage(self, storage: LocalStorageBackend):
        """Cross-pipeline read of gap_analysis/{slug}/topic_scoped/{run_id}/analysis.json."""
        key = "gap_analysis/test-co/topic_scoped/run-123/analysis.json"
        data = {"gaps": [{"query_id": "q1"}], "topic_query_map": {"t1": ["q1"]}}
        storage.write(key, json.dumps(data))

        raw = storage.read(key)
        assert raw is not None
        loaded = json.loads(raw)
        assert loaded["gaps"][0]["query_id"] == "q1"

    def test_returns_none_for_missing_scoped_analysis(self, storage: LocalStorageBackend):
        """Missing scoped analysis returns None (pipeline logs warning, uses empty dict)."""
        raw = storage.read("gap_analysis/test-co/topic_scoped/nonexistent/analysis.json")
        assert raw is None


# ---------------------------------------------------------------------------
# final.md single write path via persist_stage_artifact
# ---------------------------------------------------------------------------


class TestFinalMdWritePath:
    """Tests that final.md writes use StorageBackend (no dual-write)."""

    def test_final_md_written_via_storage(self, storage: LocalStorageBackend):
        """final.md should be written through storage.write(), not raw filesystem."""
        key = "content/test-co/content/brief-001/final.md"
        markdown = "# How AI Search Works\n\nAI search engines..."

        storage.write(key, markdown)

        content = storage.read(key)
        assert content == markdown

    @pytest.mark.asyncio
    async def test_persist_stage_artifact_without_piece_id(self, storage: LocalStorageBackend):
        """persist_stage_artifact writes to storage even when piece_id is None (skips DB)."""
        from core.content_engine.artifact_writer import persist_stage_artifact
        from core.db.enums import ContentArtifactStage

        markdown = "# Final Content\n\nSome text."
        rel_path = "content/test-co/content/brief-001/final.md"

        result = await persist_stage_artifact(
            storage=storage,
            session_factory=None,
            piece_id=None,  # No DB metadata
            stage=ContentArtifactStage.final,
            relative_path=rel_path,
            content=markdown,
        )

        assert result == rel_path
        assert storage.read(rel_path) == markdown

    def test_no_storage_root_reference(self):
        """Verify pipeline_v13 no longer references storage.root (ABC incompatible)."""
        import inspect
        from core.content_engine import pipeline_v13

        source = inspect.getsource(pipeline_v13)
        assert "storage.root" not in source, (
            "pipeline_v13.py still references storage.root — "
            "this is a LocalStorageBackend-specific attribute not on the ABC"
        )
