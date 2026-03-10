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
import os
import tempfile
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
        """Persist the manifest to disk (atomic via temp-file + os.replace)."""
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
            # Clean up on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

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
