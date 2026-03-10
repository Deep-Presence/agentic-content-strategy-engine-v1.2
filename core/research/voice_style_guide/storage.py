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
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from core.models.voice_style_guide import (
    AuthorBrief,
    AuthorEntry,
    VoiceStyleGuideEntry,
    VoiceStyleGuideManifest,
)

logger = logging.getLogger(__name__)


class VoiceStyleGuideStorage:
    """Read / write / version voice style guide artifacts on the filesystem."""

    def __init__(self, artifacts_root: Path, slug: str) -> None:
        self._root = Path(artifacts_root) / "voice_style_guide" / slug
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

    def read_manifest(self) -> VoiceStyleGuideManifest:
        """Read the manifest, returning a blank one if it doesn't exist."""
        path = self._manifest_path()
        if not path.exists():
            return VoiceStyleGuideManifest(slug=self._slug)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return VoiceStyleGuideManifest.model_validate(data)
        except Exception as exc:
            logger.warning("Failed to read VSG manifest at %s: %s", path, exc)
            return VoiceStyleGuideManifest(slug=self._slug)

    def write_manifest(self, manifest: VoiceStyleGuideManifest) -> None:
        """Persist the manifest to disk (atomic via temp-file + os.replace)."""
        self._root.mkdir(parents=True, exist_ok=True)
        self._atomic_write(self._manifest_path(), manifest.model_dump_json(indent=2))

    # ------------------------------------------------------------------
    # Discovery artifact
    # ------------------------------------------------------------------

    def _discovery_dir(self) -> Path:
        return self._root / "discovery"

    def write_discovery(self, briefs: List[AuthorBrief], version: int = 0) -> int:
        """Write an author discovery artifact. Returns the version written."""
        manifest = self.read_manifest()
        if version == 0:
            # Auto-increment: count existing discovery files
            disc_dir = self._discovery_dir()
            if disc_dir.exists():
                existing = [f for f in disc_dir.iterdir() if f.suffix == ".json"]
                version = len(existing) + 1
            else:
                version = 1

        disc_dir = self._discovery_dir()
        disc_dir.mkdir(parents=True, exist_ok=True)

        path = disc_dir / f"v{version}.json"
        data = [b.model_dump(mode="json") for b in briefs]
        self._atomic_write(path, json.dumps(data, indent=2, default=str))

        manifest.slug = manifest.slug or self._slug
        self.write_manifest(manifest)

        logger.info(
            "VSG/%s: wrote discovery v%d (%d authors)",
            self._slug, version, len(briefs),
        )
        return version

    def read_discovery(self, version: int) -> List[AuthorBrief]:
        """Read a discovery artifact. Returns empty list if missing."""
        path = self._discovery_dir() / f"v{version}.json"
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return [AuthorBrief.model_validate(item) for item in data]
        except Exception as exc:
            logger.warning("Failed to read discovery v%d: %s", version, exc)
            return []

    # ------------------------------------------------------------------
    # Author brief persistence
    # ------------------------------------------------------------------

    def _author_dir(self, author_id: str) -> Path:
        return self._root / author_id

    def write_author_brief(self, author_id: str, brief: AuthorBrief) -> None:
        """Write an author brief to {author_id}/brief.json."""
        d = self._author_dir(author_id)
        d.mkdir(parents=True, exist_ok=True)
        self._atomic_write(d / "brief.json", brief.model_dump_json(indent=2))

    def read_author_brief(self, author_id: str) -> Optional[AuthorBrief]:
        """Read an author brief. Returns None if missing."""
        path = self._author_dir(author_id) / "brief.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return AuthorBrief.model_validate(data)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Author research versioning
    # ------------------------------------------------------------------

    def _research_md_path(self, author_id: str, version: int) -> Path:
        return self._author_dir(author_id) / f"v{version}.md"

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

        author_dir = self._author_dir(author_id)
        author_dir.mkdir(parents=True, exist_ok=True)

        md_path = self._research_md_path(author_id, next_version)
        self._atomic_write(md_path, content_md)

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
        md_path = self._research_md_path(author_id, version)
        if not md_path.exists():
            return None
        return md_path.read_text(encoding="utf-8")

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

    def _guide_dir(self) -> Path:
        return self._root / "guide"

    def _guide_md_path(self, version: int) -> Path:
        return self._guide_dir() / f"v{version}.md"

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

        guide_dir = self._guide_dir()
        guide_dir.mkdir(parents=True, exist_ok=True)

        md_path = self._guide_md_path(next_version)
        self._atomic_write(md_path, content_md)

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
        md_path = self._guide_md_path(manifest.guide.current_version)
        if not md_path.exists():
            return None
        return md_path.read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # Promotion to style_guides/
    # ------------------------------------------------------------------

    def promote_to_style_guides(self, artifacts_root: Path) -> Optional[str]:
        """Copy the latest guide to artifacts/style_guides/{slug}.md.

        Returns the path if successful, None if no guide exists.
        """
        guide_md = self.get_latest_guide()
        if not guide_md:
            return None

        sg_dir = Path(artifacts_root) / "style_guides"
        sg_dir.mkdir(parents=True, exist_ok=True)
        target = sg_dir / f"{self._slug}.md"
        self._atomic_write(target, guide_md)

        logger.info("VSG/%s: promoted guide to %s", self._slug, target)
        return str(target)

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
