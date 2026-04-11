from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from core.db.repositories.content_inventory_prompt_repo import (
    ContentInventoryPromptRepository,
)


def _make_mock_session() -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    result.all.return_value = []
    result.one_or_none.return_value = None
    session.execute.return_value = result
    session.flush = AsyncMock()
    return session


class TestContentInventoryPromptRepository:
    @pytest.fixture()
    def session(self) -> AsyncMock:
        return _make_mock_session()

    @pytest.fixture()
    def repo(self, session: AsyncMock) -> ContentInventoryPromptRepository:
        return ContentInventoryPromptRepository(session)

    @pytest.mark.asyncio
    async def test_get_page_prompt_scope_includes_fanout_children(
        self, repo: ContentInventoryPromptRepository, session: AsyncMock
    ) -> None:
        inventory_id = uuid.uuid4()
        root_prompt_id = uuid.uuid4()
        fanout_prompt_id = uuid.uuid4()

        root_result = MagicMock()
        root_result.scalars.return_value.all.return_value = [root_prompt_id]

        scope_result = MagicMock()
        scope_result.all.return_value = [
            SimpleNamespace(
                prompt_id=root_prompt_id,
                root_prompt_id=root_prompt_id,
                text="expense management software",
                parent_prompt_id=None,
                active=True,
            ),
            SimpleNamespace(
                prompt_id=fanout_prompt_id,
                root_prompt_id=root_prompt_id,
                text="best expense management software for startups",
                parent_prompt_id=root_prompt_id,
                active=True,
            ),
        ]
        session.execute.side_effect = [root_result, scope_result]

        result = await repo.get_page_prompt_scope(inventory_id)

        assert result["root_prompt_ids"] == [root_prompt_id]
        assert result["prompt_ids"] == [root_prompt_id, fanout_prompt_id]
        assert result["fanout_prompt_ids"] == [fanout_prompt_id]
        assert "best expense management software for startups" in result["prompt_texts"]

    @pytest.mark.asyncio
    async def test_get_page_query_overlap_signals_uses_fanout_scope(
        self, repo: ContentInventoryPromptRepository
    ) -> None:
        repo.get_page_prompt_scope = AsyncMock(
            return_value={
                "root_prompt_ids": [uuid.uuid4()],
                "prompt_ids": [uuid.uuid4(), uuid.uuid4()],
                "fanout_prompt_ids": [uuid.uuid4()],
                "prompt_texts": [
                    "expense management software",
                    "best expense management software for startups",
                ],
            },
        )

        result = await repo.get_page_query_overlap_signals(
            uuid.uuid4(),
            [
                "best expense management software",
                "corporate card policy template",
            ],
        )

        assert result["query_overlap_score"] > 0.4
        assert result["overlapping_query_count"] == 1
        assert "best expense management software" in result["matched_queries"]
        assert any("startups" in text for text in result["matched_prompt_texts"])

    @pytest.mark.asyncio
    async def test_get_citation_timeline_uses_root_prompt_rollup_sql(
        self, repo: ContentInventoryPromptRepository, session: AsyncMock
    ) -> None:
        root_prompt_id = uuid.uuid4()
        repo.get_page_root_prompt_ids = AsyncMock(return_value=[root_prompt_id])

        result = MagicMock()
        result.all.return_value = []
        session.execute.return_value = result

        await repo.get_citation_timeline(
            uuid.uuid4(),
            datetime(2026, 4, 1, tzinfo=timezone.utc),
            datetime(2026, 4, 30, tzinfo=timezone.utc),
        )

        stmt = session.execute.call_args.args[0]
        sql = str(
            stmt.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        ).lower()
        assert "coalesce(daily_run_responses.parent_prompt_id, daily_run_responses.prompt_id)" in sql

    @pytest.mark.asyncio
    async def test_get_citation_metrics_batch_uses_root_prompt_rollup_sql(
        self, repo: ContentInventoryPromptRepository, session: AsyncMock
    ) -> None:
        result = MagicMock()
        result.all.return_value = []
        session.execute.return_value = result

        await repo.get_citation_metrics_batch(
            uuid.uuid4(),
            datetime(2026, 4, 1, tzinfo=timezone.utc),
            datetime(2026, 4, 30, tzinfo=timezone.utc),
        )

        stmt = session.execute.call_args.args[0]
        sql = str(
            stmt.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        ).lower()
        assert "coalesce(daily_run_responses.parent_prompt_id, daily_run_responses.prompt_id)" in sql
