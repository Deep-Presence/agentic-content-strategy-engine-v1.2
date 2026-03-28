"""Tests for the Prompt Library Service.

Covers CRUD operations, gap analysis import, bulk creation, deduplication,
toggle, and edge cases.  All repository calls are mocked — no real DB needed.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.daily_tracker.prompt_library import PromptLibraryService
from core.models.daily_tracker import (
    PromptLibraryFilter,
    PromptSource,
    TrackedPrompt,
)
from core.storage.backends.local import LocalStorageBackend


# ── Helpers ───────────────────────────────────────────────────────────


def _make_orm_prompt(
    *,
    id: uuid.UUID | None = None,
    company_id: str = "company-abc",
    text: str = "What is the best expense tool?",
    category: str | None = None,
    tags: list[str] | None = None,
    source: str = "manual",
    source_metadata: dict | None = None,
    active: bool = True,
    platforms: list[str] | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> SimpleNamespace:
    """Create a fake ORM-like object with the same attributes as TrackedPromptModel."""
    now = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=id or uuid.uuid4(),
        company_id=company_id,
        text=text,
        category=category,
        tags=tags or [],
        source=source,
        source_metadata=source_metadata,
        active=active,
        platforms=platforms or [],
        created_at=created_at or now,
        updated_at=updated_at or now,
    )


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture()
def mock_prompt_repo() -> AsyncMock:
    """Mock TrackedPromptRepository with all methods."""
    repo = AsyncMock()
    repo.list_by_company = AsyncMock(return_value=[])
    repo.get_by_id = AsyncMock(return_value=None)
    repo.create = AsyncMock(side_effect=lambda **kw: _make_orm_prompt(**kw))
    repo.update = AsyncMock(return_value=None)
    repo.delete = AsyncMock(return_value=True)
    repo.exists_by_text = AsyncMock(return_value=False)
    repo.bulk_create = AsyncMock(return_value=[])
    repo.get_active_prompts = AsyncMock(return_value=[])
    repo.find_by_text = AsyncMock(return_value=None)
    return repo


@pytest.fixture()
def service(mock_prompt_repo: AsyncMock) -> PromptLibraryService:
    """Service wired to a mocked repository."""
    return PromptLibraryService(prompt_repo=mock_prompt_repo)


# ── List Prompts ──────────────────────────────────────────────────────


class TestListPrompts:
    """Tests for list_prompts()."""

    @pytest.mark.asyncio
    async def test_list_prompts_no_filter(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """list_prompts with no filter calls repo with no kwargs."""
        mock_prompt_repo.list_by_company.return_value = [
            _make_orm_prompt(text="prompt 1"),
            _make_orm_prompt(text="prompt 2"),
        ]
        result = await service.list_prompts("company-abc")
        assert len(result) == 2
        assert all(isinstance(p, TrackedPrompt) for p in result)
        mock_prompt_repo.list_by_company.assert_awaited_once_with("company-abc")

    @pytest.mark.asyncio
    async def test_list_prompts_with_active_filter(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """list_prompts passes active filter to repo."""
        filters = PromptLibraryFilter(active=True)
        await service.list_prompts("company-abc", filters=filters)
        mock_prompt_repo.list_by_company.assert_awaited_once_with(
            "company-abc", is_active=True
        )

    @pytest.mark.asyncio
    async def test_list_prompts_with_source_filter(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """list_prompts passes source filter to repo."""
        filters = PromptLibraryFilter(source=PromptSource.GAP_ANALYSIS)
        await service.list_prompts("company-abc", filters=filters)
        mock_prompt_repo.list_by_company.assert_awaited_once_with(
            "company-abc", source="gap_analysis"
        )

    @pytest.mark.asyncio
    async def test_list_prompts_with_category_filter(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """list_prompts passes category filter to repo."""
        filters = PromptLibraryFilter(category="brand_awareness")
        await service.list_prompts("company-abc", filters=filters)
        mock_prompt_repo.list_by_company.assert_awaited_once_with(
            "company-abc", category="brand_awareness"
        )

    @pytest.mark.asyncio
    async def test_list_prompts_with_tags_filter(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """list_prompts passes tags filter to repo."""
        filters = PromptLibraryFilter(tags=["expense", "cards"])
        await service.list_prompts("company-abc", filters=filters)
        mock_prompt_repo.list_by_company.assert_awaited_once_with(
            "company-abc", tags=["expense", "cards"]
        )

    @pytest.mark.asyncio
    async def test_list_prompts_with_search_filter(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """list_prompts passes search text to repo."""
        filters = PromptLibraryFilter(search="expense")
        await service.list_prompts("company-abc", filters=filters)
        mock_prompt_repo.list_by_company.assert_awaited_once_with(
            "company-abc", search_text="expense"
        )

    @pytest.mark.asyncio
    async def test_list_prompts_with_all_filters(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """list_prompts passes all filters together."""
        filters = PromptLibraryFilter(
            active=True,
            source=PromptSource.MANUAL,
            category="general",
            tags=["tag1"],
            search="text",
        )
        await service.list_prompts("company-abc", filters=filters)
        mock_prompt_repo.list_by_company.assert_awaited_once_with(
            "company-abc",
            is_active=True,
            source="manual",
            category="general",
            tags=["tag1"],
            search_text="text",
        )

    @pytest.mark.asyncio
    async def test_list_prompts_empty_result(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """list_prompts returns empty list when repo returns no results."""
        mock_prompt_repo.list_by_company.return_value = []
        result = await service.list_prompts("company-abc")
        assert result == []

    @pytest.mark.asyncio
    async def test_list_prompts_converts_orm_to_pydantic(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """list_prompts converts ORM objects to TrackedPrompt Pydantic models."""
        orm = _make_orm_prompt(text="test prompt", category="general", tags=["t1"])
        mock_prompt_repo.list_by_company.return_value = [orm]
        result = await service.list_prompts("company-abc")
        assert len(result) == 1
        assert result[0].text == "test prompt"
        assert result[0].category == "general"
        assert result[0].tags == ["t1"]
        assert result[0].id == str(orm.id)


# ── Create Prompt ─────────────────────────────────────────────────────


class TestCreatePrompt:
    """Tests for create_prompt()."""

    @pytest.mark.asyncio
    async def test_create_prompt_success(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """create_prompt creates and returns a TrackedPrompt."""
        result = await service.create_prompt(
            "company-abc", "What is the best tool?"
        )
        assert isinstance(result, TrackedPrompt)
        assert result.text == "What is the best tool?"
        assert result.source == PromptSource.MANUAL
        mock_prompt_repo.exists_by_text.assert_awaited_once_with(
            "company-abc", "What is the best tool?"
        )
        mock_prompt_repo.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_prompt_with_category_and_tags(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """create_prompt passes category and tags to repo."""
        await service.create_prompt(
            "company-abc",
            "Compare X and Y",
            category="product_comparison",
            tags=["compare", "product"],
        )
        call_kwargs = mock_prompt_repo.create.call_args.kwargs
        assert call_kwargs["category"] == "product_comparison"
        assert call_kwargs["tags"] == ["compare", "product"]

    @pytest.mark.asyncio
    async def test_create_prompt_duplicate_raises(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """create_prompt raises ValueError on duplicate text."""
        mock_prompt_repo.exists_by_text.return_value = True
        with pytest.raises(ValueError, match="already exists"):
            await service.create_prompt("company-abc", "Duplicate text")
        mock_prompt_repo.create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_prompt_no_tags_defaults_empty(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """create_prompt with no tags defaults to empty list."""
        await service.create_prompt("company-abc", "Some text")
        call_kwargs = mock_prompt_repo.create.call_args.kwargs
        assert call_kwargs["tags"] == []

    @pytest.mark.asyncio
    async def test_create_prompt_source_is_manual(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """create_prompt always sets source to manual."""
        await service.create_prompt("company-abc", "Some text")
        call_kwargs = mock_prompt_repo.create.call_args.kwargs
        assert call_kwargs["source"] == "manual"


# ── Get Prompt ────────────────────────────────────────────────────────


class TestGetPrompt:
    """Tests for get_prompt()."""

    @pytest.mark.asyncio
    async def test_get_prompt_found(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """get_prompt returns TrackedPrompt when found."""
        orm = _make_orm_prompt(text="found it")
        mock_prompt_repo.get_by_id.return_value = orm
        result = await service.get_prompt(str(orm.id))
        assert result is not None
        assert result.text == "found it"

    @pytest.mark.asyncio
    async def test_get_prompt_not_found(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """get_prompt returns None when not found."""
        mock_prompt_repo.get_by_id.return_value = None
        result = await service.get_prompt("nonexistent-id")
        assert result is None


# ── Update Prompt ─────────────────────────────────────────────────────


class TestUpdatePrompt:
    """Tests for update_prompt()."""

    @pytest.mark.asyncio
    async def test_update_prompt_success(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """update_prompt updates and returns TrackedPrompt."""
        orm = _make_orm_prompt(text="updated text", category="new_cat")
        mock_prompt_repo.update.return_value = orm
        result = await service.update_prompt(
            str(orm.id), text="updated text", category="new_cat"
        )
        assert result.text == "updated text"
        assert result.category == "new_cat"

    @pytest.mark.asyncio
    async def test_update_prompt_not_found_raises(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """update_prompt raises ValueError when prompt not found."""
        mock_prompt_repo.update.return_value = None
        with pytest.raises(ValueError, match="not found"):
            await service.update_prompt("nonexistent", text="new text")


# ── Delete Prompt ─────────────────────────────────────────────────────


class TestDeletePrompt:
    """Tests for delete_prompt()."""

    @pytest.mark.asyncio
    async def test_delete_success(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """delete_prompt returns True when deleted."""
        mock_prompt_repo.delete.return_value = True
        result = await service.delete_prompt("some-id")
        assert result is True
        mock_prompt_repo.delete.assert_awaited_once_with("some-id")

    @pytest.mark.asyncio
    async def test_delete_not_found(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """delete_prompt returns False when not found."""
        mock_prompt_repo.delete.return_value = False
        result = await service.delete_prompt("nonexistent")
        assert result is False


# ── Toggle Prompt ─────────────────────────────────────────────────────


class TestTogglePrompt:
    """Tests for toggle_prompt()."""

    @pytest.mark.asyncio
    async def test_toggle_active_on(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """toggle_prompt sets active=True."""
        orm = _make_orm_prompt(active=True)
        mock_prompt_repo.update.return_value = orm
        result = await service.toggle_prompt(str(orm.id), True)
        assert result.active is True
        mock_prompt_repo.update.assert_awaited_once_with(
            str(orm.id), active=True
        )

    @pytest.mark.asyncio
    async def test_toggle_active_off(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """toggle_prompt sets active=False."""
        orm = _make_orm_prompt(active=False)
        mock_prompt_repo.update.return_value = orm
        result = await service.toggle_prompt(str(orm.id), False)
        assert result.active is False

    @pytest.mark.asyncio
    async def test_toggle_nonexistent_raises(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """toggle_prompt raises ValueError when prompt not found."""
        mock_prompt_repo.update.return_value = None
        with pytest.raises(ValueError, match="not found"):
            await service.toggle_prompt("nonexistent", True)


# ── Import from Gap Analysis ─────────────────────────────────────────


class TestImportFromGapAnalysis:
    """Tests for import_from_gap_analysis()."""

    @pytest.fixture()
    def queries_json(self, tmp_path: Path, mock_prompt_repo: AsyncMock):
        """Create a temporary queries.json and return a service with a LocalStorageBackend."""
        data = [
            {
                "query_id": "q_1",
                "cluster_id": "C1",
                "cluster_name": "Mechanism",
                "query_text": "How does real-time spend control work?",
                "buyer_stage": "Consideration",
                "persona_tag": "icp",
                "embedding": None,
            },
            {
                "query_id": "q_2",
                "cluster_id": "C2",
                "cluster_name": "Comparison",
                "query_text": "Compare Ramp vs Brex for corporate cards",
                "buyer_stage": "Decision",
                "persona_tag": "icp",
                "embedding": None,
            },
        ]
        artifacts_dir = tmp_path / "artifacts"
        slug_dir = artifacts_dir / "gap_analysis" / "test-co"
        slug_dir.mkdir(parents=True)
        queries_file = slug_dir / "queries.json"
        queries_file.write_text(json.dumps(data), encoding="utf-8")
        backend = LocalStorageBackend(artifacts_dir)
        return PromptLibraryService(prompt_repo=mock_prompt_repo, backend=backend)

    @pytest.mark.asyncio
    async def test_import_creates_prompts(
        self,
        mock_prompt_repo: AsyncMock,
        queries_json: PromptLibraryService,
    ) -> None:
        """import_from_gap_analysis creates prompts from queries.json."""
        result = await queries_json.import_from_gap_analysis(
            "company-abc", "test-co"
        )
        assert len(result) == 2
        assert mock_prompt_repo.create.await_count == 2

    @pytest.mark.asyncio
    async def test_import_deduplicates(
        self,
        mock_prompt_repo: AsyncMock,
        queries_json: PromptLibraryService,
    ) -> None:
        """import_from_gap_analysis skips prompts that already exist."""
        # First query already exists, second does not
        mock_prompt_repo.exists_by_text.side_effect = [True, False]
        result = await queries_json.import_from_gap_analysis(
            "company-abc", "test-co"
        )
        assert len(result) == 1
        assert mock_prompt_repo.create.await_count == 1

    @pytest.mark.asyncio
    async def test_import_all_duplicates_returns_empty(
        self,
        mock_prompt_repo: AsyncMock,
        queries_json: PromptLibraryService,
    ) -> None:
        """import_from_gap_analysis returns empty when all are duplicates."""
        mock_prompt_repo.exists_by_text.return_value = True
        result = await queries_json.import_from_gap_analysis(
            "company-abc", "test-co"
        )
        assert result == []
        mock_prompt_repo.create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_import_sets_source_gap_analysis(
        self,
        mock_prompt_repo: AsyncMock,
        queries_json: PromptLibraryService,
    ) -> None:
        """import_from_gap_analysis sets source to gap_analysis."""
        await queries_json.import_from_gap_analysis("company-abc", "test-co")
        for call in mock_prompt_repo.create.call_args_list:
            assert call.kwargs["source"] == "gap_analysis"

    @pytest.mark.asyncio
    async def test_import_preserves_cluster_as_category(
        self,
        mock_prompt_repo: AsyncMock,
        queries_json: PromptLibraryService,
    ) -> None:
        """import_from_gap_analysis uses cluster_name as category."""
        await queries_json.import_from_gap_analysis("company-abc", "test-co")
        categories = [
            c.kwargs["category"] for c in mock_prompt_repo.create.call_args_list
        ]
        assert categories == ["Mechanism", "Comparison"]

    @pytest.mark.asyncio
    async def test_import_stores_source_metadata(
        self,
        mock_prompt_repo: AsyncMock,
        queries_json: PromptLibraryService,
    ) -> None:
        """import_from_gap_analysis stores query metadata in source_metadata."""
        await queries_json.import_from_gap_analysis("company-abc", "test-co")
        first_meta = mock_prompt_repo.create.call_args_list[0].kwargs[
            "source_metadata"
        ]
        assert first_meta["query_id"] == "q_1"
        assert first_meta["cluster_id"] == "C1"
        assert first_meta["buyer_stage"] == "Consideration"
        assert first_meta["slug"] == "test-co"

    @pytest.mark.asyncio
    async def test_import_file_not_found_raises(
        self,
        mock_prompt_repo: AsyncMock,
        tmp_path: Path,
    ) -> None:
        """import_from_gap_analysis raises FileNotFoundError for missing file."""
        backend = LocalStorageBackend(tmp_path)
        svc = PromptLibraryService(prompt_repo=mock_prompt_repo, backend=backend)
        with pytest.raises(FileNotFoundError, match="queries not found"):
            await svc.import_from_gap_analysis(
                "company-abc", "nonexistent-slug"
            )

    @pytest.mark.asyncio
    async def test_import_skips_empty_query_text(
        self,
        mock_prompt_repo: AsyncMock,
        tmp_path: Path,
    ) -> None:
        """import_from_gap_analysis skips queries with empty text."""
        data = [
            {"query_id": "q_1", "cluster_name": "C1", "query_text": ""},
            {"query_id": "q_2", "cluster_name": "C1", "query_text": "   "},
            {
                "query_id": "q_3",
                "cluster_name": "C1",
                "query_text": "Valid query",
            },
        ]
        slug_dir = tmp_path / "gap_analysis" / "test-co"
        slug_dir.mkdir(parents=True)
        (slug_dir / "queries.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        backend = LocalStorageBackend(tmp_path)
        svc = PromptLibraryService(prompt_repo=mock_prompt_repo, backend=backend)
        result = await svc.import_from_gap_analysis(
            "company-abc", "test-co"
        )
        assert len(result) == 1
        assert mock_prompt_repo.create.await_count == 1

    @pytest.mark.asyncio
    async def test_import_non_list_json_returns_empty(
        self,
        mock_prompt_repo: AsyncMock,
        tmp_path: Path,
    ) -> None:
        """import_from_gap_analysis returns empty if JSON is not a list."""
        slug_dir = tmp_path / "gap_analysis" / "test-co"
        slug_dir.mkdir(parents=True)
        (slug_dir / "queries.json").write_text('{"not": "a list"}', encoding="utf-8")
        backend = LocalStorageBackend(tmp_path)
        svc = PromptLibraryService(prompt_repo=mock_prompt_repo, backend=backend)
        result = await svc.import_from_gap_analysis(
            "company-abc", "test-co"
        )
        assert result == []
        mock_prompt_repo.create.assert_not_awaited()


# ── Bulk Create ───────────────────────────────────────────────────────


class TestBulkCreate:
    """Tests for bulk_create()."""

    @pytest.mark.asyncio
    async def test_bulk_create_success(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """bulk_create creates multiple prompts."""
        created_orms = [
            _make_orm_prompt(text="Prompt A"),
            _make_orm_prompt(text="Prompt B"),
        ]
        mock_prompt_repo.bulk_create.return_value = created_orms
        result = await service.bulk_create(
            "company-abc",
            [{"text": "Prompt A"}, {"text": "Prompt B"}],
        )
        assert len(result) == 2
        assert all(isinstance(p, TrackedPrompt) for p in result)

    @pytest.mark.asyncio
    async def test_bulk_create_skips_duplicates(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """bulk_create skips prompts whose text already exists."""
        mock_prompt_repo.exists_by_text.side_effect = [True, False]
        created = [_make_orm_prompt(text="Prompt B")]
        mock_prompt_repo.bulk_create.return_value = created
        result = await service.bulk_create(
            "company-abc",
            [{"text": "Duplicate"}, {"text": "Prompt B"}],
        )
        assert len(result) == 1
        # bulk_create should be called with only the non-duplicate
        bulk_args = mock_prompt_repo.bulk_create.call_args[0][0]
        assert len(bulk_args) == 1
        assert bulk_args[0]["text"] == "Prompt B"

    @pytest.mark.asyncio
    async def test_bulk_create_empty_list(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """bulk_create with empty list returns empty."""
        result = await service.bulk_create("company-abc", [])
        assert result == []
        mock_prompt_repo.bulk_create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_bulk_create_all_duplicates(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """bulk_create returns empty when all prompts are duplicates."""
        mock_prompt_repo.exists_by_text.return_value = True
        result = await service.bulk_create(
            "company-abc",
            [{"text": "Dup A"}, {"text": "Dup B"}],
        )
        assert result == []
        mock_prompt_repo.bulk_create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_bulk_create_skips_empty_text(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """bulk_create skips prompts with empty or whitespace text."""
        created = [_make_orm_prompt(text="Valid")]
        mock_prompt_repo.bulk_create.return_value = created
        result = await service.bulk_create(
            "company-abc",
            [{"text": ""}, {"text": "   "}, {"text": "Valid"}],
        )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_bulk_create_preserves_source(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """bulk_create preserves source from input dict."""
        created = [_make_orm_prompt(text="X", source="imported")]
        mock_prompt_repo.bulk_create.return_value = created
        await service.bulk_create(
            "company-abc",
            [{"text": "X", "source": "imported"}],
        )
        bulk_args = mock_prompt_repo.bulk_create.call_args[0][0]
        assert bulk_args[0]["source"] == "imported"

    @pytest.mark.asyncio
    async def test_bulk_create_defaults_source_manual(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """bulk_create defaults source to manual when not specified."""
        created = [_make_orm_prompt(text="X")]
        mock_prompt_repo.bulk_create.return_value = created
        await service.bulk_create("company-abc", [{"text": "X"}])
        bulk_args = mock_prompt_repo.bulk_create.call_args[0][0]
        assert bulk_args[0]["source"] == "manual"

    @pytest.mark.asyncio
    async def test_bulk_create_with_category_and_tags(
        self, service: PromptLibraryService, mock_prompt_repo: AsyncMock
    ) -> None:
        """bulk_create passes category and tags from input dicts."""
        created = [_make_orm_prompt(text="X", category="general", tags=["t1"])]
        mock_prompt_repo.bulk_create.return_value = created
        await service.bulk_create(
            "company-abc",
            [{"text": "X", "category": "general", "tags": ["t1"]}],
        )
        bulk_args = mock_prompt_repo.bulk_create.call_args[0][0]
        assert bulk_args[0]["category"] == "general"
        assert bulk_args[0]["tags"] == ["t1"]


# ── ORM to Pydantic Conversion ───────────────────────────────────────


class TestOrmToPydantic:
    """Tests for the _orm_to_pydantic helper."""

    def test_converts_all_fields(self, service: PromptLibraryService) -> None:
        """_orm_to_pydantic maps all ORM fields to Pydantic correctly."""
        orm_id = uuid.uuid4()
        now = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)
        orm = _make_orm_prompt(
            id=orm_id,
            company_id="co-1",
            text="Test text",
            category="general",
            tags=["a", "b"],
            source="gap_analysis",
            source_metadata={"key": "val"},
            active=False,
            platforms=["openai"],
            created_at=now,
            updated_at=now,
        )
        result = service._orm_to_pydantic(orm)
        assert result.id == str(orm_id)
        assert result.company_id == "co-1"
        assert result.text == "Test text"
        assert result.category == "general"
        assert result.tags == ["a", "b"]
        assert result.source == PromptSource.GAP_ANALYSIS
        assert result.source_metadata == {"key": "val"}
        assert result.active is False
        assert result.platforms == ["openai"]
        assert result.created_at == now
        assert result.updated_at == now

    def test_none_tags_defaults_empty(
        self, service: PromptLibraryService
    ) -> None:
        """_orm_to_pydantic handles None tags gracefully."""
        orm = _make_orm_prompt(tags=None)
        result = service._orm_to_pydantic(orm)
        assert result.tags == []

    def test_none_platforms_defaults_empty(
        self, service: PromptLibraryService
    ) -> None:
        """_orm_to_pydantic handles None platforms gracefully."""
        orm = _make_orm_prompt(platforms=None)
        result = service._orm_to_pydantic(orm)
        assert result.platforms == []

    def test_none_source_defaults_manual(
        self, service: PromptLibraryService
    ) -> None:
        """_orm_to_pydantic handles None source gracefully."""
        orm = _make_orm_prompt(source=None)
        result = service._orm_to_pydantic(orm)
        assert result.source == PromptSource.MANUAL
