"""Artifact listing and retrieval endpoints."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from api.dependencies import get_artifacts_root

router = APIRouter(prefix="/api/v1/artifacts", tags=["artifacts"])

VALID_TYPES = {"company_context", "personas", "style_guides", "gap_analysis", "content"}
_EXCLUDED_DIRS = {"chroma_db", "_logs", ".DS_Store"}

# Artifact types where files live directly in the type dir (not in slug subdirs)
_FLAT_TYPES = {"company_context", "personas", "style_guides"}


def _slugs_from_flat_dir(type_dir: Path) -> set[str]:
    """Extract company slugs from flat file naming convention.

    Files like ramp.md, carta.md → slugs ramp, carta
    Files like ramp__persona-icp.md → slug ramp
    """
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
    artifacts_root: Path = Depends(get_artifacts_root),
) -> Dict[str, List[str]]:
    """List all company slugs aggregated across artifact types."""
    all_slugs: set[str] = set()

    for type_name in VALID_TYPES:
        type_dir = artifacts_root / type_name
        if not type_dir.is_dir():
            continue
        if type_name in _FLAT_TYPES:
            all_slugs |= _slugs_from_flat_dir(type_dir)
        else:
            all_slugs |= _slugs_from_nested_dir(type_dir)

    return {"companies": sorted(all_slugs)}


@router.get("/{artifact_type}/{slug}")
def list_artifacts(
    artifact_type: str,
    slug: str,
    artifacts_root: Path = Depends(get_artifacts_root),
) -> Dict[str, Any]:
    """List files for a given artifact type and company slug."""
    if artifact_type not in VALID_TYPES:
        raise HTTPException(
            status_code=422, detail=f"Invalid artifact type: {artifact_type}. Valid: {sorted(VALID_TYPES)}"
        )

    if artifact_type in _FLAT_TYPES:
        # Flat layout — find files matching this slug at the type dir root
        type_dir = artifacts_root / artifact_type
        if not type_dir.is_dir():
            raise HTTPException(status_code=404, detail=f"No artifacts of type {artifact_type}")

        files = []
        for f in sorted(type_dir.iterdir()):
            if not f.is_file() or f.name.startswith("."):
                continue
            stem = f.stem
            # Match slug.md or slug__*.md
            if stem == slug or stem.startswith(f"{slug}__"):
                files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                })

        if not files:
            raise HTTPException(status_code=404, detail=f"No artifacts for {slug} in {artifact_type}")
        return {"artifact_type": artifact_type, "slug": slug, "files": files}

    else:
        # Nested layout — look inside type_dir/slug/
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
    artifacts_root: Path = Depends(get_artifacts_root),
) -> Any:
    """Retrieve artifact file content."""
    if artifact_type not in VALID_TYPES:
        raise HTTPException(
            status_code=422, detail=f"Invalid artifact type: {artifact_type}"
        )

    # Path traversal check
    if ".." in filename:
        raise HTTPException(status_code=400, detail="Path traversal not allowed")

    if artifact_type in _FLAT_TYPES:
        file_path = (artifacts_root / artifact_type / filename).resolve()
        expected_parent = (artifacts_root / artifact_type).resolve()
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
