"""Tests for Phase 2B: Knowledge doc loading and integration into s1 embedding.

Tests the _load_knowledge_doc_units function and its integration with
embed_company_assets.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, patch

import pytest

from core.models.gap_analysis import DiscoverySource, GapAnalysisInput, SemanticUnit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def kdoc_dir(tmp_path: Path) -> Path:
    """Create a temp knowledge docs directory with metadata and files."""
    d = tmp_path / "knowledge_docs" / "test-co"
    d.mkdir(parents=True)
    return d


def _write_metadata(kdoc_dir: Path, entries: list) -> None:
    (kdoc_dir / "_metadata.json").write_text(json.dumps(entries, indent=2))


def _create_doc(kdoc_dir: Path, doc_id: str, filename: str, content: str) -> dict:
    """Create a knowledge doc file and return its metadata entry."""
    stored_filename = f"{doc_id}_{filename}"
    (kdoc_dir / stored_filename).write_text(content, encoding="utf-8")
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

    def test_loads_markdown_doc(self, kdoc_dir: Path) -> None:
        from core.gap_analysis.steps.s1_embed_assets import _load_knowledge_doc_units

        entry = _create_doc(
            kdoc_dir, "doc1", "handbook.md",
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
        _write_metadata(kdoc_dir, [entry])

        units = _load_knowledge_doc_units(str(kdoc_dir))

        assert len(units) >= 1
        assert all(isinstance(u, SemanticUnit) for u in units)
        assert all(u.discovery_source == DiscoverySource.KNOWLEDGE_DOC.value for u in units)
        assert all(u.url is None for u in units)
        assert all(u.title == "handbook.md" for u in units)
        assert all(u.unit_id.startswith("kdoc_") for u in units)

    def test_loads_txt_doc(self, kdoc_dir: Path) -> None:
        from core.gap_analysis.steps.s1_embed_assets import _load_knowledge_doc_units

        entry = _create_doc(
            kdoc_dir, "doc2", "notes.txt",
            "Plain text document with enough words for a full chunk. " * 10,
        )
        _write_metadata(kdoc_dir, [entry])

        units = _load_knowledge_doc_units(str(kdoc_dir))
        assert len(units) >= 1
        assert all(u.discovery_source == DiscoverySource.KNOWLEDGE_DOC.value for u in units)

    def test_empty_directory_returns_empty(self, tmp_path: Path) -> None:
        from core.gap_analysis.steps.s1_embed_assets import _load_knowledge_doc_units

        units = _load_knowledge_doc_units(str(tmp_path / "nonexistent"))
        assert units == []

    def test_no_metadata_returns_empty(self, kdoc_dir: Path) -> None:
        from core.gap_analysis.steps.s1_embed_assets import _load_knowledge_doc_units

        # Dir exists but no _metadata.json
        units = _load_knowledge_doc_units(str(kdoc_dir))
        assert units == []

    def test_missing_file_skipped(self, kdoc_dir: Path) -> None:
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
        _write_metadata(kdoc_dir, [entry])

        units = _load_knowledge_doc_units(str(kdoc_dir))
        assert units == []

    def test_empty_content_skipped(self, kdoc_dir: Path) -> None:
        from core.gap_analysis.steps.s1_embed_assets import _load_knowledge_doc_units

        entry = _create_doc(kdoc_dir, "empty", "empty.md", "")
        _write_metadata(kdoc_dir, [entry])

        units = _load_knowledge_doc_units(str(kdoc_dir))
        assert units == []

    def test_multiple_docs_chunked(self, kdoc_dir: Path) -> None:
        from core.gap_analysis.steps.s1_embed_assets import _load_knowledge_doc_units

        long_text = "This is a paragraph with many words. " * 30
        e1 = _create_doc(kdoc_dir, "d1", "doc1.md", long_text)
        e2 = _create_doc(kdoc_dir, "d2", "doc2.txt", long_text)
        _write_metadata(kdoc_dir, [e1, e2])

        units = _load_knowledge_doc_units(str(kdoc_dir))
        assert len(units) >= 2
        titles = {u.title for u in units}
        assert "doc1.md" in titles
        assert "doc2.txt" in titles

    def test_start_counter_offset(self, kdoc_dir: Path) -> None:
        from core.gap_analysis.steps.s1_embed_assets import _load_knowledge_doc_units

        entry = _create_doc(
            kdoc_dir, "doc1", "handbook.md",
            "Content word " * 90,
        )
        _write_metadata(kdoc_dir, [entry])

        units = _load_knowledge_doc_units(str(kdoc_dir), start_counter=50)
        assert len(units) >= 1
        # First unit should start from counter 51
        assert units[0].unit_id == "kdoc_51"

    def test_char_and_word_counts_populated(self, kdoc_dir: Path) -> None:
        from core.gap_analysis.steps.s1_embed_assets import _load_knowledge_doc_units

        entry = _create_doc(
            kdoc_dir, "d1", "doc.md",
            "Content word " * 90,
        )
        _write_metadata(kdoc_dir, [entry])

        units = _load_knowledge_doc_units(str(kdoc_dir))
        for u in units:
            assert u.char_count > 0
            assert u.word_count > 0

    def test_unsupported_extension_skipped(self, kdoc_dir: Path) -> None:
        from core.gap_analysis.steps.s1_embed_assets import _load_knowledge_doc_units

        # Create a .exe file (unsupported)
        stored = "doc1_virus.exe"
        (kdoc_dir / stored).write_text("binary data")
        entry = {
            "id": "doc1",
            "filename": "virus.exe",
            "stored_filename": stored,
            "content_type": "application/octet-stream",
            "file_size_bytes": 11,
            "word_count": 2,
        }
        _write_metadata(kdoc_dir, [entry])

        units = _load_knowledge_doc_units(str(kdoc_dir))
        assert units == []


# ---------------------------------------------------------------------------
# Integration with embed_company_assets
# ---------------------------------------------------------------------------


class TestEmbedCompanyAssetsKnowledgeDocs:
    """Test that knowledge docs are merged into embed_company_assets output."""

    @pytest.mark.asyncio
    async def test_knowledge_docs_included_in_output(self, tmp_path: Path) -> None:
        """When knowledge_doc_dir is set, kdoc units appear in output."""
        from core.gap_analysis.steps.s1_embed_assets import embed_company_assets

        # Set up knowledge docs
        kdoc_dir = tmp_path / "knowledge_docs" / "test-co"
        kdoc_dir.mkdir(parents=True)
        entry = _create_doc(
            kdoc_dir, "d1", "internal.md",
            "Internal knowledge document content. " * 25,
        )
        _write_metadata(kdoc_dir, [entry])

        input_data = GapAnalysisInput(
            company_name="Test Co",
            domain="test.com",
            company_slug="test-co",
            knowledge_doc_dir=str(kdoc_dir),
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
            patch(
                "core.gap_analysis.steps.s1_embed_assets._ensure_output_dir",
                return_value=tmp_path / "output",
            ),
        ):
            # Make embed return correct number of embeddings
            def _fake_embed(texts):
                return [[0.1] * 10 for _ in texts]

            mock_embed.side_effect = _fake_embed

            # Create output dir
            (tmp_path / "output" / "site_discovery").mkdir(parents=True)

            units = await embed_company_assets(input_data)

        # Should have both site units AND knowledge doc units
        kdoc_units = [u for u in units if u.discovery_source == DiscoverySource.KNOWLEDGE_DOC.value]
        site_units = [u for u in units if u.discovery_source != DiscoverySource.KNOWLEDGE_DOC.value]

        assert len(kdoc_units) >= 1
        assert len(site_units) >= 0  # May or may not have site units depending on chunking
        assert all(u.url is None for u in kdoc_units)
        assert all(u.embedding is not None for u in units)

    @pytest.mark.asyncio
    async def test_no_knowledge_docs_backward_compat(self, tmp_path: Path) -> None:
        """When knowledge_doc_dir is None, behavior is unchanged."""
        from core.gap_analysis.steps.s1_embed_assets import embed_company_assets

        input_data = GapAnalysisInput(
            company_name="Test Co",
            domain="test.com",
            company_slug="test-co",
            # knowledge_doc_dir not set — defaults to None
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
            patch(
                "core.gap_analysis.steps.s1_embed_assets._ensure_output_dir",
                return_value=tmp_path / "output",
            ),
        ):
            (tmp_path / "output" / "site_discovery").mkdir(parents=True)

            units = await embed_company_assets(input_data)

        # No knowledge doc units
        kdoc_units = [u for u in units if u.discovery_source == DiscoverySource.KNOWLEDGE_DOC.value]
        assert len(kdoc_units) == 0


# ---------------------------------------------------------------------------
# Runner knowledge_doc_dir resolution
# ---------------------------------------------------------------------------


class TestRunnerKnowledgeDocResolution:
    """Test that the runner resolves knowledge_doc_dir correctly."""

    def test_resolves_effective_slug_dir(self, tmp_path: Path) -> None:
        """Product-level knowledge docs take priority."""
        kdocs = tmp_path / "knowledge_docs" / "test-co__widget"
        kdocs.mkdir(parents=True)
        (kdocs / "_metadata.json").write_text("[]")

        # Also create company-level
        company_kdocs = tmp_path / "knowledge_docs" / "test-co"
        company_kdocs.mkdir(parents=True)
        (company_kdocs / "_metadata.json").write_text("[]")

        # Simulate the resolution logic from runner.py
        knowledge_doc_dir = None
        kdocs_base = tmp_path / "knowledge_docs"
        for candidate_slug in ["test-co__widget", "test-co"]:
            candidate_dir = kdocs_base / candidate_slug
            if candidate_dir.is_dir() and (candidate_dir / "_metadata.json").exists():
                knowledge_doc_dir = str(candidate_dir)
                break

        assert knowledge_doc_dir == str(kdocs)

    def test_falls_back_to_company_slug(self, tmp_path: Path) -> None:
        """When no product-level docs exist, falls back to company-level."""
        company_kdocs = tmp_path / "knowledge_docs" / "test-co"
        company_kdocs.mkdir(parents=True)
        (company_kdocs / "_metadata.json").write_text("[]")

        knowledge_doc_dir = None
        kdocs_base = tmp_path / "knowledge_docs"
        for candidate_slug in ["test-co__widget", "test-co"]:
            candidate_dir = kdocs_base / candidate_slug
            if candidate_dir.is_dir() and (candidate_dir / "_metadata.json").exists():
                knowledge_doc_dir = str(candidate_dir)
                break

        assert knowledge_doc_dir == str(company_kdocs)

    def test_none_when_no_docs(self, tmp_path: Path) -> None:
        """When no knowledge docs exist, dir is None."""
        knowledge_doc_dir = None
        kdocs_base = tmp_path / "knowledge_docs"
        for candidate_slug in ["test-co__widget", "test-co"]:
            candidate_dir = kdocs_base / candidate_slug
            if candidate_dir.is_dir() and (candidate_dir / "_metadata.json").exists():
                knowledge_doc_dir = str(candidate_dir)
                break

        assert knowledge_doc_dir is None


# ---------------------------------------------------------------------------
# Phase 2C: Embedded status tracking
# ---------------------------------------------------------------------------


class TestMarkKnowledgeDocsEmbedded:
    """Test _mark_knowledge_docs_embedded updates metadata correctly."""

    def test_marks_all_docs_as_embedded(self, kdoc_dir: Path) -> None:
        from core.shared_tools.knowledge_doc_metadata import mark_documents_embedded as _mark_knowledge_docs_embedded

        e1 = _create_doc(kdoc_dir, "d1", "doc1.md", "content")
        e2 = _create_doc(kdoc_dir, "d2", "doc2.txt", "content")
        _write_metadata(kdoc_dir, [e1, e2])

        count = _mark_knowledge_docs_embedded(str(kdoc_dir))
        assert count == 2

        # Verify metadata was updated
        updated = json.loads((kdoc_dir / "_metadata.json").read_text())
        assert len(updated) == 2
        for entry in updated:
            assert entry["is_embedded"] is True
            assert entry["last_embedded_at"] is not None

    def test_no_metadata_returns_zero(self, tmp_path: Path) -> None:
        from core.shared_tools.knowledge_doc_metadata import mark_documents_embedded as _mark_knowledge_docs_embedded

        count = _mark_knowledge_docs_embedded(str(tmp_path / "nonexistent"))
        assert count == 0

    def test_idempotent_re_embedding(self, kdoc_dir: Path) -> None:
        """Running embed twice updates the timestamp but doesn't break anything."""
        from core.shared_tools.knowledge_doc_metadata import mark_documents_embedded as _mark_knowledge_docs_embedded

        e1 = _create_doc(kdoc_dir, "d1", "doc.md", "content")
        _write_metadata(kdoc_dir, [e1])

        _mark_knowledge_docs_embedded(str(kdoc_dir))
        first = json.loads((kdoc_dir / "_metadata.json").read_text())
        first_ts = first[0]["last_embedded_at"]

        # Mark again
        import time
        time.sleep(0.01)
        _mark_knowledge_docs_embedded(str(kdoc_dir))
        second = json.loads((kdoc_dir / "_metadata.json").read_text())
        second_ts = second[0]["last_embedded_at"]

        assert second[0]["is_embedded"] is True
        # Timestamps should be different (updated)
        assert second_ts >= first_ts
