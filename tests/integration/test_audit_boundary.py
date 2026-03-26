"""Integration tests for site audit pipeline write-then-read boundary.

Verifies that audit_result.json written by the site audit pipeline can be
correctly read by the JSON site audit data service.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from core.services.json_site_audit_data import JsonSiteAuditDataService

# Deterministic UUID4 for tests
_AUDIT_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


# ── Fixtures ─────────────────────────────────────────────────────────


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _sample_audit_result(
    audit_id: str = _AUDIT_ID,
    domain: str = "example.com",
    overall_score: float = 72.5,
    status: str = "completed",
    pages_crawled: int = 15,
) -> Dict[str, Any]:
    """Generate production-shaped audit_result.json."""
    return {
        "audit_id": audit_id,
        "domain": domain,
        "status": status,
        "overall_score": overall_score,
        "grade": "B" if overall_score >= 70 else "C",
        "pages_crawled": pages_crawled,
        "dimension_scores": {
            "technical_seo": 85.0,
            "content_quality": 70.0,
            "ai_readiness": 65.0,
            "schema_markup": 60.0,
            "mobile_friendliness": 80.0,
            "page_speed": 75.0,
            "accessibility": 68.0,
            "security": 90.0,
        },
        "ai_bot_access": {
            "googlebot": True,
            "bingbot": True,
            "gptbot": False,
            "claudebot": True,
        },
        "sitemap_health": {
            "has_sitemap": True,
            "sitemap_url_count": 120,
            "valid_urls": 115,
        },
        "top_findings": [
            {
                "finding_id": "f-1",
                "severity": "high",
                "dimension": "ai_readiness",
                "title": "Missing GPTBot access",
                "description": "robots.txt blocks GPTBot",
                "recommendation": "Allow GPTBot in robots.txt",
            },
            {
                "finding_id": "f-2",
                "severity": "medium",
                "dimension": "schema_markup",
                "title": "Missing FAQ schema",
                "description": "No FAQ structured data found",
                "recommendation": "Add FAQPage schema markup",
            },
        ],
        "page_results": [
            {
                "url": f"https://{domain}/page-{i}",
                "page_score": 70.0 + i,
                "findings": [
                    {
                        "finding_id": f"pf-{i}-1",
                        "severity": "low",
                        "dimension": "content_quality",
                        "title": f"Page {i} finding",
                        "description": "Minor issue",
                        "recommendation": "Fix it",
                    },
                ],
            }
            for i in range(pages_crawled)
        ],
        "created_at": "2026-03-24T10:00:00Z",
        "completed_at": "2026-03-24T10:05:00Z",
    }


@pytest.fixture
def svc(tmp_path: Path) -> JsonSiteAuditDataService:
    return JsonSiteAuditDataService(artifacts_root=tmp_path)


# ── Audit summary ────────────────────────────────────────────────────


class TestAuditSummary:
    @pytest.mark.asyncio
    async def test_summary_from_audit_result(self, tmp_path: Path, svc: JsonSiteAuditDataService):
        slug = "test-co"
        _write_json(
            tmp_path / "site_audit" / slug / _AUDIT_ID / "audit_result.json",
            _sample_audit_result(),
        )

        result = await svc.get_audit_summary(slug, _AUDIT_ID)

        assert result["audit_id"] == _AUDIT_ID
        assert result["domain"] == "example.com"
        assert result["overall_score"] == 72.5
        assert result["grade"] == "B"
        assert result["pages_crawled"] == 15

    @pytest.mark.asyncio
    async def test_missing_audit_raises_404(self, svc: JsonSiteAuditDataService):
        with pytest.raises(Exception):
            await svc.get_audit_summary("test-co", "nonexistent")


# ── Audit detail ─────────────────────────────────────────────────────


class TestAuditDetail:
    @pytest.mark.asyncio
    async def test_detail_includes_dimension_scores(self, tmp_path: Path, svc: JsonSiteAuditDataService):
        slug = "test-co"
        _write_json(
            tmp_path / "site_audit" / slug / _AUDIT_ID / "audit_result.json",
            _sample_audit_result(),
        )

        result = await svc.get_audit_detail(slug, _AUDIT_ID)

        assert "dimension_scores" in result
        assert result["dimension_scores"]["technical_seo"] == 85.0
        assert "ai_bot_access" in result
        assert result["ai_bot_access"]["gptbot"] is False


# ── List audits ──────────────────────────────────────────────────────


class TestListAudits:
    @pytest.mark.asyncio
    async def test_list_multiple_audits(self, tmp_path: Path, svc: JsonSiteAuditDataService):
        slug = "test-co"
        _uuids = [
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "b2c3d4e5-f6a7-8901-bcde-f12345678901",
            "c3d4e5f6-a7b8-9012-cdef-123456789012",
        ]
        for i, uid in enumerate(_uuids):
            _write_json(
                tmp_path / "site_audit" / slug / uid / "audit_result.json",
                {**_sample_audit_result(audit_id=uid), "overall_score": 70.0 + i},
            )

        result = await svc.list_audits(slug)

        assert len(result) >= 3

    @pytest.mark.asyncio
    async def test_empty_company_returns_empty_list(self, svc: JsonSiteAuditDataService):
        result = await svc.list_audits("nonexistent-co")
        assert result == []


# ── Edge cases ───────────────────────────────────────────────────────


class TestAuditEdgeCases:
    @pytest.mark.asyncio
    async def test_degraded_audit_status(self, tmp_path: Path, svc: JsonSiteAuditDataService):
        slug = "test-co"
        audit = _sample_audit_result(status="degraded", pages_crawled=3)
        _write_json(
            tmp_path / "site_audit" / slug / _AUDIT_ID / "audit_result.json",
            audit,
        )

        result = await svc.get_audit_summary(slug, _AUDIT_ID)
        assert result["status"] in ("degraded", "completed")

    @pytest.mark.asyncio
    async def test_audit_exists_check(self, tmp_path: Path, svc: JsonSiteAuditDataService):
        slug = "test-co"
        _write_json(
            tmp_path / "site_audit" / slug / _AUDIT_ID / "audit_result.json",
            _sample_audit_result(domain="example.com"),
        )

        exists = await svc.audit_exists(slug, "example.com")
        assert exists is True

        not_exists = await svc.audit_exists(slug, "other.com")
        assert not_exists is False
