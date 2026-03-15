"""Tests for JsonVSGDataService — filesystem-backed VSG read service."""
from __future__ import annotations

from pathlib import Path

import pytest

from core.services.json_vsg_data import JsonVSGDataService
from core.services.vsg_data import VSGDataServiceProtocol


@pytest.fixture
def vsg_root(tmp_path: Path) -> Path:
    """Create a minimal VSG fixture using actual storage class."""
    from core.research.voice_style_guide.storage import VoiceStyleGuideStorage

    storage = VoiceStyleGuideStorage(tmp_path, "test-co")
    storage.write_author_research(
        "author-001", "Jane Doe",
        "# Jane Doe Research\n\nWriting style analysis.",
    )
    storage.write_guide(
        "# Voice Style Guide\n\nBrand voice: authoritative yet approachable.",
        source_authors=["author-001"],
    )
    return tmp_path


class TestJsonVSGDataService:
    async def test_protocol_conformance(self, tmp_path):
        svc = JsonVSGDataService(tmp_path)
        assert isinstance(svc, VSGDataServiceProtocol)

    async def test_get_summary(self, vsg_root):
        svc = JsonVSGDataService(vsg_root)
        result = await svc.get_summary("test-co")
        assert result["slug"] == "test-co"
        assert result["has_guide"] is True
        assert result["guide_word_count"] > 0

    async def test_get_guide(self, vsg_root):
        svc = JsonVSGDataService(vsg_root)
        result = await svc.get_guide("test-co")
        assert result is not None
        assert "authoritative" in result["content_md"]

    async def test_get_guide_missing(self, tmp_path):
        svc = JsonVSGDataService(tmp_path)
        result = await svc.get_guide("nonexistent")
        assert result is None

    async def test_list_authors(self, vsg_root):
        svc = JsonVSGDataService(vsg_root)
        result = await svc.list_authors("test-co")
        assert len(result) >= 1
        assert result[0]["name"] == "Jane Doe"
        assert result[0]["has_research"] is True

    async def test_get_author_research(self, vsg_root):
        svc = JsonVSGDataService(vsg_root)
        result = await svc.get_author_research("test-co", "author-001")
        assert result is not None
        assert "Writing style" in result["content_md"]

    async def test_get_author_research_missing(self, vsg_root):
        svc = JsonVSGDataService(vsg_root)
        result = await svc.get_author_research("test-co", "nonexistent")
        assert result is None

    async def test_get_summary_missing_slug(self, tmp_path):
        svc = JsonVSGDataService(tmp_path)
        result = await svc.get_summary("nonexistent")
        assert result["has_guide"] is False
        assert result["authors_count"] == 0
