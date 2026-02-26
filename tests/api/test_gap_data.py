"""Tests for gap analysis data endpoints.

Covers all 6 GET endpoints under /api/v1/companies/{slug}/gap-analysis/:
  - /summary
  - /queries
  - /clusters
  - /signals
  - /platforms
  - /heatmap

Tests both new-format (gap_analysis_complete.json) and old-format (analysis.json)
artifacts for backward compatibility.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

# ── Fixture builders ─────────────────────────────────────────────────


def _make_gap(
    idx: int,
    cluster_name: str = "Product Comparisons",
    cluster_id: str = "c1",
    interpretation: str = "significant_gap",
    gap: float = 0.15,
    with_brief: bool = True,
    with_exemplars: bool = True,
) -> Dict[str, Any]:
    """Build a single gap entry."""
    g: Dict[str, Any] = {
        "query_id": f"q{idx}",
        "query_text": f"test query {idx}",
        "cluster_name": cluster_name,
        "cluster_id": cluster_id,
        "interpretation": interpretation,
        "gap": gap,
        "best_company_similarity": 0.3 + idx * 0.01,
        "avg_citation_similarity": 0.5 + idx * 0.01,
    }
    if with_brief:
        g["content_brief"] = {
            "target_word_count": [1000, 2000],
            "target_reading_level": [8.0, 12.0],
            "recommended_header_count": [3, 8],
            "header_hierarchy": {"h2": 4, "h3": 3},
            "has_faq_section": 0.7,
            "has_key_takeaways": 0.6,
            "has_step_by_step": 0.2,  # below threshold
            "has_tables": 0.9,        # GapContentBrief field (not has_comparison_table)
            "has_definition_opening": 0.0,
            "has_research_refs": 0.0,
            "has_expert_quotes": 0.0,
            "dominant_authority_type": "industry_report",
            "dominant_content_type": "guide",
            "exemplar_count": 5,
        }
    if with_exemplars:
        g["top_cited_exemplars"] = [
            {
                "similarity": 0.85,
                "domain": "example.com",
                "url": f"https://example.com/article-{idx}",
                "snippet": "Top exemplar snippet",
                "authority_type": "industry_report",
                "structural_signals": {"content_type": "guide"},
            },
            {
                "similarity": 0.72,
                "domain": "other.com",
                "url": f"https://other.com/page-{idx}",
                "snippet": "Second exemplar",
                "authority_type": "blog",
                "structural_signals": {"content_type": "article"},
            },
        ]
    return g


def _make_cluster_spec(
    name: str,
    cluster_id: str = "c1",
    query_count: int = 5,
    citations: int = 20,
) -> Dict[str, Any]:
    return {
        "cluster_name": name,
        "cluster_id": cluster_id,
        "query_count": query_count,
        "total_citations_analyzed": citations,
        "word_count_range": [800, 2500],
        "required_elements": ["headers", "lists"],
        "structural_rates": {
            "headers": 0.9,
            "lists": 0.6,
            "tables": 0.2,
            "stats": 0.3,
            "citations": 0.1,
        },
        "avg_word_count": 1500.0,
        "faq_rate": 0.4,
        "table_rate": 0.2,
        "key_takeaways_rate": 0.5,
        "dominant_content_type": "guide",
        "dominant_authority_type": "industry_report",
        "exemplar_themes": ["comparisons", "pricing"],
    }


def _make_complete_new_format(
    num_gaps: int = 5,
    num_clusters: int = 2,
    with_briefs: bool = True,
) -> Dict[str, Any]:
    """Webflow-style gap_analysis_complete.json with content_briefs."""
    cluster_names = [f"cluster-{i}" for i in range(num_clusters)]
    gaps = []
    for i in range(num_gaps):
        cname = cluster_names[i % num_clusters]
        cid = f"c{i % num_clusters}"
        interps = ["significant_gap", "gap_to_close", "roughly_equal", "company_wins"]
        gaps.append(
            _make_gap(
                i,
                cluster_name=cname,
                cluster_id=cid,
                interpretation=interps[i % 4],
                gap=0.1 + i * 0.05,
                with_brief=with_briefs,
            )
        )

    cluster_specs = [
        _make_cluster_spec(cname, cluster_id=f"c{idx}")
        for idx, cname in enumerate(cluster_names)
    ]

    return {
        "generated_at": "2026-02-25T00:00:00",
        "analysis": {
            "gaps": gaps,
            "spa_results": [
                {
                    "cluster_name": "all",
                    "t_stat": -3.45,
                    "p_value": 0.001,
                    "effect": "medium",
                    "mean_citation_similarity": 0.52,
                    "mean_company_similarity": 0.35,
                },
            ],
            "proximity_stats": {
                "citation_similarity_mean": 0.52,
                "citation_similarity_median": 0.50,
                "company_similarity_mean": 0.35,
                "company_similarity_median": 0.33,
                "per_cluster": {
                    cname: {"mean": 0.5 + idx * 0.01}
                    for idx, cname in enumerate(cluster_names)
                },
            },
            "centroids": [
                {"cluster_name": cname, "distance": 0.1 + idx * 0.05}
                for idx, cname in enumerate(cluster_names)
            ],
            "cluster_specs": cluster_specs,
            "decision_metrics": {
                "total_queries": num_gaps,
                "total_citations": num_gaps * 4,
                "avg_gap": 0.2,
            },
        },
        "report": {
            "executive_summary": "Test executive summary.",
            "recommendations": [
                {"title": "Create FAQ content", "priority": "high"},
                {"title": "Improve structure", "priority": "medium"},
            ],
        },
        "cluster_specs": cluster_specs,
    }


def _make_analysis_old_format(
    num_gaps: int = 5,
    num_clusters: int = 2,
) -> Dict[str, Any]:
    """Ramp-style analysis.json — no content_briefs, 11-field structural signals."""
    cluster_names = [f"cluster-{i}" for i in range(num_clusters)]
    gaps = []
    for i in range(num_gaps):
        cname = cluster_names[i % num_clusters]
        gaps.append(
            _make_gap(
                i,
                cluster_name=cname,
                cluster_id=f"c{i % num_clusters}",
                interpretation="significant_gap" if i < 3 else "roughly_equal",
                gap=0.1 + i * 0.05,
                with_brief=False,
                with_exemplars=False,
            )
        )

    return {
        "gaps": gaps,
        "spa_results": [
            {
                "cluster_name": "all",
                "t_stat": -2.1,
                "p_value": 0.04,
                "effect": "small",
                "mean_citation_similarity": 0.45,
                "mean_company_similarity": 0.38,
            }
        ],
        "proximity_stats": {
            "citation_similarity_mean": 0.45,
            "citation_similarity_median": 0.43,
            "company_similarity_mean": 0.38,
            "company_similarity_median": 0.36,
        },
        "centroids": [],
        "cluster_specs": [
            _make_cluster_spec(cname, cluster_id=f"c{idx}")
            for idx, cname in enumerate(cluster_names)
        ],
        "decision_metrics": {
            "total_queries": num_gaps,
            "total_citations": num_gaps * 3,
            "avg_gap": 0.18,
        },
    }


def _make_gap_report(
    summary: str = "Test executive summary",
    num_recs: int = 2,
    num_gaps: int = 0,
) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "executive_summary": summary,
        "recommendations": [
            {"title": f"Rec {i}", "priority": "high"} for i in range(num_recs)
        ],
        "spa_results": [
            {
                "cluster_name": "all",
                "t_stat": -4.0,
                "p_value": 0.0005,
                "effect": "large",
                "mean_citation_similarity": 0.60,
                "mean_company_similarity": 0.30,
            }
        ],
        "proximity_stats": {
            "citation_similarity_mean": 0.60,
            "citation_similarity_median": 0.58,
            "company_similarity_mean": 0.30,
            "company_similarity_median": 0.28,
        },
        "decision_metrics": {
            "total_queries": 10,
            "total_citations": 40,
            "avg_gap": 0.25,
        },
    }
    if num_gaps > 0:
        report["gaps"] = [
            _make_gap(i, interpretation="gap_to_close", gap=0.2)
            for i in range(num_gaps)
        ]
    return report


def _make_enriched(
    count: int = 10,
    engines: list[str] | None = None,
    with_similarity: bool = True,
    cluster_name: str = "cluster-0",
    with_new_signals: bool = True,
) -> List[Dict[str, Any]]:
    """Build enriched_citations.json data."""
    if engines is None:
        engines = ["openai", "claude", "perplexity", "gemini"]
    citations = []
    for i in range(count):
        engine = engines[i % len(engines)]
        cit: Dict[str, Any] = {
            "query_id": f"q{i % 5}",
            "query_text": f"test query {i % 5}",
            "engine": engine,
            "url": f"https://example-{i}.com/article",
            "domain": f"example-{i}.com",
            "cluster_name": cluster_name,
        }
        if with_similarity:
            cit["best_paragraphs"] = [
                {"text": "sample text", "similarity": 0.5 + i * 0.03}
            ]
        else:
            cit["best_paragraphs"] = []

        ss: Dict[str, Any] = {
            "word_count": 800 + i * 100,
            "paragraph_count": 10 + i,
            "header_count": 5 + i % 3,
        }
        if with_new_signals:
            ss.update({
                "sentence_count": 30 + i,
                "avg_paragraph_length": 80 + i * 5,
                "reading_level": 9.0 + i * 0.2,
                "self_contained_ratio": 0.7,
                "h1_count": 1,
                "h2_count": 3 + i % 2,
                "h3_count": 2,
                "h4_count": 0,
                "list_block_count": 2 + i % 3,
                "ordered_list_count": 1,
                "table_count": 1 if i % 3 == 0 else 0,
                "code_block_count": 0,
                "has_faq_section": i % 2 == 0,
                "has_definition_opening": i % 3 == 0,
                "has_key_takeaways": i % 2 == 0,
                "has_comparison_table": False,
                "has_step_by_step": False,
                "has_research_refs": False,
                "has_expert_quotes": False,
                "data_point_count": 5 + i,
                "citation_density": 0.002 + i * 0.0005,
                "named_entity_density": 0.01 + i * 0.001,
                "content_type": "guide",
                "authority_type": "industry_report",
            })
        cit["structural_signals"] = ss
        citations.append(cit)
    return citations


def _write_artifact(artifacts_root: Path, slug: str, filename: str, data: Any) -> None:
    """Write a JSON artifact file to the test directory."""
    d = artifacts_root / "gap_analysis" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / filename).write_text(json.dumps(data), encoding="utf-8")


# ── Helper to clear service cache between tests ─────────────────────

@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the service layer JSON cache before each test."""
    from api.services import gap_data_service
    gap_data_service._CACHE.clear()
    yield
    gap_data_service._CACHE.clear()


# ── URL prefix ───────────────────────────────────────────────────────

_PREFIX = "/api/v1/companies"


def _url(slug: str, endpoint: str) -> str:
    return f"{_PREFIX}/{slug}/gap-analysis/{endpoint}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestSlugValidation:
    """Shared slug validation for all endpoints — 400 / 404."""

    endpoints = ["summary", "queries", "clusters", "signals", "platforms", "heatmap"]

    def test_invalid_slug_returns_400(self, client: TestClient, artifacts_root: Path):
        for ep in self.endpoints:
            r = client.get(_url("INVALID_SLUG!", ep))
            assert r.status_code == 400, f"Expected 400 for {ep}"

    def test_missing_slug_returns_404(self, client: TestClient, artifacts_root: Path):
        for ep in self.endpoints:
            r = client.get(_url("nonexistent", ep))
            assert r.status_code == 404, f"Expected 404 for {ep}"

    def test_slug_with_leading_hyphen_returns_400(
        self, client: TestClient, artifacts_root: Path,
    ):
        r = client.get(_url("-bad", "summary"))
        assert r.status_code == 400


class TestGapSummary:
    """GET /summary endpoint."""

    def test_summary_with_complete_json(
        self, client: TestClient, artifacts_root: Path,
    ):
        data = _make_complete_new_format(num_gaps=6)
        _write_artifact(artifacts_root, "webflow", "gap_analysis_complete.json", data)

        r = client.get(_url("webflow", "summary"))
        assert r.status_code == 200
        body = r.json()

        assert body["spa_score"]["t_stat"] == -3.45
        assert body["spa_score"]["effect"] == "medium"
        assert body["proximity_stats"]["citation_similarity_mean"] == 0.52
        assert body["total_queries"] == 6
        assert body["executive_summary"] == "Test executive summary."
        assert len(body["recommendations"]) == 2

    def test_summary_spa_score_fields(
        self, client: TestClient, artifacts_root: Path,
    ):
        data = _make_complete_new_format()
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(_url("test", "summary")).json()
        spa = body["spa_score"]
        assert spa["p_value"] == 0.001
        assert spa["mean_citation_similarity"] == 0.52
        assert spa["mean_company_similarity"] == 0.35
        assert spa["median_citation_similarity"] == 0.50
        assert spa["median_company_similarity"] == 0.33

    def test_summary_classification_counts(
        self, client: TestClient, artifacts_root: Path,
    ):
        data = _make_complete_new_format(num_gaps=8)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(_url("test", "summary")).json()
        counts = body["classification_counts"]
        # 8 gaps with interpretations cycling: sig, gap, eq, win, sig, gap, eq, win
        assert counts["significant_gap"] == 2
        assert counts["gap_to_close"] == 2
        assert counts["roughly_equal"] == 2
        assert counts["company_wins"] == 2

    def test_summary_cluster_performance(
        self, client: TestClient, artifacts_root: Path,
    ):
        data = _make_complete_new_format(num_gaps=4, num_clusters=2)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(_url("test", "summary")).json()
        perf = body["cluster_performance"]
        assert len(perf) == 2
        assert perf[0]["cluster_name"] == "cluster-0"
        assert "structural_rates" in perf[0]

    def test_summary_with_report_json_fallback(
        self, client: TestClient, artifacts_root: Path,
    ):
        """When gap_report.json exists, summary uses it for SPA/proximity."""
        analysis = _make_analysis_old_format()
        report = _make_gap_report(summary="Report summary", num_gaps=3)
        _write_artifact(artifacts_root, "ramp", "analysis.json", analysis)
        _write_artifact(artifacts_root, "ramp", "gap_report.json", report)

        body = client.get(_url("ramp", "summary")).json()
        # Report SPA values should take priority
        assert body["spa_score"]["t_stat"] == -4.0
        assert body["spa_score"]["effect"] == "large"
        assert body["executive_summary"] == "Report summary"

    def test_summary_with_analysis_json_only(
        self, client: TestClient, artifacts_root: Path,
    ):
        """When only analysis.json exists (no complete, no report)."""
        data = _make_analysis_old_format(num_gaps=3)
        _write_artifact(artifacts_root, "ramp", "analysis.json", data)

        body = client.get(_url("ramp", "summary")).json()
        assert body["spa_score"]["t_stat"] == -2.1
        assert body["total_queries"] == 3

    def test_summary_empty_gaps(
        self, client: TestClient, artifacts_root: Path,
    ):
        data = _make_complete_new_format(num_gaps=0)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(_url("test", "summary")).json()
        counts = body["classification_counts"]
        assert counts["significant_gap"] == 0
        assert body["total_queries"] == 0

    def test_summary_no_artifact_files_returns_defaults(
        self, client: TestClient, artifacts_root: Path,
    ):
        """Directory exists but no JSON files — returns default values."""
        (artifacts_root / "gap_analysis" / "empty").mkdir(parents=True)

        body = client.get(_url("empty", "summary")).json()
        assert body["total_queries"] == 0
        assert body["executive_summary"] == ""


class TestGapQueries:
    """GET /queries endpoint — pagination, filtering, sorting."""

    def test_basic_query_list(self, client: TestClient, artifacts_root: Path):
        data = _make_complete_new_format(num_gaps=5)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(_url("test", "queries")).json()
        assert body["total"] == 5
        assert body["page"] == 1
        assert body["page_size"] == 15
        assert body["total_pages"] == 1
        assert len(body["queries"]) == 5

    def test_query_fields(self, client: TestClient, artifacts_root: Path):
        data = _make_complete_new_format(num_gaps=1)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(_url("test", "queries")).json()
        q = body["queries"][0]
        assert "query_id" in q
        assert "query_text" in q
        assert "gap_score" in q
        assert "classification" in q
        assert "platform_citations" in q
        assert "top_exemplars" in q

    def test_query_content_brief_present(
        self, client: TestClient, artifacts_root: Path,
    ):
        data = _make_complete_new_format(num_gaps=1, with_briefs=True)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        q = client.get(_url("test", "queries")).json()["queries"][0]
        brief = q["content_brief"]
        assert brief is not None
        assert brief["target_word_count"] == {"min": 1000, "max": 2000}
        assert brief["target_reading_level"] == {"min": 8.0, "max": 12.0}
        assert brief["recommended_header_count"] == 8  # max of tuple
        assert "FAQ" in brief["content_patterns"]
        assert "Key Takeaways" in brief["content_patterns"]
        assert "Tables" in brief["content_patterns"]
        # Step-by-Step should NOT be there (0.2 < 0.5)
        assert "Step-by-Step" not in brief["content_patterns"]

    def test_query_content_brief_none_for_old_format(
        self, client: TestClient, artifacts_root: Path,
    ):
        data = _make_analysis_old_format(num_gaps=3)
        _write_artifact(artifacts_root, "test", "analysis.json", data)

        q = client.get(_url("test", "queries")).json()["queries"][0]
        assert q["content_brief"] is None

    def test_query_exemplars(self, client: TestClient, artifacts_root: Path):
        data = _make_complete_new_format(num_gaps=1)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        q = client.get(_url("test", "queries")).json()["queries"][0]
        exemplars = q["top_exemplars"]
        assert len(exemplars) == 2
        assert exemplars[0]["similarity"] == 0.85
        assert exemplars[0]["domain"] == "example.com"
        assert exemplars[0]["content_type"] == "guide"

    def test_query_platform_citations(
        self, client: TestClient, artifacts_root: Path,
    ):
        data = _make_complete_new_format(num_gaps=2)
        enriched = _make_enriched(count=8)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)
        _write_artifact(artifacts_root, "test", "enriched_citations.json", enriched)

        q0 = client.get(_url("test", "queries")).json()["queries"][0]
        pc = q0["platform_citations"]
        # enriched has 8 citations cycling q0-q4, so q0 gets at least some
        assert isinstance(pc, dict)

    def test_pagination(self, client: TestClient, artifacts_root: Path):
        data = _make_complete_new_format(num_gaps=25)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(_url("test", "queries") + "?page=1&page_size=10").json()
        assert body["total"] == 25
        assert body["total_pages"] == 3
        assert len(body["queries"]) == 10
        assert body["page"] == 1

        body2 = client.get(_url("test", "queries") + "?page=3&page_size=10").json()
        assert len(body2["queries"]) == 5
        assert body2["page"] == 3

    def test_filter_by_cluster(self, client: TestClient, artifacts_root: Path):
        data = _make_complete_new_format(num_gaps=10, num_clusters=2)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(
            _url("test", "queries") + "?cluster=cluster-0"
        ).json()
        assert body["total"] == 5
        for q in body["queries"]:
            assert q["cluster_name"] == "cluster-0"

    def test_filter_by_classification(
        self, client: TestClient, artifacts_root: Path,
    ):
        data = _make_complete_new_format(num_gaps=8)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(
            _url("test", "queries") + "?classification=significant_gap"
        ).json()
        for q in body["queries"]:
            assert q["classification"] == "significant_gap"

    def test_filter_by_search(self, client: TestClient, artifacts_root: Path):
        data = _make_complete_new_format(num_gaps=5)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(
            _url("test", "queries") + "?search=query+2"
        ).json()
        assert body["total"] >= 1
        for q in body["queries"]:
            assert "query 2" in q["query_text"].lower()

    def test_sort_by_gap_score_asc(
        self, client: TestClient, artifacts_root: Path,
    ):
        data = _make_complete_new_format(num_gaps=5)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(
            _url("test", "queries") + "?sort_by=gap_score&sort_dir=asc"
        ).json()
        scores = [q["gap_score"] for q in body["queries"]]
        assert scores == sorted(scores)

    def test_sort_by_gap_score_desc(
        self, client: TestClient, artifacts_root: Path,
    ):
        data = _make_complete_new_format(num_gaps=5)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(
            _url("test", "queries") + "?sort_by=gap_score&sort_dir=desc"
        ).json()
        scores = [q["gap_score"] for q in body["queries"]]
        assert scores == sorted(scores, reverse=True)

    def test_invalid_page_size_rejected(
        self, client: TestClient, artifacts_root: Path,
    ):
        """page_size > 100 should be rejected by FastAPI validation."""
        data = _make_complete_new_format(num_gaps=1)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        r = client.get(_url("test", "queries") + "?page_size=200")
        assert r.status_code == 422

    def test_page_zero_rejected(
        self, client: TestClient, artifacts_root: Path,
    ):
        data = _make_complete_new_format(num_gaps=1)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        r = client.get(_url("test", "queries") + "?page=0")
        assert r.status_code == 422

    def test_combined_filters(
        self, client: TestClient, artifacts_root: Path,
    ):
        data = _make_complete_new_format(num_gaps=20, num_clusters=4)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(
            _url("test", "queries")
            + "?cluster=cluster-0&classification=significant_gap&sort_by=gap_score&sort_dir=asc&page_size=5"
        ).json()
        for q in body["queries"]:
            assert q["cluster_name"] == "cluster-0"
            assert q["classification"] == "significant_gap"


class TestGapClusters:
    """GET /clusters endpoint."""

    def test_cluster_list(self, client: TestClient, artifacts_root: Path):
        data = _make_complete_new_format(num_clusters=3)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(_url("test", "clusters")).json()
        assert len(body["clusters"]) == 3

    def test_cluster_fields(self, client: TestClient, artifacts_root: Path):
        data = _make_complete_new_format(num_clusters=1)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        c = client.get(_url("test", "clusters")).json()["clusters"][0]
        assert c["cluster_name"] == "cluster-0"
        assert c["query_count"] == 5
        assert c["word_count_range"] == {"min": 800, "max": 2500}
        assert isinstance(c["structural_rates"], dict)
        assert c["faq_rate"] == 0.4
        assert c["dominant_content_type"] == "guide"
        assert "comparisons" in c["exemplar_themes"]

    def test_cluster_centroid_distance(
        self, client: TestClient, artifacts_root: Path,
    ):
        data = _make_complete_new_format(num_clusters=2)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        clusters = client.get(_url("test", "clusters")).json()["clusters"]
        assert clusters[0]["centroid_distance"] == pytest.approx(0.1)
        assert clusters[1]["centroid_distance"] == pytest.approx(0.15)

    def test_cluster_centroid_none_when_missing(
        self, client: TestClient, artifacts_root: Path,
    ):
        """Old format may not have centroid data."""
        data = _make_analysis_old_format(num_clusters=1)
        _write_artifact(artifacts_root, "test", "analysis.json", data)

        c = client.get(_url("test", "clusters")).json()["clusters"][0]
        assert c["centroid_distance"] is None

    def test_cluster_word_count_range_format(
        self, client: TestClient, artifacts_root: Path,
    ):
        data = _make_complete_new_format(num_clusters=1)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        c = client.get(_url("test", "clusters")).json()["clusters"][0]
        assert "min" in c["word_count_range"]
        assert "max" in c["word_count_range"]


class TestGapSignals:
    """GET /signals endpoint — averages, correlations, cluster patterns."""

    def test_signal_averages_new_format(
        self, client: TestClient, artifacts_root: Path,
    ):
        enriched = _make_enriched(count=10, with_new_signals=True)
        data = _make_complete_new_format(num_clusters=1)
        _write_artifact(artifacts_root, "test", "enriched_citations.json", enriched)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(_url("test", "signals")).json()
        signals = body["signals"]
        assert len(signals) > 10  # should have many signals from new format
        names = {s["signal"] for s in signals}
        assert "Word Count" in names
        assert "H2 Count" in names
        assert "FAQ Section" in names

    def test_signal_averages_old_format(
        self, client: TestClient, artifacts_root: Path,
    ):
        """Old format with only 3 known signals — should return only those."""
        enriched = _make_enriched(count=5, with_new_signals=False)
        data = _make_analysis_old_format(num_clusters=1)
        _write_artifact(artifacts_root, "test", "enriched_citations.json", enriched)
        _write_artifact(artifacts_root, "test", "analysis.json", data)

        body = client.get(_url("test", "signals")).json()
        signals = body["signals"]
        names = {s["signal"] for s in signals}
        # Old format has word_count, paragraph_count, header_count
        assert "Word Count" in names
        assert "Paragraph Count" in names
        # Should NOT have new-format-only signals
        assert "H2 Count" not in names
        assert "FAQ Section" not in names

    def test_signal_categories(
        self, client: TestClient, artifacts_root: Path,
    ):
        enriched = _make_enriched(count=10)
        data = _make_complete_new_format()
        _write_artifact(artifacts_root, "test", "enriched_citations.json", enriched)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(_url("test", "signals")).json()
        categories = {s["category"] for s in body["signals"]}
        assert "Text Composition" in categories
        assert "Structural Elements" in categories

    def test_signal_correlations(
        self, client: TestClient, artifacts_root: Path,
    ):
        enriched = _make_enriched(count=10, with_similarity=True)
        data = _make_complete_new_format()
        _write_artifact(artifacts_root, "test", "enriched_citations.json", enriched)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(_url("test", "signals")).json()
        correlations = body["correlations"]
        assert len(correlations) > 0
        # Should be sorted by absolute correlation descending
        abs_corrs = [abs(c["correlation"]) for c in correlations]
        assert abs_corrs == sorted(abs_corrs, reverse=True)

    def test_signal_correlations_empty_with_no_similarity(
        self, client: TestClient, artifacts_root: Path,
    ):
        enriched = _make_enriched(count=2, with_similarity=False)
        data = _make_complete_new_format()
        _write_artifact(artifacts_root, "test", "enriched_citations.json", enriched)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(_url("test", "signals")).json()
        # Only 2 citations without similarity — not enough for correlation
        assert body["correlations"] == []

    def test_cluster_patterns(
        self, client: TestClient, artifacts_root: Path,
    ):
        enriched = _make_enriched(count=10, cluster_name="cluster-0")
        data = _make_complete_new_format(num_clusters=1)
        _write_artifact(artifacts_root, "test", "enriched_citations.json", enriched)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(_url("test", "signals")).json()
        patterns = body["cluster_patterns"]
        assert len(patterns) >= 1
        p = patterns[0]
        assert "faq" in p
        assert "definition_opening" in p
        assert "key_takeaways" in p

    def test_cluster_fingerprints(
        self, client: TestClient, artifacts_root: Path,
    ):
        data = _make_complete_new_format(num_clusters=2)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)
        # Need enriched for the endpoint to not error
        _write_artifact(artifacts_root, "test", "enriched_citations.json", [])

        body = client.get(_url("test", "signals")).json()
        fps = body["cluster_fingerprints"]
        assert len(fps) == 2
        # Values should be between 0 and 1 (normalized)
        for cid, vals in fps.items():
            for dim, v in vals.items():
                assert 0.0 <= v <= 1.0, f"{cid}.{dim} = {v} not in [0,1]"

    def test_signals_empty_enriched(
        self, client: TestClient, artifacts_root: Path,
    ):
        data = _make_complete_new_format()
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)
        _write_artifact(artifacts_root, "test", "enriched_citations.json", [])

        body = client.get(_url("test", "signals")).json()
        assert body["signals"] == []
        assert body["correlations"] == []


class TestGapPlatforms:
    """GET /platforms endpoint."""

    def test_platform_list(self, client: TestClient, artifacts_root: Path):
        enriched = _make_enriched(count=12)
        (artifacts_root / "gap_analysis" / "test").mkdir(parents=True)
        _write_artifact(artifacts_root, "test", "enriched_citations.json", enriched)

        body = client.get(_url("test", "platforms")).json()
        names = {p["name"] for p in body["platforms"]}
        assert "ChatGPT" in names
        assert "Claude" in names
        assert "Perplexity" in names
        assert "Gemini" in names

    def test_platform_total_citations(
        self, client: TestClient, artifacts_root: Path,
    ):
        enriched = _make_enriched(count=8, engines=["openai", "claude"])
        (artifacts_root / "gap_analysis" / "test").mkdir(parents=True)
        _write_artifact(artifacts_root, "test", "enriched_citations.json", enriched)

        body = client.get(_url("test", "platforms")).json()
        totals = {p["name"]: p["total_citations"] for p in body["platforms"]}
        assert totals["ChatGPT"] == 4
        assert totals["Claude"] == 4

    def test_platform_unique_domains(
        self, client: TestClient, artifacts_root: Path,
    ):
        enriched = _make_enriched(count=4, engines=["openai"])
        (artifacts_root / "gap_analysis" / "test").mkdir(parents=True)
        _write_artifact(artifacts_root, "test", "enriched_citations.json", enriched)

        body = client.get(_url("test", "platforms")).json()
        p = body["platforms"][0]
        assert p["unique_domains"] == 4  # each citation has unique domain

    def test_platform_agreement_matrix(
        self, client: TestClient, artifacts_root: Path,
    ):
        enriched = _make_enriched(count=8)
        (artifacts_root / "gap_analysis" / "test").mkdir(parents=True)
        _write_artifact(artifacts_root, "test", "enriched_citations.json", enriched)

        body = client.get(_url("test", "platforms")).json()
        agreement = body["agreement"]
        # Each platform should have 1.0 agreement with itself
        for platform_name, row in agreement.items():
            assert row[platform_name] == 1.0

    def test_platform_exclusivity(
        self, client: TestClient, artifacts_root: Path,
    ):
        enriched = _make_enriched(count=8, cluster_name="cluster-0")
        (artifacts_root / "gap_analysis" / "test").mkdir(parents=True)
        _write_artifact(artifacts_root, "test", "enriched_citations.json", enriched)

        body = client.get(_url("test", "platforms")).json()
        excl = body["citation_exclusivity"]
        assert "cluster-0" in excl
        cluster_excl = excl["cluster-0"]
        assert "all_4" in cluster_excl
        assert "one" in cluster_excl

    def test_platform_per_cluster(
        self, client: TestClient, artifacts_root: Path,
    ):
        enriched = _make_enriched(count=8, engines=["openai"], cluster_name="cluster-0")
        (artifacts_root / "gap_analysis" / "test").mkdir(parents=True)
        _write_artifact(artifacts_root, "test", "enriched_citations.json", enriched)

        body = client.get(_url("test", "platforms")).json()
        p = body["platforms"][0]
        assert "cluster-0" in p["per_cluster"]

    def test_platform_none_engine_skipped(
        self, client: TestClient, artifacts_root: Path,
    ):
        enriched = [
            {"query_id": "q1", "engine": None, "url": "https://a.com", "domain": "a.com"},
            {"query_id": "q1", "engine": "openai", "url": "https://b.com", "domain": "b.com"},
        ]
        (artifacts_root / "gap_analysis" / "test").mkdir(parents=True)
        _write_artifact(artifacts_root, "test", "enriched_citations.json", enriched)

        body = client.get(_url("test", "platforms")).json()
        # Only openai/ChatGPT should be present
        names = {p["name"] for p in body["platforms"]}
        assert "ChatGPT" in names
        assert len(names) == 1

    def test_platforms_empty_enriched(
        self, client: TestClient, artifacts_root: Path,
    ):
        (artifacts_root / "gap_analysis" / "test").mkdir(parents=True)
        _write_artifact(artifacts_root, "test", "enriched_citations.json", [])

        body = client.get(_url("test", "platforms")).json()
        assert body["platforms"] == []
        assert body["agreement"] == {}

    def test_platform_engine_name_mapping(
        self, client: TestClient, artifacts_root: Path,
    ):
        """Verify openai -> ChatGPT display name mapping."""
        enriched = _make_enriched(count=4, engines=["openai"])
        (artifacts_root / "gap_analysis" / "test").mkdir(parents=True)
        _write_artifact(artifacts_root, "test", "enriched_citations.json", enriched)

        body = client.get(_url("test", "platforms")).json()
        assert body["platforms"][0]["name"] == "ChatGPT"


class TestGapHeatmap:
    """GET /heatmap endpoint."""

    def test_heatmap_structure(self, client: TestClient, artifacts_root: Path):
        data = _make_complete_new_format(num_gaps=6, num_clusters=2)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(_url("test", "heatmap")).json()
        assert len(body["clusters"]) == 2
        assert "min_gap" in body
        assert "max_gap" in body

    def test_heatmap_cluster_grouping(
        self, client: TestClient, artifacts_root: Path,
    ):
        data = _make_complete_new_format(num_gaps=6, num_clusters=3)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(_url("test", "heatmap")).json()
        names = {c["cluster_name"] for c in body["clusters"]}
        assert "cluster-0" in names
        assert "cluster-1" in names
        assert "cluster-2" in names

    def test_heatmap_queries_sorted_by_gap(
        self, client: TestClient, artifacts_root: Path,
    ):
        data = _make_complete_new_format(num_gaps=10, num_clusters=1)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(_url("test", "heatmap")).json()
        c = body["clusters"][0]
        scores = [q["gap_score"] for q in c["queries"]]
        assert scores == sorted(scores, reverse=True)

    def test_heatmap_min_max_gap(
        self, client: TestClient, artifacts_root: Path,
    ):
        data = _make_complete_new_format(num_gaps=5)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(_url("test", "heatmap")).json()
        assert body["min_gap"] <= body["max_gap"]
        # Verify against actual gap values
        all_gaps = [q["gap_score"] for c in body["clusters"] for q in c["queries"]]
        if all_gaps:
            assert body["min_gap"] == round(min(all_gaps), 4)
            assert body["max_gap"] == round(max(all_gaps), 4)

    def test_heatmap_empty_gaps(self, client: TestClient, artifacts_root: Path):
        data = _make_complete_new_format(num_gaps=0)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(_url("test", "heatmap")).json()
        assert body["clusters"] == []
        assert body["min_gap"] == 0.0
        assert body["max_gap"] == 0.0

    def test_heatmap_avg_gap_per_cluster(
        self, client: TestClient, artifacts_root: Path,
    ):
        data = _make_complete_new_format(num_gaps=4, num_clusters=2)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body = client.get(_url("test", "heatmap")).json()
        for c in body["clusters"]:
            queries = c["queries"]
            if queries:
                expected_avg = round(
                    sum(q["gap_score"] for q in queries) / len(queries), 4
                )
                assert c["avg_gap"] == expected_avg


class TestBackwardCompat:
    """Tests specifically for old-format (ramp-style) artifacts."""

    def test_analysis_json_fallback(
        self, client: TestClient, artifacts_root: Path,
    ):
        """When only analysis.json exists (no gap_analysis_complete.json)."""
        data = _make_analysis_old_format(num_gaps=5)
        _write_artifact(artifacts_root, "ramp", "analysis.json", data)

        # Summary should work
        body = client.get(_url("ramp", "summary")).json()
        assert body["total_queries"] == 5

        # Queries should work
        body = client.get(_url("ramp", "queries")).json()
        assert body["total"] == 5

        # Clusters should work
        body = client.get(_url("ramp", "clusters")).json()
        assert len(body["clusters"]) == 2

    def test_no_content_briefs_in_queries(
        self, client: TestClient, artifacts_root: Path,
    ):
        data = _make_analysis_old_format(num_gaps=3)
        _write_artifact(artifacts_root, "ramp", "analysis.json", data)

        body = client.get(_url("ramp", "queries")).json()
        for q in body["queries"]:
            assert q["content_brief"] is None
            assert q["patterns"] == []

    def test_no_exemplars_in_queries(
        self, client: TestClient, artifacts_root: Path,
    ):
        data = _make_analysis_old_format(num_gaps=3)
        _write_artifact(artifacts_root, "ramp", "analysis.json", data)

        body = client.get(_url("ramp", "queries")).json()
        for q in body["queries"]:
            assert q["top_exemplars"] == []
            assert q["top_domain"] is None

    def test_heatmap_with_analysis_json(
        self, client: TestClient, artifacts_root: Path,
    ):
        data = _make_analysis_old_format(num_gaps=5, num_clusters=2)
        _write_artifact(artifacts_root, "ramp", "analysis.json", data)

        body = client.get(_url("ramp", "heatmap")).json()
        assert len(body["clusters"]) == 2


class TestCaching:
    """Cache behavior tests."""

    def test_cache_hit(self, client: TestClient, artifacts_root: Path):
        """Second call should use cached data."""
        from api.services import gap_data_service

        data = _make_complete_new_format(num_gaps=3)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        # First call populates cache
        client.get(_url("test", "summary"))
        assert len(gap_data_service._CACHE) > 0

        # Second call uses cache
        client.get(_url("test", "summary"))
        assert len(gap_data_service._CACHE) > 0

    def test_cache_invalidation_on_mtime_change(
        self, client: TestClient, artifacts_root: Path,
    ):
        """Cache should invalidate when file mtime changes."""
        from api.services import gap_data_service

        data = _make_complete_new_format(num_gaps=2)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        body1 = client.get(_url("test", "summary")).json()
        assert body1["total_queries"] == 2

        # Update the file with different data
        data2 = _make_complete_new_format(num_gaps=7)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data2)

        body2 = client.get(_url("test", "summary")).json()
        assert body2["total_queries"] == 7

    def test_cache_eviction(self, client: TestClient, artifacts_root: Path):
        """Cache should evict oldest entry when at capacity."""
        from api.services import gap_data_service

        # Fill cache with more than MAX entries
        for i in range(gap_data_service._CACHE_MAX_ENTRIES + 2):
            slug = f"slug{i}"
            data = _make_complete_new_format(num_gaps=1)
            _write_artifact(artifacts_root, slug, "gap_analysis_complete.json", data)
            client.get(_url(slug, "summary"))

        assert len(gap_data_service._CACHE) <= gap_data_service._CACHE_MAX_ENTRIES

    def test_corrupted_json_returns_defaults(
        self, client: TestClient, artifacts_root: Path,
    ):
        """Corrupted JSON file should be handled gracefully, not crash (C1 fix)."""
        slug_dir = artifacts_root / "gap_analysis" / "broken"
        slug_dir.mkdir(parents=True, exist_ok=True)
        (slug_dir / "gap_analysis_complete.json").write_text(
            "{ this is not valid json !!!", encoding="utf-8",
        )

        resp = client.get(_url("broken", "summary"))
        assert resp.status_code == 200
        body = resp.json()
        # Should return defaults rather than 500
        assert body["total_queries"] == 0

    def test_embeddings_invalid_method_returns_422(
        self, client: TestClient, artifacts_root: Path,
    ):
        """Invalid projection method should return 422 (H1 Literal validation)."""
        data = _make_complete_new_format(num_gaps=1)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        resp = client.get(_url("test", "embeddings"), params={"method": "pca"})
        assert resp.status_code == 422


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CX Regression Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestCX3SortByStringField:
    """CX-3: Sort by string field should not crash with mixed types."""

    def test_sort_by_classification(self, client: TestClient, artifacts_root: Path):
        """sort_by=classification must not TypeError on mixed string/int."""
        data = _make_complete_new_format(num_gaps=5)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        resp = client.get(
            _url("test", "queries"),
            params={"sort_by": "classification", "sort_dir": "asc"},
        )
        assert resp.status_code == 200
        rows = resp.json()["queries"]
        classifications = [r["classification"] for r in rows]
        assert classifications == sorted(classifications)

    def test_sort_by_query_text(self, client: TestClient, artifacts_root: Path):
        """sort_by=query_text must work with string comparison."""
        data = _make_complete_new_format(num_gaps=3)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        resp = client.get(
            _url("test", "queries"),
            params={"sort_by": "query_text", "sort_dir": "asc"},
        )
        assert resp.status_code == 200
        texts = [r["query_text"] for r in resp.json()["queries"]]
        assert texts == sorted(texts)

    def test_sort_by_cluster_name(self, client: TestClient, artifacts_root: Path):
        """sort_by=cluster_name must work as string sort."""
        data = _make_complete_new_format(num_gaps=4, num_clusters=2)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        resp = client.get(
            _url("test", "queries"),
            params={"sort_by": "cluster_name", "sort_dir": "desc"},
        )
        assert resp.status_code == 200
        names = [r["cluster_name"] for r in resp.json()["queries"]]
        assert names == sorted(names, reverse=True)


class TestCX5PlatformStringSimilarity:
    """CX-5: String similarity values should not crash sum()."""

    def test_string_similarity_skipped(self, client: TestClient, artifacts_root: Path):
        """Citations with string similarity values should be silently skipped."""
        data = _make_complete_new_format(num_gaps=1)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        enriched = [
            {
                "query_id": "q0",
                "engine": "openai",
                "url": "https://a.com",
                "domain": "a.com",
                "cluster_name": "cluster-0",
                "best_paragraphs": [{"text": "text", "similarity": "0.9"}],
                "structural_signals": {"word_count": 1000},
            },
            {
                "query_id": "q0",
                "engine": "claude",
                "url": "https://b.com",
                "domain": "b.com",
                "cluster_name": "cluster-0",
                "best_paragraphs": [{"text": "text", "similarity": 0.8}],
                "structural_signals": {"word_count": 1200},
            },
        ]
        _write_artifact(artifacts_root, "test", "enriched_citations.json", enriched)

        resp = client.get(_url("test", "platforms"))
        assert resp.status_code == 200
        platforms = resp.json()["platforms"]
        for p in platforms:
            if p["name"] == "Claude":
                assert p["avg_citation_sim"] == 0.8
            elif p["name"] == "ChatGPT":
                assert p["avg_citation_sim"] == 0.0


class TestCX6NaNInSignals:
    """CX-6: NaN/Inf in structural signals should not cause 500."""

    def test_nan_signal_values_filtered(self, client: TestClient, artifacts_root: Path):
        """NaN structural signal values should be silently dropped."""
        data = _make_complete_new_format(num_gaps=1)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        enriched = [
            {
                "query_id": "q0",
                "engine": "openai",
                "url": "https://a.com",
                "domain": "a.com",
                "cluster_name": "cluster-0",
                "best_paragraphs": [{"text": "t", "similarity": 0.7}],
                "structural_signals": {
                    "word_count": float("nan"),
                    "h2_count": 3,
                    "paragraph_count": float("inf"),
                },
            },
            {
                "query_id": "q0",
                "engine": "claude",
                "url": "https://b.com",
                "domain": "b.com",
                "cluster_name": "cluster-0",
                "best_paragraphs": [{"text": "t", "similarity": 0.8}],
                "structural_signals": {
                    "word_count": 1000,
                    "h2_count": 5,
                    "paragraph_count": 10,
                },
            },
        ]
        _write_artifact(artifacts_root, "test", "enriched_citations.json", enriched)

        resp = client.get(_url("test", "signals"))
        assert resp.status_code == 200
        signals = resp.json()["signals"]
        for sig in signals:
            if sig["signal"] == "Word Count":
                assert sig["citation_avg"] == 1000.0
            if sig["signal"] == "H2 Count":
                assert sig["citation_avg"] == 4.0


class TestCX7MalformedEmbeddingPoints:
    """CX-7: Malformed embedding points should return 422, not 500."""

    def test_malformed_points_return_422(self, client: TestClient, artifacts_root: Path):
        """Points with non-numeric x/y should return 422."""
        viz_dir = artifacts_root / "gap_analysis" / "test" / "visualizations"
        viz_dir.mkdir(parents=True, exist_ok=True)
        data = _make_complete_new_format(num_gaps=1)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        malformed = {
            "method": "umap",
            "point_count": 1,
            "points": [{"x": "not_a_number", "y": "bad", "type": "query"}],
        }
        (viz_dir / "embedding_projections_umap.json").write_text(
            json.dumps(malformed), encoding="utf-8",
        )

        resp = client.get(_url("test", "embeddings"), params={"method": "umap"})
        assert resp.status_code == 422


class TestC7HasComparisonTableRemoved:
    """C7: has_comparison_table removed from _PATTERN_FLAGS.

    GapContentBrief has has_tables (float), not has_comparison_table (StructuralSignals bool).
    Setting only has_comparison_table on a brief should NOT produce a 'Tables' pattern.
    Setting has_tables >= 0.5 SHOULD produce a 'Tables' pattern.
    """

    def _setup(self, artifacts_root: Path, brief_overrides: dict) -> dict:
        """Write a single-gap artifact with custom brief fields and return first query."""
        data = _make_complete_new_format(num_gaps=1, with_briefs=True)
        # Overwrite the content_brief of the single gap
        data["analysis"]["gaps"][0]["content_brief"].update(brief_overrides)
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)
        return data

    def test_has_comparison_table_alone_does_not_produce_tables_pattern(
        self, client: TestClient, artifacts_root: Path,
    ):
        """has_comparison_table is a StructuralSignals field — not checked in _PATTERN_FLAGS."""
        data = _make_complete_new_format(num_gaps=1, with_briefs=True)
        brief = data["analysis"]["gaps"][0]["content_brief"]
        # Remove has_tables (set to 0), keep only has_comparison_table
        brief["has_tables"] = 0.0
        brief["has_comparison_table"] = 0.9
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        q = client.get(_url("test", "queries")).json()["queries"][0]
        assert "Tables" not in q["content_brief"]["content_patterns"]

    def test_has_tables_produces_tables_pattern(
        self, client: TestClient, artifacts_root: Path,
    ):
        """has_tables >= 0.5 on GapContentBrief should produce 'Tables' pattern."""
        data = _make_complete_new_format(num_gaps=1, with_briefs=True)
        data["analysis"]["gaps"][0]["content_brief"]["has_tables"] = 0.9
        _write_artifact(artifacts_root, "test", "gap_analysis_complete.json", data)

        q = client.get(_url("test", "queries")).json()["queries"][0]
        assert "Tables" in q["content_brief"]["content_patterns"]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Phase 5: product_slug query param for all 8 gap-data endpoints
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestGapDataProductSlug:
    """?product_slug= query param routes to {slug}__{product_slug} artifact dir."""

    _ENDPOINTS = ["summary", "queries", "clusters", "signals", "platforms", "heatmap"]

    def test_product_slug_reads_product_dir(
        self, client: TestClient, artifacts_root: Path,
    ) -> None:
        """summary with ?product_slug writes to ramp__card dir, not ramp/."""
        data = _make_complete_new_format(num_gaps=3)
        _write_artifact(artifacts_root, "ramp__card", "gap_analysis_complete.json", data)

        r = client.get(_url("ramp", "summary") + "?product_slug=card")
        assert r.status_code == 200
        assert r.json()["total_queries"] == 3

    def test_company_level_not_affected_by_product_dir(
        self, client: TestClient, artifacts_root: Path,
    ) -> None:
        """Company-level slug still reads from ramp/ dir when no product_slug."""
        company_data = _make_complete_new_format(num_gaps=7)
        product_data = _make_complete_new_format(num_gaps=3)
        _write_artifact(artifacts_root, "ramp", "gap_analysis_complete.json", company_data)
        _write_artifact(artifacts_root, "ramp__card", "gap_analysis_complete.json", product_data)

        r_company = client.get(_url("ramp", "summary"))
        r_product = client.get(_url("ramp", "summary") + "?product_slug=card")

        assert r_company.json()["total_queries"] == 7
        assert r_product.json()["total_queries"] == 3

    def test_missing_product_dir_returns_404(
        self, client: TestClient, artifacts_root: Path,
    ) -> None:
        """?product_slug pointing to nonexistent dir returns 404."""
        r = client.get(_url("ramp", "summary") + "?product_slug=nonexistent")
        assert r.status_code == 404

    def test_all_endpoints_accept_product_slug_param(
        self, client: TestClient, artifacts_root: Path,
    ) -> None:
        """All 7 non-trend endpoints accept ?product_slug= without 422."""
        data = _make_complete_new_format(num_gaps=3)
        _write_artifact(artifacts_root, "ramp__card", "gap_analysis_complete.json", data)
        enriched = _make_enriched(count=5)
        _write_artifact(artifacts_root, "ramp__card", "enriched_citations.json", enriched)

        for ep in self._ENDPOINTS:
            url = _url("ramp", ep) + "?product_slug=card"
            r = client.get(url)
            # All return either 200 (data found) or 404 (artifact missing) — never 422
            assert r.status_code in (200, 404), f"{ep}: unexpected {r.status_code}"

    def test_queries_with_product_slug(
        self, client: TestClient, artifacts_root: Path,
    ) -> None:
        """GET /queries?product_slug= returns queries from product artifact dir."""
        data = _make_complete_new_format(num_gaps=4)
        _write_artifact(artifacts_root, "ramp__card", "gap_analysis_complete.json", data)

        r = client.get(_url("ramp", "queries") + "?product_slug=card")
        assert r.status_code == 200
        assert r.json()["total"] == 4

    def test_embeddings_with_product_slug(
        self, client: TestClient, artifacts_root: Path,
    ) -> None:
        """GET /embeddings?product_slug= reads from product dir's visualizations/ subdir."""
        import json
        viz_dir = artifacts_root / "gap_analysis" / "ramp__card" / "visualizations"
        viz_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "method": "umap",
            "points": [{"id": "q1", "x": 0.1, "y": 0.2, "type": "query", "text": "t"}],
        }
        (viz_dir / "embedding_projections_umap.json").write_text(
            json.dumps(data), encoding="utf-8"
        )

        r = client.get(_url("ramp", "embeddings") + "?product_slug=card")
        assert r.status_code == 200

    # ── Trend endpoint ─────────────────────────────────────────────────

    def test_trend_product_slug_returns_product_run(
        self, client: TestClient, task_store,
    ) -> None:
        """GET /trend?product_slug=card returns only the product-scoped run."""
        from api.tasks.models import TaskStatus

        _SPA_RESULT = {
            "cluster_name": "all",
            "t_stat": -2.5,
            "p_value": 0.01,
            "effect": "medium",
            "mean_citation_similarity": 0.6,
            "mean_company_similarity": 0.4,
        }

        task = task_store.create_task("gap_analysis", "ramp", product_slug="card")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.COMPLETED,
            result={
                "report_json": {
                    "spa_results": [_SPA_RESULT],
                    "decision_metrics": {"total_queries": 10, "total_citations": 20},
                }
            },
        )

        r = client.get(_url("ramp", "trend") + "?product_slug=card")
        assert r.status_code == 200
        body = r.json()
        assert len(body["trend"]) == 1
        assert body["trend"][0]["run_id"] == task.task_id
        assert body["trend"][0]["spa_score"] == pytest.approx(-2.5)
        assert body["trend"][0]["total_queries"] == 10

    def test_trend_company_level_excludes_product_run(
        self, client: TestClient, task_store,
    ) -> None:
        """GET /trend (no product_slug) must NOT include product-scoped runs."""
        from api.tasks.models import TaskStatus

        _SPA = {
            "cluster_name": "all",
            "t_stat": -1.0,
            "p_value": 0.05,
            "effect": "small",
            "mean_citation_similarity": 0.5,
            "mean_company_similarity": 0.4,
        }
        _DM = {"total_queries": 5, "total_citations": 8}

        # Company-level run
        t_company = task_store.create_task("gap_analysis", "ramp")
        task_store.update_task(
            t_company.task_id,
            status=TaskStatus.COMPLETED,
            result={"report_json": {"spa_results": [_SPA], "decision_metrics": _DM}},
        )

        # Product-level run — must NOT appear in company-level trend
        t_product = task_store.create_task("gap_analysis", "ramp", product_slug="card")
        task_store.update_task(
            t_product.task_id,
            status=TaskStatus.COMPLETED,
            result={"report_json": {"spa_results": [_SPA], "decision_metrics": _DM}},
        )

        r = client.get(_url("ramp", "trend"))
        assert r.status_code == 200
        run_ids = [pt["run_id"] for pt in r.json()["trend"]]
        assert t_company.task_id in run_ids
        assert t_product.task_id not in run_ids, (
            "Product-scoped run must not appear in company-level trend"
        )
