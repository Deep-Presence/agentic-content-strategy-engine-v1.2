"""Tenant-scoped prompt library operations."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.daily_tracker.prompt_library import PromptLibraryService


def _make_orm_prompt(*, company_id: str = "test-co") -> SimpleNamespace:
    now = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        company_id=company_id,
        text="What is the best tool?",
        category=None,
        tags=[],
        source="manual",
        source_metadata=None,
        active=True,
        platforms=[],
        created_at=now,
        updated_at=now,
    )


@pytest.fixture()
def mock_prompt_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_by_id_for_company = AsyncMock(return_value=None)
    repo.update = AsyncMock(return_value=None)
    repo.delete = AsyncMock(return_value=True)
    return repo


@pytest.fixture()
def service(mock_prompt_repo: AsyncMock) -> PromptLibraryService:
    return PromptLibraryService(mock_prompt_repo)


@pytest.mark.asyncio
async def test_get_prompt_for_company_returns_none_for_wrong_tenant(
    service: PromptLibraryService,
    mock_prompt_repo: AsyncMock,
) -> None:
    prompt_id = str(uuid.uuid4())
    result = await service.get_prompt_for_company(prompt_id, "test-co")
    assert result is None
    mock_prompt_repo.get_by_id_for_company.assert_awaited_once_with(prompt_id, "test-co")


@pytest.mark.asyncio
async def test_update_prompt_for_company_rejects_cross_tenant(
    service: PromptLibraryService,
    mock_prompt_repo: AsyncMock,
) -> None:
    prompt_id = str(uuid.uuid4())
    with pytest.raises(ValueError, match="not found"):
        await service.update_prompt_for_company(prompt_id, "test-co", text="new")


@pytest.mark.asyncio
async def test_delete_prompt_for_company_returns_false_when_not_owned(
    service: PromptLibraryService,
    mock_prompt_repo: AsyncMock,
) -> None:
    prompt_id = str(uuid.uuid4())
    deleted = await service.delete_prompt_for_company(prompt_id, "other-co")
    assert deleted is False
    mock_prompt_repo.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_prompt_passes_workspace_id(
    service: PromptLibraryService,
    mock_prompt_repo: AsyncMock,
) -> None:
    ws_id = str(uuid.uuid4())
    orm = _make_orm_prompt()
    mock_prompt_repo.exists_by_text = AsyncMock(return_value=False)
    mock_prompt_repo.create = AsyncMock(return_value=orm)

    await service.create_prompt(
        company_id="test-co",
        text="New prompt",
        workspace_id=ws_id,
    )

    create_kwargs = mock_prompt_repo.create.await_args.kwargs
    assert str(create_kwargs["workspace_id"]) == ws_id
