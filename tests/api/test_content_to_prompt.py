"""Tests for Content-to-Prompt API endpoints.

Uses the ``client`` fixture (authenticated, member role) from conftest.
The router's ``_get_repos`` is patched to return mock repos, avoiding
real DB connections.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from core.models.daily_tracker import (
    ContentToPromptRunResult,
    GeneratedPagePrompt,
    PagePromptGenerationResult,
)


# ── Helpers ───────────────────────────────────────────────────────────


def _make_link_model(**overrides) -> MagicMock:
    """Create a mock ContentInventoryPromptModel."""
    m = MagicMock()
    m.id = overrides.get("id", uuid.uuid4())
    m.content_inventory_id = overrides.get("content_inventory_id", uuid.uuid4())
    m.tracked_prompt_id = overrides.get("tracked_prompt_id", uuid.uuid4())
    m.generation_run_id = overrides.get("generation_run_id", uuid.uuid4())
    m.buyer_stage = overrides.get("buyer_stage", "tofu")
    m.intent_type = overrides.get("intent_type", "informational")
    m.is_branded = overrides.get("is_branded", False)
    m.approved = overrides.get("approved", True)
    m.is_user_edited = overrides.get("is_user_edited", False)
    return m


def _make_prompt_model(**overrides) -> MagicMock:
    """Create a mock TrackedPromptModel."""
    m = MagicMock()
    m.id = overrides.get("id", uuid.uuid4())
    m.text = overrides.get("text", "What is automation?")
    m.category = overrides.get("category", "informational")
    m.source = overrides.get("source", "content_inventory")
    m.active = overrides.get("active", True)
    m.created_at = overrides.get("created_at", datetime.now(timezone.utc))
    return m


def _make_inventory_model(**overrides) -> MagicMock:
    """Create a mock ContentInventoryModel."""
    m = MagicMock()
    m.id = overrides.get("id", uuid.uuid4())
    m.title = overrides.get("title", "Test Page")
    m.url = overrides.get("url", "https://example.com/test")
    m.company_id = overrides.get("company_id", uuid.uuid4())
    return m


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_repos():
    """Create mock repos matching the dict returned by _get_repos."""
    session = AsyncMock()
    link_repo = AsyncMock()
    prompt_repo = AsyncMock()
    inventory_repo = AsyncMock()

    return {
        "session": session,
        "link_repo": link_repo,
        "prompt_repo": prompt_repo,
        "inventory_repo": inventory_repo,
    }


@pytest.fixture
def patched_client(client: TestClient, mock_repos: dict):
    """Client with _get_repos and _resolve_company_uuid patched."""
    async def _fake_get_repos(request):
        return mock_repos

    async def _fake_resolve_company_uuid(request, auth_service):
        return uuid.UUID("00000000-0000-0000-0000-000000000001")

    with (
        patch("api.routers.content_to_prompt._get_repos", _fake_get_repos),
        patch("api.routers.content_to_prompt._resolve_company_uuid", _fake_resolve_company_uuid),
    ):
        yield client


# ── POST /generate tests ──────────────────────────────────────────────


class TestGeneratePrompts:
    def test_successful_generation(self, patched_client, mock_repos):
        """POST /generate returns 202 with generation summary."""
        run_result = ContentToPromptRunResult(
            generation_run_id=str(uuid.uuid4()),
            pages_processed=1,
            pages_succeeded=1,
            pages_failed=0,
            prompts_created=6,
            prompts_deduplicated=0,
        )

        mock_orchestrator = AsyncMock()
        mock_orchestrator.run_for_pages = AsyncMock(return_value=run_result)

        with (
            patch(
                "core.daily_tracker.content_to_prompt_orchestrator.ContentToPromptOrchestrator",
                return_value=mock_orchestrator,
            ),
            patch(
                "core.daily_tracker.content_to_prompt.ContentToPromptService",
            ),
        ):
            resp = patched_client.post(
                "/api/v1/content-to-prompt/generate",
                json={
                    "page_ids": [str(uuid.uuid4())],
                    "k": 6,
                    "brand_name": "TestBrand",
                },
            )

        assert resp.status_code == 202
        data = resp.json()
        assert data["pages_succeeded"] == 1
        assert data["prompts_created"] == 6

    def test_validation_error_empty_page_ids(self, patched_client):
        """POST /generate with empty page_ids returns 422."""
        resp = patched_client.post(
            "/api/v1/content-to-prompt/generate",
            json={"page_ids": [], "k": 6},
        )
        assert resp.status_code == 422

    def test_validation_error_k_out_of_range(self, patched_client):
        """POST /generate with k < 4 returns 422."""
        resp = patched_client.post(
            "/api/v1/content-to-prompt/generate",
            json={"page_ids": [str(uuid.uuid4())], "k": 2},
        )
        assert resp.status_code == 422

    def test_unauthenticated_returns_401(self, public_client):
        """POST /generate without auth returns 401."""
        resp = public_client.post(
            "/api/v1/content-to-prompt/generate",
            json={"page_ids": [str(uuid.uuid4())]},
        )
        assert resp.status_code == 401


# ── GET /pages/{id}/prompts tests ──────────────────────────────────────


class TestGetPagePrompts:
    def test_returns_linked_prompts(self, patched_client, mock_repos):
        inv_id = uuid.uuid4()
        prompt_id = uuid.uuid4()
        link = _make_link_model(
            content_inventory_id=inv_id,
            tracked_prompt_id=prompt_id,
        )
        prompt = _make_prompt_model(id=prompt_id)

        # Mock page ownership check (company_id matches resolved UUID)
        page = _make_inventory_model(id=inv_id, company_id=uuid.UUID("00000000-0000-0000-0000-000000000001"))
        mock_repos["inventory_repo"].get_by_id = AsyncMock(return_value=page)
        mock_repos["link_repo"].get_prompts_for_page = AsyncMock(return_value=[link])
        mock_repos["prompt_repo"].get_by_id = AsyncMock(return_value=prompt)

        resp = patched_client.get(f"/api/v1/content-to-prompt/pages/{inv_id}/prompts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["prompts"][0]["prompt_id"] == str(prompt_id)
        assert data["prompts"][0]["buyer_stage"] == "tofu"

    def test_empty_page_returns_empty_list(self, patched_client, mock_repos):
        inv_id = uuid.uuid4()
        page = _make_inventory_model(id=inv_id, company_id=uuid.UUID("00000000-0000-0000-0000-000000000001"))
        mock_repos["inventory_repo"].get_by_id = AsyncMock(return_value=page)
        mock_repos["link_repo"].get_prompts_for_page = AsyncMock(return_value=[])

        resp = patched_client.get(f"/api/v1/content-to-prompt/pages/{inv_id}/prompts")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ── GET /pages/{id}/metrics tests ──────────────────────────────────────


class TestGetPageMetrics:
    def test_returns_aggregated_metrics(self, patched_client, mock_repos):
        inv_id = uuid.uuid4()
        page = _make_inventory_model(id=inv_id, company_id=uuid.UUID("00000000-0000-0000-0000-000000000001"))
        mock_repos["inventory_repo"].get_by_id = AsyncMock(return_value=page)
        mock_repos["link_repo"].get_page_metrics = AsyncMock(return_value={
            "total_prompts": 6,
            "active_prompts": 5,
            "mention_rate": 0.42,
            "citation_rate": 0.28,
            "total_responses": 120,
            "by_buyer_stage": [
                {"stage": "tofu", "prompt_count": 2},
                {"stage": "mofu", "prompt_count": 2},
                {"stage": "bofu", "prompt_count": 2},
            ],
        })

        resp = patched_client.get(f"/api/v1/content-to-prompt/pages/{inv_id}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_prompts"] == 6
        assert data["mention_rate"] == 0.42
        assert len(data["by_buyer_stage"]) == 3


# ── POST /approve tests ──────────────────────────────────────────────


class TestApprovePrompts:
    def test_bulk_approve(self, patched_client, mock_repos):
        link_id = uuid.uuid4()
        link = _make_link_model(id=link_id, approved=True)

        mock_repos["link_repo"].approve_links = AsyncMock(return_value=1)
        mock_repos["link_repo"].get_by_id = AsyncMock(return_value=link)
        mock_repos["prompt_repo"].update = AsyncMock()

        resp = patched_client.post(
            "/api/v1/content-to-prompt/approve",
            json={"link_ids": [str(link_id)]},
        )
        assert resp.status_code == 200
        assert resp.json()["approved_count"] == 1


# ── GET /pending tests ────────────────────────────────────────────────


class TestGetPending:
    def test_returns_pending_items(self, patched_client, mock_repos):
        inv_id = uuid.uuid4()
        prompt_id = uuid.uuid4()
        link = _make_link_model(
            content_inventory_id=inv_id,
            tracked_prompt_id=prompt_id,
            approved=False,
        )
        prompt = _make_prompt_model(id=prompt_id)
        inv = _make_inventory_model(id=inv_id)

        mock_repos["link_repo"].get_pending_by_slug = AsyncMock(return_value=[link])
        mock_repos["prompt_repo"].get_by_id = AsyncMock(return_value=prompt)
        mock_repos["inventory_repo"].get_by_id = AsyncMock(return_value=inv)

        resp = patched_client.get("/api/v1/content-to-prompt/pending")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["pending"][0]["prompt_text"] == "What is automation?"
