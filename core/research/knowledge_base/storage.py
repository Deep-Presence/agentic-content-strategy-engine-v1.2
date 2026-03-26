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

from core.models.knowledge_base import (
    KB_DEFAULT_STALENESS_DAYS,
    KB_DEPENDENCY_GRAPH,
    L2_DOC_TYPES,
    KBDocEntry,
    KBDocHealth,
    KBDocType,
    KBDocVersion,
    KBHealthReport,
    KBManifest,
)
from core.storage.backends.base import StorageBackend

logger = logging.getLogger(__name__)


class KBStorage:
    """Read / write / version Knowledge Base documents via a StorageBackend."""

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
        self._prefix = f"knowledge_base/{slug}/"

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def base_dir(self) -> Path:
        """Root directory for this slug's knowledge base.

        Retained for backward compatibility with tests and callers that
        inspect the filesystem directly.
        """
        return self._artifacts_root / "knowledge_base" / self._slug

    @property
    def slug(self) -> str:
        return self._slug

    # ------------------------------------------------------------------
    # Key helpers (return paths relative to backend root)
    # ------------------------------------------------------------------

    def _manifest_key(self) -> str:
        return f"{self._prefix}_manifest.json"

    def _doc_md_key(self, doc_type: KBDocType, version: int) -> str:
        return f"{self._prefix}{doc_type.value}/v{version}.md"

    def _doc_json_key(self, doc_type: KBDocType, version: int) -> str:
        return f"{self._prefix}{doc_type.value}/v{version}.json"

    def _synthesis_md_key(self, version: int) -> str:
        return f"{self._prefix}synthesis/v{version}.md"

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------

    def read_manifest(self) -> KBManifest:
        """Read the manifest, returning a blank one if it doesn't exist."""
        raw = self._backend.read(self._manifest_key())
        if raw is None:
            return KBManifest(slug=self._slug)
        try:
            data = json.loads(raw)
            return KBManifest.model_validate(data)
        except Exception as exc:
            logger.warning(
                "Failed to read manifest for %s: %s", self._slug, exc,
            )
            return KBManifest(slug=self._slug)

    def write_manifest(self, manifest: KBManifest) -> None:
        """Persist the manifest (atomic via backend)."""
        self._backend.write(
            self._manifest_key(), manifest.model_dump_json(indent=2),
        )

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

        # Write markdown
        self._backend.write(
            self._doc_md_key(doc_type, next_version), content_md,
        )

        # Write JSON sidecar (optional)
        if content_json is not None:
            self._backend.write(
                self._doc_json_key(doc_type, next_version),
                json.dumps(content_json, indent=2, default=str),
            )

        # Compute metadata
        sha = hashlib.sha256(content_md.encode("utf-8")).hexdigest()
        word_count = len(content_md.split())
        now = datetime.now(timezone.utc)

        # Update manifest entry — dependencies always sourced from DAG constant
        manifest.documents[entry_key] = KBDocEntry(
            doc_type=doc_type,
            current_version=next_version,
            last_updated=now,
            staleness_days=KB_DEFAULT_STALENESS_DAYS.get(doc_type, 90),
            status="fresh",
            dependencies=KB_DEPENDENCY_GRAPH.get(doc_type, []),
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
        content_md = self._backend.read(self._doc_md_key(doc_type, version))
        if content_md is None:
            return None

        sha = hashlib.sha256(content_md.encode("utf-8")).hexdigest()

        content_json: Optional[Dict[str, Any]] = None
        raw_json = self._backend.read(self._doc_json_key(doc_type, version))
        if raw_json is not None:
            try:
                content_json = json.loads(raw_json)
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

    def write_synthesis(self, content_md: str) -> int:
        """Write a new synthesis version and update the manifest.

        Returns the version number written.
        """
        manifest = self.read_manifest()
        next_version = manifest.synthesis_version + 1

        self._backend.write(
            self._synthesis_md_key(next_version), content_md,
        )

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

        content_md = self._backend.read(self._synthesis_md_key(version))
        if content_md is None:
            return None

        return KBDocVersion(
            version=version,
            content_md=content_md,
            word_count=len(content_md.split()),
            sha256=hashlib.sha256(content_md.encode("utf-8")).hexdigest(),
        )

    # ------------------------------------------------------------------
    # Promotion
    # ------------------------------------------------------------------

    def promote_synthesis_to_company_context(self, content_md: str) -> None:
        """Promote synthesis markdown to ``company_context/{slug}.md``."""
        self._backend.write(
            f"company_context/{self._slug}.md", content_md,
        )

    # ------------------------------------------------------------------
    # Staleness Report & Propagation
    # ------------------------------------------------------------------

    def get_staleness_report(
        self,
        threshold_override: Optional[int] = None,
    ) -> KBHealthReport:
        """Generate a full health report for all KB documents.

        Uses per-doc-type thresholds from KB_DEFAULT_STALENESS_DAYS,
        or *threshold_override* if provided (applies globally).
        """
        manifest = self.read_manifest()
        now = datetime.now(timezone.utc)

        doc_health: Dict[str, KBDocHealth] = {}
        stale_docs: List[str] = []
        missing_docs: List[str] = []
        fresh_count = 0

        for dt in L2_DOC_TYPES:
            entry = manifest.documents.get(dt.value)
            threshold = (
                threshold_override
                if threshold_override is not None
                else KB_DEFAULT_STALENESS_DAYS.get(dt, 90)
            )

            if not entry or entry.current_version == 0:
                doc_health[dt.value] = KBDocHealth(
                    doc_type=dt,
                    status="missing",
                    staleness_threshold_days=threshold,
                    dependencies=KB_DEPENDENCY_GRAPH.get(dt, []),
                )
                missing_docs.append(dt.value)
                continue

            age_days = (
                (now - entry.last_updated).days
                if entry.last_updated
                else 999
            )

            # Check upstream-changed staleness
            stale_reason: Optional[str] = None
            status: str = "fresh"

            if entry.last_updated is None or age_days > threshold:
                status = "stale"
                stale_reason = "age_exceeded"
            else:
                # Check if any upstream dependency was updated after this doc
                for dep in KB_DEPENDENCY_GRAPH.get(dt, []):
                    dep_entry = manifest.documents.get(dep.value)
                    if (
                        dep_entry
                        and dep_entry.last_updated
                        and entry.last_updated
                        and dep_entry.last_updated > entry.last_updated
                    ):
                        status = "stale"
                        stale_reason = "upstream_changed"
                        break

            if status == "fresh":
                fresh_count += 1
            else:
                stale_docs.append(dt.value)

            doc_health[dt.value] = KBDocHealth(
                doc_type=dt,
                status=status,
                current_version=entry.current_version,
                last_updated=entry.last_updated,
                age_days=age_days,
                staleness_threshold_days=threshold,
                dependencies=KB_DEPENDENCY_GRAPH.get(dt, []),
                stale_reason=stale_reason,
            )

        # Synthesis freshness
        synthesis_needs_refresh = False
        if manifest.synthesis_version > 0 and manifest.synthesis_last_updated:
            for dt in L2_DOC_TYPES:
                entry = manifest.documents.get(dt.value)
                if (
                    entry
                    and entry.last_updated
                    and entry.last_updated > manifest.synthesis_last_updated
                ):
                    synthesis_needs_refresh = True
                    break
        elif manifest.synthesis_version == 0:
            # Never synthesized — needs synthesis if any docs exist
            synthesis_needs_refresh = any(
                manifest.documents.get(dt.value)
                and manifest.documents[dt.value].current_version > 0
                for dt in L2_DOC_TYPES
            )

        # Score: (fresh / 5) * 100, penalized if synthesis stale
        base_score = (fresh_count / len(L2_DOC_TYPES)) * 100
        if synthesis_needs_refresh and base_score > 0:
            base_score = max(base_score - 10, 0)

        return KBHealthReport(
            slug=self._slug,
            overall_score=round(base_score, 1),
            doc_health=doc_health,
            synthesis_version=manifest.synthesis_version,
            synthesis_last_updated=manifest.synthesis_last_updated,
            synthesis_needs_refresh=synthesis_needs_refresh,
            stale_docs=stale_docs,
            missing_docs=missing_docs,
            last_full_refresh=manifest.last_full_refresh,
        )

    def propagate_staleness(
        self,
        refreshed_doc_types: List[KBDocType],
    ) -> List[KBDocType]:
        """Mark downstream docs as stale when upstream docs were refreshed.

        Returns the list of doc types that were marked stale.
        """
        if not refreshed_doc_types:
            return []

        manifest = self.read_manifest()
        marked_stale: List[KBDocType] = []
        refreshed_set = set(refreshed_doc_types)

        # Build reverse DAG: for each doc type, find which doc types depend on it
        reverse_dag: Dict[KBDocType, List[KBDocType]] = {dt: [] for dt in L2_DOC_TYPES}
        for dt, deps in KB_DEPENDENCY_GRAPH.items():
            for dep in deps:
                reverse_dag[dep].append(dt)

        # BFS from refreshed docs to find all downstream docs
        queue = list(refreshed_set)
        visited: set[KBDocType] = set(refreshed_set)

        while queue:
            current = queue.pop(0)
            for downstream in reverse_dag.get(current, []):
                if downstream in visited:
                    continue
                visited.add(downstream)

                entry = manifest.documents.get(downstream.value)
                if entry and entry.current_version > 0 and entry.status != "missing":
                    entry.status = "stale"
                    marked_stale.append(downstream)

                queue.append(downstream)

        if marked_stale:
            self.write_manifest(manifest)
            logger.info(
                "KB/%s: propagated staleness from %s → marked stale: %s",
                self._slug,
                [dt.value for dt in refreshed_doc_types],
                [dt.value for dt in marked_stale],
            )

        return marked_stale

    def get_changed_since_synthesis(self) -> List[KBDocType]:
        """Return L2 doc types updated after the last synthesis."""
        manifest = self.read_manifest()
        if manifest.synthesis_version == 0:
            # Never synthesized — return all existing docs
            return [
                dt
                for dt in L2_DOC_TYPES
                if manifest.documents.get(dt.value)
                and manifest.documents[dt.value].current_version > 0
            ]

        syn_time = manifest.synthesis_last_updated
        if syn_time is None:
            return list(L2_DOC_TYPES)

        changed: List[KBDocType] = []
        for dt in L2_DOC_TYPES:
            entry = manifest.documents.get(dt.value)
            if entry and entry.last_updated and entry.last_updated > syn_time:
                changed.append(dt)
        return changed
