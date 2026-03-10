"""Tests for VoiceStyleGuideStorage — manifest, versioning, promotion.

Phase B of the Voice Style Guide pipeline.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.models.voice_style_guide import (
    AuthorBrief,
    AuthorEntry,
    VoiceStyleGuideManifest,
    WorkPersonaMapping,
)
from core.research.voice_style_guide.storage import VoiceStyleGuideStorage


@pytest.fixture()
def storage(tmp_path: Path) -> VoiceStyleGuideStorage:
    return VoiceStyleGuideStorage(tmp_path, "ramp")


@pytest.fixture()
def sample_brief() -> AuthorBrief:
    return AuthorBrief(
        author_id="ann-handley",
        name="Ann Handley",
        description="Marketing content pioneer",
        famous_works=["Everybody Writes"],
        resonance_rationale="B2B authority",
        work_persona_mapping=[
            WorkPersonaMapping(
                work_title="Everybody Writes",
                persona_id="vp-marketing",
                persona_name="Sarah",
                relevance="Practical content advice",
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Manifest CRUD
# ---------------------------------------------------------------------------


class TestManifestCRUD:
    def test_read_missing_returns_blank(self, storage: VoiceStyleGuideStorage):
        m = storage.read_manifest()
        assert m.slug == "ramp"
        assert m.authors == {}
        assert m.guide.current_version == 0

    def test_write_then_read(self, storage: VoiceStyleGuideStorage):
        m = VoiceStyleGuideManifest(
            slug="ramp", company_name="Ramp",
            created_at=datetime.now(timezone.utc),
        )
        storage.write_manifest(m)
        m2 = storage.read_manifest()
        assert m2.slug == "ramp"
        assert m2.company_name == "Ramp"

    def test_atomic_write_creates_dir(self, storage: VoiceStyleGuideStorage):
        assert not storage.base_dir.exists()
        storage.write_manifest(VoiceStyleGuideManifest(slug="ramp"))
        assert storage.base_dir.exists()
        assert (storage.base_dir / "_manifest.json").exists()

    def test_overwrite_manifest(self, storage: VoiceStyleGuideStorage):
        m1 = VoiceStyleGuideManifest(slug="ramp", company_name="Ramp v1")
        storage.write_manifest(m1)
        m2 = VoiceStyleGuideManifest(slug="ramp", company_name="Ramp v2")
        storage.write_manifest(m2)
        m3 = storage.read_manifest()
        assert m3.company_name == "Ramp v2"

    def test_corrupted_manifest_returns_blank(self, storage: VoiceStyleGuideStorage):
        storage.base_dir.mkdir(parents=True, exist_ok=True)
        (storage.base_dir / "_manifest.json").write_text("not json", encoding="utf-8")
        m = storage.read_manifest()
        assert m.slug == "ramp"


# ---------------------------------------------------------------------------
# Discovery artifact
# ---------------------------------------------------------------------------


class TestDiscovery:
    def test_write_and_read_discovery(
        self, storage: VoiceStyleGuideStorage, sample_brief: AuthorBrief,
    ):
        briefs = [sample_brief]
        version = storage.write_discovery(briefs)
        assert version == 1

        loaded = storage.read_discovery(1)
        assert len(loaded) == 1
        assert loaded[0].author_id == "ann-handley"

    def test_discovery_versioning(
        self, storage: VoiceStyleGuideStorage, sample_brief: AuthorBrief,
    ):
        v1 = storage.write_discovery([sample_brief])
        assert v1 == 1

        brief2 = AuthorBrief(author_id="paul-graham", name="Paul Graham")
        v2 = storage.write_discovery([sample_brief, brief2])
        assert v2 == 2

        loaded_v2 = storage.read_discovery(2)
        assert len(loaded_v2) == 2

    def test_read_missing_discovery_returns_empty(
        self, storage: VoiceStyleGuideStorage,
    ):
        loaded = storage.read_discovery(99)
        assert loaded == []


# ---------------------------------------------------------------------------
# Author brief persistence
# ---------------------------------------------------------------------------


class TestAuthorBrief_:
    def test_write_and_read_brief(
        self, storage: VoiceStyleGuideStorage, sample_brief: AuthorBrief,
    ):
        storage.write_author_brief("ann-handley", sample_brief)
        loaded = storage.read_author_brief("ann-handley")
        assert loaded is not None
        assert loaded.name == "Ann Handley"
        assert len(loaded.work_persona_mapping) == 1

    def test_read_missing_brief(self, storage: VoiceStyleGuideStorage):
        assert storage.read_author_brief("nonexistent") is None


# ---------------------------------------------------------------------------
# Author research versioning
# ---------------------------------------------------------------------------


class TestAuthorResearch:
    def test_write_first_version(self, storage: VoiceStyleGuideStorage):
        v = storage.write_author_research(
            "ann-handley", "Ann Handley", "# Ann Handley\n\nResearch content...",
        )
        assert v == 1

        m = storage.read_manifest()
        entry = m.authors["ann-handley"]
        assert entry.current_version == 1
        assert entry.status == "fresh"
        assert entry.word_count > 0
        assert entry.sha256 != ""

    def test_write_second_version(self, storage: VoiceStyleGuideStorage):
        storage.write_author_research("ann-handley", "Ann Handley", "v1 content")
        v2 = storage.write_author_research("ann-handley", "Ann Handley", "v2 content updated")
        assert v2 == 2

        m = storage.read_manifest()
        assert m.authors["ann-handley"].current_version == 2

    def test_read_specific_version(self, storage: VoiceStyleGuideStorage):
        storage.write_author_research("ann-handley", "Ann Handley", "version one")
        storage.write_author_research("ann-handley", "Ann Handley", "version two")

        md = storage.read_author_research("ann-handley", 1)
        assert md == "version one"

        md2 = storage.read_author_research("ann-handley", 2)
        assert md2 == "version two"

    def test_read_missing_version(self, storage: VoiceStyleGuideStorage):
        assert storage.read_author_research("ann-handley", 1) is None

    def test_get_latest_author_research(self, storage: VoiceStyleGuideStorage):
        storage.write_author_research("ann-handley", "Ann Handley", "v1")
        storage.write_author_research("ann-handley", "Ann Handley", "v2 latest")

        md = storage.get_latest_author_research("ann-handley")
        assert md == "v2 latest"

    def test_get_latest_missing_author(self, storage: VoiceStyleGuideStorage):
        assert storage.get_latest_author_research("nonexistent") is None

    def test_multiple_authors(self, storage: VoiceStyleGuideStorage):
        storage.write_author_research("author-a", "Author A", "content A")
        storage.write_author_research("author-b", "Author B", "content B")

        m = storage.read_manifest()
        assert len(m.authors) == 2
        assert m.authors["author-a"].name == "Author A"
        assert m.authors["author-b"].name == "Author B"


# ---------------------------------------------------------------------------
# Guide versioning
# ---------------------------------------------------------------------------


class TestGuide:
    def test_write_guide(self, storage: VoiceStyleGuideStorage):
        authors = ["ann-handley", "paul-graham"]
        v = storage.write_guide("# Voice Style Guide\n\nContent...", source_authors=authors)
        assert v == 1

        m = storage.read_manifest()
        assert m.guide.current_version == 1
        assert m.guide.status == "fresh"
        assert m.guide.source_authors == authors
        assert m.guide.word_count > 0

    def test_guide_versioning(self, storage: VoiceStyleGuideStorage):
        storage.write_guide("v1 guide")
        v2 = storage.write_guide("v2 guide updated")
        assert v2 == 2

    def test_get_latest_guide(self, storage: VoiceStyleGuideStorage):
        storage.write_guide("v1 guide")
        storage.write_guide("v2 guide latest")
        md = storage.get_latest_guide()
        assert md == "v2 guide latest"

    def test_get_latest_guide_missing(self, storage: VoiceStyleGuideStorage):
        assert storage.get_latest_guide() is None


# ---------------------------------------------------------------------------
# Promotion to style_guides/
# ---------------------------------------------------------------------------


class TestPromotion:
    def test_promote_to_style_guides(self, storage: VoiceStyleGuideStorage, tmp_path: Path):
        storage.write_guide("# Final Voice Guide\n\nContent here.")
        path = storage.promote_to_style_guides(tmp_path)

        assert path is not None
        assert Path(path).exists()
        assert Path(path).name == "ramp.md"
        content = Path(path).read_text(encoding="utf-8")
        assert "Final Voice Guide" in content

    def test_promote_no_guide_returns_none(self, storage: VoiceStyleGuideStorage, tmp_path: Path):
        path = storage.promote_to_style_guides(tmp_path)
        assert path is None

    def test_promote_overwrites_existing(self, storage: VoiceStyleGuideStorage, tmp_path: Path):
        # Write old style guide
        sg_dir = tmp_path / "style_guides"
        sg_dir.mkdir(parents=True)
        (sg_dir / "ramp.md").write_text("old guide", encoding="utf-8")

        storage.write_guide("new guide from VSG pipeline")
        storage.promote_to_style_guides(tmp_path)

        content = (sg_dir / "ramp.md").read_text(encoding="utf-8")
        assert content == "new guide from VSG pipeline"


# ---------------------------------------------------------------------------
# List / query helpers
# ---------------------------------------------------------------------------


class TestListHelpers:
    def test_list_author_ids_empty(self, storage: VoiceStyleGuideStorage):
        assert storage.list_author_ids() == []

    def test_list_author_ids(self, storage: VoiceStyleGuideStorage):
        storage.write_author_research("a", "Author A", "content")
        storage.write_author_research("b", "Author B", "content")
        ids = storage.list_author_ids()
        assert set(ids) == {"a", "b"}

    def test_list_active_author_ids(self, storage: VoiceStyleGuideStorage):
        storage.write_author_research("a", "Author A", "content")
        storage.write_author_research("b", "Author B", "content")

        # Archive one
        m = storage.read_manifest()
        m.authors["b"].status = "archived"
        storage.write_manifest(m)

        active = storage.list_active_author_ids()
        assert active == ["a"]

    def test_properties(self, storage: VoiceStyleGuideStorage):
        assert storage.slug == "ramp"
        assert "voice_style_guide" in str(storage.base_dir)
        assert "ramp" in str(storage.base_dir)
