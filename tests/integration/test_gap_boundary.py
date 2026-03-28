"""Integration tests for gap analysis pipeline write-then-read boundary.

Verifies that artifacts written by the gap analysis pipeline can be
correctly read by the JSON service layer (gap_data_service.py).

Each test writes production-shaped artifacts to tmp_path, then calls
the service function and verifies the response.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from api.services.gap_data_service import (
    get_clusters,
    get_queries,
    get_summary,
)
from core.storage.backends.local import LocalStorageBackend


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def storage(tmp_path):
    """Return a LocalStorageBackend rooted at tmp_path."""
    return LocalStorageBackend(tmp_path)


@pytest.fixture(autouse=True)
def _clear_cache(monkeypatch):
    """Ensure no Redis cache interferes with tests.

    The old in-memory _CACHE dict was removed in Session 6 (Redis cache migration).
    Tests run without Redis, so cache calls are no-ops — nothing to clear.
    """
    monkeypatch.setattr("core.redis.get_sync_redis_or_none", lambda: None)
    yield


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _sample_gaps(count: int = 3) -> List[Dict[str, Any]]:
    """Generate production-shaped gap entries."""
    interpretations = ["significant_gap", "gap_to_close", "company_wins", "roughly_equal"]
    return [
        {
            "query_id": f"q-{i}",
            "query_text": f"What is the best B2B tool for {['SEO', 'analytics', 'email'][i % 3]}?",
            "cluster_name": f"cluster-{i % 2}",
            "gap": 0.3 - (i * 0.1),
            "citation_similarity": 0.7 + (i * 0.05),
            "company_similarity": 0.4 + (i * 0.05),
            "interpretation": interpretations[i % len(interpretations)],
            "company_cited": i % 2 == 0,
            "content_brief": {
                "target_word_count": [1200, 2000],
                "target_reading_level": [8.0, 12.0],
                "recommended_header_count": [3, 6],
                "has_faq_section": 0.8 if i == 0 else 0.2,
                "has_key_takeaways": 0.7,
                "has_step_by_step": 0.1,
                "has_tables": 0.6,
                "has_definition_opening": 0.9,
                "has_research_refs": 0.3,
                "has_expert_quotes": 0.1,
            },
            "top_cited_exemplars": [
                {
                    "url": f"https://example.com/article-{i}",
                    "domain": "example.com",
                    "similarity": 0.85,
                    "structural_signals": {
                        "word_count": 1500,
                        "h2_count": 5,
                    },
                },
            ],
        }
        for i in range(count)
    ]


def _sample_cluster_specs(count: int = 2) -> List[Dict[str, Any]]:
    """Generate production-shaped cluster specification entries."""
    return [
        {
            "cluster_id": f"cl-{i}",
            "cluster_name": f"cluster-{i}",
            "query_count": 5 + i,
            "total_citations_analyzed": 20 + (i * 10),
            "word_count_range": [1200, 2000],
            "min_similarity_threshold": 0.65,
            "required_elements": ["H2", "FAQ"],
            "structural_rates": {"has_faq_section": 0.6, "has_tables": 0.3},
            "avg_word_count": 1600.0,
            "faq_rate": 0.6,
            "table_rate": 0.3,
            "key_takeaways_rate": 0.4,
            "dominant_content_type": "blog",
            "dominant_authority_type": "expert",
            "exemplar_themes": ["optimization", "strategy"],
        }
        for i in range(count)
    ]


def _sample_analysis(
    gaps: List[Dict[str, Any]] | None = None,
    cluster_specs: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Generate production-shaped analysis.json."""
    return {
        "gaps": gaps or _sample_gaps(),
        "cluster_specs": cluster_specs or _sample_cluster_specs(),
        "spa_results": [
            {
                "cluster_name": "all",
                "t_stat": 2.5,
                "p_value": 0.01,
                "effect": "significant_gap",
                "mean_citation_similarity": 0.75,
                "mean_company_similarity": 0.45,
            },
        ],
        "proximity_stats": {
            "citation_similarity_mean": 0.75,
            "citation_similarity_median": 0.73,
            "company_similarity_mean": 0.45,
            "company_similarity_median": 0.42,
            "per_cluster": {
                "cluster-0": {"mean": 0.76},
                "cluster-1": {"mean": 0.72},
            },
        },
        "centroids": [
            {"cluster_name": "cluster-0", "distance": 0.35},
            {"cluster_name": "cluster-1", "distance": 0.42},
        ],
    }


# ── Summary endpoint ─────────────────────────────────────────────────


class TestGapSummary:
    """Test get_summary reads analysis.json and report correctly."""

    def test_summary_from_analysis_json(self, tmp_path: Path):
        slug = "test-co"
        _write_json(
            tmp_path / "gap_analysis" / slug / "analysis.json",
            _sample_analysis(),
        )

        result = get_summary(LocalStorageBackend(tmp_path), slug)

        assert result.spa_score.t_stat == 2.5
        assert result.spa_score.p_value == 0.01
        assert result.spa_score.effect == "significant_gap"
        assert result.proximity_stats.citation_similarity_mean == 0.75
        assert result.proximity_stats.company_similarity_median == 0.42

    def test_classification_counts(self, tmp_path: Path):
        slug = "test-co"
        gaps = _sample_gaps(4)  # sig_gap, gap_to_close, company_wins, roughly_equal
        _write_json(
            tmp_path / "gap_analysis" / slug / "analysis.json",
            _sample_analysis(gaps=gaps),
        )

        result = get_summary(LocalStorageBackend(tmp_path), slug)

        assert result.classification_counts.significant_gap == 1
        assert result.classification_counts.gap_to_close == 1
        assert result.classification_counts.company_wins == 1
        assert result.classification_counts.roughly_equal == 1

    def test_cluster_performance_populated(self, tmp_path: Path):
        slug = "test-co"
        _write_json(
            tmp_path / "gap_analysis" / slug / "analysis.json",
            _sample_analysis(),
        )

        result = get_summary(LocalStorageBackend(tmp_path), slug)

        assert len(result.cluster_performance) == 2
        assert result.cluster_performance[0].cluster_name == "cluster-0"
        assert result.cluster_performance[0].query_count == 5

    def test_gap_analysis_complete_json_preferred(self, tmp_path: Path):
        """gap_analysis_complete.json takes precedence over analysis.json."""
        slug = "test-co"
        gap_dir = tmp_path / "gap_analysis" / slug

        _write_json(
            gap_dir / "gap_analysis_complete.json",
            {
                "analysis": _sample_analysis(),
                "report": {
                    "gaps": _sample_gaps(2),
                    "spa_results": [
                        {
                            "cluster_name": "all",
                            "t_stat": 3.0,
                            "p_value": 0.005,
                            "effect": "significant_gap",
                            "mean_citation_similarity": 0.80,
                            "mean_company_similarity": 0.50,
                        },
                    ],
                    "proximity_stats": {
                        "citation_similarity_mean": 0.80,
                        "citation_similarity_median": 0.78,
                        "company_similarity_mean": 0.50,
                        "company_similarity_median": 0.48,
                    },
                },
                "cluster_specs": _sample_cluster_specs(),
            },
        )
        # Also write analysis.json (should be ignored)
        _write_json(gap_dir / "analysis.json", _sample_analysis())

        result = get_summary(LocalStorageBackend(tmp_path), slug)

        # Should use values from gap_analysis_complete.json report
        assert result.spa_score.t_stat == 3.0

    def test_missing_slug_dir_raises_404(self, tmp_path: Path):
        with pytest.raises(Exception) as exc_info:
            get_summary(LocalStorageBackend(tmp_path), "nonexistent-co")
        assert exc_info.value.status_code == 404


# ── Queries endpoint ─────────────────────────────────────────────────


class TestGapQueries:
    """Test get_queries reads gaps and builds paginated query list."""

    def test_queries_from_analysis(self, tmp_path: Path):
        slug = "test-co"
        _write_json(
            tmp_path / "gap_analysis" / slug / "analysis.json",
            _sample_analysis(gaps=_sample_gaps(3)),
        )

        result = get_queries(LocalStorageBackend(tmp_path), slug)

        assert result.total == 3
        assert len(result.queries) == 3
        assert result.queries[0].query_text.startswith("What is the best")

    def test_queries_pagination(self, tmp_path: Path):
        slug = "test-co"
        _write_json(
            tmp_path / "gap_analysis" / slug / "analysis.json",
            _sample_analysis(gaps=_sample_gaps(5)),
        )

        result = get_queries(LocalStorageBackend(tmp_path), slug, page=1, page_size=2)

        assert result.total == 5
        assert len(result.queries) == 2
        assert result.page == 1
        assert result.page_size == 2

    def test_queries_filter_by_cluster(self, tmp_path: Path):
        slug = "test-co"
        gaps = _sample_gaps(4)
        _write_json(
            tmp_path / "gap_analysis" / slug / "analysis.json",
            _sample_analysis(gaps=gaps),
        )

        result = get_queries(LocalStorageBackend(tmp_path), slug, cluster="cluster-0")

        # Only gaps with cluster_name == "cluster-0" (indices 0, 2)
        assert all(q.cluster_name == "cluster-0" for q in result.queries)


# ── Clusters endpoint ────────────────────────────────────────────────


class TestGapClusters:
    """Test get_clusters reads cluster_specs from analysis."""

    def test_clusters_from_analysis(self, tmp_path: Path):
        slug = "test-co"
        _write_json(
            tmp_path / "gap_analysis" / slug / "analysis.json",
            _sample_analysis(),
        )

        result = get_clusters(LocalStorageBackend(tmp_path), slug)

        assert len(result.clusters) == 2
        assert result.clusters[0].cluster_name == "cluster-0"
        assert result.clusters[0].query_count == 5
        assert result.clusters[0].centroid_distance == 0.35
        assert result.clusters[0].word_count_range == {"min": 1200, "max": 2000}

    def test_clusters_structural_rates(self, tmp_path: Path):
        slug = "test-co"
        _write_json(
            tmp_path / "gap_analysis" / slug / "analysis.json",
            _sample_analysis(),
        )

        result = get_clusters(LocalStorageBackend(tmp_path), slug)

        assert result.clusters[0].structural_rates["has_faq_section"] == 0.6
        assert result.clusters[0].faq_rate == 0.6


# ── Edge cases ───────────────────────────────────────────────────────


class TestGapEdgeCases:
    """Test graceful handling of missing/malformed gap artifacts."""

    def test_empty_analysis_returns_defaults(self, tmp_path: Path):
        slug = "test-co"
        _write_json(tmp_path / "gap_analysis" / slug / "analysis.json", {})

        result = get_summary(LocalStorageBackend(tmp_path), slug)

        assert result.spa_score.t_stat == 0.0
        assert result.total_queries == 0
        assert result.cluster_performance == []

    def test_corrupted_analysis_handled_gracefully(self, tmp_path: Path):
        slug = "test-co"
        gap_dir = tmp_path / "gap_analysis" / slug
        gap_dir.mkdir(parents=True)
        (gap_dir / "analysis.json").write_text("not-json{{{", encoding="utf-8")

        result = get_summary(LocalStorageBackend(tmp_path), slug)

        # Should return defaults, not crash
        assert result.spa_score.t_stat == 0.0

    def test_invalid_slug_raises_400(self, tmp_path: Path):
        with pytest.raises(Exception) as exc_info:
            get_summary(LocalStorageBackend(tmp_path), "INVALID SLUG!!!")
        assert exc_info.value.status_code == 400
