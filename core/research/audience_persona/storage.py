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
All I/O goes through a ``StorageBackend`` so the underlying persistence
layer (local filesystem, S3, GCS) can be swapped via configuration.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.models.audience_persona import (
    PERSONA_DEFAULT_STALENESS_DAYS,
    PersonaBrief,
    PersonaManifest,
    PersonaProfileEntry,
)
from core.storage.backends.base import StorageBackend

logger = logging.getLogger(__name__)


class PersonaStorage:
    """Read / write / version audience persona artifacts via a StorageBackend."""

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
        self._prefix = f"audience_personas/{slug}/"

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def base_dir(self) -> Path:
        return self._artifacts_root / "audience_personas" / self._slug

    @property
    def slug(self) -> str:
        return self._slug

    # ------------------------------------------------------------------
    # Key helpers (return paths relative to backend root)
    # ------------------------------------------------------------------

    def _manifest_key(self) -> str:
        return f"{self._prefix}_manifest.json"

    def _brief_key(self, persona_id: str) -> str:
        return f"{self._prefix}{persona_id}/brief.json"

    def _version_md_key(self, persona_id: str, version: int) -> str:
        return f"{self._prefix}{persona_id}/v{version}.md"

    def _version_json_key(self, persona_id: str, version: int) -> str:
        return f"{self._prefix}{persona_id}/v{version}.json"

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------

    def read_manifest(self) -> PersonaManifest:
        raw = self._backend.read(self._manifest_key())
        if raw is None:
            return PersonaManifest(slug=self._slug)
        try:
            data = json.loads(raw)
            return PersonaManifest.model_validate(data)
        except Exception as exc:
            logger.warning(
                "Failed to read persona manifest for %s: %s", self._slug, exc,
            )
            return PersonaManifest(slug=self._slug)

    def write_manifest(self, manifest: PersonaManifest) -> None:
        self._backend.write(
            self._manifest_key(), manifest.model_dump_json(indent=2),
        )

    # ------------------------------------------------------------------
    # Brief persistence
    # ------------------------------------------------------------------

    def write_brief(self, persona_id: str, brief: PersonaBrief) -> None:
        self._backend.write(
            self._brief_key(persona_id),
            brief.model_dump_json(indent=2),
        )

    def read_brief(self, persona_id: str) -> Optional[PersonaBrief]:
        raw = self._backend.read(self._brief_key(persona_id))
        if raw is None:
            return None
        try:
            data = json.loads(raw)
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

        # Write markdown
        self._backend.write(
            self._version_md_key(persona_id, next_version), content_md,
        )

        # Write JSON sidecar (optional)
        if content_json is not None:
            self._backend.write(
                self._version_json_key(persona_id, next_version),
                json.dumps(content_json, indent=2, default=str),
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
        content_md = self._backend.read(
            self._version_md_key(persona_id, version),
        )
        if content_md is None:
            return None

        sha = hashlib.sha256(content_md.encode("utf-8")).hexdigest()

        content_json: Optional[Dict[str, Any]] = None
        raw_json = self._backend.read(
            self._version_json_key(persona_id, version),
        )
        if raw_json is not None:
            try:
                content_json = json.loads(raw_json)
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
        """Return relative storage keys to latest .md files for active personas.

        Always returns relative paths (storage keys) compatible with any
        StorageBackend (R2, local, etc.). Downstream consumers must use
        the storage backend to read these paths.
        """
        manifest = self.read_manifest()
        paths: List[str] = []
        for pid, entry in manifest.personas.items():
            if entry.status in ("fresh", "stale") and entry.current_version > 0:
                rel_key = self._version_md_key(pid, entry.current_version)
                if self._backend.exists(rel_key):
                    paths.append(rel_key)
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
