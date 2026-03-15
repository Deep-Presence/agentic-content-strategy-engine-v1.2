"""Tests for JsonKBDataService — filesystem-backed KB read service."""
from __future__ import annotations

from pathlib import Path

import pytest

from core.services.json_kb_data import JsonKBDataService
from core.services.kb_data import KBDataServiceProtocol


@pytest.fixture
def kb_root(tmp_path: Path) -> Path:
    """Create a minimal KB fixture using actual storage class."""
    from core.models.knowledge_base import KBDocType
    from core.research.knowledge_base.storage import KBStorage

    storage = KBStorage(tmp_path, "test-co")
    storage.write_version(
        KBDocType.COMPANY_OVERVIEW,
        "# Company Overview\n\nTest Co is a fintech company.",
        {"title": "Company Overview"},
    )
    storage.write_synthesis("# Synthesis\n\nTest Co consolidated profile.")
    return tmp_path


class TestJsonKBDataService:
    async def test_protocol_conformance(self, tmp_path):
        svc = JsonKBDataService(tmp_path)
        assert isinstance(svc, KBDataServiceProtocol)

    async def test_get_summary(self, kb_root):
        svc = JsonKBDataService(kb_root)
        result = await svc.get_summary("test-co")
        assert result["slug"] == "test-co"
        assert "company_overview" in result["docs"]
        assert result["synthesis_version"] >= 1

    async def test_get_doc(self, kb_root):
        svc = JsonKBDataService(kb_root)
        result = await svc.get_doc("test-co", "company_overview")
        assert result is not None
        assert result["doc_type"] == "company_overview"
        assert "fintech" in result["content_md"]
        assert result["word_count"] > 0

    async def test_get_doc_with_version(self, kb_root):
        svc = JsonKBDataService(kb_root)
        result = await svc.get_doc("test-co", "company_overview", version=1)
        assert result is not None
        assert result["version"] == 1

    async def test_get_doc_missing(self, kb_root):
        svc = JsonKBDataService(kb_root)
        result = await svc.get_doc("test-co", "customer_reviews")
        assert result is None

    async def test_get_synthesis(self, kb_root):
        svc = JsonKBDataService(kb_root)
        result = await svc.get_synthesis("test-co")
        assert result is not None
        assert "consolidated" in result["content_md"]
        assert result["word_count"] > 0

    async def test_get_synthesis_missing(self, tmp_path):
        svc = JsonKBDataService(tmp_path)
        result = await svc.get_synthesis("nonexistent")
        assert result is None

    async def test_get_health(self, kb_root):
        svc = JsonKBDataService(kb_root)
        result = await svc.get_health("test-co")
        assert isinstance(result, dict)

    async def test_get_staleness_report_delegates(self, kb_root):
        svc = JsonKBDataService(kb_root)
        result = await svc.get_staleness_report("test-co")
        assert isinstance(result, dict)

    async def test_get_summary_missing_slug(self, tmp_path):
        svc = JsonKBDataService(tmp_path)
        result = await svc.get_summary("nonexistent")
        assert result["slug"] == "nonexistent"
        assert result["docs"] == {}
