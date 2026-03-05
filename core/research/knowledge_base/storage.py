"""Filesystem-backed storage for the Knowledge Base.

Layout::

    artifacts/knowledge_base/{slug}/
        _manifest.json
        company_overview/
            v1.md, v1.json
        customer_reviews/
            v1.md, v1.json
        competitor_registry/
            v1.md, v1.json
        weakness_analysis/
            v1.md, v1.json
        brand_perception/
            v1.md, v1.json
        synthesis/
            v1.md

Atomicity: version files are written first, manifest is updated last.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from core.models.knowledge_base import (
    L2_DOC_TYPES,
    KBDocEntry,
    KBDocType,
    KBDocVersion,
    KBManifest,
)

logger = logging.getLogger(__name__)


class KBStorage:
    """Read / write / version Knowledge Base documents on the filesystem."""

    def __init__(self, artifacts_root: Path, slug: str) -> None:
        self._root = Path(artifacts_root) / "knowledge_base" / slug
        self._slug = slug

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def base_dir(self) -> Path:
        """Root directory for this slug's knowledge base."""
        return self._root

    @property
    def slug(self) -> str:
        return self._slug

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------

    def _manifest_path(self) -> Path:
        return self._root / "_manifest.json"

    def read_manifest(self) -> KBManifest:
        """Read the manifest, returning a blank one if it doesn't exist."""
        path = self._manifest_path()
        if not path.exists():
            return KBManifest(slug=self._slug)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return KBManifest.model_validate(data)
        except Exception as exc:
            logger.warning("Failed to read manifest at %s: %s", path, exc)
            return KBManifest(slug=self._slug)

    def write_manifest(self, manifest: KBManifest) -> None:
        """Persist the manifest to disk."""
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._manifest_path()
        path.write_text(
            manifest.model_dump_json(indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Doc-type directory helpers
    # ------------------------------------------------------------------

    def _doc_dir(self, doc_type: KBDocType) -> Path:
        return self._root / doc_type.value

    def _version_md_path(self, doc_type: KBDocType, version: int) -> Path:
        return self._doc_dir(doc_type) / f"v{version}.md"

    def _version_json_path(self, doc_type: KBDocType, version: int) -> Path:
        return self._doc_dir(doc_type) / f"v{version}.json"

    # ------------------------------------------------------------------
    # Write a new version
    # ------------------------------------------------------------------

    def write_version(
        self,
        doc_type: KBDocType,
        content_md: str,
        content_json: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Write a new version for a doc type and update the manifest.

        Returns the version number that was written.
        """
        manifest = self.read_manifest()

        # Determine next version
        entry_key = doc_type.value
        entry = manifest.documents.get(entry_key)
        next_version = (entry.current_version + 1) if entry else 1

        # Create directory
        doc_dir = self._doc_dir(doc_type)
        doc_dir.mkdir(parents=True, exist_ok=True)

        # Write markdown
        md_path = self._version_md_path(doc_type, next_version)
        md_path.write_text(content_md, encoding="utf-8")

        # Write JSON sidecar (optional)
        if content_json is not None:
            json_path = self._version_json_path(doc_type, next_version)
            json_path.write_text(
                json.dumps(content_json, indent=2, default=str),
                encoding="utf-8",
            )

        # Compute metadata
        sha = hashlib.sha256(content_md.encode("utf-8")).hexdigest()
        word_count = len(content_md.split())
        now = datetime.now(timezone.utc)

        # Update manifest entry
        manifest.documents[entry_key] = KBDocEntry(
            doc_type=doc_type,
            current_version=next_version,
            last_updated=now,
            status="fresh",
            dependencies=entry.dependencies if entry else [],
        )
        manifest.slug = manifest.slug or self._slug

        # Persist manifest last (atomicity)
        self.write_manifest(manifest)

        logger.info(
            "KB/%s: wrote %s v%d (%d words, sha=%s…)",
            self._slug,
            doc_type.value,
            next_version,
            word_count,
            sha[:12],
        )
        return next_version

    # ------------------------------------------------------------------
    # Read a version
    # ------------------------------------------------------------------

    def read_version(
        self,
        doc_type: KBDocType,
        version: int,
    ) -> Optional[KBDocVersion]:
        """Read a specific version of a doc type.

        Returns None if the version file doesn't exist.
        """
        md_path = self._version_md_path(doc_type, version)
        if not md_path.exists():
            return None

        content_md = md_path.read_text(encoding="utf-8")
        sha = hashlib.sha256(content_md.encode("utf-8")).hexdigest()

        content_json: Optional[Dict[str, Any]] = None
        json_path = self._version_json_path(doc_type, version)
        if json_path.exists():
            try:
                content_json = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        return KBDocVersion(
            version=version,
            content_md=content_md,
            content_json=content_json,
            word_count=len(content_md.split()),
            sha256=sha,
        )

    def get_latest_version(
        self,
        doc_type: KBDocType,
    ) -> Optional[KBDocVersion]:
        """Read the latest version of a doc type (from manifest)."""
        manifest = self.read_manifest()
        entry = manifest.documents.get(doc_type.value)
        if not entry or entry.current_version == 0:
            return None
        return self.read_version(doc_type, entry.current_version)

    def get_all_latest(self) -> Dict[KBDocType, Optional[KBDocVersion]]:
        """Read the latest version of every doc type."""
        return {dt: self.get_latest_version(dt) for dt in L2_DOC_TYPES}

    # ------------------------------------------------------------------
    # Staleness
    # ------------------------------------------------------------------

    def check_staleness(
        self,
        doc_type: KBDocType,
        threshold_days: int = 30,
    ) -> bool:
        """Return True if the doc is stale or missing.

        A doc is stale if ``last_updated`` is older than *threshold_days*.
        A missing doc is always considered stale.
        """
        manifest = self.read_manifest()
        entry = manifest.documents.get(doc_type.value)
        if not entry or entry.status == "missing" or entry.current_version == 0:
            return True

        if entry.last_updated is None:
            return True

        age = (datetime.now(timezone.utc) - entry.last_updated).days
        return age > threshold_days

    # ------------------------------------------------------------------
    # Synthesis (L3)
    # ------------------------------------------------------------------

    def _synthesis_dir(self) -> Path:
        return self._root / "synthesis"

    def _synthesis_md_path(self, version: int) -> Path:
        return self._synthesis_dir() / f"v{version}.md"

    def write_synthesis(self, content_md: str) -> int:
        """Write a new synthesis version and update the manifest.

        Returns the version number written.
        """
        manifest = self.read_manifest()
        next_version = manifest.synthesis_version + 1

        syn_dir = self._synthesis_dir()
        syn_dir.mkdir(parents=True, exist_ok=True)

        md_path = self._synthesis_md_path(next_version)
        md_path.write_text(content_md, encoding="utf-8")

        manifest.synthesis_version = next_version
        manifest.synthesis_last_updated = datetime.now(timezone.utc)
        manifest.slug = manifest.slug or self._slug
        self.write_manifest(manifest)

        logger.info(
            "KB/%s: wrote synthesis v%d (%d words)",
            self._slug,
            next_version,
            len(content_md.split()),
        )
        return next_version

    def read_synthesis(self, version: Optional[int] = None) -> Optional[KBDocVersion]:
        """Read a synthesis version (latest if version is None)."""
        if version is None:
            manifest = self.read_manifest()
            version = manifest.synthesis_version
        if version == 0:
            return None

        md_path = self._synthesis_md_path(version)
        if not md_path.exists():
            return None

        content_md = md_path.read_text(encoding="utf-8")
        return KBDocVersion(
            version=version,
            content_md=content_md,
            word_count=len(content_md.split()),
            sha256=hashlib.sha256(content_md.encode("utf-8")).hexdigest(),
        )
