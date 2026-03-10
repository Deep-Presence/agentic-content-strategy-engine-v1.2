"""Tests for PersonaStorage — manifest, brief, version, staleness."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.models.audience_persona import (
    PersonaBrief,
    PersonaManifest,
    PersonaProfileEntry,
)
from core.research.audience_persona.storage import PersonaStorage


@pytest.fixture()
def storage(tmp_path: Path) -> PersonaStorage:
    return PersonaStorage(artifacts_root=tmp_path, slug="test-co")


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


class TestManifestCRUD:
    def test_read_returns_blank_when_no_file(self, storage: PersonaStorage) -> None:
        m = storage.read_manifest()
        assert m.slug == "test-co"
        assert m.personas == {}

    def test_write_then_read_roundtrip(self, storage: PersonaStorage) -> None:
        m = PersonaManifest(
            slug="test-co",
            company_name="Test Co",
            kb_synthesis_version=2,
        )
        storage.write_manifest(m)
        loaded = storage.read_manifest()
        assert loaded.slug == "test-co"
        assert loaded.company_name == "Test Co"
        assert loaded.kb_synthesis_version == 2

    def test_manifest_creates_directory(self, storage: PersonaStorage) -> None:
        assert not storage.base_dir.exists()
        storage.write_manifest(PersonaManifest(slug="test-co"))
        assert storage.base_dir.exists()
        assert (storage.base_dir / "_manifest.json").exists()

    def test_corrupt_manifest_returns_blank(self, storage: PersonaStorage) -> None:
        storage.base_dir.mkdir(parents=True, exist_ok=True)
        (storage.base_dir / "_manifest.json").write_text("NOT JSON", encoding="utf-8")
        m = storage.read_manifest()
        assert m.slug == "test-co"
        assert m.personas == {}

    def test_atomic_write_leaves_no_temp(self, storage: PersonaStorage) -> None:
        storage.write_manifest(PersonaManifest(slug="test-co"))
        temps = list(storage.base_dir.glob("_manifest_*.tmp"))
        assert temps == []


# ---------------------------------------------------------------------------
# Brief persistence
# ---------------------------------------------------------------------------


class TestBriefPersistence:
    def test_write_and_read_brief(self, storage: PersonaStorage) -> None:
        brief = PersonaBrief(
            brief_id="pb-001",
            persona_name="Sarah",
            tagline="VP of Finance",
            description="Manages finances.",
            rationale=["Evidence 1"],
            source="agent",
        )
        storage.write_brief("vp-finance", brief)
        loaded = storage.read_brief("vp-finance")
        assert loaded is not None
        assert loaded.brief_id == "pb-001"
        assert loaded.persona_name == "Sarah"
        assert loaded.source == "agent"

    def test_read_brief_missing_returns_none(self, storage: PersonaStorage) -> None:
        assert storage.read_brief("nonexistent") is None

    def test_brief_file_location(self, storage: PersonaStorage) -> None:
        storage.write_brief("vp-finance", PersonaBrief(brief_id="pb-001"))
        path = storage.base_dir / "vp-finance" / "brief.json"
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["brief_id"] == "pb-001"


# ---------------------------------------------------------------------------
# Version writes
# ---------------------------------------------------------------------------


class TestWriteVersion:
    def test_first_version_is_1(self, storage: PersonaStorage) -> None:
        v = storage.write_version(
            "vp-finance", "Sarah", "# Persona: Sarah\nProfile content."
        )
        assert v == 1

    def test_increments_version(self, storage: PersonaStorage) -> None:
        storage.write_version("vp-finance", "Sarah", "v1 content")
        v2 = storage.write_version("vp-finance", "Sarah", "v2 content")
        assert v2 == 2

    def test_writes_md_file(self, storage: PersonaStorage) -> None:
        storage.write_version("vp-finance", "Sarah", "# Persona: Sarah")
        md = storage.base_dir / "vp-finance" / "v1.md"
        assert md.exists()
        assert md.read_text(encoding="utf-8") == "# Persona: Sarah"

    def test_writes_json_sidecar(self, storage: PersonaStorage) -> None:
        storage.write_version(
            "vp-finance", "Sarah", "# Sarah",
            content_json={"sections": {"summary": "text"}},
        )
        json_path = storage.base_dir / "vp-finance" / "v1.json"
        assert json_path.exists()
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["sections"]["summary"] == "text"

    def test_no_json_sidecar_when_none(self, storage: PersonaStorage) -> None:
        storage.write_version("vp-finance", "Sarah", "content")
        json_path = storage.base_dir / "vp-finance" / "v1.json"
        assert not json_path.exists()

    def test_updates_manifest_entry(self, storage: PersonaStorage) -> None:
        storage.write_version(
            "vp-finance", "Sarah", "# Persona: Sarah\nContent here.",
            kind="icp", created_by="agent", tagline="VP of Finance",
        )
        m = storage.read_manifest()
        entry = m.personas["vp-finance"]
        assert entry.persona_id == "vp-finance"
        assert entry.persona_name == "Sarah"
        assert entry.kind == "icp"
        assert entry.current_version == 1
        assert entry.status == "fresh"
        assert entry.word_count > 0
        assert entry.sha256 != ""
        assert entry.tagline == "VP of Finance"

    def test_multiple_personas(self, storage: PersonaStorage) -> None:
        storage.write_version("vp-finance", "Sarah", "Sarah content", kind="icp")
        storage.write_version("head-ops", "Marcus", "Marcus content", kind="secondary")
        m = storage.read_manifest()
        assert len(m.personas) == 2
        assert m.personas["vp-finance"].kind == "icp"
        assert m.personas["head-ops"].kind == "secondary"

    def test_pending_review_status(self, storage: PersonaStorage) -> None:
        storage.write_version(
            "manual-persona", "Jane", "Jane content",
            status="pending_review", created_by="manual",
        )
        m = storage.read_manifest()
        assert m.personas["manual-persona"].status == "pending_review"
        assert m.personas["manual-persona"].created_by == "manual"


# ---------------------------------------------------------------------------
# Read versions
# ---------------------------------------------------------------------------


class TestReadVersion:
    def test_read_existing_version(self, storage: PersonaStorage) -> None:
        storage.write_version("vp-finance", "Sarah", "Profile content here.")
        result = storage.read_version("vp-finance", 1)
        assert result is not None
        assert result["version"] == 1
        assert result["content_md"] == "Profile content here."
        assert result["word_count"] == 3
        assert result["sha256"] != ""

    def test_read_nonexistent_version_returns_none(self, storage: PersonaStorage) -> None:
        assert storage.read_version("vp-finance", 99) is None

    def test_read_with_json_sidecar(self, storage: PersonaStorage) -> None:
        storage.write_version(
            "vp-finance", "Sarah", "content",
            content_json={"key": "value"},
        )
        result = storage.read_version("vp-finance", 1)
        assert result is not None
        assert result["content_json"] == {"key": "value"}

    def test_read_without_json_sidecar(self, storage: PersonaStorage) -> None:
        storage.write_version("vp-finance", "Sarah", "content")
        result = storage.read_version("vp-finance", 1)
        assert result is not None
        assert result["content_json"] is None

    def test_get_latest_version(self, storage: PersonaStorage) -> None:
        storage.write_version("vp-finance", "Sarah", "v1")
        storage.write_version("vp-finance", "Sarah", "v2 updated")
        latest = storage.get_latest_version("vp-finance")
        assert latest is not None
        assert latest["version"] == 2
        assert latest["content_md"] == "v2 updated"

    def test_get_latest_version_missing_returns_none(self, storage: PersonaStorage) -> None:
        assert storage.get_latest_version("nonexistent") is None

    def test_get_all_latest(self, storage: PersonaStorage) -> None:
        storage.write_version("vp-finance", "Sarah", "Sarah v1", kind="icp")
        storage.write_version("head-ops", "Marcus", "Marcus v1")
        storage.write_version("vp-finance", "Sarah", "Sarah v2", kind="icp")

        all_latest = storage.get_all_latest()
        assert len(all_latest) == 2
        assert all_latest["vp-finance"]["version"] == 2
        assert all_latest["head-ops"]["version"] == 1


# ---------------------------------------------------------------------------
# List / query helpers
# ---------------------------------------------------------------------------


class TestListHelpers:
    def test_list_persona_ids_empty(self, storage: PersonaStorage) -> None:
        assert storage.list_persona_ids() == []

    def test_list_persona_ids(self, storage: PersonaStorage) -> None:
        storage.write_version("vp-finance", "Sarah", "content")
        storage.write_version("head-ops", "Marcus", "content")
        ids = storage.list_persona_ids()
        assert set(ids) == {"vp-finance", "head-ops"}

    def test_list_active_excludes_archived(self, storage: PersonaStorage) -> None:
        storage.write_version("vp-finance", "Sarah", "content", status="fresh")
        storage.write_version("old-persona", "Old", "content", status="archived")
        active = storage.list_active_persona_ids()
        assert "vp-finance" in active
        assert "old-persona" not in active

    def test_list_active_includes_pending_review(self, storage: PersonaStorage) -> None:
        storage.write_version("manual", "Jane", "content", status="pending_review")
        active = storage.list_active_persona_ids()
        assert "manual" in active

    def test_list_persona_paths(self, storage: PersonaStorage) -> None:
        storage.write_version("vp-finance", "Sarah", "content", status="fresh")
        storage.write_version("archived", "Old", "content", status="archived")
        paths = storage.list_persona_paths()
        assert len(paths) == 1
        assert "vp-finance" in paths[0]
        assert paths[0].endswith("v1.md")

    def test_list_persona_paths_excludes_pending_review(self, storage: PersonaStorage) -> None:
        storage.write_version("pending", "Jane", "content", status="pending_review")
        paths = storage.list_persona_paths()
        assert len(paths) == 0


# ---------------------------------------------------------------------------
# Staleness
# ---------------------------------------------------------------------------


class TestStaleness:
    def test_missing_persona_is_stale(self, storage: PersonaStorage) -> None:
        assert storage.check_staleness("nonexistent") is True

    def test_fresh_persona_not_stale(self, storage: PersonaStorage) -> None:
        storage.write_version("vp-finance", "Sarah", "content")
        assert storage.check_staleness("vp-finance", threshold_days=60) is False

    def test_old_persona_is_stale(self, storage: PersonaStorage) -> None:
        storage.write_version("vp-finance", "Sarah", "content")
        # Backdate the manifest entry
        m = storage.read_manifest()
        m.personas["vp-finance"].last_updated = datetime.now(timezone.utc) - timedelta(days=100)
        storage.write_manifest(m)
        assert storage.check_staleness("vp-finance", threshold_days=60) is True

    def test_kb_staleness_no_version_recorded(self, storage: PersonaStorage) -> None:
        storage.write_manifest(PersonaManifest(slug="test-co"))
        assert storage.check_kb_staleness(kb_synthesis_version=1) is True

    def test_kb_staleness_behind(self, storage: PersonaStorage) -> None:
        m = PersonaManifest(slug="test-co", kb_synthesis_version=2)
        storage.write_manifest(m)
        assert storage.check_kb_staleness(kb_synthesis_version=3) is True

    def test_kb_staleness_current(self, storage: PersonaStorage) -> None:
        m = PersonaManifest(slug="test-co", kb_synthesis_version=3)
        storage.write_manifest(m)
        assert storage.check_kb_staleness(kb_synthesis_version=3) is False

    def test_kb_staleness_ahead(self, storage: PersonaStorage) -> None:
        m = PersonaManifest(slug="test-co", kb_synthesis_version=5)
        storage.write_manifest(m)
        assert storage.check_kb_staleness(kb_synthesis_version=3) is False


# ---------------------------------------------------------------------------
# Mark persona status
# ---------------------------------------------------------------------------


class TestMarkPersonaStatus:
    def test_mark_archived(self, storage: PersonaStorage) -> None:
        storage.write_version("vp-finance", "Sarah", "content", status="fresh")
        storage.mark_persona_status("vp-finance", "archived")
        m = storage.read_manifest()
        assert m.personas["vp-finance"].status == "archived"

    def test_mark_fresh_from_pending(self, storage: PersonaStorage) -> None:
        storage.write_version("manual", "Jane", "content", status="pending_review")
        storage.mark_persona_status("manual", "fresh")
        m = storage.read_manifest()
        assert m.personas["manual"].status == "fresh"

    def test_mark_nonexistent_is_noop(self, storage: PersonaStorage) -> None:
        storage.mark_persona_status("nonexistent", "archived")
        m = storage.read_manifest()
        assert "nonexistent" not in m.personas


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestStorageProperties:
    def test_base_dir(self, tmp_path: Path) -> None:
        s = PersonaStorage(artifacts_root=tmp_path, slug="ramp")
        assert s.base_dir == tmp_path / "audience_personas" / "ramp"

    def test_slug(self, tmp_path: Path) -> None:
        s = PersonaStorage(artifacts_root=tmp_path, slug="ramp")
        assert s.slug == "ramp"
