"""Filesystem-backed storage for Audience Persona artifacts.

Layout::

    artifacts/audience_personas/{slug}/
        _manifest.json
        {persona_id}/
            brief.json
            v1.md
            v1.json          (optional structured sidecar)
            v2.md
            ...

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
from typing import Any, Dict, List, Optional

from core.models.audience_persona import (
    PERSONA_DEFAULT_STALENESS_DAYS,
    PersonaBrief,
    PersonaManifest,
    PersonaProfileEntry,
)

logger = logging.getLogger(__name__)


class PersonaStorage:
    """Read / write / version audience persona artifacts on the filesystem."""

    def __init__(self, artifacts_root: Path, slug: str) -> None:
        self._root = Path(artifacts_root) / "audience_personas" / slug
        self._slug = slug

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

    def read_manifest(self) -> PersonaManifest:
        path = self._manifest_path()
        if not path.exists():
            return PersonaManifest(slug=self._slug)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return PersonaManifest.model_validate(data)
        except Exception as exc:
            logger.warning("Failed to read persona manifest at %s: %s", path, exc)
            return PersonaManifest(slug=self._slug)

    def write_manifest(self, manifest: PersonaManifest) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._manifest_path()
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._root), suffix=".tmp", prefix="_manifest_",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(manifest.model_dump_json(indent=2))
            os.replace(tmp_path, str(path))
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # ------------------------------------------------------------------
    # Persona directory helpers
    # ------------------------------------------------------------------

    def _persona_dir(self, persona_id: str) -> Path:
        return self._root / persona_id

    def _brief_path(self, persona_id: str) -> Path:
        return self._persona_dir(persona_id) / "brief.json"

    def _version_md_path(self, persona_id: str, version: int) -> Path:
        return self._persona_dir(persona_id) / f"v{version}.md"

    def _version_json_path(self, persona_id: str, version: int) -> Path:
        return self._persona_dir(persona_id) / f"v{version}.json"

    # ------------------------------------------------------------------
    # Brief persistence
    # ------------------------------------------------------------------

    def write_brief(self, persona_id: str, brief: PersonaBrief) -> None:
        d = self._persona_dir(persona_id)
        d.mkdir(parents=True, exist_ok=True)
        self._brief_path(persona_id).write_text(
            brief.model_dump_json(indent=2), encoding="utf-8",
        )

    def read_brief(self, persona_id: str) -> Optional[PersonaBrief]:
        path = self._brief_path(persona_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return PersonaBrief.model_validate(data)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Write a new version
    # ------------------------------------------------------------------

    def write_version(
        self,
        persona_id: str,
        persona_name: str,
        content_md: str,
        content_json: Optional[Dict[str, Any]] = None,
        *,
        kind: str = "secondary",
        created_by: str = "agent",
        tagline: str = "",
        status: str = "fresh",
    ) -> int:
        """Write a new persona profile version and update the manifest.

        Returns the version number that was written.

        Concurrency note: This method performs a read-manifest → write-file →
        write-manifest sequence without internal locking. Callers must serialize
        concurrent writes externally (e.g., asyncio.Lock or task_store.semaphore).
        """
        manifest = self.read_manifest()

        entry = manifest.personas.get(persona_id)
        next_version = (entry.current_version + 1) if entry else 1

        persona_dir = self._persona_dir(persona_id)
        persona_dir.mkdir(parents=True, exist_ok=True)

        md_path = self._version_md_path(persona_id, next_version)
        md_path.write_text(content_md, encoding="utf-8")

        if content_json is not None:
            json_path = self._version_json_path(persona_id, next_version)
            json_path.write_text(
                json.dumps(content_json, indent=2, default=str),
                encoding="utf-8",
            )

        sha = hashlib.sha256(content_md.encode("utf-8")).hexdigest()
        word_count = len(content_md.split())
        now = datetime.now(timezone.utc)

        manifest.personas[persona_id] = PersonaProfileEntry(
            persona_id=persona_id,
            persona_name=persona_name,
            tagline=tagline,
            kind=kind,
            current_version=next_version,
            last_updated=now,
            status=status,
            created_by=created_by,
            word_count=word_count,
            sha256=sha,
        )
        manifest.slug = manifest.slug or self._slug

        self.write_manifest(manifest)

        logger.info(
            "AP/%s: wrote %s v%d (%d words, sha=%s…)",
            self._slug,
            persona_id,
            next_version,
            word_count,
            sha[:12],
        )
        return next_version

    # ------------------------------------------------------------------
    # Read a version
    # ------------------------------------------------------------------

    def read_version(self, persona_id: str, version: int) -> Optional[Dict[str, Any]]:
        """Read a specific version of a persona profile.

        Returns dict with keys: version, content_md, content_json, word_count, sha256.
        Returns None if the version file doesn't exist.
        """
        md_path = self._version_md_path(persona_id, version)
        if not md_path.exists():
            return None

        content_md = md_path.read_text(encoding="utf-8")
        sha = hashlib.sha256(content_md.encode("utf-8")).hexdigest()

        content_json: Optional[Dict[str, Any]] = None
        json_path = self._version_json_path(persona_id, version)
        if json_path.exists():
            try:
                content_json = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        return {
            "version": version,
            "content_md": content_md,
            "content_json": content_json,
            "word_count": len(content_md.split()),
            "sha256": sha,
        }

    def get_latest_version(self, persona_id: str) -> Optional[Dict[str, Any]]:
        """Read the latest version of a persona profile (from manifest)."""
        manifest = self.read_manifest()
        entry = manifest.personas.get(persona_id)
        if not entry or entry.current_version == 0:
            return None
        return self.read_version(persona_id, entry.current_version)

    def get_all_latest(self) -> Dict[str, Optional[Dict[str, Any]]]:
        """Read the latest version of every persona profile."""
        manifest = self.read_manifest()
        return {
            pid: self.get_latest_version(pid)
            for pid in manifest.personas
        }

    # ------------------------------------------------------------------
    # List / query helpers
    # ------------------------------------------------------------------

    def list_persona_ids(self) -> List[str]:
        """Return persona IDs from the manifest."""
        manifest = self.read_manifest()
        return list(manifest.personas.keys())

    def list_active_persona_ids(self) -> List[str]:
        """Return persona IDs with status fresh or stale (excludes archived/missing)."""
        manifest = self.read_manifest()
        return [
            pid
            for pid, entry in manifest.personas.items()
            if entry.status in ("fresh", "stale", "pending_review")
        ]

    def list_persona_paths(self) -> List[str]:
        """Return paths to latest .md files for active personas (content engine integration)."""
        manifest = self.read_manifest()
        paths: List[str] = []
        for pid, entry in manifest.personas.items():
            if entry.status in ("fresh", "stale") and entry.current_version > 0:
                md_path = self._version_md_path(pid, entry.current_version)
                if md_path.exists():
                    paths.append(str(md_path))
        return paths

    # ------------------------------------------------------------------
    # Staleness
    # ------------------------------------------------------------------

    def check_staleness(
        self,
        persona_id: str,
        threshold_days: int = PERSONA_DEFAULT_STALENESS_DAYS,
    ) -> bool:
        """Return True if a persona is stale or missing."""
        manifest = self.read_manifest()
        entry = manifest.personas.get(persona_id)
        if not entry or entry.status == "missing" or entry.current_version == 0:
            return True
        if entry.last_updated is None:
            return True
        age = (datetime.now(timezone.utc) - entry.last_updated).days
        return age > threshold_days

    def check_kb_staleness(self, kb_synthesis_version: int) -> bool:
        """Return True if persona manifest's kb_synthesis_version is behind.

        If persona manifest has no kb_synthesis_version recorded, returns True
        (assumes stale — KB has been updated since personas were generated).
        """
        manifest = self.read_manifest()
        if manifest.kb_synthesis_version is None:
            return True
        return manifest.kb_synthesis_version < kb_synthesis_version

    def mark_persona_status(self, persona_id: str, status: str) -> None:
        """Update a persona's status in the manifest."""
        manifest = self.read_manifest()
        entry = manifest.personas.get(persona_id)
        if entry:
            entry.status = status  # type: ignore[assignment]
            self.write_manifest(manifest)
