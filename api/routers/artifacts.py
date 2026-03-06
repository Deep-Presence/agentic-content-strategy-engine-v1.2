"""Artifact listing and retrieval endpoints.

All endpoints require authentication. Tenant isolation ensures users
can only access artifacts belonging to their own company.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from api.auth.dependencies import require_auth
from api.dependencies import get_artifacts_root
from core.models.organization import UserProfile

router = APIRouter(prefix="/api/v1/artifacts", tags=["artifacts"])

VALID_TYPES = {"company_context", "personas", "style_guides", "gap_analysis", "content"}
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


def _slugs_from_flat_dir(type_dir: Path) -> set[str]:
    """Extract company slugs from flat file naming convention."""
    slugs: set[str] = set()
    if not type_dir.is_dir():
        return slugs
    for f in type_dir.iterdir():
        if f.name.startswith(".") or f.name.endswith(".draft.md"):
            continue
        stem = f.stem
        if "__" in stem:
            slugs.add(stem.split("__")[0])
        else:
            slugs.add(stem)
    return slugs


def _slugs_from_nested_dir(type_dir: Path) -> set[str]:
    """Extract company slugs from nested directory structure (gap_analysis, content)."""
    slugs: set[str] = set()
    if not type_dir.is_dir():
        return slugs
    for d in type_dir.iterdir():
        if d.is_dir() and d.name not in _EXCLUDED_DIRS and not d.name.startswith("."):
            slugs.add(d.name)
    return slugs


@router.get("/companies")
def list_companies(
    request: Request,
    artifacts_root: Path = Depends(get_artifacts_root),
    _user: UserProfile = Depends(require_auth),
) -> Dict[str, List[str]]:
    """List company slugs visible to the authenticated user.

    Returns only slugs belonging to the user's company (bare + effective).
    """
    company_slug = _user_company_slug(request)
    all_slugs: set[str] = set()

    for type_name in VALID_TYPES:
        type_dir = artifacts_root / type_name
        if not type_dir.is_dir():
            continue
        if type_name in _FLAT_TYPES:
            all_slugs |= _slugs_from_flat_dir(type_dir)
        else:
            all_slugs |= _slugs_from_nested_dir(type_dir)

    # Filter to only the user's company slugs
    visible = sorted(s for s in all_slugs if _slug_belongs_to_user(s, company_slug))
    return {"companies": visible}


@router.get("/{artifact_type}/{slug}")
def list_artifacts(
    artifact_type: str,
    slug: str,
    request: Request,
    artifacts_root: Path = Depends(get_artifacts_root),
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
        type_dir = artifacts_root / artifact_type
        if not type_dir.is_dir():
            raise HTTPException(status_code=404, detail=f"No artifacts of type {artifact_type}")

        files = []
        for f in sorted(type_dir.iterdir()):
            if not f.is_file() or f.name.startswith("."):
                continue
            stem = f.stem
            if stem == slug or stem.startswith(f"{slug}__"):
                files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                })

        if not files:
            raise HTTPException(status_code=404, detail=f"No artifacts for {slug} in {artifact_type}")
        return {"artifact_type": artifact_type, "slug": slug, "files": files}

    else:
        slug_dir = artifacts_root / artifact_type / slug
        if not slug_dir.is_dir():
            raise HTTPException(status_code=404, detail=f"No {artifact_type} artifacts for {slug}")

        files = []
        for f in sorted(slug_dir.rglob("*")):
            if not f.is_file() or f.name.startswith("."):
                continue
            rel = f.relative_to(slug_dir)
            files.append({
                "name": str(rel),
                "size": f.stat().st_size,
            })

        return {"artifact_type": artifact_type, "slug": slug, "files": files}


@router.get("/{artifact_type}/{slug}/{filename:path}")
def get_artifact_content(
    artifact_type: str,
    slug: str,
    filename: str,
    request: Request,
    artifacts_root: Path = Depends(get_artifacts_root),
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
        file_path = (artifacts_root / artifact_type / filename).resolve()
        expected_parent = (artifacts_root / artifact_type).resolve()

        # C1 fix: verify filename belongs to the authorized slug (prevents IDOR)
        stem = Path(filename).stem
        # Strip .draft suffix for draft files (e.g., "ramp.draft" → "ramp")
        if stem.endswith(".draft"):
            stem = stem[: -len(".draft")]
        if not (stem == slug or stem.startswith(f"{slug}__")):
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        file_path = (artifacts_root / artifact_type / slug / filename).resolve()
        expected_parent = (artifacts_root / artifact_type / slug).resolve()

    # Ensure resolved path stays within expected directory
    if not file_path.is_relative_to(expected_parent):
        raise HTTPException(status_code=400, detail="Path traversal not allowed")

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    content = file_path.read_text(encoding="utf-8")

    if filename.endswith(".json"):
        return JSONResponse(content=json.loads(content))
    elif filename.endswith(".html"):
        return HTMLResponse(content=content)
    else:
        return PlainTextResponse(content=content)
