"""Tests for ProductRepository — DB-only (auto-skip without TEST_DATABASE_URL)."""
from __future__ import annotations

import pytest
import pytest_asyncio

from tests.db.conftest import pytestmark  # noqa: F401 (auto-skip marker)

from core.db.models.organization import ProductModel
from core.db.repositories.product_repo import ProductRepository


@pytest_asyncio.fixture
async def product_repo(db_session):
    return ProductRepository(db_session)


class TestProductRepository:
    @pytest.mark.asyncio
    async def test_create_product(self, product_repo, sample_company):
        product = await product_repo.create(
            company_id=sample_company.id,
            slug="widget",
            name="Widget",
            domain="widget.test.com",
        )
        assert product.id is not None
        assert product.slug == "widget"
        assert product.company_id == sample_company.id

    @pytest.mark.asyncio
    async def test_get_by_slugs(self, product_repo, sample_company):
        await product_repo.create(
            company_id=sample_company.id,
            slug="gizmo",
            name="Gizmo",
        )
        found = await product_repo.get_by_slugs(sample_company.id, "gizmo")
        assert found is not None
        assert found.name == "Gizmo"

    @pytest.mark.asyncio
    async def test_get_by_slugs_not_found(self, product_repo, sample_company):
        found = await product_repo.get_by_slugs(sample_company.id, "nonexistent")
        assert found is None

    @pytest.mark.asyncio
    async def test_list_by_company(self, product_repo, sample_company):
        for name in ["Alpha", "Beta", "Gamma"]:
            await product_repo.create(
                company_id=sample_company.id,
                slug=name.lower(),
                name=name,
            )
        products = await product_repo.list_by_company(sample_company.id)
        assert len(products) == 3

    @pytest.mark.asyncio
    async def test_update_product(self, product_repo, sample_company):
        product = await product_repo.create(
            company_id=sample_company.id,
            slug="old-name",
            name="Old Name",
        )
        updated = await product_repo.update(product.id, name="New Name")
        assert updated is not None
        assert updated.name == "New Name"

    @pytest.mark.asyncio
    async def test_delete_product(self, product_repo, sample_company):
        product = await product_repo.create(
            company_id=sample_company.id,
            slug="to-delete",
            name="To Delete",
        )
        deleted = await product_repo.delete(product.id)
        assert deleted is True
        found = await product_repo.get_by_id(product.id)
        assert found is None

    @pytest.mark.asyncio
    async def test_product_with_description(self, product_repo, sample_company):
        product = await product_repo.create(
            company_id=sample_company.id,
            slug="detailed",
            name="Detailed Product",
            description="A very detailed product.",
        )
        assert product.description == "A very detailed product."
