"""Shared helpers for company/workspace profile artifact and task aggregation."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from core.services.task_store import TaskStoreProtocol


def detect_artifact_status(
    artifacts_root: Path,
    type_name: str,
    slug: str,
    *,
    backend: Optional[Any] = None,
) -> str:
    """Check if an artifact exists: 'approved', 'draft', or 'none'."""
    from core.storage.backends.local import LocalStorageBackend

    _backend = backend or LocalStorageBackend(artifacts_root)
    if _backend.exists(f"{type_name}/{slug}.md"):
        return "approved"
    if _backend.exists(f"{type_name}/{slug}.draft.md"):
        return "draft"
    return "none"


def detect_personas(
    artifacts_root: Path,
    slug: str,
    *,
    backend: Optional[Any] = None,
) -> List[str]:
    """Find all persona files for a company slug via PersonaStorage."""
    try:
        from core.research.audience_persona.storage import PersonaStorage
        from core.storage.backends.local import LocalStorageBackend

        _backend = backend or LocalStorageBackend(artifacts_root)
        ap_storage = PersonaStorage(artifacts_root, slug, backend=_backend)
        manifest = ap_storage.read_manifest()
        if not manifest.personas:
            return []
        persona_files: List[str] = []
        for pid, entry in manifest.personas.items():
            if entry.status in ("fresh", "stale") and entry.current_version > 0:
                persona_files.append(f"{pid}.md")
        return sorted(persona_files)
    except Exception:
        return []


def has_nested_artifacts(
    artifacts_root: Path,
    type_name: str,
    slug: str,
    *,
    backend: Optional[Any] = None,
) -> bool:
    """Check if nested artifact directory exists and has files."""
    from core.storage.backends.local import LocalStorageBackend

    _backend = backend or LocalStorageBackend(artifacts_root)
    entries = _backend.list_dir(f"{type_name}/{slug}/")
    return any(not e.rsplit("/", 1)[-1].startswith(".") for e in entries)


def build_research_summary(
    artifacts_root: Path,
    slug: str,
    *,
    backend: Optional[Any] = None,
) -> dict[str, Any]:
    """Scan filesystem for research artifacts belonging to this workspace slug."""
    cc_status = detect_artifact_status(
        artifacts_root, "company_context", slug, backend=backend
    )
    sg_status = detect_artifact_status(
        artifacts_root, "style_guides", slug, backend=backend
    )
    personas = detect_personas(artifacts_root, slug, backend=backend)

    cc_file = None
    if cc_status == "approved":
        cc_file = f"{slug}.md"
    elif cc_status == "draft":
        cc_file = f"{slug}.draft.md"

    sg_file = None
    if sg_status == "approved":
        sg_file = f"{slug}.md"
    elif sg_status == "draft":
        sg_file = f"{slug}.draft.md"

    return {
        "company_context": cc_file,
        "company_context_status": cc_status,
        "personas": personas,
        "style_guide": sg_file,
        "style_guide_status": sg_status,
    }


def get_latest_runs(
    task_store: TaskStoreProtocol, slug: str
) -> Dict[str, Optional[dict[str, Any]]]:
    """Find the most recent task per pipeline type for this workspace slug."""
    latest: Dict[str, Optional[dict[str, Any]]] = {
        "research": None,
        "gap_analysis": None,
        "content": None,
        "topic_discovery": None,
    }

    for task in task_store.list_tasks():
        if task.company_slug != slug:
            continue
        pipeline = task.pipeline
        if pipeline in ("content_v13", "td_content"):
            pipeline = "content"
        elif pipeline in ("td_gap_analysis",):
            pipeline = "gap_analysis"
        elif pipeline not in latest:
            continue

        current = latest[pipeline]
        if current is None or task.created_at > current["created_at"]:
            latest[pipeline] = {
                "run_id": task.task_id,
                "status": task.status.value,
                "created_at": task.created_at,
                "completed_at": (
                    task.updated_at
                    if task.status.value in ("completed", "failed", "cancelled")
                    else None
                ),
                "summary": task.result,
            }

    return latest


def get_running_tasks(
    task_store: TaskStoreProtocol, slug: str
) -> List[dict[str, Any]]:
    """Return in-flight tasks for the workspace slug."""
    active_statuses = frozenset(
        {"pending", "running", "PENDING", "RUNNING", "pending_approval"}
    )
    running: List[dict[str, Any]] = []
    for task in task_store.list_tasks():
        if task.company_slug != slug:
            continue
        if task.status.value not in active_statuses:
            continue
        running.append(
            {
                "task_id": task.task_id,
                "pipeline": task.pipeline,
                "status": task.status.value,
                "created_at": task.created_at,
                "current_step": task.current_step,
            }
        )
    return sorted(running, key=lambda t: t["created_at"], reverse=True)
