"""Tests for KBStorage — filesystem CRUD, versioning, staleness, synthesis."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.models.knowledge_base import (
    KBDocEntry,
    KBDocType,
    KBManifest,
)
from core.research.knowledge_base.storage import KBStorage


@pytest.fixture()
def storage(tmp_path: Path) -> KBStorage:
    """KBStorage rooted in a temporary directory."""
    return KBStorage(artifacts_root=tmp_path / "artifacts", slug="test-co")


# ---------------------------------------------------------------------------
# Manifest basics
# ---------------------------------------------------------------------------


class TestManifest:
    def test_read_missing_returns_blank(self, storage: KBStorage) -> None:
        m = storage.read_manifest()
        assert m.slug == "test-co"
        assert m.documents == {}

    def test_write_then_read(self, storage: KBStorage) -> None:
        m = KBManifest(slug="test-co", company_name="Test Co")
        storage.write_manifest(m)
        m2 = storage.read_manifest()
        assert m2.slug == "test-co"
        assert m2.company_name == "Test Co"

    def test_write_creates_dirs(self, storage: KBStorage) -> None:
        m = KBManifest(slug="test-co")
        storage.write_manifest(m)
        assert storage.base_dir.exists()
        assert (storage.base_dir / "_manifest.json").exists()

    def test_corrupt_manifest_returns_blank(self, storage: KBStorage) -> None:
        storage.base_dir.mkdir(parents=True, exist_ok=True)
        (storage.base_dir / "_manifest.json").write_text("NOT JSON", encoding="utf-8")
        m = storage.read_manifest()
        assert m.slug == "test-co"
        assert m.documents == {}


# ---------------------------------------------------------------------------
# write_version + read_version
# ---------------------------------------------------------------------------


class TestVersioning:
    def test_write_first_version(self, storage: KBStorage) -> None:
        ver = storage.write_version(KBDocType.COMPANY_OVERVIEW, "# Overview\nGreat company.")
        assert ver == 1

        # Verify file on disk
        md_path = storage.base_dir / "company_overview" / "v1.md"
        assert md_path.exists()
        assert md_path.read_text(encoding="utf-8") == "# Overview\nGreat company."

    def test_write_increments_version(self, storage: KBStorage) -> None:
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "v1 content")
        ver = storage.write_version(KBDocType.COMPANY_OVERVIEW, "v2 content")
        assert ver == 2

        assert (storage.base_dir / "company_overview" / "v1.md").exists()
        assert (storage.base_dir / "company_overview" / "v2.md").exists()

    def test_write_with_json_sidecar(self, storage: KBStorage) -> None:
        storage.write_version(
            KBDocType.CUSTOMER_REVIEWS,
            "# Reviews",
            content_json={"reviews": [{"quote": "Great!"}]},
        )
        json_path = storage.base_dir / "customer_reviews" / "v1.json"
        assert json_path.exists()
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["reviews"][0]["quote"] == "Great!"

    def test_write_updates_manifest(self, storage: KBStorage) -> None:
        storage.write_version(KBDocType.COMPETITOR_REGISTRY, "# Competitors")
        m = storage.read_manifest()
        entry = m.documents["competitor_registry"]
        assert entry.current_version == 1
        assert entry.status == "fresh"
        assert entry.last_updated is not None

    def test_read_version(self, storage: KBStorage) -> None:
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "# Hello World")
        v = storage.read_version(KBDocType.COMPANY_OVERVIEW, 1)
        assert v is not None
        assert v.version == 1
        assert v.content_md == "# Hello World"
        assert v.word_count == 3
        assert len(v.sha256) == 64  # SHA-256 hex digest

    def test_read_version_with_json(self, storage: KBStorage) -> None:
        storage.write_version(
            KBDocType.WEAKNESS_ANALYSIS,
            "# Weaknesses",
            content_json={"per_competitor": {}},
        )
        v = storage.read_version(KBDocType.WEAKNESS_ANALYSIS, 1)
        assert v is not None
        assert v.content_json == {"per_competitor": {}}

    def test_read_missing_version_returns_none(self, storage: KBStorage) -> None:
        assert storage.read_version(KBDocType.COMPANY_OVERVIEW, 99) is None

    def test_get_latest_version(self, storage: KBStorage) -> None:
        storage.write_version(KBDocType.BRAND_PERCEPTION, "v1")
        storage.write_version(KBDocType.BRAND_PERCEPTION, "v2 updated")
        latest = storage.get_latest_version(KBDocType.BRAND_PERCEPTION)
        assert latest is not None
        assert latest.version == 2
        assert latest.content_md == "v2 updated"

    def test_get_latest_version_missing_returns_none(self, storage: KBStorage) -> None:
        assert storage.get_latest_version(KBDocType.COMPANY_OVERVIEW) is None

    def test_get_all_latest(self, storage: KBStorage) -> None:
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "overview")
        storage.write_version(KBDocType.CUSTOMER_REVIEWS, "reviews")
        all_latest = storage.get_all_latest()
        assert len(all_latest) == len(KBDocType)
        assert all_latest[KBDocType.COMPANY_OVERVIEW] is not None
        assert all_latest[KBDocType.CUSTOMER_REVIEWS] is not None
        assert all_latest[KBDocType.COMPETITOR_REGISTRY] is None

    def test_sha256_consistency(self, storage: KBStorage) -> None:
        content = "# Consistent Content"
        storage.write_version(KBDocType.COMPANY_OVERVIEW, content)
        v = storage.read_version(KBDocType.COMPANY_OVERVIEW, 1)
        assert v is not None
        import hashlib

        expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
        assert v.sha256 == expected

    def test_preserves_dependencies(self, storage: KBStorage) -> None:
        """write_version preserves dependencies from the existing entry."""
        # Pre-seed the manifest with a dependency
        m = KBManifest(
            slug="test-co",
            documents={
                "competitor_registry": KBDocEntry(
                    doc_type=KBDocType.COMPETITOR_REGISTRY,
                    dependencies=[KBDocType.COMPANY_OVERVIEW],
                )
            },
        )
        storage.write_manifest(m)

        storage.write_version(KBDocType.COMPETITOR_REGISTRY, "# Competitors v1")
        m2 = storage.read_manifest()
        assert m2.documents["competitor_registry"].dependencies == [
            KBDocType.COMPANY_OVERVIEW
        ]


# ---------------------------------------------------------------------------
# Staleness
# ---------------------------------------------------------------------------


class TestStaleness:
    def test_missing_doc_is_stale(self, storage: KBStorage) -> None:
        assert storage.check_staleness(KBDocType.COMPANY_OVERVIEW) is True

    def test_fresh_doc_not_stale(self, storage: KBStorage) -> None:
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "fresh content")
        assert storage.check_staleness(KBDocType.COMPANY_OVERVIEW, threshold_days=30) is False

    def test_old_doc_is_stale(self, storage: KBStorage) -> None:
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "old content")

        # Manually backdate the manifest entry
        m = storage.read_manifest()
        m.documents["company_overview"].last_updated = datetime.now(timezone.utc) - timedelta(
            days=60
        )
        storage.write_manifest(m)

        assert storage.check_staleness(KBDocType.COMPANY_OVERVIEW, threshold_days=30) is True

    def test_threshold_boundary(self, storage: KBStorage) -> None:
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "content")

        # Set exactly at threshold
        m = storage.read_manifest()
        m.documents["company_overview"].last_updated = datetime.now(timezone.utc) - timedelta(
            days=30
        )
        storage.write_manifest(m)

        # At exactly threshold_days → not stale (uses > not >=)
        assert storage.check_staleness(KBDocType.COMPANY_OVERVIEW, threshold_days=30) is False

    def test_null_last_updated_is_stale(self, storage: KBStorage) -> None:
        """Doc with version but no last_updated is stale."""
        m = KBManifest(
            slug="test-co",
            documents={
                "company_overview": KBDocEntry(
                    doc_type=KBDocType.COMPANY_OVERVIEW,
                    current_version=1,
                    status="fresh",
                    last_updated=None,
                )
            },
        )
        storage.write_manifest(m)
        assert storage.check_staleness(KBDocType.COMPANY_OVERVIEW) is True


# ---------------------------------------------------------------------------
# Synthesis (L3)
# ---------------------------------------------------------------------------


class TestSynthesis:
    def test_write_synthesis_first(self, storage: KBStorage) -> None:
        ver = storage.write_synthesis("# Company Profile\nSynthesized content.")
        assert ver == 1
        assert (storage.base_dir / "synthesis" / "v1.md").exists()

    def test_write_synthesis_increments(self, storage: KBStorage) -> None:
        storage.write_synthesis("v1 synthesis")
        ver = storage.write_synthesis("v2 synthesis")
        assert ver == 2

    def test_write_synthesis_updates_manifest(self, storage: KBStorage) -> None:
        storage.write_synthesis("synthesis content")
        m = storage.read_manifest()
        assert m.synthesis_version == 1
        assert m.synthesis_last_updated is not None

    def test_read_synthesis_latest(self, storage: KBStorage) -> None:
        storage.write_synthesis("v1")
        storage.write_synthesis("v2 final")
        v = storage.read_synthesis()
        assert v is not None
        assert v.version == 2
        assert v.content_md == "v2 final"

    def test_read_synthesis_specific_version(self, storage: KBStorage) -> None:
        storage.write_synthesis("v1 content")
        storage.write_synthesis("v2 content")
        v = storage.read_synthesis(version=1)
        assert v is not None
        assert v.content_md == "v1 content"

    def test_read_synthesis_missing_returns_none(self, storage: KBStorage) -> None:
        assert storage.read_synthesis() is None

    def test_read_synthesis_nonexistent_version_returns_none(
        self, storage: KBStorage
    ) -> None:
        storage.write_synthesis("v1")
        assert storage.read_synthesis(version=99) is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_multiple_doc_types_independent(self, storage: KBStorage) -> None:
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "overview")
        storage.write_version(KBDocType.CUSTOMER_REVIEWS, "reviews")
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "overview v2")

        m = storage.read_manifest()
        assert m.documents["company_overview"].current_version == 2
        assert m.documents["customer_reviews"].current_version == 1

    def test_empty_content(self, storage: KBStorage) -> None:
        ver = storage.write_version(KBDocType.COMPANY_OVERVIEW, "")
        assert ver == 1
        v = storage.read_version(KBDocType.COMPANY_OVERVIEW, 1)
        assert v is not None
        assert v.content_md == ""
        assert v.word_count == 0

    def test_slug_property(self, storage: KBStorage) -> None:
        assert storage.slug == "test-co"

    def test_base_dir_property(self, tmp_path: Path) -> None:
        s = KBStorage(artifacts_root=tmp_path / "art", slug="acme")
        assert s.base_dir == tmp_path / "art" / "knowledge_base" / "acme"
