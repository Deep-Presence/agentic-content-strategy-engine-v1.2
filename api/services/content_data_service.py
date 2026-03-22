"""Service layer for content data endpoints (Phase 3).

Reads content pipeline v1.3 artifacts from disk (blueprints.json,
planner_selections.json, run_metadata.json, per-brief stage files),
reshapes them to match the frontend TypeScript types, and infers brief
statuses from artifacts + run metadata.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timezone
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

logger = logging.getLogger(__name__)

# ── Caching ──────────────────────────────────────────────────────────

_CACHE: Dict[Tuple[str, str], Tuple[int, Any]] = {}
_CACHE_MAX_ENTRIES = 10
_CACHE_LOCK = threading.Lock()  # C6: protects compound check-evict-insert


def _load_pipeline_state(content_root: Path, slug: str) -> Dict[str, Any]:
    """Load pipeline state from Redis (preferred) or file (fallback).

    When ``redis_pipeline_state`` is enabled and Redis is healthy, reads
    from the ``pipeline_state:{slug}`` Redis Hash. If Redis returns an
    empty dict, also consults the file (handles migration window where
    old runs wrote to file before Redis was enabled). Falls back to file
    entirely on Redis error or when disabled.
    """
    from core.config.settings import settings

    if settings.redis_pipeline_state and settings.redis_url:
        try:
            from core.redis import get_sync_redis_or_none
            from core.content_engine.state_redis import read_pipeline_state_redis

            rc = get_sync_redis_or_none()
            if rc is not None:
                result = read_pipeline_state_redis(rc, slug)
                if result:
                    return result
                # Redis empty — check file too (migration window)
        except Exception:
            logger.warning(
                "Redis pipeline state read failed — falling back to file",
                exc_info=True,
            )
    return _load_json_cached(content_root, "pipeline_state.json") or {}


def _load_json_cached(base_dir: Path, filename: str) -> Optional[Any]:
    """Load and parse a JSON file with mtime-based cache invalidation."""
    file_path = base_dir / filename

    # CX-9: guard stat() — eliminates TOCTOU between is_file() and stat()
    try:
        mtime_ns = file_path.stat().st_mtime_ns
    except (FileNotFoundError, OSError):
        return None

    cache_key = (str(base_dir), filename)

    cached = _CACHE.get(cache_key)
    if cached is not None and cached[0] == mtime_ns:
        return cached[1]

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to parse %s: %s", file_path, exc)
        return None

    # C6: lock protects the compound check-evict-insert against concurrent writes
    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_MAX_ENTRIES and cache_key not in _CACHE:
            oldest_key = next(iter(_CACHE))
            del _CACHE[oldest_key]
        _CACHE[cache_key] = (mtime_ns, data)
    return data


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


def _content_dir(artifacts_root: Path, slug: str) -> Path:
    return artifacts_root / "content" / slug


def _require_content_dir(artifacts_root: Path, slug: str) -> Path:
    _validate_slug(slug)
    d = _content_dir(artifacts_root, slug)
    if not d.is_dir():
        raise HTTPException(404, f"No content artifacts for company '{slug}'")
    return d


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


def _mtime_iso(path: Path) -> str:
    """Get file modification time as ISO string."""
    try:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except (OSError, ValueError):
        return ""


def _latest_stage_mtime(brief_dir: Path) -> str:
    """Get the latest mtime among stage files in a brief directory."""
    latest = 0.0
    for fname, _ in _STAGE_FILES.values():
        fp = brief_dir / fname
        if fp.is_file():
            latest = max(latest, fp.stat().st_mtime)
    if latest > 0:
        return datetime.fromtimestamp(latest, tz=timezone.utc).isoformat()
    return ""


# ── Status inference ─────────────────────────────────────────────────


def _infer_brief_status(
    brief_id: str,
    pieces: List[Dict[str, Any]],
    content_dir: Path,
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

    # Phase 2: File-based inference
    brief_dir = content_dir / "content" / brief_id
    if (brief_dir / "final.md").exists():
        return "completed"
    if (brief_dir / "eval_history.json").exists():
        try:
            eh = json.loads((brief_dir / "eval_history.json").read_text())
            if eh.get("final_passed", False):
                return "review"
        except (json.JSONDecodeError, KeyError, OSError):
            pass
        return "evaluating"
    if (brief_dir / "fact_checked.md").exists() or (brief_dir / "enriched.md").exists():
        return "enriching"
    if (brief_dir / "linked.md").exists():
        return "linking"
    if (brief_dir / "draft.md").exists():
        return "drafting"
    if (brief_dir / "outline.json").exists():
        return "outlining"
    return "suggested"


# ── Citability score ─────────────────────────────────────────────────


def _compute_citability_score(eval_data: Optional[Dict[str, Any]]) -> Optional[float]:
    """Derive 0-100 citability score from eval history.

    Uses max overall_score across all cycles, × 100, clamped to [0, 100].
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


def _get_available_stages(brief_dir: Path) -> List[str]:
    """Return list of stages that have files on disk."""
    stages = []
    for stage, (fname, _) in _STAGE_FILES.items():
        if (brief_dir / fname).is_file():
            stages.append(stage)
    return stages


# ── Metadata loading ────────────────────────────────────────────────


def _load_all_pieces(content_root: Path) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Load pieces from standard + namespaced run_metadata_v13 files.

    Manual-mode parallel runs write ``run_metadata_v13_{brief_id}.json`` instead
    of the standard ``run_metadata_v13.json``.  This function merges pieces from
    all such files, deduplicating by ``brief_id``.

    Returns ``(merged_pieces, session_id)``.
    Standard file takes priority for ``session_id``.
    """
    # Standard file
    run_meta = _load_json_cached(content_root, "run_metadata_v13.json")
    pieces: List[Dict[str, Any]] = list((run_meta or {}).get("pieces", []))
    session_id: Optional[str] = (run_meta or {}).get("run_metadata", {}).get("session_id")

    # Collect brief_ids already in standard pieces to avoid duplicates
    seen_brief_ids = {p.get("brief_id") for p in pieces}

    # Namespaced files (manual parallel runs)
    for meta_path in sorted(content_root.glob("run_metadata_v13_*.json")):
        data = _load_json_cached(content_root, meta_path.name)
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


def get_briefs(artifacts_root: Path, slug: str) -> ContentBriefListResponse:
    """List all content briefs with inferred statuses.

    Returns 200 with empty list if content dir doesn't exist (W2).
    """
    _validate_slug(slug)
    content_root = _content_dir(artifacts_root, slug)
    if not content_root.is_dir():
        return ContentBriefListResponse(briefs=[], total=0)

    # v1.3 pipeline outputs: blueprints.json (after brief builder) or
    # planner_selections.json (while strategic planner is still running).
    # ContentBlueprint extends ContentBrief, so the same fields are present.
    briefs_data: Optional[Dict[str, Any]] = None

    blueprints_raw = _load_json_cached(content_root, "blueprints.json")
    if blueprints_raw and isinstance(blueprints_raw, list) and blueprints_raw:
        briefs_data = {"briefs": blueprints_raw}
    else:
        # Strategic planner in progress — surface topics as early-stage briefs
        planner_data = _load_json_cached(content_root, "planner_selections.json")
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
    analysis_json = load_analysis_json(artifacts_root, slug)

    # Load run_metadata for pieces + session_id (standard + namespaced files)
    pieces, session_id = _load_all_pieces(content_root)

    # Load pipeline state — Redis first (when configured), file fallback
    pipeline_state = _load_pipeline_state(content_root, slug)
    # Extract brief_id → task_id mapping for frontend HITL approval calls
    task_id_map: Dict[str, str] = {}
    raw_task_ids = pipeline_state.get("__task_ids__")
    if isinstance(raw_task_ids, dict):
        task_id_map = raw_task_ids

    # Use mtime of the source artifact as created_at
    for _fname in ("blueprints.json", "planner_selections.json"):
        _src = content_root / _fname
        if _src.is_file():
            created_at = _mtime_iso(_src)
            break
    else:
        created_at = ""

    items: List[ContentBriefListItem] = []
    for brief in briefs_list:
        brief_id = brief.get("brief_id", "")
        brief_dir = content_root / "content" / brief_id

        # Status
        status = _infer_brief_status(brief_id, pieces, content_root, pipeline_state=pipeline_state)

        # Content type
        content_type = _map_content_format(brief.get("content_format", "long_blog"))

        # Word count (max of range)
        wc_range = brief.get("word_count_range", [0, 0])
        target_wc = wc_range[1] if isinstance(wc_range, (list, tuple)) and len(wc_range) >= 2 else 0

        # Citability score from eval_history
        eval_data = _load_json_cached(
            brief_dir, "eval_history.json"
        ) if brief_dir.is_dir() else None
        citability = _compute_citability_score(eval_data)

        # Updated at (latest stage file mtime)
        updated_at = _latest_stage_mtime(brief_dir) if brief_dir.is_dir() else created_at

        # Gap context for sidebar
        gap_ctx = extract_gap_context(
            brief, analysis_json,
            gap_query_id=brief.get("_gap_query_id", ""),
        )

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
            created_at=created_at,
            updated_at=updated_at or created_at,
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
) -> ContentBriefListItem:
    """Immediately create a brief entry on disk so it appears in Content Studio.

    Appends to blueprints.json (or creates it). The brief starts with
    status "suggested" and can later be enriched by the content pipeline.
    """
    _validate_slug(slug)
    content_root = _content_dir(artifacts_root, slug)
    content_root.mkdir(parents=True, exist_ok=True)

    # Load existing blueprints or start fresh
    bp_path = content_root / "blueprints.json"
    existing: List[Dict[str, Any]] = []
    if bp_path.is_file():
        try:
            raw = json.loads(bp_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                existing = raw
        except (json.JSONDecodeError, OSError):
            pass

    # Determine next brief_id
    existing_ids = {b.get("brief_id", "") for b in existing}
    idx = len(existing) + 1
    while f"brief-{idx:03d}" in existing_ids:
        idx += 1
    brief_id = f"brief-{idx:03d}"

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
    bp_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    # Invalidate cache for this file
    cache_key = (str(content_root), "blueprints.json")
    _CACHE.pop(cache_key, None)

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
    artifacts_root: Path, slug: str, brief_id: str
) -> ContentBriefDetailResponse:
    """Get full detail for a single content brief."""
    _validate_slug(slug)
    _validate_brief_id(brief_id)
    content_root = _require_content_dir(artifacts_root, slug)

    # Load briefs from v1.3 artifacts
    briefs_list: List[Dict[str, Any]] = []
    blueprints_raw = _load_json_cached(content_root, "blueprints.json")
    if blueprints_raw and isinstance(blueprints_raw, list):
        briefs_list = blueprints_raw
    else:
        planner_data = _load_json_cached(content_root, "planner_selections.json")
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
    pieces, _session_id = _load_all_pieces(content_root)

    # Pipeline state — Redis first, file fallback
    pipeline_state = _load_pipeline_state(content_root, slug)

    # Status
    status = _infer_brief_status(brief_id, pieces, content_root, pipeline_state=pipeline_state)

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
    brief_dir = content_root / "content" / brief_id
    eval_data = _load_json_cached(brief_dir, "eval_history.json") if brief_dir.is_dir() else None
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
    available = _get_available_stages(brief_dir) if brief_dir.is_dir() else []

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
    artifacts_root: Path, slug: str, brief_id: str, stage: str
) -> StageContentResponse:
    """Get stage-specific file content for a brief."""
    _validate_slug(slug)
    _validate_brief_id(brief_id)

    if stage not in _VALID_STAGES:
        raise HTTPException(400, f"Invalid stage '{stage}'. Valid: {sorted(_VALID_STAGES)}")

    content_root = _require_content_dir(artifacts_root, slug)
    brief_dir = content_root / "content" / brief_id

    # Path traversal guard: reject symlinks and ensure resolved path is under content_root
    if brief_dir.is_symlink():
        raise HTTPException(400, f"Invalid brief_id: '{brief_id}'")
    resolved = brief_dir.resolve()
    if not resolved.is_relative_to(content_root.resolve()):
        raise HTTPException(400, f"Invalid brief_id: '{brief_id}'")

    filename, mime_type = _STAGE_FILES[stage]
    file_path = brief_dir / filename

    if not file_path.is_file():
        raise HTTPException(404, f"Stage '{stage}' not found for brief '{brief_id}'")

    raw = file_path.read_text(encoding="utf-8")

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
