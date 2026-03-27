"""Artifact listing and retrieval endpoints.

All endpoints require authentication. Tenant isolation ensures users
can only access artifacts belonging to their own company.

Uses StorageBackend for all file I/O so that R2, local filesystem, or any
other backend works transparently.
"""
from __future__ import annotations

import json
import re
from pathlib import PurePosixPath
from typing import Any, Dict, List

_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from api.auth.dependencies import require_auth
from api.dependencies import get_storage_backend
from core.models.organization import UserProfile
from core.storage.backends.base import StorageBackend

router = APIRouter(prefix="/api/v1/artifacts", tags=["artifacts"])

VALID_TYPES = {"company_context", "personas", "style_guides", "gap_analysis", "content", "knowledge_base"}
_EXCLUDED_DIRS = {"chroma_db", "_logs", ".DS_Store"}

# Artifact types where files live directly in the type dir (not in slug subdirs)
_FLAT_TYPES = {"company_context", "personas", "style_guides"}


def _user_company_slug(request: Request) -> str:
    """Extract the authenticated user's company slug from request state."""
    slug = getattr(request.state, "company_slug", None)
    if not slug:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return slug


def _slug_belongs_to_user(slug: str, company_slug: str) -> bool:
    """Check if a slug (bare or effective) belongs to the user's company.

    Handles both:
      - bare slug: "ramp" matches company_slug "ramp"
      - effective slug: "ramp__corporate-card" matches company_slug "ramp"
    """
    return slug == company_slug or slug.startswith(f"{company_slug}__")


def _basename(path: str) -> str:
    """Extract the last component of a storage path."""
    return PurePosixPath(path).name


def _stem(path: str) -> str:
    """Extract the stem (filename without extension) of a storage path."""
    return PurePosixPath(path).stem


def _list_recursive(backend: StorageBackend, prefix: str) -> List[str]:
    """Recursively list all file paths under a prefix via StorageBackend.

    Uses breadth-first traversal of list_dir to discover all files.
    Filters out hidden files/dirs (starting with '.') and excluded dirs.
    """
    result: List[str] = []
    queue = [prefix]
    while queue:
        current = queue.pop(0)
        children = backend.list_dir(current)
        for child in children:
            name = _basename(child)
            if name.startswith(".") or name in _EXCLUDED_DIRS:
                continue
            # If child has content, it's a file
            if backend.exists(child):
                # Could be a file or a prefix that also exists as a key.
                # Try listing children to distinguish dirs from files.
                sub_children = backend.list_dir(child)
                if sub_children:
                    # It's a directory (has children) — recurse
                    queue.append(child)
                else:
                    # It's a leaf file
                    result.append(child)
            else:
                # Prefix-only entry (virtual directory in R2) — recurse
                queue.append(child)
    return sorted(result)


def _slugs_from_flat_listing(entries: List[str]) -> set[str]:
    """Extract company slugs from flat file naming convention."""
    slugs: set[str] = set()
    for entry in entries:
        name = _basename(entry)
        if name.startswith(".") or name.endswith(".draft.md"):
            continue
        stem = _stem(entry)
        if "__" in stem:
            slugs.add(stem.split("__")[0])
        else:
            slugs.add(stem)
    return slugs


def _slugs_from_nested_listing(entries: List[str]) -> set[str]:
    """Extract company slugs from nested directory listing."""
    slugs: set[str] = set()
    for entry in entries:
        name = _basename(entry)
        if name not in _EXCLUDED_DIRS and not name.startswith("."):
            slugs.add(name)
    return slugs


@router.get("/companies")
def list_companies(
    request: Request,
    backend: StorageBackend = Depends(get_storage_backend),
    _user: UserProfile = Depends(require_auth),
) -> Dict[str, List[str]]:
    """List company slugs visible to the authenticated user.

    Returns only slugs belonging to the user's company (bare + effective).
    """
    company_slug = _user_company_slug(request)
    all_slugs: set[str] = set()

    for type_name in VALID_TYPES:
        entries = backend.list_dir(type_name)
        if not entries:
            continue
        if type_name in _FLAT_TYPES:
            all_slugs |= _slugs_from_flat_listing(entries)
        else:
            all_slugs |= _slugs_from_nested_listing(entries)

    # Filter to only the user's company slugs
    visible = sorted(s for s in all_slugs if _slug_belongs_to_user(s, company_slug))
    return {"companies": visible}


@router.get("/{artifact_type}/{slug}")
def list_artifacts(
    artifact_type: str,
    slug: str,
    request: Request,
    backend: StorageBackend = Depends(get_storage_backend),
    _user: UserProfile = Depends(require_auth),
) -> Dict[str, Any]:
    """List files for a given artifact type and company slug."""
    if not _SLUG_PATTERN.match(slug):
        raise HTTPException(status_code=400, detail="Invalid slug format")
    if artifact_type not in VALID_TYPES:
        raise HTTPException(
            status_code=422, detail=f"Invalid artifact type: {artifact_type}. Valid: {sorted(VALID_TYPES)}"
        )

    # Tenant isolation
    company_slug = _user_company_slug(request)
    if not _slug_belongs_to_user(slug, company_slug):
        raise HTTPException(status_code=403, detail="Access denied")

    if artifact_type in _FLAT_TYPES:
        entries = backend.list_dir(artifact_type)
        if not entries:
            raise HTTPException(status_code=404, detail=f"No artifacts of type {artifact_type}")

        files = []
        for entry in entries:
            name = _basename(entry)
            if name.startswith("."):
                continue
            stem = _stem(entry)
            # Strip .draft suffix for matching
            match_stem = stem[: -len(".draft")] if stem.endswith(".draft") else stem
            if match_stem == slug or match_stem.startswith(f"{slug}__"):
                files.append({
                    "name": name,
                    "size": 0,  # StorageBackend doesn't expose size; frontend doesn't use it
                })

        if not files:
            raise HTTPException(status_code=404, detail=f"No artifacts for {slug} in {artifact_type}")
        return {"artifact_type": artifact_type, "slug": slug, "files": sorted(files, key=lambda f: f["name"])}

    else:
        prefix = f"{artifact_type}/{slug}"
        all_files = _list_recursive(backend, prefix)

        if not all_files:
            raise HTTPException(status_code=404, detail=f"No {artifact_type} artifacts for {slug}")

        files = []
        for file_path in all_files:
            name = _basename(file_path)
            if name.startswith("."):
                continue
            # Relative path from {artifact_type}/{slug}/
            rel = file_path[len(prefix) + 1:]  # strip "knowledge_base/ramp/"
            files.append({
                "name": rel,
                "size": 0,  # StorageBackend doesn't expose size; frontend doesn't use it
            })

        return {"artifact_type": artifact_type, "slug": slug, "files": files}


@router.get("/{artifact_type}/{slug}/{filename:path}")
def get_artifact_content(
    artifact_type: str,
    slug: str,
    filename: str,
    request: Request,
    backend: StorageBackend = Depends(get_storage_backend),
    _user: UserProfile = Depends(require_auth),
) -> Any:
    """Retrieve artifact file content."""
    if not _SLUG_PATTERN.match(slug):
        raise HTTPException(status_code=400, detail="Invalid slug format")
    if artifact_type not in VALID_TYPES:
        raise HTTPException(
            status_code=422, detail=f"Invalid artifact type: {artifact_type}"
        )

    # Tenant isolation
    company_slug = _user_company_slug(request)
    if not _slug_belongs_to_user(slug, company_slug):
        raise HTTPException(status_code=403, detail="Access denied")

    # Path traversal check
    if ".." in filename:
        raise HTTPException(status_code=400, detail="Path traversal not allowed")

    if artifact_type in _FLAT_TYPES:
        storage_key = f"{artifact_type}/{filename}"

        # C1 fix: verify filename belongs to the authorized slug (prevents IDOR)
        stem = PurePosixPath(filename).stem
        # Strip .draft suffix for draft files (e.g., "ramp.draft" → "ramp")
        if stem.endswith(".draft"):
            stem = stem[: -len(".draft")]
        if not (stem == slug or stem.startswith(f"{slug}__")):
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        storage_key = f"{artifact_type}/{slug}/{filename}"

    content = backend.read(storage_key)
    if content is None:
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    if filename.endswith(".json"):
        return JSONResponse(content=json.loads(content))
    elif filename.endswith(".html"):
        return HTMLResponse(content=content)
    else:
        return PlainTextResponse(content=content)
