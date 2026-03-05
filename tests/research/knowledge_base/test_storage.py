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
        assert len(all_latest) == 5  # L2_DOC_TYPES only (excludes synthesis)
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

    def test_populates_dependencies_from_dag(self, storage: KBStorage) -> None:
        """write_version populates dependencies from KB_DEPENDENCY_GRAPH."""
        storage.write_version(KBDocType.COMPETITOR_REGISTRY, "# Competitors v1")
        m = storage.read_manifest()
        assert m.documents["competitor_registry"].dependencies == [
            KBDocType.COMPANY_OVERVIEW
        ]

    def test_populates_staleness_days_from_constant(self, storage: KBStorage) -> None:
        """write_version populates staleness_days from KB_DEFAULT_STALENESS_DAYS."""
        storage.write_version(KBDocType.CUSTOMER_REVIEWS, "# Reviews")
        m = storage.read_manifest()
        assert m.documents["customer_reviews"].staleness_days == 30


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


# ---------------------------------------------------------------------------
# Dependency Population
# ---------------------------------------------------------------------------


class TestDependencyPopulation:
    def test_root_docs_get_empty_dependencies(self, storage: KBStorage) -> None:
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "overview")
        m = storage.read_manifest()
        assert m.documents["company_overview"].dependencies == []

    def test_weakness_gets_dag_dependencies(self, storage: KBStorage) -> None:
        storage.write_version(KBDocType.WEAKNESS_ANALYSIS, "weakness")
        m = storage.read_manifest()
        deps = m.documents["weakness_analysis"].dependencies
        assert KBDocType.COMPANY_OVERVIEW in deps
        assert KBDocType.COMPETITOR_REGISTRY in deps

    def test_overwrite_replaces_with_dag_deps(self, storage: KBStorage) -> None:
        """Even if manifest had wrong deps, write_version always uses DAG."""
        # Pre-seed with wrong deps
        m = KBManifest(
            slug="test-co",
            documents={
                "brand_perception": KBDocEntry(
                    doc_type=KBDocType.BRAND_PERCEPTION,
                    current_version=1,
                    dependencies=[],  # wrong
                )
            },
        )
        storage.write_manifest(m)
        # Write creates v2 dir needed on disk
        (storage.base_dir / "brand_perception").mkdir(parents=True, exist_ok=True)

        storage.write_version(KBDocType.BRAND_PERCEPTION, "brand v2")
        m2 = storage.read_manifest()
        deps = m2.documents["brand_perception"].dependencies
        assert KBDocType.COMPANY_OVERVIEW in deps
        assert KBDocType.CUSTOMER_REVIEWS in deps
        assert KBDocType.COMPETITOR_REGISTRY in deps


# ---------------------------------------------------------------------------
# Staleness Report
# ---------------------------------------------------------------------------


def _backdate_doc(storage: KBStorage, dt: KBDocType, days_ago: int) -> None:
    """Helper: backdate a doc's last_updated in the manifest."""
    m = storage.read_manifest()
    entry = m.documents.get(dt.value)
    if entry:
        entry.last_updated = datetime.now(timezone.utc) - timedelta(days=days_ago)
    storage.write_manifest(m)


def _backdate_synthesis(storage: KBStorage, days_ago: int) -> None:
    """Helper: backdate synthesis_last_updated in the manifest."""
    m = storage.read_manifest()
    m.synthesis_last_updated = datetime.now(timezone.utc) - timedelta(days=days_ago)
    storage.write_manifest(m)


class TestStalenessReport:
    def test_empty_kb_all_missing(self, storage: KBStorage) -> None:
        report = storage.get_staleness_report()
        assert report.overall_score == 0.0
        assert len(report.missing_docs) == 5
        assert report.stale_docs == []

    def test_all_fresh_score_100(self, storage: KBStorage) -> None:
        for dt in [
            KBDocType.COMPANY_OVERVIEW,
            KBDocType.CUSTOMER_REVIEWS,
            KBDocType.COMPETITOR_REGISTRY,
            KBDocType.WEAKNESS_ANALYSIS,
            KBDocType.BRAND_PERCEPTION,
        ]:
            storage.write_version(dt, f"# {dt.value}")
        storage.write_synthesis("# Profile")

        report = storage.get_staleness_report()
        assert report.overall_score == 100.0
        assert report.stale_docs == []
        assert report.missing_docs == []
        assert report.synthesis_needs_refresh is False

    def test_per_doc_threshold_used(self, storage: KBStorage) -> None:
        """customer_reviews threshold=30, company_overview=90.
        Both backdated 35 days: reviews stale, overview fresh."""
        storage.write_version(KBDocType.CUSTOMER_REVIEWS, "reviews")
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "overview")
        _backdate_doc(storage, KBDocType.CUSTOMER_REVIEWS, 35)
        _backdate_doc(storage, KBDocType.COMPANY_OVERVIEW, 35)

        report = storage.get_staleness_report()
        assert report.doc_health["customer_reviews"].status == "stale"
        assert report.doc_health["customer_reviews"].stale_reason == "age_exceeded"
        assert report.doc_health["company_overview"].status == "fresh"

    def test_threshold_override(self, storage: KBStorage) -> None:
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "overview")
        _backdate_doc(storage, KBDocType.COMPANY_OVERVIEW, 15)

        # Default threshold=90 → fresh
        report_default = storage.get_staleness_report()
        assert report_default.doc_health["company_overview"].status == "fresh"

        # Override threshold=10 → stale
        report_override = storage.get_staleness_report(threshold_override=10)
        assert report_override.doc_health["company_overview"].status == "stale"

    def test_upstream_change_marks_downstream_stale(self, storage: KBStorage) -> None:
        """If company_overview is newer than competitor_registry,
        competitor_registry should show stale_reason=upstream_changed."""
        storage.write_version(KBDocType.COMPETITOR_REGISTRY, "competitors")
        _backdate_doc(storage, KBDocType.COMPETITOR_REGISTRY, 5)
        # Now write a fresh overview (newer than competitor)
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "overview refreshed")

        report = storage.get_staleness_report()
        cr_health = report.doc_health["competitor_registry"]
        assert cr_health.status == "stale"
        assert cr_health.stale_reason == "upstream_changed"

    def test_synthesis_needs_refresh_when_doc_newer(self, storage: KBStorage) -> None:
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "overview")
        storage.write_synthesis("# Profile")
        _backdate_synthesis(storage, 2)
        # Overview is newer than synthesis now
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "overview v2")

        report = storage.get_staleness_report()
        assert report.synthesis_needs_refresh is True

    def test_synthesis_fresh_when_no_changes(self, storage: KBStorage) -> None:
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "overview")
        storage.write_synthesis("# Profile")

        report = storage.get_staleness_report()
        assert report.synthesis_needs_refresh is False


# ---------------------------------------------------------------------------
# Propagate Staleness
# ---------------------------------------------------------------------------


class TestPropagateStaleness:
    def test_propagate_marks_downstream_stale(self, storage: KBStorage) -> None:
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "overview")
        storage.write_version(KBDocType.COMPETITOR_REGISTRY, "competitors")
        storage.write_version(KBDocType.WEAKNESS_ANALYSIS, "weakness")

        marked = storage.propagate_staleness([KBDocType.COMPANY_OVERVIEW])
        marked_values = [dt.value for dt in marked]
        assert "competitor_registry" in marked_values
        assert "weakness_analysis" in marked_values

    def test_propagate_no_crash_on_missing_docs(self, storage: KBStorage) -> None:
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "overview")
        # competitor_registry not written — should not crash
        marked = storage.propagate_staleness([KBDocType.COMPANY_OVERVIEW])
        # Only existing docs that are downstream
        assert all(
            dt in [KBDocType.COMPETITOR_REGISTRY, KBDocType.WEAKNESS_ANALYSIS, KBDocType.BRAND_PERCEPTION]
            for dt in marked
        )

    def test_propagate_returns_affected_docs(self, storage: KBStorage) -> None:
        storage.write_version(KBDocType.CUSTOMER_REVIEWS, "reviews")
        storage.write_version(KBDocType.BRAND_PERCEPTION, "brand")

        marked = storage.propagate_staleness([KBDocType.CUSTOMER_REVIEWS])
        assert KBDocType.BRAND_PERCEPTION in marked

    def test_propagate_cascades_through_dag(self, storage: KBStorage) -> None:
        """Refreshing overview cascades: overview → competitor → weakness + brand."""
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "overview")
        storage.write_version(KBDocType.COMPETITOR_REGISTRY, "competitors")
        storage.write_version(KBDocType.WEAKNESS_ANALYSIS, "weakness")
        storage.write_version(KBDocType.BRAND_PERCEPTION, "brand")

        marked = storage.propagate_staleness([KBDocType.COMPANY_OVERVIEW])
        marked_values = {dt.value for dt in marked}
        # All three downstream should be marked
        assert "competitor_registry" in marked_values
        assert "weakness_analysis" in marked_values
        assert "brand_perception" in marked_values

    def test_propagate_empty_list_noop(self, storage: KBStorage) -> None:
        marked = storage.propagate_staleness([])
        assert marked == []


# ---------------------------------------------------------------------------
# Changed Since Synthesis
# ---------------------------------------------------------------------------


class TestChangedSinceSynthesis:
    def test_no_changes_returns_empty(self, storage: KBStorage) -> None:
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "overview")
        storage.write_synthesis("# Profile")

        changed = storage.get_changed_since_synthesis()
        assert changed == []

    def test_one_doc_changed_returns_it(self, storage: KBStorage) -> None:
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "overview")
        storage.write_synthesis("# Profile")
        _backdate_synthesis(storage, 2)
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "overview v2")

        changed = storage.get_changed_since_synthesis()
        assert KBDocType.COMPANY_OVERVIEW in changed

    def test_no_synthesis_returns_all_existing(self, storage: KBStorage) -> None:
        storage.write_version(KBDocType.COMPANY_OVERVIEW, "overview")
        storage.write_version(KBDocType.CUSTOMER_REVIEWS, "reviews")

        changed = storage.get_changed_since_synthesis()
        assert KBDocType.COMPANY_OVERVIEW in changed
        assert KBDocType.CUSTOMER_REVIEWS in changed
        assert len(changed) == 2
