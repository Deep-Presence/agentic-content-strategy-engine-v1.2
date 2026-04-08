"""DbContentDataService — Postgres-backed implementation of ContentDataServiceProtocol.

Reads content brief metadata from content_pieces table via ContentRepository.
Stage content reads via StorageBackend (R2 in prod, local in dev).
Pipeline state is read from Redis exclusively (no file fallback).
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid as _uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from api.schemas.content_data import (
    ContentBriefDetailResponse,
    ContentBriefListItem,
    ContentBriefListResponse,
    StageContentResponse,
)
from core.db.enums import ContentArtifactStage, ContentPieceStatus, PipelineType
from core.services.gap_context_helper import extract_gap_context, load_analysis_json
from core.db.repositories.content_artifact_repo import ContentArtifactRepository
from core.db.repositories.content_repo import ContentRepository
from core.db.repositories.pipeline_repo import PipelineRepository

logger = logging.getLogger(__name__)


# Map ContentPieceStatus → frontend display status
_PIECE_STATUS_MAP = {
    "planned": "suggested",
    "drafting": "drafting",
    "review": "review",
    "approved": "completed",  # HITL-3 approved → Approved/Published column
    "published": "published",
    "archived": "published",
}

# Map backend content_type to frontend display type
_FORMAT_TO_TYPE = {
    "long_blog": "blog",
    "short_faq": "blog",
    "pillar_page": "guide",
    "comparison": "guide",
    "how_to": "guide",
}


class DbContentDataService:
    """Postgres-backed content data service.

    - ``get_briefs`` reads from content_pieces table
    - ``get_brief_detail`` reads from content_pieces table
    - ``get_brief_stage_content`` reads via DB artifact metadata → StorageBackend
    """

    def __init__(
        self,
        content_repo: ContentRepository,
        pipeline_repo: PipelineRepository,
        artifacts_root: Path,
        artifact_repo: Optional[ContentArtifactRepository] = None,
        *,
        backend: Optional["StorageBackend"] = None,
    ) -> None:
        self._content_repo = content_repo
        self._pipeline_repo = pipeline_repo
        self._artifacts_root = artifacts_root
        self._artifact_repo = artifact_repo
        if backend is not None:
            self._backend = backend
        else:
            from core.storage import get_storage_backend
            self._backend = get_storage_backend(artifacts_root)

    async def _resolve_run_id(self, effective_slug: str) -> Optional[str]:
        """Resolve effective_slug → latest completed content run id."""
        run = await self._pipeline_repo.get_latest_completed(
            effective_slug, PipelineType.content,
        )
        return str(run.id) if run else None

    # ── Brief List (DB-backed) ───────────────────────────────────────

    async def get_briefs(
        self, effective_slug: str,
    ) -> ContentBriefListResponse:
        """List content pieces from the DB (including pre-pipeline planned briefs).

        Also merges GA-phase cards from Redis (topic assignments undergoing
        gap analysis that don't yet have DB content_pieces rows).
        """
        # ── Load GA-phase cards from Redis FIRST (before early-return) ──
        ga_cards: List[ContentBriefListItem] = []
        try:
            ga_cards = await self._load_ga_phase_cards(effective_slug)
        except Exception:
            logger.warning(
                "GA-phase card load failed for %s", effective_slug, exc_info=True,
            )

        # Resolve run_id for cycle_id display (may be None for pre-pipeline briefs)
        run_id = await self._resolve_run_id(effective_slug)

        # Query by effective_slug to include run_id=NULL pieces from add_brief()
        pieces = await self._content_repo.list_by_slug(effective_slug)
        if not pieces and run_id:
            # Fallback: try run-scoped query for backward compat
            pieces = await self._content_repo.list_by_run(run_id)
        if not pieces and not ga_cards:
            return ContentBriefListResponse(briefs=[], total=0)
        if not pieces:
            # Only GA-phase cards exist — return them
            return ContentBriefListResponse(briefs=ga_cards, total=len(ga_cards))

        # Load gap analysis data for sidebar enrichment via StorageBackend
        # Derive base company slug from effective_slug for gap analysis lookup
        base_slug = effective_slug.split("__")[0] if "__" in effective_slug else effective_slug
        analysis_json = await asyncio.to_thread(
            load_analysis_json, self._backend, base_slug,
        )

        # Load pipeline state — Redis only (no file fallback).
        # When Redis is empty/unavailable, status comes from DB content_pieces.status.
        # File fallback removed: stale cross-run entries caused 4-min kanban lag.
        pipeline_state: Dict[str, Any] = {}
        from core.config.settings import settings as _cfg

        if _cfg.redis_pipeline_state and _cfg.redis_url:
            try:
                from core.redis import get_redis_or_none
                from core.content_engine.state_redis import read_pipeline_state_redis_async

                rc = get_redis_or_none()
                if rc is not None:
                    pipeline_state = await read_pipeline_state_redis_async(rc, effective_slug)
            except Exception:
                logger.warning(
                    "Redis pipeline state read failed for %s", effective_slug,
                    exc_info=True,
                )
        if pipeline_state:
            logger.info(
                "get_briefs: pipeline_state from Redis for %s: %s",
                effective_slug,
                {k: v for k, v in pipeline_state.items() if not k.startswith("__")},
            )

        # Extract brief_id → task_id mapping for frontend HITL approval calls
        task_id_map: Dict[str, str] = {}
        raw_task_ids = pipeline_state.get("__task_ids__")
        if isinstance(raw_task_ids, dict):
            task_id_map = raw_task_ids

        items: List[ContentBriefListItem] = []
        for piece in pieces:
            # Status mapping: Redis pipeline_state overrides DB status
            brief_id = piece.brief_id or ""
            ps_status = pipeline_state.get(brief_id)
            if isinstance(ps_status, str):
                display_status = ps_status
            else:
                raw_status = piece.status.value if piece.status else "planned"
                display_status = _PIECE_STATUS_MAP.get(raw_status, "suggested")
                logger.debug(
                    "get_briefs: brief %s — no Redis override, DB status=%s → display=%s",
                    brief_id, raw_status, display_status,
                )

            # Content type mapping
            content_type = _FORMAT_TO_TYPE.get(
                piece.content_type or "long_blog", "blog",
            )

            # Word count
            word_count = piece.word_count or 0

            # Citability score (stored as 0-1 in DB, display as 0-100)
            citability: Optional[float] = None
            if piece.citability_score is not None:
                score = piece.citability_score
                # If stored as 0-1, multiply by 100; if already 0-100, keep as-is
                citability = min(100.0, max(0.0, round(
                    score * 100 if score <= 1.0 else score, 1,
                )))

            # Cluster from evaluation_results JSONB or cluster_name column
            cluster = piece.cluster_name or ""

            # Gap context for sidebar (filesystem-based enrichment)
            brief_dict = {"title": piece.title or "", "target_cluster": cluster}
            gap_ctx = extract_gap_context(brief_dict, analysis_json)

            # Use filesystem brief_id when available — this is what the pipeline,
            # artifact directories, and HITL approval endpoints use. Fall back
            # to DB UUID only when brief_id was never set.
            display_id = piece.brief_id or str(piece.id)

            items.append(ContentBriefListItem(
                id=display_id,
                display_id=display_id,
                title=piece.title or "",
                status=display_status,
                content_type=content_type,
                cluster=cluster,
                target_word_count=word_count,
                citability_score=citability,
                cycle_id=str(run_id) if run_id else str(piece.run_id or ""),
                task_id=task_id_map.get(brief_id),
                created_at=piece.created_at.isoformat() if piece.created_at else "",
                updated_at=(
                    piece.updated_at.isoformat()
                    if hasattr(piece, "updated_at") and piece.updated_at
                    else (piece.created_at.isoformat() if piece.created_at else "")
                ),
                gap_context=gap_ctx,
                published_url=piece.published_url or "",
                published_at=(
                    piece.published_at.isoformat()
                    if hasattr(piece, "published_at") and piece.published_at
                    else None
                ),
            ))

        # Dedup: filter out GA cards whose topic_assignment_id already has
        # a DB content piece (prevents transient duplication when
        # cleanup_ga_phase_state fails after persist_blueprints_early).
        piece_ta_ids: set[str] = set()
        for piece in pieces:
            ta_id = getattr(piece, "topic_assignment_id", None)
            if ta_id is not None:
                piece_ta_ids.add(str(ta_id))
        if piece_ta_ids:
            ga_cards = [
                card for card in ga_cards
                if card.topic_assignment_id not in piece_ta_ids
            ]

        # Prepend GA-phase cards (Queue column) before DB brief cards
        all_items = ga_cards + items
        return ContentBriefListResponse(briefs=all_items, total=len(all_items))

    # ── GA-phase card loader ─────────────────────────────────────────

    async def _load_ga_phase_cards(
        self, effective_slug: str,
    ) -> List[ContentBriefListItem]:
        """Load GA-phase topic assignment cards from Redis.

        These are cards for topics undergoing gap analysis that don't yet
        have content_pieces DB rows. They appear in the Content Studio Queue.
        """
        from core.config.settings import settings as _cfg

        if not (_cfg.redis_pipeline_state and _cfg.redis_url):
            return []

        from core.redis import get_redis_or_none
        from core.content_engine.state_redis import read_ga_phase_cards_async

        rc = get_redis_or_none()
        if rc is None:
            return []

        raw_cards = await read_ga_phase_cards_async(rc, effective_slug)
        if not raw_cards:
            return []

        items: List[ContentBriefListItem] = []
        for card in raw_cards:
            items.append(ContentBriefListItem(
                id=card["id"],  # ta-{uuid}
                display_id=card.get("display_id", ""),
                title=card.get("title", ""),
                status=card["status"],
                content_type="blog",  # default, will be determined by Brief Builder later
                cluster=card.get("cluster", ""),
                task_id=card.get("task_id"),
                priority_score=card.get("priority_score", 0.0),
                topic_assignment_id=card.get("topic_assignment_id"),
                buyer_stage=card.get("buyer_stage"),
                source="planner",
                ga_run_id=card.get("ga_run_id"),
                effective_slug=effective_slug,
                # Enriched topic assignment metadata
                intent_type=card.get("intent_type"),
                persona_name=card.get("persona_name"),
                persona_id=card.get("persona_id"),
                persona_affinity=card.get("persona_affinity"),
                priority_factors=card.get("priority_factors"),
                content_format=card.get("content_format"),
                estimated_word_count=card.get("estimated_word_count"),
                citation_opportunity=card.get("citation_opportunity"),
                description=card.get("description"),
                target_keywords=card.get("target_keywords"),
                content_angle=card.get("content_angle"),
            ))
        return items

    # ── Brief Detail (DB-backed) ─────────────────────────────────────

    async def get_brief_detail(
        self, effective_slug: str, brief_id: str,
    ) -> ContentBriefDetailResponse:
        """Get full detail for a single content piece from DB.

        Accepts both filesystem brief IDs (e.g. "brief-017") and DB UUIDs.
        Tries slug+brief_id lookup first, falls back to run-scoped UUID lookup.
        """
        # Try filesystem brief_id lookup first (handles "brief-NNN" IDs)
        piece = await self._content_repo.get_by_slug_and_brief_id(
            effective_slug, brief_id,
        )

        # Fallback: try UUID-based lookup via run_id (legacy path)
        if piece is None:
            run_id = await self._resolve_run_id(effective_slug)
            if run_id:
                try:
                    piece = await self._content_repo.get_piece_detail(run_id, brief_id)
                except (ValueError, Exception):
                    pass  # brief_id is not a valid UUID — already tried slug lookup

        if piece is None:
            raise HTTPException(
                404, f"Brief '{brief_id}' not found for '{effective_slug}'",
            )

        # Status
        raw_status = piece.status.value if piece.status else "planned"
        display_status = _PIECE_STATUS_MAP.get(raw_status, "suggested")

        # Content type
        content_type = _FORMAT_TO_TYPE.get(
            piece.content_type or "long_blog", "blog",
        )

        # Eval history from evaluation_results JSONB
        eval_results = piece.evaluation_results or {}
        eval_history = eval_results.get("eval_history", [])
        final_passed = eval_results.get("final_passed", False)

        # Citability
        citability: Optional[float] = None
        if piece.citability_score is not None:
            score = piece.citability_score
            citability = min(100.0, max(0.0, round(
                score * 100 if score <= 1.0 else score, 1,
            )))

        # Extract structured data from evaluation_results JSONB
        word_count_range = eval_results.get(
            "word_count_range", {"min": 0, "max": piece.word_count or 0},
        )
        structural_targets = eval_results.get("structural_targets", {})
        key_topics = eval_results.get("key_topics", [])
        key_angles = eval_results.get("key_angles", [])
        priority_score = eval_results.get("priority_score", 0.0)
        exemplars = eval_results.get("exemplars", [])

        # StorageBackend fallback: if DB has no blueprint data (common for
        # newly created briefs), read from blueprints.json via StorageBackend.
        fs_brief_id = piece.brief_id or brief_id
        if not key_topics and not key_angles:
            bp_key = f"content/{effective_slug}/blueprints.json"
            bp_raw = self._backend.read(bp_key)
            if bp_raw is not None:
                try:
                    bp_list = json.loads(bp_raw)
                    if isinstance(bp_list, list):
                        bp_entry = next(
                            (b for b in bp_list if b.get("brief_id") == fs_brief_id),
                            None,
                        )
                        if bp_entry:
                            key_topics = bp_entry.get("key_topics", key_topics)
                            key_angles = bp_entry.get("key_angles", key_angles)
                            structural_targets = structural_targets or bp_entry.get("structural_targets", {})
                            wc_range = bp_entry.get("word_count_range", [0, 0])
                            if isinstance(wc_range, (list, tuple)) and len(wc_range) >= 2:
                                word_count_range = {"min": wc_range[0], "max": wc_range[1]}
                            priority_score = priority_score or bp_entry.get("priority_score", 0.0)
                except (json.JSONDecodeError, OSError):
                    pass

        return ContentBriefDetailResponse(
            id=piece.brief_id or str(piece.id),
            title=piece.title or "",
            status=display_status,
            content_type=content_type,
            cluster=piece.cluster_name or "",
            target_word_count=word_count_range,
            structural_targets=structural_targets,
            key_topics=key_topics,
            key_angles=key_angles,
            priority_score=priority_score,
            citability_score=citability,
            eval_history=eval_history,
            final_passed=final_passed,
            exemplars=exemplars,
            available_stages=await self._get_available_stages(piece.id)
        )

    async def _get_available_stages(self, piece_id: _uuid.UUID) -> list[str]:
        """Query artifact table for available stages."""
        if not self._artifact_repo:
            return []
        try:
            artifacts = await self._artifact_repo.list_by_piece(piece_id)
            return [a.stage.value for a in artifacts]
        except Exception:
            return []

    # ── Stage Content (DB metadata → StorageBackend, filesystem fallback) ──

    _API_TO_ARTIFACT_STAGE = {
        "outline": ContentArtifactStage.outline,
        "draft": ContentArtifactStage.draft,
        "linked": ContentArtifactStage.linked,
        "enriched": ContentArtifactStage.enriched,
        "formatted": ContentArtifactStage.enriched,  # v1.0 compat alias
        "eval_history": ContentArtifactStage.eval_history,
        "final": ContentArtifactStage.final,
    }

    async def get_brief_stage_content(
        self, effective_slug: str, brief_id: str, stage: str,
    ) -> StageContentResponse:
        """Read stage content via DB artifact metadata → StorageBackend.

        Falls back to filesystem heuristic if DB artifact row is missing.
        """
        # Try DB path: artifact metadata → StorageBackend
        if self._artifact_repo and stage in self._API_TO_ARTIFACT_STAGE:
            try:
                piece = await self._content_repo.get_by_slug_and_brief_id(
                    effective_slug, brief_id,
                )
                if piece:
                    artifact_stage = self._API_TO_ARTIFACT_STAGE[stage]
                    artifact = await self._artifact_repo.get_by_piece_and_stage(
                        piece.id, artifact_stage,
                    )
                    if artifact:
                        content = self._backend.read(artifact.storage_key)
                        if content is not None:
                            if artifact.content_type == "application/json":
                                try:
                                    parsed = json.loads(content)
                                    return StageContentResponse(
                                        brief_id=brief_id, stage=stage,
                                        content_type=artifact.content_type,
                                        content=parsed,
                                    )
                                except json.JSONDecodeError:
                                    pass
                            return StageContentResponse(
                                brief_id=brief_id, stage=stage,
                                content_type=artifact.content_type,
                                content=content,
                            )
            except Exception:
                logger.warning(
                    "DB artifact lookup failed for %s/%s/%s — falling back to StorageBackend",
                    effective_slug, brief_id, stage, exc_info=True,
                )

        # Fallback: StorageBackend-based heuristic (backward compat)
        from api.services.content_data_service import get_brief_stage_content

        return await asyncio.to_thread(
            get_brief_stage_content,
            self._artifacts_root,
            effective_slug,
            brief_id,
            stage,
            storage=self._backend,
        )

    # ── Add Brief (filesystem-backed) ─────────────────────────────

    async def add_brief(
        self,
        effective_slug: str,
        title: str,
        cluster: str = "",
        description: str = "",
        source: str = "manual",
        gap_query_id: str = "",
    ) -> ContentBriefListItem:
        """Create a brief entry via StorageBackend AND in DB.

        StorageBackend write (blueprints.json) is the source of truth for
        Content Studio. DB row (status=planned) enables DB-backed queries.
        """
        from api.services.content_data_service import add_brief

        item = await asyncio.to_thread(
            add_brief,
            self._artifacts_root,
            effective_slug,
            title,
            cluster,
            description,
            source,
            gap_query_id,
            storage=self._backend,
        )

        # DB write (additive) — create ContentPieceModel with status=planned
        try:
            await self._content_repo.create_piece(
                effective_slug=effective_slug,
                brief_id=item.id,
                title=title,
                cluster_name=cluster,
                content_type="long_blog",
                status=ContentPieceStatus.planned,
                word_count=0,
            )
        except Exception:
            logger.warning(
                "add_brief: DB write failed for %s/%s — brief exists on filesystem",
                effective_slug, item.id, exc_info=True,
            )

        return item
