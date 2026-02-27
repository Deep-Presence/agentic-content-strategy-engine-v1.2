"""Tests for CacheRepository (platform result & URL enrichment caches)."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

from core.db.enums import SearchEngine
from core.db.repositories.cache_repo import CacheRepository

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", ""),
    reason="TEST_DATABASE_URL not set",
)


# ── Platform Result Cache ─────────────────────────────────────────────


async def test_upsert_platform_result_creates_new(db_session):
    """upsert_platform_result() creates a new cache entry."""
    repo = CacheRepository(db_session)
    now = datetime.now(timezone.utc)

    result = await repo.upsert_platform_result(
        query_text_hash="hash_abc",
        query_text="What is Ramp?",
        engine=SearchEngine.openai,
        response_text="Ramp is a spend management platform.",
        citations={"urls": ["https://ramp.com"]},
        fetched_at=now,
    )

    assert result.id is not None
    assert result.query_text_hash == "hash_abc"
    assert result.engine == SearchEngine.openai
    assert result.response_text == "Ramp is a spend management platform."


async def test_upsert_platform_result_updates_existing(db_session):
    """upsert_platform_result() updates when same hash+engine already exists."""
    repo = CacheRepository(db_session)
    now = datetime.now(timezone.utc)

    # First insert
    first = await repo.upsert_platform_result(
        query_text_hash="hash_dup",
        query_text="What is Carta?",
        engine=SearchEngine.claude,
        response_text="Original answer",
        citations={"urls": []},
        fetched_at=now,
    )
    first_id = first.id

    # Second insert with same hash+engine — should update
    updated = await repo.upsert_platform_result(
        query_text_hash="hash_dup",
        query_text="What is Carta?",
        engine=SearchEngine.claude,
        response_text="Updated answer",
        citations={"urls": ["https://carta.com"]},
        fetched_at=now + timedelta(hours=1),
    )

    assert updated.id == first_id
    assert updated.response_text == "Updated answer"
    assert updated.citations == {"urls": ["https://carta.com"]}


async def test_get_fresh_platform_result_within_ttl(db_session):
    """get_fresh_platform_result() returns result when within TTL."""
    repo = CacheRepository(db_session)
    now = datetime.now(timezone.utc)

    await repo.upsert_platform_result(
        query_text_hash="fresh_hash",
        query_text="Fresh query",
        engine=SearchEngine.gemini,
        response_text="Fresh response",
        citations={},
        fetched_at=now,
    )

    result = await repo.get_fresh_platform_result(
        "fresh_hash", SearchEngine.gemini, max_age_days=7
    )
    assert result is not None
    assert result.response_text == "Fresh response"


async def test_get_fresh_platform_result_expired(db_session):
    """get_fresh_platform_result() returns None for expired entries."""
    repo = CacheRepository(db_session)
    old_time = datetime.now(timezone.utc) - timedelta(days=30)

    await repo.upsert_platform_result(
        query_text_hash="old_hash",
        query_text="Old query",
        engine=SearchEngine.perplexity,
        response_text="Old response",
        citations={},
        fetched_at=old_time,
    )

    result = await repo.get_fresh_platform_result(
        "old_hash", SearchEngine.perplexity, max_age_days=7
    )
    assert result is None


# ── URL Enrichment Cache ──────────────────────────────────────────────


async def test_upsert_url_enrichment_creates_new(db_session):
    """upsert_url_enrichment() creates a new URL enrichment entry."""
    repo = CacheRepository(db_session)
    now = datetime.now(timezone.utc)

    result = await repo.upsert_url_enrichment(
        url_hash="url_hash_1",
        url="https://example.com/article",
        domain="example.com",
        title="Example Article",
        http_status=200,
        scraped_at=now,
    )

    assert result.id is not None
    assert result.url_hash == "url_hash_1"
    assert result.url == "https://example.com/article"
    assert result.domain == "example.com"
    assert result.http_status == 200


async def test_get_fresh_url_enrichment_respects_ttl(db_session):
    """get_fresh_url_enrichment() returns None when TTL expired."""
    repo = CacheRepository(db_session)
    old_time = datetime.now(timezone.utc) - timedelta(days=14)

    await repo.upsert_url_enrichment(
        url_hash="url_expired",
        url="https://old.com/page",
        scraped_at=old_time,
    )

    # Within TTL
    fresh = await repo.get_fresh_url_enrichment("url_expired", max_age_days=30)
    assert fresh is not None

    # Outside TTL
    stale = await repo.get_fresh_url_enrichment("url_expired", max_age_days=7)
    assert stale is None
