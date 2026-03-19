"""DbContentDataService — Postgres-backed implementation of ContentDataServiceProtocol.

Reads content brief metadata from content_pieces table via ContentRepository.
Stage content files (outline.json, draft.md, etc.) remain filesystem-backed
since they are large blobs read as whole units.
"""
from __future__ import annotations

import asyncio
import logging
import uuid as _uuid
from pathlib import Path
from typing import List, Optional

from fastapi import HTTPException

from api.schemas.content_data import (
    ContentBriefDetailResponse,
    ContentBriefListItem,
    ContentBriefListResponse,
    StageContentResponse,
)
from core.db.enums import ContentArtifactStage, ContentPieceStatus, PipelineType
from core.db.repositories.content_artifact_repo import ContentArtifactRepository
from core.db.repositories.content_repo import ContentRepository
from core.db.repositories.pipeline_repo import PipelineRepository

logger = logging.getLogger(__name__)


# Map ContentPieceStatus → frontend display status
_PIECE_STATUS_MAP = {
    "planned": "suggested",
    "drafting": "drafting",
    "review": "review",
    "approved": "approved",
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
    - ``get_brief_stage_content`` delegates to filesystem (large blob files)
    """

    def __init__(
        self,
        content_repo: ContentRepository,
        pipeline_repo: PipelineRepository,
        artifacts_root: Path,
        artifact_repo: Optional[ContentArtifactRepository] = None,
    ) -> None:
        self._content_repo = content_repo
        self._pipeline_repo = pipeline_repo
        self._artifacts_root = artifacts_root
        self._artifact_repo = artifact_repo

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
        """List content pieces from the DB (including pre-pipeline planned briefs)."""
        # Resolve run_id for cycle_id display (may be None for pre-pipeline briefs)
        run_id = await self._resolve_run_id(effective_slug)

        # Query by effective_slug to include run_id=NULL pieces from add_brief()
        pieces = await self._content_repo.list_by_slug(effective_slug)
        if not pieces and run_id:
            # Fallback: try run-scoped query for backward compat
            pieces = await self._content_repo.list_by_run(run_id)
        if not pieces:
            return ContentBriefListResponse(briefs=[], total=0)

        items: List[ContentBriefListItem] = []
        for piece in pieces:
            # Status mapping
            raw_status = piece.status.value if piece.status else "planned"
            display_status = _PIECE_STATUS_MAP.get(raw_status, "suggested")

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

            items.append(ContentBriefListItem(
                id=str(piece.id),
                title=piece.title or "",
                status=display_status,
                content_type=content_type,
                cluster=cluster,
                target_word_count=word_count,
                citability_score=citability,
                cycle_id=str(run_id) if run_id else str(piece.run_id or ""),
                created_at=piece.created_at.isoformat() if piece.created_at else "",
                updated_at=(
                    piece.updated_at.isoformat()
                    if hasattr(piece, "updated_at") and piece.updated_at
                    else (piece.created_at.isoformat() if piece.created_at else "")
                ),
            ))

        return ContentBriefListResponse(briefs=items, total=len(items))

    # ── Brief Detail (DB-backed) ─────────────────────────────────────

    async def get_brief_detail(
        self, effective_slug: str, brief_id: str,
    ) -> ContentBriefDetailResponse:
        """Get full detail for a single content piece from DB."""
        run_id = await self._resolve_run_id(effective_slug)
        if run_id is None:
            raise HTTPException(404, f"No content runs for '{effective_slug}'")

        piece = await self._content_repo.get_piece_detail(run_id, brief_id)
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

        return ContentBriefDetailResponse(
            id=str(piece.id),
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
                        from core.storage import get_storage_backend

                        storage = get_storage_backend(self._artifacts_root)
                        content = storage.read(artifact.storage_key)
                        if content is not None:
                            import json

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
                    "DB artifact lookup failed for %s/%s/%s — falling back to filesystem",
                    effective_slug, brief_id, stage, exc_info=True,
                )

        # Fallback: filesystem heuristic (backward compat)
        from api.services.content_data_service import get_brief_stage_content

        return await asyncio.to_thread(
            get_brief_stage_content,
            self._artifacts_root,
            effective_slug,
            brief_id,
            stage,
        )

    # ── Add Brief (filesystem-backed) ─────────────────────────────

    async def add_brief(
        self,
        effective_slug: str,
        title: str,
        cluster: str = "",
        description: str = "",
        source: str = "manual",
    ) -> ContentBriefListItem:
        """Create a brief entry on disk AND in DB.

        Filesystem write (blueprints.json) is the source of truth for
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
