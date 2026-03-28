"""Filesystem-backed storage for Voice Style Guide artifacts.

Layout::

    artifacts/voice_style_guide/{slug}/
        _manifest.json
        discovery/
            v1.json            (AuthorBrief list)
        {author_id}/
            brief.json         (AuthorBrief)
            v1.md              (research markdown)
        guide/
            v1.md              (final voice style guide)

Atomicity: version files are written first, manifest is updated last.
All I/O goes through a ``StorageBackend`` so the underlying persistence
layer (local filesystem, S3, GCS) can be swapped via configuration.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional

from core.models.voice_style_guide import (
    AuthorBrief,
    AuthorEntry,
    VoiceStyleGuideEntry,
    VoiceStyleGuideManifest,
)
from core.storage.backends.base import StorageBackend

logger = logging.getLogger(__name__)


class VoiceStyleGuideStorage:
    """Read / write / version voice style guide artifacts via a StorageBackend."""

    def __init__(
        self,
        artifacts_root: Path,
        slug: str,
        *,
        backend: Optional[StorageBackend] = None,
    ) -> None:
        self._artifacts_root = Path(artifacts_root)
        self._slug = slug
        if backend is not None:
            self._backend = backend
        else:
            from core.storage import get_storage_backend
            self._backend = get_storage_backend(self._artifacts_root)
        self._prefix = f"voice_style_guide/{slug}/"

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def base_dir(self) -> Path:
        return self._artifacts_root / "voice_style_guide" / self._slug

    @property
    def slug(self) -> str:
        return self._slug

    # ------------------------------------------------------------------
    # Key helpers (return paths relative to backend root)
    # ------------------------------------------------------------------

    def _manifest_key(self) -> str:
        return f"{self._prefix}_manifest.json"

    def _discovery_key(self, version: int) -> str:
        return f"{self._prefix}discovery/v{version}.json"

    def _author_brief_key(self, author_id: str) -> str:
        return f"{self._prefix}{author_id}/brief.json"

    def _research_md_key(self, author_id: str, version: int) -> str:
        return f"{self._prefix}{author_id}/v{version}.md"

    def _guide_md_key(self, version: int) -> str:
        return f"{self._prefix}guide/v{version}.md"

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------

    def read_manifest(self) -> VoiceStyleGuideManifest:
        """Read the manifest, returning a blank one if it doesn't exist."""
        raw = self._backend.read(self._manifest_key())
        if raw is None:
            return VoiceStyleGuideManifest(slug=self._slug)
        try:
            data = json.loads(raw)
            return VoiceStyleGuideManifest.model_validate(data)
        except Exception as exc:
            logger.warning(
                "Failed to read VSG manifest for %s: %s", self._slug, exc,
            )
            return VoiceStyleGuideManifest(slug=self._slug)

    def write_manifest(self, manifest: VoiceStyleGuideManifest) -> None:
        """Persist the manifest (atomic via backend)."""
        self._backend.write(
            self._manifest_key(), manifest.model_dump_json(indent=2),
        )

    # ------------------------------------------------------------------
    # Discovery artifact
    # ------------------------------------------------------------------

    def write_discovery(self, briefs: List[AuthorBrief], version: int = 0) -> int:
        """Write an author discovery artifact. Returns the version written."""
        manifest = self.read_manifest()
        if version == 0:
            # Auto-increment: count existing discovery .json files
            disc_prefix = f"{self._prefix}discovery"
            entries = self._backend.list_dir(disc_prefix)
            json_files = [
                e for e in entries
                if PurePosixPath(e).suffix == ".json"
            ]
            version = len(json_files) + 1

        data = [b.model_dump(mode="json") for b in briefs]
        self._backend.write(
            self._discovery_key(version),
            json.dumps(data, indent=2, default=str),
        )

        manifest.slug = manifest.slug or self._slug
        self.write_manifest(manifest)

        logger.info(
            "VSG/%s: wrote discovery v%d (%d authors)",
            self._slug, version, len(briefs),
        )
        return version

    def read_discovery(self, version: int) -> List[AuthorBrief]:
        """Read a discovery artifact. Returns empty list if missing."""
        raw = self._backend.read(self._discovery_key(version))
        if raw is None:
            return []
        try:
            data = json.loads(raw)
            return [AuthorBrief.model_validate(item) for item in data]
        except Exception as exc:
            logger.warning("Failed to read discovery v%d: %s", version, exc)
            return []

    # ------------------------------------------------------------------
    # Author brief persistence
    # ------------------------------------------------------------------

    def write_author_brief(self, author_id: str, brief: AuthorBrief) -> None:
        """Write an author brief to {author_id}/brief.json."""
        self._backend.write(
            self._author_brief_key(author_id),
            brief.model_dump_json(indent=2),
        )

    def read_author_brief(self, author_id: str) -> Optional[AuthorBrief]:
        """Read an author brief. Returns None if missing."""
        raw = self._backend.read(self._author_brief_key(author_id))
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            return AuthorBrief.model_validate(data)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Author research versioning
    # ------------------------------------------------------------------

    def write_author_research(
        self,
        author_id: str,
        name: str,
        content_md: str,
    ) -> int:
        """Write a new author research version and update the manifest.

        Returns the version number that was written.
        """
        manifest = self.read_manifest()

        entry = manifest.authors.get(author_id)
        next_version = (entry.current_version + 1) if entry else 1

        self._backend.write(
            self._research_md_key(author_id, next_version), content_md,
        )

        sha = hashlib.sha256(content_md.encode("utf-8")).hexdigest()
        word_count = len(content_md.split())
        now = datetime.now(timezone.utc)

        manifest.authors[author_id] = AuthorEntry(
            author_id=author_id,
            name=name,
            current_version=next_version,
            last_updated=now,
            status="fresh",
            word_count=word_count,
            sha256=sha,
        )
        manifest.slug = manifest.slug or self._slug
        self.write_manifest(manifest)

        logger.info(
            "VSG/%s: wrote %s v%d (%d words, sha=%s…)",
            self._slug, author_id, next_version, word_count, sha[:12],
        )
        return next_version

    def read_author_research(
        self, author_id: str, version: int,
    ) -> Optional[str]:
        """Read a specific version of an author's research markdown."""
        return self._backend.read(
            self._research_md_key(author_id, version),
        )

    def get_latest_author_research(self, author_id: str) -> Optional[str]:
        """Read the latest version of an author's research."""
        manifest = self.read_manifest()
        entry = manifest.authors.get(author_id)
        if not entry or entry.current_version == 0:
            return None
        return self.read_author_research(author_id, entry.current_version)

    # ------------------------------------------------------------------
    # Guide versioning
    # ------------------------------------------------------------------

    def write_guide(
        self,
        content_md: str,
        source_authors: Optional[List[str]] = None,
    ) -> int:
        """Write a new voice style guide version and update the manifest.

        Returns the version number that was written.
        """
        manifest = self.read_manifest()
        next_version = manifest.guide.current_version + 1

        self._backend.write(
            self._guide_md_key(next_version), content_md,
        )

        sha = hashlib.sha256(content_md.encode("utf-8")).hexdigest()
        word_count = len(content_md.split())
        now = datetime.now(timezone.utc)

        manifest.guide = VoiceStyleGuideEntry(
            current_version=next_version,
            last_updated=now,
            status="fresh",
            word_count=word_count,
            sha256=sha,
            source_authors=source_authors or [],
        )
        manifest.slug = manifest.slug or self._slug
        self.write_manifest(manifest)

        logger.info(
            "VSG/%s: wrote guide v%d (%d words, sha=%s…)",
            self._slug, next_version, word_count, sha[:12],
        )
        return next_version

    def get_latest_guide(self) -> Optional[str]:
        """Read the latest voice style guide markdown."""
        manifest = self.read_manifest()
        if manifest.guide.current_version == 0:
            return None
        return self._backend.read(
            self._guide_md_key(manifest.guide.current_version),
        )

    # ------------------------------------------------------------------
    # Promotion to style_guides/
    # ------------------------------------------------------------------

    def promote_to_style_guides(self, artifacts_root: Optional[Path] = None) -> Optional[str]:
        """Copy the latest guide to style_guides/{slug}.md via the storage backend.

        Returns the relative storage key if successful, None if no guide exists.
        """
        guide_md = self.get_latest_guide()
        if not guide_md:
            return None

        rel_key = f"style_guides/{self._slug}.md"
        self._backend.write(rel_key, guide_md)

        logger.info("VSG/%s: promoted guide to %s", self._slug, rel_key)
        return rel_key

    # ------------------------------------------------------------------
    # List / query helpers
    # ------------------------------------------------------------------

    def list_author_ids(self) -> List[str]:
        """Return author IDs from the manifest."""
        manifest = self.read_manifest()
        return list(manifest.authors.keys())

    def list_active_author_ids(self) -> List[str]:
        """Return author IDs with status fresh or stale (excludes archived/missing)."""
        manifest = self.read_manifest()
        return [
            aid
            for aid, entry in manifest.authors.items()
            if entry.status in ("fresh", "stale")
        ]
