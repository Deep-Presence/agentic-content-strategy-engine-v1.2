"""Tests for content inventory Pydantic DTOs."""
from __future__ import annotations

import pytest

from core.content_inventory.models import (
    CannibalizationMatch,
    CrawledPageData,
    ExistingCoverageResult,
)


class TestCrawledPageData:
    """CrawledPageData DTO — site audit → inventory ingestion."""

    def test_minimal_construction(self):
        page = CrawledPageData(url="https://example.com/blog")
        assert page.url == "https://example.com/blog"
        assert page.title == ""
        assert page.word_count == 0
        assert page.has_faq_section is False
        assert page.sitemap_lastmod is None

    def test_full_construction(self):
        page = CrawledPageData(
            url="https://example.com/blog/post",
            title="My Blog Post",
            h1_text="Blog Post Title",
            meta_description="A description",
            content_preview="First 500 chars...",
            word_count=1500,
            has_faq_section=True,
            has_schema_markup=True,
            heading_count=8,
            content_type_detected="blog_post",
            sitemap_lastmod="2026-01-15T10:00:00Z",
        )
        assert page.title == "My Blog Post"
        assert page.word_count == 1500
        assert page.has_faq_section is True
        assert page.content_type_detected == "blog_post"
        assert page.sitemap_lastmod == "2026-01-15T10:00:00Z"

    def test_serialization_roundtrip(self):
        page = CrawledPageData(url="https://example.com", title="Test")
        data = page.model_dump()
        restored = CrawledPageData(**data)
        assert restored == page


class TestCannibalizationMatch:
    """CannibalizationMatch DTO — cannibalization check result."""

    def test_construction(self):
        match = CannibalizationMatch(
            inventory_id="abc-123",
            url="https://example.com/existing",
            title="Existing Post",
            similarity=0.87,
            word_count=1200,
        )
        assert match.similarity == 0.87
        assert match.content_preview == ""
        assert match.content_type_detected == ""

    def test_all_fields(self):
        match = CannibalizationMatch(
            inventory_id="abc-123",
            url="https://example.com/existing",
            title="Existing Post",
            similarity=0.92,
            word_count=1200,
            content_preview="Preview text...",
            content_type_detected="blog_post",
        )
        assert match.content_type_detected == "blog_post"

    def test_json_serialization(self):
        match = CannibalizationMatch(
            inventory_id="id-1",
            url="https://example.com",
            title="Test",
            similarity=0.85,
        )
        data = match.model_dump(mode="json")
        assert data["similarity"] == 0.85
        assert data["inventory_id"] == "id-1"


class TestExistingCoverageResult:
    """ExistingCoverageResult DTO — existing content coverage."""

    def test_defaults(self):
        result = ExistingCoverageResult(
            inventory_id="id-1",
            url="https://example.com",
            title="Test",
            similarity=0.80,
        )
        assert result.word_count == 0
        assert result.categories == []
        assert result.content_modified_at is None

    def test_full_construction(self):
        result = ExistingCoverageResult(
            inventory_id="id-1",
            url="https://example.com/page",
            title="Page Title",
            similarity=0.88,
            word_count=2000,
            content_preview="Preview...",
            categories=["tech", "ai"],
            content_modified_at="2026-03-15T10:00:00Z",
        )
        assert result.categories == ["tech", "ai"]
        assert result.content_modified_at == "2026-03-15T10:00:00Z"

    def test_empty_categories_default(self):
        """categories should default to empty list, not None."""
        r1 = ExistingCoverageResult(
            inventory_id="id-1", url="u", title="t", similarity=0.5
        )
        r2 = ExistingCoverageResult(
            inventory_id="id-2", url="u2", title="t2", similarity=0.6
        )
        # Ensure no shared mutable default
        r1.categories.append("x")
        assert r2.categories == []
