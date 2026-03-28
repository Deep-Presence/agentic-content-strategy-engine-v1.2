"""Prompt Library Service — manages tracked prompts for daily visibility runs.

Responsibilities:
    - CRUD operations for tracked prompts
    - Import from gap analysis queries.json artifacts
    - Bulk creation with deduplication
    - Toggle active/inactive status

Does NOT:
    - Execute prompts (that's PlatformRunnerService)
    - Compute analytics (that's AnalyticsService)
    - Own transaction boundaries (the DI/service layer commits)

Why: separating prompt management from execution follows SRP and lets the
orchestrator compose prompt selection + execution + analytics independently.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from core.storage.backends.base import StorageBackend

from core.db.repositories.daily_tracker_repo import TrackedPromptRepository
from core.models.daily_tracker import (
    PromptLibraryFilter,
    PromptSource,
    TrackedPrompt,
)

logger = logging.getLogger(__name__)

# Why: resolve the project root once at import time so artifact paths
# are consistent regardless of cwd.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # content-strategy-engine/


class PromptLibraryService:
    """Concrete implementation of PromptLibraryServiceProtocol.

    Wraps a ``TrackedPromptRepository`` for DB operations and reads
    gap analysis artifacts from the filesystem for import.
    """

    def __init__(
        self,
        prompt_repo: TrackedPromptRepository,
        backend: Optional[StorageBackend] = None,
    ) -> None:
        self._repo = prompt_repo
        self._backend = backend

    # ── CRUD ──────────────────────────────────────────────────────────

    async def create_prompt(
        self,
        company_id: str,
        text: str,
        category: str | None = None,
        tags: list[str] | None = None,
    ) -> TrackedPrompt:
        """Create a new tracked prompt.

        Args:
            company_id: Company identifier.
            text: The prompt text to track.
            category: Optional category for organization.
            tags: Optional list of tags.

        Returns:
            Created TrackedPrompt.

        Raises:
            ValueError: If a prompt with identical text already exists
                for this company.
        """
        if await self._repo.exists_by_text(company_id, text):
            raise ValueError(
                f"Prompt with this text already exists for company {company_id}"
            )

        orm_obj = await self._repo.create(
            company_id=company_id,
            text=text,
            category=category,
            tags=tags or [],
            source=PromptSource.MANUAL.value,
        )
        return self._orm_to_pydantic(orm_obj)

    async def list_prompts(
        self,
        company_id: str,
        filters: PromptLibraryFilter | None = None,
    ) -> list[TrackedPrompt]:
        """List prompts with optional filtering.

        Args:
            company_id: Company identifier.
            filters: Optional filter criteria.

        Returns:
            List of matching TrackedPrompt objects.
        """
        kwargs: dict[str, Any] = {}
        if filters:
            if filters.active is not None:
                kwargs["is_active"] = filters.active
            if filters.source is not None:
                kwargs["source"] = filters.source.value
            if filters.category is not None:
                kwargs["category"] = filters.category
            if filters.tags:
                kwargs["tags"] = filters.tags
            if filters.search:
                kwargs["search_text"] = filters.search

        rows = await self._repo.list_by_company(company_id, **kwargs)
        return [self._orm_to_pydantic(r) for r in rows]

    async def get_prompt(self, prompt_id: str) -> TrackedPrompt | None:
        """Get a single prompt by ID.

        Args:
            prompt_id: Prompt UUID string.

        Returns:
            TrackedPrompt or None if not found.
        """
        orm_obj = await self._repo.get_by_id(prompt_id)
        if orm_obj is None:
            return None
        return self._orm_to_pydantic(orm_obj)

    async def update_prompt(
        self, prompt_id: str, **kwargs: object
    ) -> TrackedPrompt:
        """Update a prompt's fields.

        Args:
            prompt_id: Prompt UUID string.
            **kwargs: Fields to update (text, category, tags, active, etc.).

        Returns:
            Updated TrackedPrompt.

        Raises:
            ValueError: If prompt not found.
        """
        orm_obj = await self._repo.update(prompt_id, **kwargs)
        if orm_obj is None:
            raise ValueError(f"Prompt {prompt_id} not found")
        return self._orm_to_pydantic(orm_obj)

    async def delete_prompt(self, prompt_id: str) -> bool:
        """Delete a prompt by ID.

        Args:
            prompt_id: Prompt UUID string.

        Returns:
            True if deleted, False if not found.
        """
        return await self._repo.delete(prompt_id)

    async def toggle_prompt(
        self, prompt_id: str, active: bool
    ) -> TrackedPrompt:
        """Toggle a prompt's active status.

        Args:
            prompt_id: Prompt UUID string.
            active: New active state.

        Returns:
            Updated TrackedPrompt.

        Raises:
            ValueError: If prompt not found.
        """
        orm_obj = await self._repo.update(prompt_id, active=active)
        if orm_obj is None:
            raise ValueError(f"Prompt {prompt_id} not found")
        return self._orm_to_pydantic(orm_obj)

    # ── Import ────────────────────────────────────────────────────────

    async def import_from_gap_analysis(
        self, company_id: str, slug: str
    ) -> list[TrackedPrompt]:
        """Import prompts from a gap analysis run's queries.json.

        Reads ``GeneratedQuery`` objects from the gap analysis artifacts
        directory, deduplicates against existing prompts, and creates
        new tracked prompts with ``source=gap_analysis``.

        Args:
            company_id: Company identifier.
            slug: Company/product slug used for artifact directory lookup.

        Returns:
            List of newly created TrackedPrompt objects (duplicates skipped).

        Raises:
            FileNotFoundError: If queries.json does not exist for the slug.
        """
        key = f"gap_analysis/{slug}/queries.json"
        raw_text: Optional[str] = None
        if self._backend is not None:
            raw_text = self._backend.read(key)
        if raw_text is None:
            # StorageBackend fallback (R2-aware) when no backend injected
            from core.storage import get_storage_backend
            fallback_backend = get_storage_backend()
            raw_text = fallback_backend.read(key)
        if raw_text is None:
            raise FileNotFoundError(
                f"Gap analysis queries not found: {key}"
            )

        raw = json.loads(raw_text)
        if not isinstance(raw, list):
            logger.warning("queries.json is not a list, skipping import")
            return []

        created: list[TrackedPrompt] = []
        for query in raw:
            text = query.get("query_text", "").strip()
            if not text:
                continue

            # Why: deduplication by exact text match prevents importing
            # the same prompt twice from repeated gap analysis runs.
            if await self._repo.exists_by_text(company_id, text):
                logger.debug("Skipping duplicate prompt: %s", text[:60])
                continue

            source_metadata = {
                "query_id": query.get("query_id"),
                "cluster_id": query.get("cluster_id"),
                "buyer_stage": query.get("buyer_stage"),
                "persona_tag": query.get("persona_tag"),
                "slug": slug,
            }

            orm_obj = await self._repo.create(
                company_id=company_id,
                text=text,
                category=query.get("cluster_name"),
                tags=[],
                source=PromptSource.GAP_ANALYSIS.value,
                source_metadata=source_metadata,
            )
            created.append(self._orm_to_pydantic(orm_obj))

        logger.info(
            "Imported %d prompts from gap analysis slug=%s (total queries: %d)",
            len(created),
            slug,
            len(raw),
        )
        return created

    # ── Bulk ──────────────────────────────────────────────────────────

    async def bulk_create(
        self,
        company_id: str,
        prompts: list[dict[str, object]],
    ) -> list[TrackedPrompt]:
        """Create multiple prompts, skipping duplicates.

        Args:
            company_id: Company identifier.
            prompts: List of prompt dicts, each with at least a "text" key.
                Optional keys: "category", "tags", "source".

        Returns:
            List of newly created TrackedPrompt objects (duplicates skipped).
        """
        to_create: list[dict[str, object]] = []
        for p in prompts:
            text = str(p.get("text", "")).strip()
            if not text:
                continue
            if await self._repo.exists_by_text(company_id, text):
                logger.debug("Bulk: skipping duplicate prompt: %s", text[:60])
                continue
            to_create.append(
                {
                    "company_id": company_id,
                    "text": text,
                    "category": p.get("category"),
                    "tags": p.get("tags", []),
                    "source": p.get("source", PromptSource.MANUAL.value),
                }
            )

        if not to_create:
            return []

        orm_objs = await self._repo.bulk_create(to_create)
        return [self._orm_to_pydantic(o) for o in orm_objs]

    # ── Private helpers ───────────────────────────────────────────────

    def _orm_to_pydantic(self, model: Any) -> TrackedPrompt:
        """Convert ORM model to Pydantic TrackedPrompt.

        Args:
            model: TrackedPromptModel ORM instance.

        Returns:
            TrackedPrompt Pydantic model.
        """
        return TrackedPrompt(
            id=str(model.id),
            company_id=str(model.company_id),
            text=model.text,
            category=model.category,
            tags=model.tags or [],
            source=PromptSource(model.source) if model.source else PromptSource.MANUAL,
            source_metadata=model.source_metadata,
            active=model.active,
            platforms=model.platforms or [],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
