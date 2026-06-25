"""Content-to-Prompt Orchestrator — coordinates generation + dedup + persistence.

Mediates between ``ContentToPromptService`` (LLM generation) and the
repository layer to produce tracked prompts from content inventory pages.

Architecture follows the ``DailyTrackerOrchestrator`` mediator pattern:
- Fetches page metadata from content_inventory repository
- Delegates LLM generation to ContentToPromptService
- Deduplicates against existing tracked prompts (text-based)
- Persists new tracked_prompts + content_inventory_prompts links
- Handles auto-approve vs manual review mode

Does NOT own transaction boundaries — caller (API layer) commits.
"""
from __future__ import annotations

import logging
import uuid as _uuid
from typing import Any

from core.daily_tracker.content_to_prompt import ContentToPromptService
from core.db.repositories.content_inventory_prompt_repo import (
    ContentInventoryPromptRepository,
)
from core.db.repositories.content_inventory_repo import ContentInventoryRepository
from core.db.repositories.daily_tracker_repo import TrackedPromptRepository
from core.models.daily_tracker import (
    ContentToPromptRunResult,
    PageContext,
    PromptSource,
)

logger = logging.getLogger(__name__)


def _orm_to_page_context(item: Any) -> PageContext:
    """Convert a ContentInventoryModel ORM instance to a PageContext."""
    return PageContext(
        inventory_id=str(item.id),
        url=item.url or "",
        title=item.title or "",
        meta_description=item.meta_description or "",
        content_preview=item.content_preview or "",
        categories=item.categories or [],
        detected_primary_topic=item.detected_primary_topic or "",
        content_type_detected=item.content_type_detected or "",
        word_count=item.word_count or 0,
    )


class ContentToPromptOrchestrator:
    """Orchestrates content-to-prompt: generation → dedup → persist → link."""

    def __init__(
        self,
        generator: ContentToPromptService,
        prompt_repo: TrackedPromptRepository,
        link_repo: ContentInventoryPromptRepository,
        inventory_repo: ContentInventoryRepository,
    ) -> None:
        self._generator = generator
        self._prompt_repo = prompt_repo
        self._link_repo = link_repo
        self._inventory_repo = inventory_repo

    async def run_for_pages(
        self,
        company_id: str,
        company_uuid: _uuid.UUID | None,
        page_ids: list[_uuid.UUID],
        brand_name: str,
        brand_category: str = "",
        competitors: list[str] | None = None,
        k: int = 6,
        auto_approve: bool = True,
        workspace_id: str = "",
        workspace_slug: str = "",
    ) -> ContentToPromptRunResult:
        """Generate and persist prompts for the given content inventory pages.

        Args:
            company_id: Company identifier (string, matching tracked_prompts.company_id).
            company_uuid: Company UUID for tenant isolation (validates page ownership).
            page_ids: Content inventory UUIDs to process.
            brand_name: Brand name for prompt context.
            brand_category: Optional brand category.
            competitors: Optional competitor names.
            k: Number of prompts per page (4-12, default 6).
            auto_approve: If True, prompts are immediately active. If False,
                prompts are created as inactive + link.approved=False.
            workspace_id: Workspace id used for BYOK model resolution.
            workspace_slug: Workspace slug used for BYOK model resolution.

        Returns:
            ContentToPromptRunResult summary.
        """
        generation_run_id = _uuid.uuid4()
        pages_succeeded = 0
        pages_failed = 0
        prompts_created = 0
        prompts_deduplicated = 0
        errors: list[dict[str, str]] = []

        # 1. Load page metadata with tenant isolation
        page_contexts: list[PageContext] = []
        for pid in page_ids:
            item = await self._inventory_repo.get_by_id(pid)
            if item is None:
                errors.append({"page_id": str(pid), "error": "Page not found"})
                pages_failed += 1
                continue
            # Tenant isolation: verify page belongs to the requesting company
            if company_uuid and item.company_id != company_uuid:
                errors.append({"page_id": str(pid), "error": "Access denied"})
                pages_failed += 1
                continue
            page_contexts.append(_orm_to_page_context(item))

        if not page_contexts:
            return ContentToPromptRunResult(
                generation_run_id=str(generation_run_id),
                pages_processed=len(page_ids),
                pages_succeeded=0,
                pages_failed=pages_failed,
                errors=errors,
            )

        # 2. Generate prompts via LLM (batched with concurrency)
        results = await self._generator.generate_prompts_batch(
            page_contexts,
            brand_name,
            brand_category,
            competitors,
            k=k,
            workspace_id=workspace_id,
            workspace_slug=workspace_slug,
            company_slug=company_id,
        )

        # 3. Dedup + persist per page
        for gen_result in results:
            if not gen_result.prompts:
                pages_failed += 1
                if not any(e["page_id"] == gen_result.inventory_id for e in errors):
                    errors.append({
                        "page_id": gen_result.inventory_id,
                        "error": "LLM returned no prompts",
                    })
                continue

            page_created = 0
            page_deduped = 0
            inventory_uuid = _uuid.UUID(gen_result.inventory_id)

            for prompt in gen_result.prompts:
                query_text = prompt.query_text.strip()
                if not query_text:
                    continue

                # Check for existing prompt with same text
                existing = await self._prompt_repo.exists_by_text(
                    company_id, query_text,
                )

                if existing:
                    # Find the existing prompt to link it
                    existing_prompts = await self._prompt_repo.list_by_company(
                        company_id, search_text=query_text, limit=1,
                    )
                    if existing_prompts:
                        existing_prompt = existing_prompts[0]
                        # Check if link already exists
                        link_exists = await self._link_repo.link_exists(
                            inventory_uuid, existing_prompt.id,
                        )
                        if not link_exists:
                            await self._link_repo.bulk_create_links([{
                                "content_inventory_id": inventory_uuid,
                                "tracked_prompt_id": existing_prompt.id,
                                "generation_run_id": generation_run_id,
                                "buyer_stage": prompt.buyer_stage or None,
                                "intent_type": prompt.intent_type or None,
                                "is_branded": prompt.is_branded,
                                "approved": auto_approve,
                            }])
                    page_deduped += 1
                    continue

                # Create new tracked prompt (race-safe: catch IntegrityError
                # if a concurrent request created the same prompt between our
                # exists_by_text check and this insert)
                source_metadata = {
                    "inventory_id": gen_result.inventory_id,
                    "generation_run_id": str(generation_run_id),
                    "buyer_stage": prompt.buyer_stage,
                    "intent_type": prompt.intent_type,
                }

                try:
                    new_prompt = await self._prompt_repo.create(
                        company_id=company_id,
                        text=query_text,
                        category=prompt.intent_type or None,
                        tags=[],
                        source=PromptSource.CONTENT_INVENTORY.value,
                        source_metadata=source_metadata,
                        active=auto_approve,
                    )
                except Exception:
                    # Concurrent insert created the same prompt — treat as dedup
                    logger.debug("Concurrent dedup for prompt: %s", query_text[:60])
                    page_deduped += 1
                    continue

                # Create link row
                await self._link_repo.bulk_create_links([{
                    "content_inventory_id": inventory_uuid,
                    "tracked_prompt_id": new_prompt.id,
                    "generation_run_id": generation_run_id,
                    "buyer_stage": prompt.buyer_stage or None,
                    "intent_type": prompt.intent_type or None,
                    "is_branded": prompt.is_branded,
                    "approved": auto_approve,
                }])

                page_created += 1

            prompts_created += page_created
            prompts_deduplicated += page_deduped
            pages_succeeded += 1

        logger.info(
            "Content-to-prompt run completed: %d pages processed, "
            "%d prompts created, %d deduplicated, %d failed",
            len(page_ids),
            prompts_created,
            prompts_deduplicated,
            pages_failed,
        )

        return ContentToPromptRunResult(
            generation_run_id=str(generation_run_id),
            pages_processed=len(page_ids),
            pages_succeeded=pages_succeeded,
            pages_failed=pages_failed,
            prompts_created=prompts_created,
            prompts_deduplicated=prompts_deduplicated,
            errors=errors,
        )

    async def regenerate_for_page(
        self,
        company_id: str,
        company_uuid: _uuid.UUID | None,
        page_id: _uuid.UUID,
        brand_name: str,
        brand_category: str = "",
        competitors: list[str] | None = None,
        k: int = 6,
        auto_approve: bool = True,
        workspace_id: str = "",
        workspace_slug: str = "",
    ) -> ContentToPromptRunResult:
        """Re-generate prompts for a page. Deletes old non-edited links first.

        User-edited links are preserved. Orphaned prompts (linked only to
        this page) are deactivated.

        Args:
            company_id: Company identifier.
            page_id: Content inventory UUID.
            brand_name: Brand name.
            brand_category: Optional category.
            competitors: Optional competitor names.
            k: Prompts per page.
            auto_approve: Auto-approve new prompts.

        Returns:
            ContentToPromptRunResult summary.
        """
        # 1. Get existing links for this page (to detect orphans)
        old_links = await self._link_repo.get_prompts_for_page(page_id)
        old_prompt_ids = [link.tracked_prompt_id for link in old_links if not link.is_user_edited]

        # 2. Delete non-user-edited links
        deleted = await self._link_repo.delete_links_for_page(
            page_id, preserve_user_edited=True,
        )
        logger.info("Deleted %d old links for page %s (preserved user-edited)", deleted, page_id)

        # 3. Deactivate orphaned prompts (only linked to this page)
        for prompt_id in old_prompt_ids:
            remaining = await self._link_repo.count_links_for_prompt(prompt_id)
            if remaining == 0:
                await self._prompt_repo.update(prompt_id, active=False)

        # 4. Generate fresh prompts
        return await self.run_for_pages(
            company_id=company_id,
            company_uuid=company_uuid,
            page_ids=[page_id],
            brand_name=brand_name,
            brand_category=brand_category,
            competitors=competitors,
            k=k,
            auto_approve=auto_approve,
            workspace_id=workspace_id,
            workspace_slug=workspace_slug,
        )
