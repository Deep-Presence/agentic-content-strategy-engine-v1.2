"""Tests for auto-prompt generation chained inside run_cms_sync_task.

Validates that:
- New pages trigger prompt generation
- No new pages → no prompt generation
- Prompt gen failure doesn't fail the sync task
- Page cap is respected
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.tasks.runner import _run_auto_prompt_generation, run_cms_sync_task


def _make_event_bus() -> MagicMock:
    eb = MagicMock()
    eb.publish = MagicMock()
    return eb


def _make_task_store() -> MagicMock:
    ts = MagicMock()
    ts.update_task = MagicMock()
    ts.release_slug_lock = MagicMock()
    ts.remove_task_handle = MagicMock()
    ts.flush_terminal = AsyncMock()

    class _Semaphore:
        async def __aenter__(self):
            return None

        async def __aexit__(self, exc_type, exc, tb):
            return False

    ts.pipeline_semaphore = MagicMock(return_value=_Semaphore())
    return ts


def _make_mock_company(name: str = "Test Co") -> MagicMock:
    c = MagicMock()
    c.id = uuid.uuid4()
    c.name = name
    return c


# Patch targets — all local imports inside _run_auto_prompt_generation
_P = "core."  # prefix for core patches
_PT_SETTINGS = "core.config.settings.settings"
_PT_SERVICE = "core.daily_tracker.content_to_prompt.ContentToPromptService"
_PT_ORCHESTRATOR = "core.daily_tracker.content_to_prompt_orchestrator.ContentToPromptOrchestrator"
_PT_PROMPT_REPO = "core.db.repositories.daily_tracker_repo.TrackedPromptRepository"
_PT_LINK_REPO = "core.db.repositories.content_inventory_prompt_repo.ContentInventoryPromptRepository"
_PT_INV_REPO = "core.db.repositories.content_inventory_repo.ContentInventoryRepository"
_PT_COMPANY_REPO = "core.db.repositories.company_repo.CompanyRepository"


# ── Tests ────────────────────────────────────────────────────────────


class TestAutoPromptGeneration:
    """_run_auto_prompt_generation helper."""

    @pytest.mark.asyncio
    async def test_chains_prompt_gen_for_new_pages(self):
        """Prompt generation runs when new_page_ids is non-empty."""
        mock_result = MagicMock()
        mock_result.prompts_created = 12
        mock_result.prompts_deduplicated = 3
        mock_result.pages_processed = 2

        mock_orchestrator_instance = AsyncMock()
        mock_orchestrator_instance.run_for_pages = AsyncMock(return_value=mock_result)

        session = AsyncMock()
        session_factory = MagicMock(return_value=session)

        company = _make_mock_company()
        new_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        result: dict = {}
        event_bus = _make_event_bus()
        task_store = _make_task_store()

        with (
            patch(_PT_SETTINGS) as mock_settings,
            patch(_PT_SERVICE),
            patch(_PT_ORCHESTRATOR, return_value=mock_orchestrator_instance),
            patch(_PT_PROMPT_REPO),
            patch(_PT_LINK_REPO),
            patch(_PT_INV_REPO),
            patch(_PT_COMPANY_REPO) as MockCompanyRepo,
        ):
            mock_settings.auto_prompt_max_pages = 50
            MockCompanyRepo.return_value.get_by_slug = AsyncMock(return_value=company)

            await _run_auto_prompt_generation(
                task_id="task-1",
                company_slug="test-co",
                new_page_ids=new_ids,
                session_factory=session_factory,
                event_bus=event_bus,
                task_store=task_store,
                result=result,
            )

        mock_orchestrator_instance.run_for_pages.assert_awaited_once()
        call_kwargs = mock_orchestrator_instance.run_for_pages.call_args.kwargs
        assert call_kwargs["auto_approve"] is True
        assert len(call_kwargs["page_ids"]) == 2
        assert result["prompts_created"] == 12
        assert result["prompts_deduplicated"] == 3
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_prompt_gen_when_cap_is_zero(self):
        """If auto_prompt_max_pages=0, prompt generation is skipped."""
        result: dict = {}
        event_bus = _make_event_bus()
        task_store = _make_task_store()

        with patch(_PT_SETTINGS) as mock_settings:
            mock_settings.auto_prompt_max_pages = 0
            await _run_auto_prompt_generation(
                task_id="task-1",
                company_slug="test-co",
                new_page_ids=[str(uuid.uuid4())],
                session_factory=MagicMock(),
                event_bus=event_bus,
                task_store=task_store,
                result=result,
            )

        assert "prompts_created" not in result

    @pytest.mark.asyncio
    async def test_prompt_gen_failure_doesnt_fail_sync(self):
        """If orchestrator raises, error is captured but no exception propagates."""
        session = AsyncMock()
        session_factory = MagicMock(return_value=session)

        company = _make_mock_company()
        result: dict = {}
        event_bus = _make_event_bus()
        task_store = _make_task_store()

        with (
            patch(_PT_SETTINGS) as mock_settings,
            patch(_PT_SERVICE),
            patch(_PT_ORCHESTRATOR) as MockOrch,
            patch(_PT_PROMPT_REPO),
            patch(_PT_LINK_REPO),
            patch(_PT_INV_REPO),
            patch(_PT_COMPANY_REPO) as MockCompanyRepo,
        ):
            mock_settings.auto_prompt_max_pages = 50
            MockCompanyRepo.return_value.get_by_slug = AsyncMock(return_value=company)
            MockOrch.return_value.run_for_pages = AsyncMock(
                side_effect=RuntimeError("LLM API down")
            )

            # Should NOT raise
            await _run_auto_prompt_generation(
                task_id="task-1",
                company_slug="test-co",
                new_page_ids=[str(uuid.uuid4())],
                session_factory=session_factory,
                event_bus=event_bus,
                task_store=task_store,
                result=result,
            )

        assert "prompt_generation_error" in result
        assert "LLM API down" in result["prompt_generation_error"]
        # SSE event emitted for failure
        event_bus.publish.assert_any_call(
            "task-1", "prompt_generation_failed", {"error": "LLM API down"},
        )

    @pytest.mark.asyncio
    async def test_prompt_gen_respects_page_cap(self):
        """When more new pages than cap, only cap pages are processed."""
        mock_result = MagicMock()
        mock_result.prompts_created = 5
        mock_result.prompts_deduplicated = 0
        mock_result.pages_processed = 10

        mock_orchestrator_instance = AsyncMock()
        mock_orchestrator_instance.run_for_pages = AsyncMock(return_value=mock_result)

        session = AsyncMock()
        session_factory = MagicMock(return_value=session)

        company = _make_mock_company()
        # 100 new pages, cap at 10
        new_ids = [str(uuid.uuid4()) for _ in range(100)]
        result: dict = {}
        event_bus = _make_event_bus()
        task_store = _make_task_store()

        with (
            patch(_PT_SETTINGS) as mock_settings,
            patch(_PT_SERVICE),
            patch(_PT_ORCHESTRATOR, return_value=mock_orchestrator_instance),
            patch(_PT_PROMPT_REPO),
            patch(_PT_LINK_REPO),
            patch(_PT_INV_REPO),
            patch(_PT_COMPANY_REPO) as MockCompanyRepo,
        ):
            mock_settings.auto_prompt_max_pages = 10
            MockCompanyRepo.return_value.get_by_slug = AsyncMock(return_value=company)

            await _run_auto_prompt_generation(
                task_id="task-1",
                company_slug="test-co",
                new_page_ids=new_ids,
                session_factory=session_factory,
                event_bus=event_bus,
                task_store=task_store,
                result=result,
            )

        call_kwargs = mock_orchestrator_instance.run_for_pages.call_args.kwargs
        assert len(call_kwargs["page_ids"]) == 10

    @pytest.mark.asyncio
    async def test_company_not_found_skips_gracefully(self):
        """If company not in DB, prompt generation is skipped (no crash)."""
        session = AsyncMock()
        session_factory = MagicMock(return_value=session)
        result: dict = {}
        event_bus = _make_event_bus()
        task_store = _make_task_store()

        with (
            patch(_PT_SETTINGS) as mock_settings,
            patch(_PT_SERVICE),
            patch(_PT_ORCHESTRATOR) as MockOrch,
            patch(_PT_PROMPT_REPO),
            patch(_PT_LINK_REPO),
            patch(_PT_INV_REPO),
            patch(_PT_COMPANY_REPO) as MockCompanyRepo,
        ):
            mock_settings.auto_prompt_max_pages = 50
            MockCompanyRepo.return_value.get_by_slug = AsyncMock(return_value=None)

            await _run_auto_prompt_generation(
                task_id="task-1",
                company_slug="nonexistent",
                new_page_ids=[str(uuid.uuid4())],
                session_factory=session_factory,
                event_bus=event_bus,
                task_store=task_store,
                result=result,
            )

        MockOrch.return_value.run_for_pages.assert_not_called()
        assert "prompts_created" not in result


class TestCMSSyncTask:
    @pytest.mark.asyncio
    async def test_sync_invalidates_ga4_caches(self):
        session = AsyncMock()
        session_factory = MagicMock(return_value=session)
        task_store = _make_task_store()
        event_bus = _make_event_bus()

        mock_connection = MagicMock()
        mock_service = AsyncMock()
        mock_service.get_connection = AsyncMock(return_value=mock_connection)
        mock_service.sync_existing_content = AsyncMock(return_value={
            "synced": 3,
            "stale": 0,
            "categories": 1,
            "new_page_ids": [],
        })

        with (
            patch("core.db.repositories.cms_repo.CMSConnectionRepository"),
            patch("core.db.repositories.cms_repo.CMSPublishRecordRepository"),
            patch("core.db.repositories.cms_repo.CMSSyncedPostRepository"),
            patch("core.db.repositories.content_inventory_repo.ContentInventoryRepository"),
            patch("core.services.content_inventory_service.ContentInventoryService"),
            patch("core.services.cms_service.CMSService", return_value=mock_service),
            patch("api.tasks.runner.get_sync_redis_or_none", return_value=None),
            patch("core.services.analytics_cache.invalidate_all_ga4_caches") as mock_inv,
        ):
            await run_cms_sync_task(
                task_id="task-1",
                company_slug="test-co",
                tenant_id="test-co",
                task_store=task_store,
                event_bus=event_bus,
                session_factory=session_factory,
                storage=MagicMock(),
                fernet_key="secret",
            )

        mock_inv.assert_called_once_with("test-co")
        session.commit.assert_awaited_once()
        task_store.release_slug_lock.assert_called_once_with("cms_sync:test-co")
