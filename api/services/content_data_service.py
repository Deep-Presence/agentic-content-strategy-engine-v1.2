"""Service layer for content data endpoints (Phase 3 + Phase 5 R2 migration).

Reads content pipeline v1.3 artifacts via StorageBackend (R2 or local),
reshapes them to match the frontend TypeScript types, and caches parsed
JSON with TTL-based invalidation.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from api.schemas.content_data import (
    BriefExemplar,
    ContentBriefDetailResponse,
    ContentBriefListItem,
    ContentBriefListResponse,
    EvalCycle,
    EvalDimension,
    StageContentResponse,
)
from core.services.gap_context_helper import extract_gap_context, load_analysis_json
from core.storage.backends.base import StorageBackend

logger = logging.getLogger(__name__)

# ── Caching ──────────────────────────────────────────────────────────

_CACHE: Dict[str, Tuple[float, Any]] = {}
_CACHE_MAX_ENTRIES = 10
_CACHE_LOCK = threading.Lock()  # C6: protects compound check-evict-insert

# Split TTLs by artifact write pattern (Codex C5)
_TTL_BY_FILE: Dict[str, int] = {
    "blueprints.json": 60,
    "planner_selections.json": 60,
    "run_metadata_v13.json": 120,
    "eval_history.json": 120,
}
_DEFAULT_CACHE_TTL_S = 120


def _load_json_cached(
    storage: StorageBackend, key: str,
) -> Optional[Any]:
    """Load and parse a JSON artifact via StorageBackend with TTL cache.

    *key* is the full storage path, e.g. ``content/test-co/blueprints.json``.
    """
    now = time.monotonic()

    # Determine TTL from filename suffix
    fname = key.rsplit("/", 1)[-1] if "/" in key else key
    ttl = _TTL_BY_FILE.get(fname, _DEFAULT_CACHE_TTL_S)

    cached = _CACHE.get(key)
    if cached is not None and (now - cached[0]) < ttl:
        return cached[1]

    content = storage.read(key)
    if content is None:
        return None

    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to parse %s: %s", key, exc)
        return None

    # C6: lock protects the compound check-evict-insert against concurrent writes
    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_MAX_ENTRIES and key not in _CACHE:
            oldest_key = next(iter(_CACHE))
            del _CACHE[oldest_key]
        _CACHE[key] = (now, data)
    return data


def _load_pipeline_state(artifacts_root: Path, slug: str) -> Dict[str, Any]:
    """Load pipeline_state.json from local filesystem (NOT StorageBackend).

    pipeline_state.json is ephemeral, sub-second writes during pipeline
    execution.  It is NOT an R2 artifact — earmarked for Redis migration.
    Returns empty dict if missing.
    """
    state_path = artifacts_root / "content" / slug / "pipeline_state.json"
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}


# ── Storage resolution ───────────────────────────────────────────────


def _resolve_storage(
    artifacts_root: Path, storage: Optional[StorageBackend],
) -> StorageBackend:
    """Return the given StorageBackend or create a LocalStorageBackend."""
    if storage is not None:
        return storage
    from core.storage.backends.local import LocalStorageBackend
    return LocalStorageBackend(artifacts_root)


# ── Validation ───────────────────────────────────────────────────────

# Accepts bare company slugs ("ramp") and effective product slugs ("ramp__card")
_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*(__[a-z0-9][a-z0-9-]*)?$")
_BRIEF_ID_PATTERN = re.compile(r"^brief-\d{1,4}$")

_VALID_STAGES = frozenset(
    {"outline", "draft", "enriched", "formatted", "eval_history", "final"}
)

_STAGE_FILES = {
    "outline": ("outline.json", "application/json"),
    "draft": ("draft.md", "text/markdown"),
    "enriched": ("enriched.md", "text/markdown"),
    "formatted": ("formatted.md", "text/markdown"),
    "eval_history": ("eval_history.json", "application/json"),
    "final": ("final.md", "text/markdown"),
}


def _validate_slug(slug: str) -> None:
    if not _SLUG_PATTERN.match(slug):
        raise HTTPException(400, f"Invalid slug format: '{slug}'")


def _validate_brief_id(brief_id: str) -> None:
    if not _BRIEF_ID_PATTERN.match(brief_id):
        raise HTTPException(400, f"Invalid brief_id format: '{brief_id}'")


# ── Mapping helpers ──────────────────────────────────────────────────

_FORMAT_TO_TYPE = {
    "long_blog": "blog",
    "short_faq": "blog",
    "pillar_page": "guide",
    "comparison": "guide",
    "how_to": "guide",
}


def _map_content_format(format_str: str) -> str:
    """Map backend content_format to frontend content_type."""
    result = _FORMAT_TO_TYPE.get(format_str)
    if result is None:
        logger.warning("Unknown content_format '%s', defaulting to 'blog'", format_str)
        return "blog"
    return result


# ── Status inference ─────────────────────────────────────────────────


def _infer_brief_status(
    brief_id: str,
    pieces: List[Dict[str, Any]],
    storage: StorageBackend,
    slug: str,
    pipeline_state: Optional[Dict[str, Any]] = None,
) -> str:
    """Infer brief status from pipeline state, run_metadata pieces, or stage files.

    Phase 0: Check pipeline_state.json (in-progress authoritative, during pipeline execution).
    Phase 1: Check run_metadata_v13.json pieces array (post-HITL authoritative).
    Phase 2: File-based inference (during/after pipeline execution).
    """
    # Phase 0: pipeline_state.json (highest priority during pipeline execution)
    # Skip reserved keys like __task_ids__ (dict, not a status string)
    if pipeline_state and brief_id in pipeline_state:
        val = pipeline_state[brief_id]
        if isinstance(val, str):
            return val

    # Phase 1: Check pieces (post-HITL authoritative)
    for piece in pieces:
        if piece.get("brief_id") == brief_id:
            status = piece.get("status", "")
            return {
                "approved": "completed",  # HITL-3 approved → Published column
                "edited": "completed",    # Human-edited → Published column
                "rejected": "rejected",
                "pending": "review",
            }.get(status, "review")

    # Phase 2: Storage-based inference
    prefix = f"content/{slug}/content/{brief_id}"
    if storage.exists(f"{prefix}/final.md"):
        return "completed"
    if storage.exists(f"{prefix}/eval_history.json"):
        try:
            raw = storage.read(f"{prefix}/eval_history.json")
            if raw:
                eh = json.loads(raw)
                if eh.get("final_passed", False):
                    return "review"
        except (json.JSONDecodeError, KeyError):
            pass
        return "evaluating"
    if storage.exists(f"{prefix}/fact_checked.md") or storage.exists(f"{prefix}/enriched.md"):
        return "enriching"
    if storage.exists(f"{prefix}/linked.md"):
        return "linking"
    if storage.exists(f"{prefix}/draft.md"):
        return "drafting"
    if storage.exists(f"{prefix}/outline.json"):
        return "outlining"
    return "suggested"


# ── Citability score ─────────────────────────────────────────────────


def _compute_citability_score(eval_data: Optional[Dict[str, Any]]) -> Optional[float]:
    """Derive 0-100 citability score from eval history.

    Uses max overall_score across all cycles, x 100, clamped to [0, 100].
    """
    if not eval_data:
        return None
    cycles = eval_data.get("cycles", [])
    if not cycles:
        return None
    valid = [
        s for c in cycles
        if isinstance((s := c.get("overall_score")), (int, float))
    ]
    if not valid:
        return None
    best = max(valid)
    return min(100.0, max(0.0, round(best * 100, 1)))


# ── Available stages ─────────────────────────────────────────────────


def _get_available_stages(
    storage: StorageBackend, slug: str, brief_id: str,
) -> List[str]:
    """Return list of stages that have files in storage."""
    stages = []
    prefix = f"content/{slug}/content/{brief_id}"
    for stage, (fname, _) in _STAGE_FILES.items():
        if storage.exists(f"{prefix}/{fname}"):
            stages.append(stage)
    return stages


# ── Metadata loading ────────────────────────────────────────────────


def _load_all_pieces(
    storage: StorageBackend, slug: str,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Load pieces from standard + namespaced run_metadata_v13 files.

    Manual-mode parallel runs write ``run_metadata_v13_{brief_id}.json`` instead
    of the standard ``run_metadata_v13.json``.  This function merges pieces from
    all such files, deduplicating by ``brief_id``.

    Returns ``(merged_pieces, session_id)``.
    Standard file takes priority for ``session_id``.
    """
    content_prefix = f"content/{slug}"

    # Standard file
    run_meta = _load_json_cached(storage, f"{content_prefix}/run_metadata_v13.json")
    pieces: List[Dict[str, Any]] = list((run_meta or {}).get("pieces", []))
    session_id: Optional[str] = (run_meta or {}).get("run_metadata", {}).get("session_id")

    # Collect brief_ids already in standard pieces to avoid duplicates
    seen_brief_ids = {p.get("brief_id") for p in pieces}

    # Namespaced files (manual parallel runs) via StorageBackend.list_dir
    try:
        children = storage.list_dir(content_prefix)
    except Exception:
        children = []

    for child in sorted(children):
        fname = child.rsplit("/", 1)[-1] if "/" in child else child
        if fname.startswith("run_metadata_v13_") and fname.endswith(".json"):
            data = _load_json_cached(storage, f"{content_prefix}/{fname}")
            if not data:
                continue
            for p in data.get("pieces", []):
                bid = p.get("brief_id")
                if bid and bid not in seen_brief_ids:
                    pieces.append(p)
                    seen_brief_ids.add(bid)
            if not session_id:
                session_id = (data.get("run_metadata") or {}).get("session_id")

    return pieces, session_id


# ── Public API ───────────────────────────────────────────────────────


def get_briefs(
    artifacts_root: Path, slug: str,
    *, storage: Optional[StorageBackend] = None,
) -> ContentBriefListResponse:
    """List all content briefs with inferred statuses.

    Returns 200 with empty list if content dir doesn't exist (W2).
    """
    _validate_slug(slug)
    sb = _resolve_storage(artifacts_root, storage)
    content_prefix = f"content/{slug}"

    # Check if any content artifacts exist
    if not (
        sb.exists(f"{content_prefix}/blueprints.json")
        or sb.exists(f"{content_prefix}/planner_selections.json")
    ):
        return ContentBriefListResponse(briefs=[], total=0)

    # v1.3 pipeline outputs: blueprints.json (after brief builder) or
    # planner_selections.json (while strategic planner is still running).
    # ContentBlueprint extends ContentBrief, so the same fields are present.
    briefs_data: Optional[Dict[str, Any]] = None

    blueprints_raw = _load_json_cached(sb, f"{content_prefix}/blueprints.json")
    if blueprints_raw and isinstance(blueprints_raw, list) and blueprints_raw:
        briefs_data = {"briefs": blueprints_raw}
    else:
        # Strategic planner in progress — surface topics as early-stage briefs
        planner_data = _load_json_cached(sb, f"{content_prefix}/planner_selections.json")
        if planner_data and isinstance(planner_data, dict):
            selections = planner_data.get("selections", [])
            if selections:
                briefs_data = {"briefs": [
                    {
                        "brief_id": f"brief-{i + 1:03d}",
                        "title": (
                            sel.get("query_texts", [""])[0]
                            or f"Topic {i + 1}"
                        ),
                        "target_cluster": sel.get("cluster_name", ""),
                        "content_format": "long_blog",
                        "word_count_range": [0, 0],
                    }
                    for i, sel in enumerate(selections)
                ]}

    if not briefs_data:
        return ContentBriefListResponse(briefs=[], total=0)

    briefs_list = briefs_data.get("briefs", [])
    if not briefs_list:
        return ContentBriefListResponse(briefs=[], total=0)

    # Load gap analysis data for sidebar enrichment
    analysis_json = load_analysis_json(sb, slug)

    # Load run_metadata for pieces + session_id (standard + namespaced files)
    pieces, session_id = _load_all_pieces(sb, slug)

    # Load pipeline_state.json (stays on local filesystem, not R2)
    pipeline_state = _load_pipeline_state(artifacts_root, slug)
    # Extract brief_id → task_id mapping for frontend HITL approval calls
    task_id_map: Dict[str, str] = {}
    raw_task_ids = pipeline_state.get("__task_ids__")
    if isinstance(raw_task_ids, dict):
        task_id_map = raw_task_ids

    # created_at from blueprint entry if available, else empty
    created_at = ""
    if briefs_list:
        created_at = briefs_list[0].get("_created_at", "")

    items: List[ContentBriefListItem] = []
    for brief in briefs_list:
        brief_id = brief.get("brief_id", "")
        brief_prefix = f"{content_prefix}/content/{brief_id}"

        # Status
        status = _infer_brief_status(brief_id, pieces, sb, slug, pipeline_state=pipeline_state)

        # Content type
        content_type = _map_content_format(brief.get("content_format", "long_blog"))

        # Word count (max of range)
        wc_range = brief.get("word_count_range", [0, 0])
        target_wc = wc_range[1] if isinstance(wc_range, (list, tuple)) and len(wc_range) >= 2 else 0

        # Citability score from eval_history
        eval_data = _load_json_cached(sb, f"{brief_prefix}/eval_history.json")
        citability = _compute_citability_score(eval_data)

        # Gap context for sidebar
        gap_ctx = extract_gap_context(
            brief, analysis_json,
            gap_query_id=brief.get("_gap_query_id", ""),
        )

        brief_created = brief.get("_created_at", created_at)

        items.append(ContentBriefListItem(
            id=brief_id,
            title=brief.get("title", ""),
            status=status,
            content_type=content_type,
            cluster=brief.get("target_cluster", ""),
            target_word_count=target_wc,
            citability_score=citability,
            cycle_id=session_id,
            task_id=task_id_map.get(brief_id),
            created_at=brief_created,
            updated_at=brief_created,
            gap_context=gap_ctx,
        ))

    return ContentBriefListResponse(briefs=items, total=len(items))


def add_brief(
    artifacts_root: Path,
    slug: str,
    title: str,
    cluster: str = "",
    description: str = "",
    source: str = "manual",
    gap_query_id: str = "",
    *,
    storage: Optional[StorageBackend] = None,
) -> ContentBriefListItem:
    """Immediately create a brief entry so it appears in Content Studio.

    Appends to blueprints.json (or creates it). The brief starts with
    status "suggested" and can later be enriched by the content pipeline.
    """
    _validate_slug(slug)
    sb = _resolve_storage(artifacts_root, storage)
    content_prefix = f"content/{slug}"
    bp_key = f"{content_prefix}/blueprints.json"

    # Ensure content directory exists
    sb.mkdir(content_prefix)

    # Load existing blueprints or start fresh
    existing: List[Dict[str, Any]] = []
    raw_content = sb.read(bp_key)
    if raw_content is not None:
        try:
            raw = json.loads(raw_content)
            if isinstance(raw, list):
                existing = raw
        except (json.JSONDecodeError, ValueError):
            pass

    # Determine next brief_id
    existing_ids = {b.get("brief_id", "") for b in existing}
    idx = len(existing) + 1
    while f"brief-{idx:03d}" in existing_ids:
        idx += 1
    brief_id = f"brief-{idx:03d}"

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    # Create minimal blueprint entry
    new_entry: Dict[str, Any] = {
        "brief_id": brief_id,
        "title": title,
        "target_cluster": cluster,
        "content_format": "long_blog",
        "word_count_range": [0, 0],
        "key_topics": [title],
        "key_angles": [],
        "priority_score": 0.0,
        "target_queries": [{"query_text": title, "cluster_name": cluster}],
        "_source": source,
        "_description": description,
        "_created_at": now,
        "_gap_query_id": gap_query_id,
    }

    existing.append(new_entry)
    sb.write(bp_key, json.dumps(existing, indent=2))

    # Invalidate cache for this file (Codex C3: use lock)
    with _CACHE_LOCK:
        _CACHE.pop(bp_key, None)

    return ContentBriefListItem(
        id=brief_id,
        title=title,
        status="suggested",
        content_type="blog",
        cluster=cluster,
        target_word_count=0,
        created_at=now,
        updated_at=now,
    )


def get_brief_detail(
    artifacts_root: Path, slug: str, brief_id: str,
    *, storage: Optional[StorageBackend] = None,
) -> ContentBriefDetailResponse:
    """Get full detail for a single content brief."""
    _validate_slug(slug)
    _validate_brief_id(brief_id)
    sb = _resolve_storage(artifacts_root, storage)
    content_prefix = f"content/{slug}"

    # Check content artifacts exist
    if not (
        sb.exists(f"{content_prefix}/blueprints.json")
        or sb.exists(f"{content_prefix}/planner_selections.json")
    ):
        raise HTTPException(404, f"No content artifacts for company '{slug}'")

    # Load briefs from v1.3 artifacts
    briefs_list: List[Dict[str, Any]] = []
    blueprints_raw = _load_json_cached(sb, f"{content_prefix}/blueprints.json")
    if blueprints_raw and isinstance(blueprints_raw, list):
        briefs_list = blueprints_raw
    else:
        planner_data = _load_json_cached(sb, f"{content_prefix}/planner_selections.json")
        if planner_data and isinstance(planner_data, dict):
            selections = planner_data.get("selections", [])
            briefs_list = [
                {
                    "brief_id": f"brief-{i + 1:03d}",
                    "title": sel.get("query_texts", [""])[0] or f"Topic {i + 1}",
                    "target_cluster": sel.get("cluster_name", ""),
                    "content_format": "long_blog",
                    "word_count_range": [0, 0],
                }
                for i, sel in enumerate(selections)
            ]
    if not briefs_list:
        raise HTTPException(404, f"No content briefs for company '{slug}'")

    # Find the brief
    brief = None
    for b in briefs_list:
        if b.get("brief_id") == brief_id:
            brief = b
            break
    if brief is None:
        raise HTTPException(404, f"Brief '{brief_id}' not found for company '{slug}'")

    # Run metadata pieces (standard + namespaced files)
    pieces, _session_id = _load_all_pieces(sb, slug)

    # Pipeline state for in-progress statuses (stays on local filesystem)
    pipeline_state = _load_pipeline_state(artifacts_root, slug)

    # Status
    status = _infer_brief_status(brief_id, pieces, sb, slug, pipeline_state=pipeline_state)

    # Content type
    content_type = _map_content_format(brief.get("content_format", "long_blog"))

    # Word count range
    wc_range = brief.get("word_count_range", [0, 0])
    if isinstance(wc_range, (list, tuple)) and len(wc_range) >= 2:
        target_wc = {"min": wc_range[0], "max": wc_range[1]}
    else:
        target_wc = {"min": 0, "max": 0}

    # Structural targets
    structural = brief.get("structural_targets", {})

    # Eval history
    brief_prefix = f"{content_prefix}/content/{brief_id}"
    eval_data = _load_json_cached(sb, f"{brief_prefix}/eval_history.json")
    eval_history: List[EvalCycle] = []
    final_passed = False
    if eval_data:
        final_passed = eval_data.get("final_passed", False)
        for cycle in eval_data.get("cycles", []):
            dims = [
                EvalDimension(
                    dimension=d.get("dimension", ""),
                    passed=d.get("passed", False),
                    score=d.get("score", 0.0),
                    feedback=d.get("feedback", ""),
                )
                for d in cycle.get("dimensions", [])
            ]
            eval_history.append(EvalCycle(
                cycle=cycle.get("cycle", 0),
                dimensions=dims,
                overall_passed=cycle.get("overall_passed", False),
                overall_score=cycle.get("overall_score", 0.0),
            ))

    # Citability
    citability = _compute_citability_score(eval_data)

    # Exemplars
    exemplars = [
        BriefExemplar(
            url=e.get("url", ""),
            word_count=e.get("word_count", 0),
            authority_type=e.get("authority_type", ""),
            content_type=e.get("content_type", ""),
            snippet=e.get("snippet", ""),
        )
        for e in brief.get("exemplar_summaries", [])
    ]

    # Available stages
    available = _get_available_stages(sb, slug, brief_id)

    return ContentBriefDetailResponse(
        id=brief_id,
        title=brief.get("title", ""),
        status=status,
        content_type=content_type,
        cluster=brief.get("target_cluster", ""),
        target_word_count=target_wc,
        structural_targets=structural,
        key_topics=brief.get("key_topics", []),
        key_angles=brief.get("key_angles", []),
        priority_score=brief.get("priority_score", 0.0),
        citability_score=citability,
        eval_history=eval_history,
        final_passed=final_passed,
        exemplars=exemplars,
        available_stages=available,
    )


def get_brief_stage_content(
    artifacts_root: Path, slug: str, brief_id: str, stage: str,
    *, storage: Optional[StorageBackend] = None,
) -> StageContentResponse:
    """Get stage-specific file content for a brief."""
    _validate_slug(slug)
    _validate_brief_id(brief_id)

    if stage not in _VALID_STAGES:
        raise HTTPException(400, f"Invalid stage '{stage}'. Valid: {sorted(_VALID_STAGES)}")

    sb = _resolve_storage(artifacts_root, storage)
    content_prefix = f"content/{slug}"

    # Check content artifacts exist
    if not (
        sb.exists(f"{content_prefix}/blueprints.json")
        or sb.exists(f"{content_prefix}/planner_selections.json")
    ):
        raise HTTPException(404, f"No content artifacts for company '{slug}'")

    # Path traversal guard: reject symlinks on local filesystem (defense-in-depth)
    brief_dir = artifacts_root / "content" / slug / "content" / brief_id
    if brief_dir.is_symlink():
        raise HTTPException(400, f"Invalid brief_id: '{brief_id}'")

    filename, mime_type = _STAGE_FILES[stage]
    key = f"{content_prefix}/content/{brief_id}/{filename}"

    raw = sb.read(key)
    if raw is None:
        raise HTTPException(404, f"Stage '{stage}' not found for brief '{brief_id}'")

    # For JSON stages, return parsed dict (W3: avoid double-encoding)
    if mime_type == "application/json":
        try:
            content: Any = json.loads(raw)
        except json.JSONDecodeError:
            raise HTTPException(422, f"Corrupted {stage} data for brief '{brief_id}'")
    else:
        content = raw

    return StageContentResponse(
        brief_id=brief_id,
        stage=stage,
        content_type=mime_type,
        content=content,
    )
