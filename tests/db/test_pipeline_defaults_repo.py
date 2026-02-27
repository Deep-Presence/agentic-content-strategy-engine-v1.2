"""Tests for PipelineDefaultsRepository — DB-only (auto-skip without TEST_DATABASE_URL)."""
from __future__ import annotations

import pytest
import pytest_asyncio

from tests.db.conftest import pytestmark  # noqa: F401 (auto-skip marker)

from core.db.repositories.pipeline_defaults_repo import PipelineDefaultsRepository


@pytest_asyncio.fixture
async def defaults_repo(db_session):
    return PipelineDefaultsRepository(db_session)


class TestPipelineDefaultsRepository:
    @pytest.mark.asyncio
    async def test_create_defaults(self, defaults_repo, sample_company):
        defaults = await defaults_repo.create(
            company_id=sample_company.id,
            defaults_json={"platforms": ["openai", "claude"]},
        )
        assert defaults.id is not None
        assert defaults.defaults_json["platforms"] == ["openai", "claude"]

    @pytest.mark.asyncio
    async def test_get_by_company(self, defaults_repo, sample_company):
        await defaults_repo.create(
            company_id=sample_company.id,
            defaults_json={"max_queries": 50},
        )
        found = await defaults_repo.get_by_company(sample_company.id)
        assert found is not None
        assert found.defaults_json["max_queries"] == 50

    @pytest.mark.asyncio
    async def test_get_by_company_not_found(self, defaults_repo, sample_company):
        import uuid
        found = await defaults_repo.get_by_company(uuid.uuid4())
        assert found is None

    @pytest.mark.asyncio
    async def test_upsert_creates(self, defaults_repo, sample_company):
        result = await defaults_repo.upsert(
            sample_company.id,
            {"platforms": ["gemini"]},
        )
        assert result.defaults_json == {"platforms": ["gemini"]}

    @pytest.mark.asyncio
    async def test_upsert_updates(self, defaults_repo, sample_company):
        await defaults_repo.upsert(
            sample_company.id,
            {"platforms": ["openai"]},
        )
        updated = await defaults_repo.upsert(
            sample_company.id,
            {"platforms": ["openai", "claude"], "max_queries": 100},
        )
        assert updated.defaults_json["platforms"] == ["openai", "claude"]
        assert updated.defaults_json["max_queries"] == 100
        assert updated.updated_at is not None

    @pytest.mark.asyncio
    async def test_empty_defaults_json(self, defaults_repo, sample_company):
        result = await defaults_repo.upsert(sample_company.id, {})
        assert result.defaults_json == {}
