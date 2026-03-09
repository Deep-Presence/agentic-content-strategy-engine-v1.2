"""Filesystem-backed storage for Topic Discovery artifacts.

Layout::

    artifacts/topic_discovery/{effective_slug}/
        _manifest.json
        taxonomy/v1.json
        matrix/v1.json
        raw/source_a_v1.json
        raw/source_b_v1.json
        raw/source_c_v1.json
        raw/source_d_v1.json
        raw/coverage_v1.json

Atomicity: version files are written first, manifest is updated last.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from core.models.topic_discovery import (
    CaptureRecaptureResult,
    SourceResult,
    TaxonomyTree,
    TDSource,
    TopicAssignmentMatrix,
    TopicDiscoveryManifest,
)

logger = logging.getLogger(__name__)


class TopicDiscoveryStorage:
    """Read / write / version topic discovery artifacts on the filesystem."""

    def __init__(self, artifacts_root: Path, slug: str) -> None:
        self._root = Path(artifacts_root) / "topic_discovery" / slug
        self._slug = slug

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        """Write content to *path* atomically via temp-file + os.replace."""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent), suffix=".tmp", prefix=path.stem + "_",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, str(path))
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def base_dir(self) -> Path:
        return self._root

    @property
    def slug(self) -> str:
        return self._slug

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------

    def _manifest_path(self) -> Path:
        return self._root / "_manifest.json"

    def read_manifest(self) -> TopicDiscoveryManifest:
        """Read the manifest, returning a blank one if it doesn't exist."""
        path = self._manifest_path()
        if not path.exists():
            return TopicDiscoveryManifest(slug=self._slug)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return TopicDiscoveryManifest.model_validate(data)
        except Exception as exc:
            logger.warning("Failed to read TD manifest at %s: %s", path, exc)
            return TopicDiscoveryManifest(slug=self._slug)

    def write_manifest(self, manifest: TopicDiscoveryManifest) -> None:
        """Persist the manifest to disk (atomic)."""
        self._root.mkdir(parents=True, exist_ok=True)
        self._atomic_write(
            self._manifest_path(), manifest.model_dump_json(indent=2)
        )

    # ------------------------------------------------------------------
    # Raw source results
    # ------------------------------------------------------------------

    def _raw_dir(self) -> Path:
        return self._root / "raw"

    def write_source_result(
        self, source: TDSource, result: SourceResult, version: int = 1
    ) -> None:
        """Write a raw source result artifact."""
        path = self._raw_dir() / f"{source.value}_v{version}.json"
        self._atomic_write(path, result.model_dump_json(indent=2))
        logger.info(
            "TD/%s: wrote %s v%d (%d candidates)",
            self._slug, source.value, version, len(result.candidates),
        )

    def read_source_result(
        self, source: TDSource, version: int = 1
    ) -> Optional[SourceResult]:
        """Read a raw source result. Returns None if missing or corrupt."""
        path = self._raw_dir() / f"{source.value}_v{version}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return SourceResult.model_validate(data)
        except Exception as exc:
            logger.warning("Failed to read source result %s v%d: %s", source.value, version, exc)
            return None

    # ------------------------------------------------------------------
    # Coverage metrics
    # ------------------------------------------------------------------

    def write_coverage(
        self, metrics: CaptureRecaptureResult, version: int = 1
    ) -> None:
        """Write coverage metrics."""
        path = self._raw_dir() / f"coverage_v{version}.json"
        self._atomic_write(path, metrics.model_dump_json(indent=2))

    def read_coverage(self, version: int = 1) -> Optional[CaptureRecaptureResult]:
        """Read coverage metrics. Returns None if missing."""
        path = self._raw_dir() / f"coverage_v{version}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return CaptureRecaptureResult.model_validate(data)
        except Exception as exc:
            logger.warning("Failed to read coverage v%d: %s", version, exc)
            return None

    # ------------------------------------------------------------------
    # Taxonomy
    # ------------------------------------------------------------------

    def _taxonomy_dir(self) -> Path:
        return self._root / "taxonomy"

    def get_latest_taxonomy_version(self) -> int:
        """Return the highest taxonomy version number, 0 if none exist."""
        d = self._taxonomy_dir()
        if not d.exists():
            return 0
        versions = []
        for f in d.iterdir():
            if f.suffix == ".json" and f.stem.startswith("v"):
                try:
                    versions.append(int(f.stem[1:]))
                except ValueError:
                    continue
        return max(versions) if versions else 0

    def write_taxonomy(self, tree: TaxonomyTree, version: int = 0) -> int:
        """Write a taxonomy version. Auto-increments if version=0. Returns version written."""
        if version == 0:
            version = self.get_latest_taxonomy_version() + 1
        path = self._taxonomy_dir() / f"v{version}.json"
        self._atomic_write(path, tree.model_dump_json(indent=2))
        logger.info(
            "TD/%s: wrote taxonomy v%d (%d subdomains)",
            self._slug, version, tree.total_subdomains,
        )
        return version

    def read_taxonomy(self, version: int) -> Optional[TaxonomyTree]:
        """Read a specific taxonomy version. Returns None if missing."""
        path = self._taxonomy_dir() / f"v{version}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return TaxonomyTree.model_validate(data)
        except Exception as exc:
            logger.warning("Failed to read taxonomy v%d: %s", version, exc)
            return None

    def get_latest_taxonomy(self) -> Optional[TaxonomyTree]:
        """Read the latest taxonomy version."""
        v = self.get_latest_taxonomy_version()
        if v == 0:
            return None
        return self.read_taxonomy(v)

    # ------------------------------------------------------------------
    # Matrix
    # ------------------------------------------------------------------

    def _matrix_dir(self) -> Path:
        return self._root / "matrix"

    def get_latest_matrix_version(self) -> int:
        """Return the highest matrix version number, 0 if none exist."""
        d = self._matrix_dir()
        if not d.exists():
            return 0
        versions = []
        for f in d.iterdir():
            if f.suffix == ".json" and f.stem.startswith("v"):
                try:
                    versions.append(int(f.stem[1:]))
                except ValueError:
                    continue
        return max(versions) if versions else 0

    def write_matrix(self, matrix: TopicAssignmentMatrix, version: int = 0) -> int:
        """Write a matrix version. Auto-increments if version=0. Returns version written."""
        if version == 0:
            version = self.get_latest_matrix_version() + 1
        path = self._matrix_dir() / f"v{version}.json"
        self._atomic_write(path, matrix.model_dump_json(indent=2))
        logger.info(
            "TD/%s: wrote matrix v%d (%d assignments)",
            self._slug, version, matrix.total_assignments,
        )
        return version

    def read_matrix(self, version: int) -> Optional[TopicAssignmentMatrix]:
        """Read a specific matrix version. Returns None if missing."""
        path = self._matrix_dir() / f"v{version}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return TopicAssignmentMatrix.model_validate(data)
        except Exception as exc:
            logger.warning("Failed to read matrix v%d: %s", version, exc)
            return None

    def get_latest_matrix(self) -> Optional[TopicAssignmentMatrix]:
        """Read the latest matrix version."""
        v = self.get_latest_matrix_version()
        if v == 0:
            return None
        return self.read_matrix(v)
