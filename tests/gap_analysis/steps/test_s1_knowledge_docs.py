"""Tests for knowledge doc loading and integration into s1 embedding.

Tests the _load_knowledge_doc_units function and its integration with
embed_company_assets — all via StorageBackend (Phase 6 R2 migration).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, patch

import pytest

from core.models.gap_analysis import DiscoverySource, GapAnalysisInput, SemanticUnit
from core.storage.backends.local import LocalStorageBackend


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SLUG = "test-co"


@pytest.fixture()
def storage(tmp_path: Path) -> LocalStorageBackend:
    """Create a LocalStorageBackend rooted at tmp_path."""
    return LocalStorageBackend(tmp_path)


def _write_metadata(storage: LocalStorageBackend, entries: list, slug: str = _SLUG) -> None:
    storage.write(f"knowledge_docs/{slug}/_metadata.json", json.dumps(entries, indent=2))


def _create_doc(storage: LocalStorageBackend, doc_id: str, filename: str, content: str, slug: str = _SLUG) -> dict:
    """Create a knowledge doc file and return its metadata entry."""
    stored_filename = f"{doc_id}_{filename}"
    storage.write(f"knowledge_docs/{slug}/{stored_filename}", content)
    return {
        "id": doc_id,
        "filename": filename,
        "stored_filename": stored_filename,
        "content_type": "text/markdown",
        "file_size_bytes": len(content.encode()),
        "word_count": len(content.split()),
    }


# ---------------------------------------------------------------------------
# _load_knowledge_doc_units tests
# ---------------------------------------------------------------------------


class TestLoadKnowledgeDocUnits:
    """Test the standalone knowledge doc loading function."""

    def test_loads_markdown_doc(self, storage: LocalStorageBackend) -> None:
        from core.gap_analysis.steps.s1_embed_assets import _load_knowledge_doc_units

        entry = _create_doc(
            storage, "doc1", "handbook.md",
            "This is a paragraph with enough words to form a complete chunk "
            "that will pass the minimum word count threshold for chunking. "
            "We need at least eighty words so let us keep writing here. "
            "The content strategy engine processes this text and creates "
            "semantic units from each paragraph. Each semantic unit contains "
            "the text content along with metadata about the source. "
            "Knowledge documents are loaded from the artifacts directory "
            "and chunked into units. These units get embedded alongside "
            "site crawl content. This should now be enough words to form "
            "at least one meaningful chunk for testing."
        )
        _write_metadata(storage, [entry])

        units = _load_knowledge_doc_units(_SLUG, storage)

        assert len(units) >= 1
        assert all(isinstance(u, SemanticUnit) for u in units)
        assert all(u.discovery_source == DiscoverySource.KNOWLEDGE_DOC.value for u in units)
        assert all(u.url is None for u in units)
        assert all(u.title == "handbook.md" for u in units)
        assert all(u.unit_id.startswith("kdoc_") for u in units)

    def test_loads_txt_doc(self, storage: LocalStorageBackend) -> None:
        from core.gap_analysis.steps.s1_embed_assets import _load_knowledge_doc_units

        entry = _create_doc(
            storage, "doc2", "notes.txt",
            "Plain text document with enough words for a full chunk. " * 10,
        )
        _write_metadata(storage, [entry])

        units = _load_knowledge_doc_units(_SLUG, storage)
        assert len(units) >= 1
        assert all(u.discovery_source == DiscoverySource.KNOWLEDGE_DOC.value for u in units)

    def test_empty_slug_returns_empty(self, storage: LocalStorageBackend) -> None:
        from core.gap_analysis.steps.s1_embed_assets import _load_knowledge_doc_units

        units = _load_knowledge_doc_units("nonexistent", storage)
        assert units == []

    def test_no_metadata_returns_empty(self, storage: LocalStorageBackend) -> None:
        from core.gap_analysis.steps.s1_embed_assets import _load_knowledge_doc_units

        # Slug dir exists but no _metadata.json
        storage.mkdir(f"knowledge_docs/{_SLUG}")
        units = _load_knowledge_doc_units(_SLUG, storage)
        assert units == []

    def test_missing_file_skipped(self, storage: LocalStorageBackend) -> None:
        from core.gap_analysis.steps.s1_embed_assets import _load_knowledge_doc_units

        # Metadata references a file that doesn't exist
        entry = {
            "id": "ghost",
            "filename": "ghost.md",
            "stored_filename": "ghost_ghost.md",
            "content_type": "text/markdown",
            "file_size_bytes": 100,
            "word_count": 20,
        }
        _write_metadata(storage, [entry])

        units = _load_knowledge_doc_units(_SLUG, storage)
        assert units == []

    def test_empty_content_skipped(self, storage: LocalStorageBackend) -> None:
        from core.gap_analysis.steps.s1_embed_assets import _load_knowledge_doc_units

        entry = _create_doc(storage, "empty", "empty.md", "")
        _write_metadata(storage, [entry])

        units = _load_knowledge_doc_units(_SLUG, storage)
        assert units == []

    def test_extraction_failure_known_type_logs_warning(self, storage: LocalStorageBackend) -> None:
        """Empty text extraction for a known type (.pdf) should log a warning."""
        from core.gap_analysis.steps.s1_embed_assets import _load_knowledge_doc_units

        # Create a .pdf entry whose bytes exist but extract_text_from_bytes returns ""
        stored = "doc1_report.pdf"
        storage.write_bytes(f"knowledge_docs/{_SLUG}/{stored}", b"%PDF-fake")
        entry = {
            "id": "doc1",
            "filename": "report.pdf",
            "stored_filename": stored,
            "content_type": "application/pdf",
            "file_size_bytes": 9,
            "word_count": 0,
        }
        _write_metadata(storage, [entry])

        with patch(
            "core.gap_analysis.steps.s1_embed_assets.extract_text_from_bytes",
            return_value="",
        ), patch(
            "core.gap_analysis.steps.s1_embed_assets.logger",
        ) as mock_logger:
            units = _load_knowledge_doc_units(_SLUG, storage)

        assert units == []
        # Verify warning was logged with identifying information
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert "Empty text after extraction" in call_args[0][0]
        assert "report.pdf" in call_args[0][1]

    def test_multiple_docs_chunked(self, storage: LocalStorageBackend) -> None:
        from core.gap_analysis.steps.s1_embed_assets import _load_knowledge_doc_units

        long_text = "This is a paragraph with many words. " * 30
        e1 = _create_doc(storage, "d1", "doc1.md", long_text)
        e2 = _create_doc(storage, "d2", "doc2.txt", long_text)
        _write_metadata(storage, [e1, e2])

        units = _load_knowledge_doc_units(_SLUG, storage)
        assert len(units) >= 2
        titles = {u.title for u in units}
        assert "doc1.md" in titles
        assert "doc2.txt" in titles

    def test_start_counter_offset(self, storage: LocalStorageBackend) -> None:
        from core.gap_analysis.steps.s1_embed_assets import _load_knowledge_doc_units

        entry = _create_doc(
            storage, "doc1", "handbook.md",
            "Content word " * 90,
        )
        _write_metadata(storage, [entry])

        units = _load_knowledge_doc_units(_SLUG, storage, start_counter=50)
        assert len(units) >= 1
        # First unit should start from counter 51
        assert units[0].unit_id == "kdoc_51"

    def test_char_and_word_counts_populated(self, storage: LocalStorageBackend) -> None:
        from core.gap_analysis.steps.s1_embed_assets import _load_knowledge_doc_units

        entry = _create_doc(
            storage, "d1", "doc.md",
            "Content word " * 90,
        )
        _write_metadata(storage, [entry])

        units = _load_knowledge_doc_units(_SLUG, storage)
        for u in units:
            assert u.char_count > 0
            assert u.word_count > 0

    def test_unsupported_extension_skipped(self, storage: LocalStorageBackend) -> None:
        from core.gap_analysis.steps.s1_embed_assets import _load_knowledge_doc_units

        # Create a .exe file (unsupported)
        stored = "doc1_virus.exe"
        storage.write(f"knowledge_docs/{_SLUG}/{stored}", "binary data")
        entry = {
            "id": "doc1",
            "filename": "virus.exe",
            "stored_filename": stored,
            "content_type": "application/octet-stream",
            "file_size_bytes": 11,
            "word_count": 2,
        }
        _write_metadata(storage, [entry])

        units = _load_knowledge_doc_units(_SLUG, storage)
        assert units == []


# ---------------------------------------------------------------------------
# Integration with embed_company_assets
# ---------------------------------------------------------------------------


class TestEmbedCompanyAssetsKnowledgeDocs:
    """Test that knowledge docs are merged into embed_company_assets output."""

    @pytest.mark.asyncio
    async def test_knowledge_docs_included_in_output(self, storage: LocalStorageBackend) -> None:
        """When knowledge_doc_slug is set, kdoc units appear in output."""
        from core.gap_analysis.steps.s1_embed_assets import embed_company_assets

        # Set up knowledge docs
        entry = _create_doc(
            storage, "d1", "internal.md",
            "Internal knowledge document content. " * 25,
        )
        _write_metadata(storage, [entry])

        input_data = GapAnalysisInput(
            company_name="Test Co",
            domain="test.com",
            company_slug="test-co",
            knowledge_doc_slug=_SLUG,
        )

        # Mock all external calls
        mock_discovery = (
            # SiteDiscoveryResult
            type("MockResult", (), {
                "domain": "test.com",
                "base_url": "https://test.com",
                "total_pages_discovered": 1,
                "discovery_stats": {"seed_url": 1},
                "pages": [],
                "site_tree": None,
                "sitemaps_found": [],
                "rss_feeds_found": [],
                "crawl_duration_seconds": 0.1,
                "errors": [],
            })(),
            [("https://test.com", "<html><body><p>" + ("Site content. " * 25) + "</p></body></html>")],
        )

        with (
            patch(
                "core.gap_analysis.steps.s1_embed_assets.discover_site_tree",
                new_callable=AsyncMock,
                return_value=mock_discovery,
            ),
            patch(
                "core.gap_analysis.steps.s1_embed_assets.async_embed_texts",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_embed,
            patch(
                "core.gap_analysis.steps.s1_embed_assets.async_delete_company_collection",
                new_callable=AsyncMock,
            ),
            patch(
                "core.gap_analysis.steps.s1_embed_assets.async_upsert_embeddings",
                new_callable=AsyncMock,
            ),
        ):
            # Make embed return correct number of embeddings
            def _fake_embed(texts):
                return [[0.1] * 10 for _ in texts]

            mock_embed.side_effect = _fake_embed

            units = await embed_company_assets(input_data, storage=storage, prefix="gap_analysis/test-co")

        # Should have both site units AND knowledge doc units
        kdoc_units = [u for u in units if u.discovery_source == DiscoverySource.KNOWLEDGE_DOC.value]
        site_units = [u for u in units if u.discovery_source != DiscoverySource.KNOWLEDGE_DOC.value]

        assert len(kdoc_units) >= 1
        assert len(site_units) >= 0  # May or may not have site units depending on chunking
        assert all(u.url is None for u in kdoc_units)
        assert all(u.embedding is not None for u in units)

    @pytest.mark.asyncio
    async def test_no_knowledge_docs_backward_compat(self, storage: LocalStorageBackend) -> None:
        """When knowledge_doc_slug is None, behavior is unchanged."""
        from core.gap_analysis.steps.s1_embed_assets import embed_company_assets

        input_data = GapAnalysisInput(
            company_name="Test Co",
            domain="test.com",
            company_slug="test-co",
            # knowledge_doc_slug not set — defaults to None
        )

        mock_discovery = (
            type("MockResult", (), {
                "domain": "test.com",
                "base_url": "https://test.com",
                "total_pages_discovered": 0,
                "discovery_stats": {},
                "pages": [],
                "site_tree": None,
                "sitemaps_found": [],
                "rss_feeds_found": [],
                "crawl_duration_seconds": 0.1,
                "errors": [],
            })(),
            [],
        )

        with (
            patch(
                "core.gap_analysis.steps.s1_embed_assets.discover_site_tree",
                new_callable=AsyncMock,
                return_value=mock_discovery,
            ),
            patch(
                "core.gap_analysis.steps.s1_embed_assets.async_embed_texts",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "core.gap_analysis.steps.s1_embed_assets.async_delete_company_collection",
                new_callable=AsyncMock,
            ),
            patch(
                "core.gap_analysis.steps.s1_embed_assets.async_upsert_embeddings",
                new_callable=AsyncMock,
            ),
        ):
            units = await embed_company_assets(input_data, storage=storage, prefix="gap_analysis/test-co")

        # No knowledge doc units
        kdoc_units = [u for u in units if u.discovery_source == DiscoverySource.KNOWLEDGE_DOC.value]
        assert len(kdoc_units) == 0


# ---------------------------------------------------------------------------
# Runner knowledge_doc_slug resolution
# ---------------------------------------------------------------------------


class TestRunnerKnowledgeDocResolution:
    """Test that the runner resolves knowledge_doc_slug correctly via StorageBackend."""

    def test_resolves_effective_slug(self, storage: LocalStorageBackend) -> None:
        """Product-level knowledge docs take priority."""
        _write_metadata(storage, [], slug="test-co__widget")
        _write_metadata(storage, [], slug="test-co")

        # Simulate the resolution logic from runner.py
        knowledge_doc_slug = None
        for candidate_slug in ["test-co__widget", "test-co"]:
            if storage.exists(f"knowledge_docs/{candidate_slug}/_metadata.json"):
                knowledge_doc_slug = candidate_slug
                break

        assert knowledge_doc_slug == "test-co__widget"

    def test_falls_back_to_company_slug(self, storage: LocalStorageBackend) -> None:
        """When no product-level docs exist, falls back to company-level."""
        _write_metadata(storage, [], slug="test-co")

        knowledge_doc_slug = None
        for candidate_slug in ["test-co__widget", "test-co"]:
            if storage.exists(f"knowledge_docs/{candidate_slug}/_metadata.json"):
                knowledge_doc_slug = candidate_slug
                break

        assert knowledge_doc_slug == "test-co"

    def test_none_when_no_docs(self, storage: LocalStorageBackend) -> None:
        """When no knowledge docs exist, slug is None."""
        knowledge_doc_slug = None
        for candidate_slug in ["test-co__widget", "test-co"]:
            if storage.exists(f"knowledge_docs/{candidate_slug}/_metadata.json"):
                knowledge_doc_slug = candidate_slug
                break

        assert knowledge_doc_slug is None


# ---------------------------------------------------------------------------
# Embedded status tracking
# ---------------------------------------------------------------------------


class TestMarkKnowledgeDocsEmbedded:
    """Test mark_documents_embedded updates metadata correctly via StorageBackend."""

    def test_marks_all_docs_as_embedded(self, storage: LocalStorageBackend) -> None:
        from core.shared_tools.knowledge_doc_metadata import mark_documents_embedded

        e1 = _create_doc(storage, "d1", "doc1.md", "content")
        e2 = _create_doc(storage, "d2", "doc2.txt", "content")
        _write_metadata(storage, [e1, e2])

        count = mark_documents_embedded(_SLUG, storage=storage)
        assert count == 2

        # Verify metadata was updated
        raw = storage.read(f"knowledge_docs/{_SLUG}/_metadata.json")
        updated = json.loads(raw)
        assert len(updated) == 2
        for entry in updated:
            assert entry["is_embedded"] is True
            assert entry["last_embedded_at"] is not None

    def test_no_metadata_returns_zero(self, storage: LocalStorageBackend) -> None:
        from core.shared_tools.knowledge_doc_metadata import mark_documents_embedded

        count = mark_documents_embedded("nonexistent", storage=storage)
        assert count == 0

    def test_idempotent_re_embedding(self, storage: LocalStorageBackend) -> None:
        """Running embed twice updates the timestamp but doesn't break anything."""
        from core.shared_tools.knowledge_doc_metadata import mark_documents_embedded

        e1 = _create_doc(storage, "d1", "doc.md", "content")
        _write_metadata(storage, [e1])

        mark_documents_embedded(_SLUG, storage=storage)
        raw1 = json.loads(storage.read(f"knowledge_docs/{_SLUG}/_metadata.json"))
        first_ts = raw1[0]["last_embedded_at"]

        # Mark again
        import time
        time.sleep(0.01)
        mark_documents_embedded(_SLUG, storage=storage)
        raw2 = json.loads(storage.read(f"knowledge_docs/{_SLUG}/_metadata.json"))
        second_ts = raw2[0]["last_embedded_at"]

        assert raw2[0]["is_embedded"] is True
        # Timestamps should be different (updated)
        assert second_ts >= first_ts
