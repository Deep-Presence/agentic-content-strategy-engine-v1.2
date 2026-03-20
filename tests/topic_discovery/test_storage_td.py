"""Tests for TopicDiscoveryStorage (filesystem).

Covers: manifest CRUD, versioning auto-increment, atomic writes, read missing,
corrupted JSON handling, version detection edge cases.
"""
from __future__ import annotations

import json

import pytest

from core.models.topic_discovery import (
    CaptureRecaptureResult,
    SourceResult,
    SubdomainCandidate,
    SubdomainNode,
    TaxonomyTree,
    TDSource,
    TopicAssignment,
    TopicAssignmentMatrix,
    TopicDiscoveryManifest,
    TopicDiscoveryStatus,
)
from core.topic_discovery.storage import TopicDiscoveryStorage


@pytest.fixture
def storage(tmp_path) -> TopicDiscoveryStorage:
    return TopicDiscoveryStorage(artifacts_root=tmp_path, slug="test-co")


# ── Manifest ─────────────────────────────────────────────────────────────


class TestManifest:
    def test_read_manifest_returns_blank_when_missing(self, storage):
        m = storage.read_manifest()
        assert isinstance(m, TopicDiscoveryManifest)
        assert m.slug == "test-co"
        assert m.taxonomy_version == 0

    def test_write_then_read_manifest(self, storage):
        m = TopicDiscoveryManifest(
            slug="test-co",
            company_name="Test Co",
            domain_name="test.com",
            taxonomy_version=2,
            matrix_version=1,
            status=TopicDiscoveryStatus.approved,
        )
        storage.write_manifest(m)
        restored = storage.read_manifest()
        assert restored.company_name == "Test Co"
        assert restored.taxonomy_version == 2
        assert restored.status == TopicDiscoveryStatus.approved

    def test_write_manifest_creates_directory(self, storage):
        assert not storage.base_dir.exists()
        storage.write_manifest(TopicDiscoveryManifest(slug="test-co"))
        assert storage.base_dir.exists()
        assert (storage.base_dir / "_manifest.json").exists()

    def test_corrupted_manifest_returns_blank(self, storage):
        storage.base_dir.mkdir(parents=True, exist_ok=True)
        (storage.base_dir / "_manifest.json").write_text("NOT JSON")
        m = storage.read_manifest()
        assert m.slug == "test-co"
        assert m.taxonomy_version == 0


# ── Source Results ───────────────────────────────────────────────────────


class TestSourceResults:
    def test_write_and_read_source_result(self, storage):
        result = SourceResult(
            source=TDSource.source_a,
            candidates=[
                SubdomainCandidate(name="expense mgmt", source=TDSource.source_a),
            ],
            total_rounds=3,
            singletons=1,
        )
        storage.write_source_result(TDSource.source_a, result, version=1)
        restored = storage.read_source_result(TDSource.source_a, version=1)
        assert restored is not None
        assert len(restored.candidates) == 1
        assert restored.candidates[0].name == "expense mgmt"

    def test_read_missing_source_result_returns_none(self, storage):
        assert storage.read_source_result(TDSource.source_b, version=1) is None

    def test_multiple_sources_coexist(self, storage):
        for src in TDSource:
            result = SourceResult(source=src, total_rounds=1)
            storage.write_source_result(src, result, version=1)
        for src in TDSource:
            restored = storage.read_source_result(src, version=1)
            assert restored is not None
            assert restored.source == src

    def test_corrupted_source_result_returns_none(self, storage):
        raw_dir = storage.base_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / "source_a_v1.json").write_text("{bad json")
        assert storage.read_source_result(TDSource.source_a, version=1) is None


# ── Coverage ─────────────────────────────────────────────────────────────


class TestCoverage:
    def test_write_and_read_coverage(self, storage):
        metrics = CaptureRecaptureResult(
            pairwise_estimates={"a_b": 112.0},
            median_estimate=112.0,
            sample_coverage=0.94,
            observed_count=100,
            aggregate_sample_coverage=0.94,
            aggregate_chao1_ratio=0.85,
        )
        storage.write_coverage(metrics, version=1)
        restored = storage.read_coverage(version=1)
        assert restored is not None
        assert restored.median_estimate == 112.0
        assert restored.aggregate_sample_coverage == 0.94

    def test_read_missing_coverage_returns_none(self, storage):
        assert storage.read_coverage(version=1) is None


# ── Taxonomy ─────────────────────────────────────────────────────────────


class TestTaxonomy:
    def test_write_and_read_taxonomy(self, storage, sample_taxonomy):
        v = storage.write_taxonomy(sample_taxonomy, version=1)
        assert v == 1
        restored = storage.read_taxonomy(version=1)
        assert restored is not None
        assert restored.domain_name == "fintech"
        assert len(restored.root_nodes) == 2

    def test_auto_increment_version(self, storage, sample_taxonomy):
        v1 = storage.write_taxonomy(sample_taxonomy)
        assert v1 == 1
        v2 = storage.write_taxonomy(sample_taxonomy)
        assert v2 == 2

    def test_get_latest_taxonomy_version_empty_dir(self, storage):
        assert storage.get_latest_taxonomy_version() == 0

    def test_get_latest_taxonomy_version_no_dir(self, storage):
        assert storage.get_latest_taxonomy_version() == 0

    def test_get_latest_taxonomy_version_multiple(self, storage, sample_taxonomy):
        storage.write_taxonomy(sample_taxonomy, version=1)
        storage.write_taxonomy(sample_taxonomy, version=3)
        storage.write_taxonomy(sample_taxonomy, version=2)
        assert storage.get_latest_taxonomy_version() == 3

    def test_get_latest_taxonomy(self, storage, sample_taxonomy):
        storage.write_taxonomy(sample_taxonomy, version=1)
        t2 = TaxonomyTree(domain_name="fintech-v2", version=2)
        storage.write_taxonomy(t2, version=2)
        latest = storage.get_latest_taxonomy()
        assert latest is not None
        assert latest.domain_name == "fintech-v2"

    def test_get_latest_taxonomy_none(self, storage):
        assert storage.get_latest_taxonomy() is None

    def test_read_missing_taxonomy_returns_none(self, storage):
        assert storage.read_taxonomy(version=99) is None

    def test_nested_nodes_survive_roundtrip(self, storage, sample_taxonomy):
        storage.write_taxonomy(sample_taxonomy, version=1)
        restored = storage.read_taxonomy(version=1)
        expense = restored.root_nodes[0]
        assert len(expense.children) == 2
        assert expense.children[0].name == "Receipt Scanning"

    def test_corrupted_taxonomy_returns_none(self, storage):
        tax_dir = storage.base_dir / "taxonomy"
        tax_dir.mkdir(parents=True, exist_ok=True)
        (tax_dir / "v1.json").write_text("CORRUPT")
        assert storage.read_taxonomy(version=1) is None

    def test_version_detection_ignores_non_version_files(self, storage, sample_taxonomy):
        storage.write_taxonomy(sample_taxonomy, version=1)
        tax_dir = storage.base_dir / "taxonomy"
        (tax_dir / "notes.json").write_text("{}")
        (tax_dir / "v_bad.json").write_text("{}")
        assert storage.get_latest_taxonomy_version() == 1

    def test_auto_increment_syncs_taxonomy_version(self, storage, sample_taxonomy):
        """M4: Auto-incremented filename version must match JSON payload version."""
        storage.write_taxonomy(sample_taxonomy)  # v1
        v2 = storage.write_taxonomy(sample_taxonomy)  # v2
        assert v2 == 2
        restored = storage.read_taxonomy(version=2)
        assert restored is not None
        assert restored.version == 2  # Must match filename, not original

    def test_explicit_version_syncs_taxonomy(self, storage, sample_taxonomy):
        """M4: Explicit version=5 must be written into JSON payload."""
        storage.write_taxonomy(sample_taxonomy, version=5)
        restored = storage.read_taxonomy(version=5)
        assert restored is not None
        assert restored.version == 5

    def test_write_taxonomy_does_not_mutate_original(self, storage, sample_taxonomy):
        """M4: model_copy must not mutate the original object."""
        original_version = sample_taxonomy.version
        storage.write_taxonomy(sample_taxonomy, version=99)
        assert sample_taxonomy.version == original_version


# ── Matrix ───────────────────────────────────────────────────────────────


class TestMatrix:
    def test_write_and_read_matrix(self, storage, sample_matrix):
        v = storage.write_matrix(sample_matrix, version=1)
        assert v == 1
        restored = storage.read_matrix(version=1)
        assert restored is not None
        assert len(restored.assignments) == 2

    def test_auto_increment_version(self, storage, sample_matrix):
        v1 = storage.write_matrix(sample_matrix)
        assert v1 == 1
        v2 = storage.write_matrix(sample_matrix)
        assert v2 == 2

    def test_get_latest_matrix_version_empty(self, storage):
        assert storage.get_latest_matrix_version() == 0

    def test_get_latest_matrix(self, storage, sample_matrix):
        storage.write_matrix(sample_matrix, version=1)
        latest = storage.get_latest_matrix()
        assert latest is not None
        assert latest.version == 1

    def test_get_latest_matrix_none(self, storage):
        assert storage.get_latest_matrix() is None

    def test_read_missing_matrix_returns_none(self, storage):
        assert storage.read_matrix(version=99) is None

    def test_corrupted_matrix_returns_none(self, storage):
        mat_dir = storage.base_dir / "matrix"
        mat_dir.mkdir(parents=True, exist_ok=True)
        (mat_dir / "v1.json").write_text("NOT JSON")
        assert storage.read_matrix(version=1) is None

    def test_auto_increment_syncs_matrix_version(self, storage, sample_matrix):
        """M4: Auto-incremented filename version must match JSON payload version."""
        storage.write_matrix(sample_matrix)  # v1
        v2 = storage.write_matrix(sample_matrix)  # v2
        assert v2 == 2
        restored = storage.read_matrix(version=2)
        assert restored is not None
        assert restored.version == 2

    def test_explicit_version_syncs_matrix(self, storage, sample_matrix):
        """M4: Explicit version=3 must be written into JSON payload."""
        storage.write_matrix(sample_matrix, version=3)
        restored = storage.read_matrix(version=3)
        assert restored is not None
        assert restored.version == 3


# ── Properties ───────────────────────────────────────────────────────────


class TestProperties:
    def test_base_dir(self, storage, tmp_path):
        assert storage.base_dir == tmp_path / "topic_discovery" / "test-co"

    def test_slug(self, storage):
        assert storage.slug == "test-co"


# ── Atomic Write ─────────────────────────────────────────────────────────


class TestAtomicWrite:
    """Atomicity is now handled by the StorageBackend (LocalStorageBackend).

    These tests verify the same semantics via backend write operations.
    """

    def test_creates_parent_directories(self, storage, tmp_path):
        """Writing to a nested path creates parent directories automatically."""
        storage._backend.write("a/b/c/file.json", '{"ok": true}')
        deep_path = tmp_path / "a" / "b" / "c" / "file.json"
        assert deep_path.exists()
        assert json.loads(deep_path.read_text()) == {"ok": True}

    def test_overwrites_existing_file(self, storage, tmp_path):
        storage._backend.write("file.json", '{"v": 1}')
        storage._backend.write("file.json", '{"v": 2}')
        path = tmp_path / "file.json"
        assert json.loads(path.read_text()) == {"v": 2}


# ── M7: Slug path traversal guard ───────────────────────────────────────


class TestM7SlugValidation:
    """M7: Storage must reject slugs that could escape the artifacts root."""

    def test_slug_path_traversal_rejected(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid slug"):
            TopicDiscoveryStorage(tmp_path, "../../../etc")

    def test_slug_dots_rejected(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid slug"):
            TopicDiscoveryStorage(tmp_path, "test.co")

    def test_slug_spaces_rejected(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid slug"):
            TopicDiscoveryStorage(tmp_path, "test co")

    def test_slug_empty_rejected(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid slug"):
            TopicDiscoveryStorage(tmp_path, "")

    def test_slug_slashes_rejected(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid slug"):
            TopicDiscoveryStorage(tmp_path, "test/co")

    def test_slug_effective_slug_accepted(self, tmp_path):
        s = TopicDiscoveryStorage(tmp_path, "test-co__product")
        assert s.slug == "test-co__product"

    def test_slug_bare_slug_accepted(self, tmp_path):
        s = TopicDiscoveryStorage(tmp_path, "test-co")
        assert s.slug == "test-co"


# ── M5: Repository query safety ─────────────────────────────────────────


class TestM5RepositoryQuerySafety:
    """M5: get_by_effective_slug uses scalars().first() + ORDER BY, not scalar_one_or_none()."""

    def test_get_by_effective_slug_uses_scalars_first(self):
        """Verify the method uses .scalars().first() instead of .scalar_one_or_none()."""
        import inspect
        from core.topic_discovery.repository import TopicDiscoveryRepository
        source = inspect.getsource(TopicDiscoveryRepository.get_by_effective_slug)
        assert "scalars().first()" in source
        assert "scalar_one_or_none" not in source

    def test_get_by_effective_slug_orders_by_created_at(self):
        """Verify the query orders by created_at DESC to get latest."""
        import inspect
        from core.topic_discovery.repository import TopicDiscoveryRepository
        source = inspect.getsource(TopicDiscoveryRepository.get_by_effective_slug)
        assert "created_at.desc()" in source
