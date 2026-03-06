"""Tests for CompanyRepository."""
from __future__ import annotations

import os

import pytest

from core.db.repositories.company_repo import CompanyRepository

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", ""),
    reason="TEST_DATABASE_URL not set",
)


async def test_create_and_get_by_id(db_session):
    """create() then get_by_id() returns the same company."""
    repo = CompanyRepository(db_session)
    company = await repo.create(slug="round-co", name="Round Co", domain="round.com")

    fetched = await repo.get_by_id(company.id)
    assert fetched is not None
    assert fetched.id == company.id
    assert fetched.slug == "round-co"
    assert fetched.name == "Round Co"
    assert fetched.domain == "round.com"


async def test_get_by_slug(db_session):
    """get_by_slug() finds a company by its slug."""
    repo = CompanyRepository(db_session)
    await repo.create(slug="slug-find", name="Slug Find", domain="slug.com")

    found = await repo.get_by_slug("slug-find")
    assert found is not None
    assert found.slug == "slug-find"


async def test_get_by_domain(db_session):
    """get_by_domain() finds a company by its domain."""
    repo = CompanyRepository(db_session)
    await repo.create(slug="domain-co", name="Domain Co", domain="domain-co.com")

    found = await repo.get_by_domain("domain-co.com")
    assert found is not None
    assert found.domain == "domain-co.com"


async def test_list_active_excludes_archived(db_session):
    """list_active() excludes companies where is_archived=True."""
    repo = CompanyRepository(db_session)
    active = await repo.create(
        slug="active-co", name="Active Co", domain="active.com"
    )
    archived = await repo.create(
        slug="archived-co",
        name="Archived Co",
        domain="archived.com",
        is_archived=True,
    )

    results = await repo.list_active()
    result_ids = [r.id for r in results]
    assert active.id in result_ids
    assert archived.id not in result_ids


async def test_get_by_slug_returns_none_for_nonexistent(db_session):
    """get_by_slug() returns None for a slug that does not exist."""
    repo = CompanyRepository(db_session)
    result = await repo.get_by_slug("does-not-exist-xyz")
    assert result is None


async def test_slug_exists_true(db_session):
    """slug_exists() returns True when the slug is taken."""
    repo = CompanyRepository(db_session)
    await repo.create(slug="existing-slug", name="Existing", domain="existing.com")
    assert await repo.slug_exists("existing-slug") is True


async def test_slug_exists_false(db_session):
    """slug_exists() returns False when the slug is available."""
    repo = CompanyRepository(db_session)
    assert await repo.slug_exists("no-such-slug") is False
