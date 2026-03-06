"""Tests for DbContentDataService — Postgres-backed content data service.

Auto-skips without TEST_DATABASE_URL.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import pytest_asyncio

from core.db.repositories.content_repo import ContentRepository
from core.db.repositories.pipeline_repo import PipelineRepository
from core.services.db_content_data import DbContentDataService

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)


@pytest_asyncio.fixture
async def content_service(svc_db_session, tmp_path):
    """Build a DbContentDataService with repos backed by the test session."""
    return DbContentDataService(
        content_repo=ContentRepository(svc_db_session),
        pipeline_repo=PipelineRepository(svc_db_session),
        artifacts_root=tmp_path,
    )


class TestGetBriefs:
    """Test get_briefs() method."""

    @pytest.mark.asyncio
    async def test_returns_brief_list(
        self, content_service, seed_content_run, seed_content_pieces,
    ):
        resp = await content_service.get_briefs("test-co")
        assert resp.total == 3
        assert len(resp.briefs) == 3

    @pytest.mark.asyncio
    async def test_brief_status_mapping(
        self, content_service, seed_content_run, seed_content_pieces,
    ):
        """Verify DB statuses are mapped to frontend display statuses."""
        resp = await content_service.get_briefs("test-co")
        statuses = {b.status for b in resp.briefs}
        # approved→approved, review→review, drafting→drafting
        assert "approved" in statuses
        assert "review" in statuses
        assert "drafting" in statuses

    @pytest.mark.asyncio
    async def test_citability_score_scaling(
        self, content_service, seed_content_run, seed_content_pieces,
    ):
        """Citability scores stored as 0-1 should be displayed as 0-100."""
        resp = await content_service.get_briefs("test-co")
        for brief in resp.briefs:
            if brief.citability_score is not None:
                assert 0 <= brief.citability_score <= 100

    @pytest.mark.asyncio
    async def test_empty_slug(self, content_service):
        resp = await content_service.get_briefs("nonexistent-slug")
        assert resp.total == 0
        assert resp.briefs == []


class TestGetBriefDetail:
    """Test get_brief_detail() method."""

    @pytest.mark.asyncio
    async def test_returns_detail(
        self, content_service, seed_content_run, seed_content_pieces,
    ):
        piece_id = str(seed_content_pieces[0].id)
        resp = await content_service.get_brief_detail("test-co", piece_id)
        assert resp.id == piece_id
        assert resp.title == "Guide to Spend Management"
        assert resp.status == "approved"

    @pytest.mark.asyncio
    async def test_not_found_raises_404(
        self, content_service, seed_content_run,
    ):
        from fastapi import HTTPException
        import uuid

        with pytest.raises(HTTPException) as exc_info:
            await content_service.get_brief_detail(
                "test-co", str(uuid.uuid4()),
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_no_run_raises_404(self, content_service):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await content_service.get_brief_detail(
                "nonexistent-slug", "brief-1",
            )
        assert exc_info.value.status_code == 404
