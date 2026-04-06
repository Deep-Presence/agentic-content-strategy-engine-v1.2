"""Tests for ContentToPromptOrchestrator.

Tests cover:
- Full flow: page lookup �� LLM generation → dedup → persist → link
- Dedup: existing prompts get linked but not duplicated
- Auto-approve vs manual review mode
- Page not found handling
- Re-generation flow with orphan deactivation
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.daily_tracker.content_to_prompt_orchestrator import (
    ContentToPromptOrchestrator,
    _orm_to_page_context,
)
from core.models.daily_tracker import (
    ContentToPromptRunResult,
    GeneratedPagePrompt,
    PageContext,
    PagePromptGenerationResult,
)


# ── Helpers ────────────��──────────────────────────────────────────────

def _make_inventory_item(
    *,
    id: uuid.UUID | None = None,
    title: str = "Test Page",
    url: str = "https://example.com/test",
    content_preview: str = "This is a test page about automation.",
) -> MagicMock:
    """Create a mock ContentInventoryModel."""
    item = MagicMock()
    item.id = id or uuid.uuid4()
    item.url = url
    item.title = title
    item.meta_description = "Test description"
    item.content_preview = content_preview
    item.categories = ["test"]
    item.detected_primary_topic = "automation"
    item.content_type_detected = "blog_post"
    item.word_count = 1500
    return item


def _make_gen_result(
    inventory_id: str,
    prompts: list[dict] | None = None,
) -> PagePromptGenerationResult:
    """Create a PagePromptGenerationResult with defaults."""
    if prompts is None:
        prompts = [
            {"query_text": "What is automation?", "buyer_stage": "tofu", "intent_type": "informational"},
            {"query_text": "Best automation tools", "buyer_stage": "mofu", "intent_type": "commercial"},
        ]
    return PagePromptGenerationResult(
        inventory_id=inventory_id,
        prompts=[GeneratedPagePrompt(**p) for p in prompts],
        model_used="test-model",
        token_usage={"total_tokens": 100},
    )


def _make_prompt_orm(
    *,
    id: uuid.UUID | None = None,
    text: str = "test prompt",
) -> MagicMock:
    """Create a mock TrackedPromptModel."""
    prompt = MagicMock()
    prompt.id = id or uuid.uuid4()
    prompt.text = text
    return prompt


# ── Fixtures ────────────────────────────────────��─────────────────────

@pytest.fixture
def mock_generator():
    gen = AsyncMock(spec_set=["generate_prompts_batch", "generate_prompts_for_page"])
    return gen


@pytest.fixture
def mock_prompt_repo():
    repo = AsyncMock()
    repo.exists_by_text = AsyncMock(return_value=False)
    repo.create = AsyncMock(side_effect=lambda **kw: _make_prompt_orm(text=kw.get("text", "")))
    repo.list_by_company = AsyncMock(return_value=[])
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def mock_link_repo():
    repo = AsyncMock()
    repo.bulk_create_links = AsyncMock(return_value=[])
    repo.link_exists = AsyncMock(return_value=False)
    repo.count_links_for_prompt = AsyncMock(return_value=0)
    repo.get_prompts_for_page = AsyncMock(return_value=[])
    repo.delete_links_for_page = AsyncMock(return_value=0)
    return repo


@pytest.fixture
def mock_inventory_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def orchestrator(mock_generator, mock_prompt_repo, mock_link_repo, mock_inventory_repo):
    return ContentToPromptOrchestrator(
        generator=mock_generator,
        prompt_repo=mock_prompt_repo,
        link_repo=mock_link_repo,
        inventory_repo=mock_inventory_repo,
    )


# ── run_for_pages tests ──────────��───────────────────────────────────


class TestRunForPages:
    @pytest.mark.asyncio
    async def test_successful_generation_creates_prompts_and_links(
        self, orchestrator, mock_generator, mock_prompt_repo, mock_link_repo, mock_inventory_repo,
    ):
        page_id = uuid.uuid4()
        item = _make_inventory_item(id=page_id)
        mock_inventory_repo.get_by_id = AsyncMock(return_value=item)

        gen_result = _make_gen_result(str(page_id))
        mock_generator.generate_prompts_batch = AsyncMock(return_value=[gen_result])

        result = await orchestrator.run_for_pages(
            company_id="test-co",
            page_ids=[page_id],
            brand_name="TestBrand",
            k=6,
        )

        assert isinstance(result, ContentToPromptRunResult)
        assert result.pages_processed == 1
        assert result.pages_succeeded == 1
        assert result.pages_failed == 0
        assert result.prompts_created == 2
        assert result.prompts_deduplicated == 0
        assert mock_prompt_repo.create.call_count == 2
        assert mock_link_repo.bulk_create_links.call_count == 2

    @pytest.mark.asyncio
    async def test_page_not_found_records_error(
        self, orchestrator, mock_inventory_repo,
    ):
        mock_inventory_repo.get_by_id = AsyncMock(return_value=None)
        page_id = uuid.uuid4()

        result = await orchestrator.run_for_pages(
            company_id="test-co",
            page_ids=[page_id],
            brand_name="Brand",
        )

        assert result.pages_failed == 1
        assert result.pages_succeeded == 0
        assert len(result.errors) == 1
        assert result.errors[0]["error"] == "Page not found"

    @pytest.mark.asyncio
    async def test_dedup_links_existing_prompt(
        self, orchestrator, mock_generator, mock_prompt_repo, mock_link_repo, mock_inventory_repo,
    ):
        page_id = uuid.uuid4()
        existing_prompt = _make_prompt_orm(text="What is automation?")

        mock_inventory_repo.get_by_id = AsyncMock(return_value=_make_inventory_item(id=page_id))
        mock_prompt_repo.exists_by_text = AsyncMock(return_value=True)
        mock_prompt_repo.list_by_company = AsyncMock(return_value=[existing_prompt])

        gen_result = _make_gen_result(str(page_id), prompts=[
            {"query_text": "What is automation?", "buyer_stage": "tofu", "intent_type": "informational"},
        ])
        mock_generator.generate_prompts_batch = AsyncMock(return_value=[gen_result])

        result = await orchestrator.run_for_pages(
            company_id="test-co",
            page_ids=[page_id],
            brand_name="Brand",
        )

        assert result.prompts_created == 0
        assert result.prompts_deduplicated == 1
        # Should create a link to the existing prompt
        assert mock_link_repo.bulk_create_links.call_count == 1

    @pytest.mark.asyncio
    async def test_manual_review_creates_inactive_prompts(
        self, orchestrator, mock_generator, mock_prompt_repo, mock_link_repo, mock_inventory_repo,
    ):
        page_id = uuid.uuid4()
        mock_inventory_repo.get_by_id = AsyncMock(return_value=_make_inventory_item(id=page_id))

        gen_result = _make_gen_result(str(page_id), prompts=[
            {"query_text": "Q1", "buyer_stage": "tofu", "intent_type": "informational"},
        ])
        mock_generator.generate_prompts_batch = AsyncMock(return_value=[gen_result])

        result = await orchestrator.run_for_pages(
            company_id="test-co",
            page_ids=[page_id],
            brand_name="Brand",
            auto_approve=False,
        )

        assert result.prompts_created == 1
        # Prompt should be created with active=False
        create_call = mock_prompt_repo.create.call_args
        assert create_call.kwargs["active"] is False
        # Link should be created with approved=False
        link_call = mock_link_repo.bulk_create_links.call_args
        assert link_call.args[0][0]["approved"] is False

    @pytest.mark.asyncio
    async def test_empty_llm_response_counts_as_failure(
        self, orchestrator, mock_generator, mock_inventory_repo,
    ):
        page_id = uuid.uuid4()
        mock_inventory_repo.get_by_id = AsyncMock(return_value=_make_inventory_item(id=page_id))

        gen_result = PagePromptGenerationResult(inventory_id=str(page_id), prompts=[])
        mock_generator.generate_prompts_batch = AsyncMock(return_value=[gen_result])

        result = await orchestrator.run_for_pages(
            company_id="test-co",
            page_ids=[page_id],
            brand_name="Brand",
        )

        assert result.pages_failed == 1
        assert result.prompts_created == 0

    @pytest.mark.asyncio
    async def test_source_metadata_includes_inventory_id(
        self, orchestrator, mock_generator, mock_prompt_repo, mock_inventory_repo, mock_link_repo,
    ):
        page_id = uuid.uuid4()
        mock_inventory_repo.get_by_id = AsyncMock(return_value=_make_inventory_item(id=page_id))

        gen_result = _make_gen_result(str(page_id), prompts=[
            {"query_text": "Test Q", "buyer_stage": "mofu", "intent_type": "commercial"},
        ])
        mock_generator.generate_prompts_batch = AsyncMock(return_value=[gen_result])

        await orchestrator.run_for_pages(
            company_id="test-co",
            page_ids=[page_id],
            brand_name="Brand",
        )

        create_call = mock_prompt_repo.create.call_args
        metadata = create_call.kwargs["source_metadata"]
        assert metadata["inventory_id"] == str(page_id)
        assert metadata["buyer_stage"] == "mofu"
        assert metadata["intent_type"] == "commercial"
        assert create_call.kwargs["source"] == "content_inventory"


# ── regenerate_for_page tests ─────��───────────────────────────────────


class TestRegenerateForPage:
    @pytest.mark.asyncio
    async def test_deletes_old_links_and_regenerates(
        self, orchestrator, mock_generator, mock_prompt_repo, mock_link_repo, mock_inventory_repo,
    ):
        page_id = uuid.uuid4()
        prompt_id = uuid.uuid4()

        # Old link (not user-edited)
        old_link = MagicMock()
        old_link.tracked_prompt_id = prompt_id
        old_link.is_user_edited = False
        mock_link_repo.get_prompts_for_page = AsyncMock(return_value=[old_link])
        mock_link_repo.delete_links_for_page = AsyncMock(return_value=1)
        mock_link_repo.count_links_for_prompt = AsyncMock(return_value=0)

        mock_inventory_repo.get_by_id = AsyncMock(return_value=_make_inventory_item(id=page_id))
        gen_result = _make_gen_result(str(page_id))
        mock_generator.generate_prompts_batch = AsyncMock(return_value=[gen_result])

        result = await orchestrator.regenerate_for_page(
            company_id="test-co",
            page_id=page_id,
            brand_name="Brand",
        )

        # Old links deleted
        mock_link_repo.delete_links_for_page.assert_called_once_with(
            page_id, preserve_user_edited=True,
        )
        # Orphaned prompt deactivated
        mock_prompt_repo.update.assert_called_once_with(prompt_id, active=False)
        # New prompts generated
        assert result.prompts_created == 2

    @pytest.mark.asyncio
    async def test_preserves_user_edited_links(
        self, orchestrator, mock_generator, mock_prompt_repo, mock_link_repo, mock_inventory_repo,
    ):
        page_id = uuid.uuid4()

        # User-edited link should be skipped for orphan detection
        edited_link = MagicMock()
        edited_link.tracked_prompt_id = uuid.uuid4()
        edited_link.is_user_edited = True
        mock_link_repo.get_prompts_for_page = AsyncMock(return_value=[edited_link])
        mock_link_repo.delete_links_for_page = AsyncMock(return_value=0)

        mock_inventory_repo.get_by_id = AsyncMock(return_value=_make_inventory_item(id=page_id))
        gen_result = _make_gen_result(str(page_id))
        mock_generator.generate_prompts_batch = AsyncMock(return_value=[gen_result])

        await orchestrator.regenerate_for_page(
            company_id="test-co",
            page_id=page_id,
            brand_name="Brand",
        )

        # Orphan deactivation should NOT be called for user-edited prompt
        mock_prompt_repo.update.assert_not_called()


# ── _orm_to_page_context tests ────────────────────────────────────────


class TestOrmToPageContext:
    def test_converts_all_fields(self):
        item = _make_inventory_item(title="My Page", url="https://example.com/page")
        ctx = _orm_to_page_context(item)

        assert isinstance(ctx, PageContext)
        assert ctx.title == "My Page"
        assert ctx.url == "https://example.com/page"
        assert ctx.inventory_id == str(item.id)
        assert ctx.categories == ["test"]
        assert ctx.word_count == 1500

    def test_handles_none_fields(self):
        item = MagicMock()
        item.id = uuid.uuid4()
        item.url = None
        item.title = None
        item.meta_description = None
        item.content_preview = None
        item.categories = None
        item.detected_primary_topic = None
        item.content_type_detected = None
        item.word_count = None

        ctx = _orm_to_page_context(item)
        assert ctx.url == ""
        assert ctx.title == ""
        assert ctx.word_count == 0
