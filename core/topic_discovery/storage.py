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
All I/O goes through a ``StorageBackend`` so the underlying persistence
layer (local filesystem, S3, GCS) can be swapped via configuration.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path, PurePosixPath
from typing import Optional

from core.models.topic_discovery import (
    CaptureRecaptureResult,
    PersonaAffinityIndex,
    ScoredSubdomainList,
    SourceResult,
    TaxonomyTree,
    TDSource,
    TopicAssignmentMatrix,
    TopicDiscoveryManifest,
)
from core.storage.backends.base import StorageBackend
from core.storage.backends.local import LocalStorageBackend

logger = logging.getLogger(__name__)

_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*(__[a-z0-9][a-z0-9-]*)?$")


class TopicDiscoveryStorage:
    """Read / write / version topic discovery artifacts via a StorageBackend."""

    def __init__(
        self,
        artifacts_root: Path,
        slug: str,
        *,
        backend: Optional[StorageBackend] = None,
    ) -> None:
        if not slug or not _SLUG_PATTERN.match(slug):
            raise ValueError(
                f"Invalid slug: {slug!r}. "
                "Must match ^[a-z0-9][a-z0-9-]*(__[a-z0-9][a-z0-9-]*)?$"
            )
        self._artifacts_root = Path(artifacts_root)
        self._slug = slug
        self._backend = backend or LocalStorageBackend(
            self._artifacts_root.resolve(),
        )
        self._prefix = f"topic_discovery/{slug}/"

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def base_dir(self) -> Path:
        return self._artifacts_root.resolve() / "topic_discovery" / self._slug

    @property
    def slug(self) -> str:
        return self._slug

    # ------------------------------------------------------------------
    # Key helpers (return paths relative to backend root)
    # ------------------------------------------------------------------

    def _manifest_key(self) -> str:
        return f"{self._prefix}_manifest.json"

    def _source_key(self, source: TDSource, version: int) -> str:
        return f"{self._prefix}raw/{source.value}_v{version}.json"

    def _coverage_key(self, version: int) -> str:
        return f"{self._prefix}raw/coverage_v{version}.json"

    def _taxonomy_key(self, version: int) -> str:
        return f"{self._prefix}taxonomy/v{version}.json"

    def _matrix_key(self, version: int) -> str:
        return f"{self._prefix}matrix/v{version}.json"

    def _scoring_key(self, version: int) -> str:
        return f"{self._prefix}scoring/v{version}.json"

    def _persona_affinity_key(self, version: int) -> str:
        return f"{self._prefix}persona_affinity/v{version}.json"

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------

    def read_manifest(self) -> TopicDiscoveryManifest:
        """Read the manifest, returning a blank one if it doesn't exist."""
        raw = self._backend.read(self._manifest_key())
        if raw is None:
            return TopicDiscoveryManifest(slug=self._slug)
        try:
            data = json.loads(raw)
            return TopicDiscoveryManifest.model_validate(data)
        except Exception as exc:
            logger.warning("Failed to read TD manifest for %s: %s", self._slug, exc)
            return TopicDiscoveryManifest(slug=self._slug)

    def write_manifest(self, manifest: TopicDiscoveryManifest) -> None:
        """Persist the manifest to disk (atomic)."""
        self._backend.write(
            self._manifest_key(), manifest.model_dump_json(indent=2),
        )

    # ------------------------------------------------------------------
    # Raw source results
    # ------------------------------------------------------------------

    def write_source_result(
        self, source: TDSource, result: SourceResult, version: int = 1
    ) -> None:
        """Write a raw source result artifact."""
        self._backend.write(
            self._source_key(source, version),
            result.model_dump_json(indent=2),
        )
        logger.info(
            "TD/%s: wrote %s v%d (%d candidates)",
            self._slug, source.value, version, len(result.candidates),
        )

    def read_source_result(
        self, source: TDSource, version: int = 1
    ) -> Optional[SourceResult]:
        """Read a raw source result. Returns None if missing or corrupt."""
        raw = self._backend.read(self._source_key(source, version))
        if raw is None:
            return None
        try:
            data = json.loads(raw)
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
        self._backend.write(
            self._coverage_key(version),
            metrics.model_dump_json(indent=2),
        )

    def read_coverage(self, version: int = 1) -> Optional[CaptureRecaptureResult]:
        """Read coverage metrics. Returns None if missing."""
        raw = self._backend.read(self._coverage_key(version))
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            return CaptureRecaptureResult.model_validate(data)
        except Exception as exc:
            logger.warning("Failed to read coverage v%d: %s", version, exc)
            return None

    # ------------------------------------------------------------------
    # Taxonomy
    # ------------------------------------------------------------------

    def get_latest_taxonomy_version(self) -> int:
        """Return the highest taxonomy version number, 0 if none exist."""
        entries = self._backend.list_dir(f"{self._prefix}taxonomy")
        versions = []
        for entry in entries:
            name = PurePosixPath(entry).name
            if name.endswith(".json") and name.startswith("v"):
                try:
                    versions.append(int(name[1:].removesuffix(".json")))
                except ValueError:
                    continue
        return max(versions) if versions else 0

    def write_taxonomy(self, tree: TaxonomyTree, version: int = 0) -> int:
        """Write a taxonomy version. Auto-increments if version=0. Returns version written."""
        if version == 0:
            version = self.get_latest_taxonomy_version() + 1
        synced = tree.model_copy(update={"version": version})
        self._backend.write(
            self._taxonomy_key(version),
            synced.model_dump_json(indent=2),
        )
        logger.info(
            "TD/%s: wrote taxonomy v%d (%d subdomains)",
            self._slug, version, synced.total_subdomains,
        )
        return version

    def read_taxonomy(self, version: int) -> Optional[TaxonomyTree]:
        """Read a specific taxonomy version. Returns None if missing."""
        raw = self._backend.read(self._taxonomy_key(version))
        if raw is None:
            return None
        try:
            data = json.loads(raw)
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

    def get_latest_matrix_version(self) -> int:
        """Return the highest matrix version number, 0 if none exist."""
        entries = self._backend.list_dir(f"{self._prefix}matrix")
        versions = []
        for entry in entries:
            name = PurePosixPath(entry).name
            if name.endswith(".json") and name.startswith("v"):
                try:
                    versions.append(int(name[1:].removesuffix(".json")))
                except ValueError:
                    continue
        return max(versions) if versions else 0

    def write_matrix(self, matrix: TopicAssignmentMatrix, version: int = 0) -> int:
        """Write a matrix version. Auto-increments if version=0. Returns version written."""
        if version == 0:
            version = self.get_latest_matrix_version() + 1
        synced = matrix.model_copy(update={"version": version})
        self._backend.write(
            self._matrix_key(version),
            synced.model_dump_json(indent=2),
        )
        logger.info(
            "TD/%s: wrote matrix v%d (%d assignments)",
            self._slug, version, synced.total_assignments,
        )
        return version

    def read_matrix(self, version: int) -> Optional[TopicAssignmentMatrix]:
        """Read a specific matrix version. Returns None if missing."""
        raw = self._backend.read(self._matrix_key(version))
        if raw is None:
            return None
        try:
            data = json.loads(raw)
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

    # ------------------------------------------------------------------
    # Scoring (algorithmic subdomain priority)
    # ------------------------------------------------------------------

    def get_latest_scoring_version(self) -> int:
        """Return the highest scoring version number, 0 if none exist."""
        entries = self._backend.list_dir(f"{self._prefix}scoring")
        versions = []
        for entry in entries:
            name = PurePosixPath(entry).name
            if name.endswith(".json") and name.startswith("v"):
                try:
                    versions.append(int(name[1:].removesuffix(".json")))
                except ValueError:
                    continue
        return max(versions) if versions else 0

    def write_scoring(
        self, scored: ScoredSubdomainList, version: int = 0
    ) -> int:
        """Write a scoring version. Auto-increments if version=0."""
        if version == 0:
            version = self.get_latest_scoring_version() + 1
        synced = scored.model_copy(update={"version": version})
        self._backend.write(
            self._scoring_key(version),
            synced.model_dump_json(indent=2),
        )
        logger.info(
            "TD/%s: wrote scoring v%d (%d subdomains)",
            self._slug, version, synced.total_scored,
        )
        return version

    def read_scoring(self, version: int) -> Optional[ScoredSubdomainList]:
        """Read a specific scoring version. Returns None if missing."""
        raw = self._backend.read(self._scoring_key(version))
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            return ScoredSubdomainList.model_validate(data)
        except Exception as exc:
            logger.warning("Failed to read scoring v%d: %s", version, exc)
            return None

    def get_latest_scoring(self) -> Optional[ScoredSubdomainList]:
        """Read the latest scoring version."""
        v = self.get_latest_scoring_version()
        if v == 0:
            return None
        return self.read_scoring(v)

    # ------------------------------------------------------------------
    # Persona Affinity
    # ------------------------------------------------------------------

    def get_latest_persona_affinity_version(self) -> int:
        """Return the highest persona affinity version, 0 if none exist."""
        entries = self._backend.list_dir(f"{self._prefix}persona_affinity")
        versions = []
        for entry in entries:
            name = PurePosixPath(entry).name
            if name.endswith(".json") and name.startswith("v"):
                try:
                    versions.append(int(name[1:].removesuffix(".json")))
                except ValueError:
                    continue
        return max(versions) if versions else 0

    def write_persona_affinity(
        self, index: PersonaAffinityIndex, version: int = 0
    ) -> int:
        """Write a persona affinity version. Auto-increments if version=0."""
        if version == 0:
            version = self.get_latest_persona_affinity_version() + 1
        synced = index.model_copy(update={"version": version})
        self._backend.write(
            self._persona_affinity_key(version),
            synced.model_dump_json(indent=2),
        )
        logger.info(
            "TD/%s: wrote persona_affinity v%d (%d personas, %d subdomains)",
            self._slug, version, synced.total_personas, synced.total_subdomains,
        )
        return version

    def read_persona_affinity(
        self, version: int
    ) -> Optional[PersonaAffinityIndex]:
        """Read a specific persona affinity version. Returns None if missing."""
        raw = self._backend.read(self._persona_affinity_key(version))
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            return PersonaAffinityIndex.model_validate(data)
        except Exception as exc:
            logger.warning(
                "Failed to read persona_affinity v%d: %s", version, exc,
            )
            return None

    def get_latest_persona_affinity(self) -> Optional[PersonaAffinityIndex]:
        """Read the latest persona affinity version."""
        v = self.get_latest_persona_affinity_version()
        if v == 0:
            return None
        return self.read_persona_affinity(v)
