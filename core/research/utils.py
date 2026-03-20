"""Shared utilities for research pipelines.

Provides cross-pipeline helpers for reading promoted artifacts
(company context, persona profiles) through the StorageBackend
abstraction layer.
"""
from __future__ import annotations

from typing import List, Optional

from core.storage.backends import LocalStorageBackend, StorageBackend


def read_company_context(
    backend: StorageBackend,
    effective_slug: str,
    company_slug: str | None = None,
) -> str | None:
    """Read promoted company context markdown with effective → company slug fallback.

    Returns the markdown string if found, or ``None`` if both slugs are missing.
    """
    for slug in filter(None, [effective_slug, company_slug]):
        content = backend.read(f"company_context/{slug}.md")
        if content and content.strip():
            return content
    return None


def load_persona_profiles(
    backend: StorageBackend,
    effective_slug: str,
    company_slug: str | None = None,
) -> List[str]:
    """Load active persona profile markdowns via PersonaStorage.

    Follows effective_slug → company_slug fallback.
    Returns list of markdown strings (one per persona).
    """
    from core.research.audience_persona.storage import PersonaStorage

    for check_slug in filter(None, [effective_slug, company_slug]):
        # PersonaStorage needs artifacts_root; derive from backend when possible.
        if isinstance(backend, LocalStorageBackend):
            persona_storage = PersonaStorage(backend.root, check_slug, backend=backend)
        else:
            # Non-local backends — construct with a dummy root; backend handles I/O.
            from pathlib import Path

            persona_storage = PersonaStorage(Path("/unused"), check_slug, backend=backend)
        manifest = persona_storage.read_manifest()
        if manifest.personas:
            break
    else:
        return []

    persona_mds: List[str] = []
    for pid, entry in manifest.personas.items():
        if entry.status not in ("fresh", "stale"):
            continue
        version_data = persona_storage.get_latest_version(pid)
        if version_data and version_data.get("content_md"):
            persona_mds.append(version_data["content_md"])

    return persona_mds
