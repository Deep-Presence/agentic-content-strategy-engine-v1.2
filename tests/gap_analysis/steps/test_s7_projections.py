"""Tests for s7_visualize.py JSON projection export."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from core.gap_analysis.steps.s7_visualize import (
    _collect_typed_embeddings,
    _save_embedding_projections,
    generate_visualizations,
)
from core.models.gap_analysis import (
    AnalysisResult,
    EnrichedCitation,
    GeneratedQuery,
    ParagraphMatch,
    SemanticUnit,
)
from core.storage.backends.local import LocalStorageBackend


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DIM = 8  # Use small embeddings for tests


def _make_query(qid: str, cluster: str, text: str) -> GeneratedQuery:
    return GeneratedQuery(
        query_id=qid,
        cluster_id=cluster,
        query_text=text,
        cluster_name=cluster,
        embedding=[float(i) for i in range(DIM)],
    )


def _make_citation(url: str, query_id: str, cluster: str) -> EnrichedCitation:
    return EnrichedCitation(
        url=url,
        query_id=query_id,
        cluster_name=cluster,
        best_paragraphs=[
            ParagraphMatch(
                paragraph="test paragraph",
                similarity=0.85,
                embedding=[float(i + 0.5) for i in range(DIM)],
            ),
        ],
    )


def _make_company_unit(url: str, idx: int = 0) -> SemanticUnit:
    return SemanticUnit(
        unit_id=f"u-{idx}",
        url=url,
        text="company content",
        embedding=[float(i + 1.0) for i in range(DIM)],
    )


def _make_analysis() -> AnalysisResult:
    return AnalysisResult(gaps=[], citation_patterns={})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSaveEmbeddingProjections:
    """Tests for _save_embedding_projections()."""

    def test_save_umap_projection(self, tmp_path: Path) -> None:
        coords = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
        meta = [
            {"type": "Query", "cluster_name": "c1", "hover_text": "q1", "query_id": "Q1"},
            {"type": "Citation", "cluster_name": "c1", "hover_text": "http://ex.com"},
            {"type": "Company", "cluster_name": "Company", "hover_text": "http://co.com"},
        ]
        _save_embedding_projections(coords, meta, LocalStorageBackend(tmp_path), "viz","umap")

        out_file = tmp_path / "viz" / "embedding_projections_umap.json"
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert data["method"] == "umap"
        assert data["point_count"] == 3
        assert len(data["points"]) == 3

    def test_save_tsne_projection(self, tmp_path: Path) -> None:
        coords = np.array([[1.0, 2.0], [3.0, 4.0]])
        meta = [
            {"type": "Query", "cluster_name": "c1", "hover_text": "q1", "query_id": "Q1"},
            {"type": "Citation", "cluster_name": "c1", "hover_text": "http://ex.com"},
        ]
        _save_embedding_projections(coords, meta, LocalStorageBackend(tmp_path), "viz","tsne")

        out_file = tmp_path / "viz" / "embedding_projections_tsne.json"
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert data["method"] == "tsne"

    def test_point_count_matches(self, tmp_path: Path) -> None:
        n = 5
        coords = np.random.randn(n, 2)
        meta = [
            {"type": "Query", "cluster_name": f"c{i}", "hover_text": f"q{i}", "query_id": f"Q{i}"}
            for i in range(n)
        ]
        _save_embedding_projections(coords, meta, LocalStorageBackend(tmp_path), "viz","umap")
        data = json.loads((tmp_path / "viz" / "embedding_projections_umap.json").read_text())
        assert data["point_count"] == n
        assert len(data["points"]) == n

    def test_type_lowercase(self, tmp_path: Path) -> None:
        coords = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
        meta = [
            {"type": "Query", "cluster_name": "c1", "hover_text": "q1", "query_id": "Q1"},
            {"type": "Citation", "cluster_name": "c1", "hover_text": "url"},
            {"type": "Company", "cluster_name": "Company", "hover_text": "co"},
        ]
        _save_embedding_projections(coords, meta, LocalStorageBackend(tmp_path), "viz","umap")
        data = json.loads((tmp_path / "viz" / "embedding_projections_umap.json").read_text())
        types = {p["type"] for p in data["points"]}
        assert types == {"query", "citation", "company"}

    def test_query_id_preserved(self, tmp_path: Path) -> None:
        coords = np.array([[1.0, 2.0]])
        meta = [
            {"type": "Query", "cluster_name": "c1", "hover_text": "q1", "query_id": "Q-42"},
        ]
        _save_embedding_projections(coords, meta, LocalStorageBackend(tmp_path), "viz","umap")
        data = json.loads((tmp_path / "viz" / "embedding_projections_umap.json").read_text())
        assert data["points"][0]["query_id"] == "Q-42"

    def test_empty_embeddings_no_file(self, tmp_path: Path) -> None:
        coords = np.array([])
        _save_embedding_projections(coords, [], LocalStorageBackend(tmp_path), "viz", "umap")
        assert not (tmp_path / "viz" / "embedding_projections_umap.json").exists()

    def test_coordinate_rounding(self, tmp_path: Path) -> None:
        coords = np.array([[1.123456789, 2.987654321]])
        meta = [{"type": "Query", "cluster_name": "c1", "hover_text": "q", "query_id": "Q1"}]
        _save_embedding_projections(coords, meta, LocalStorageBackend(tmp_path), "viz","umap")
        data = json.loads((tmp_path / "viz" / "embedding_projections_umap.json").read_text())
        p = data["points"][0]
        assert p["x"] == 1.1235
        assert p["y"] == 2.9877

    def test_id_generation_pattern(self, tmp_path: Path) -> None:
        coords = np.array([[0, 0], [1, 1], [2, 2], [3, 3], [4, 4]])
        meta = [
            {"type": "Query", "cluster_name": "c1", "hover_text": "q0", "query_id": "Q0"},
            {"type": "Query", "cluster_name": "c1", "hover_text": "q1", "query_id": "Q1"},
            {"type": "Citation", "cluster_name": "c1", "hover_text": "url0"},
            {"type": "Company", "cluster_name": "Company", "hover_text": "co0"},
            {"type": "Citation", "cluster_name": "c1", "hover_text": "url1"},
        ]
        _save_embedding_projections(coords, meta, LocalStorageBackend(tmp_path), "viz","umap")
        data = json.loads((tmp_path / "viz" / "embedding_projections_umap.json").read_text())
        ids = [p["id"] for p in data["points"]]
        assert ids == ["q-0", "q-1", "c-0", "co-0", "c-1"]

    def test_cluster_id_defaults_to_cluster_name(self, tmp_path: Path) -> None:
        coords = np.array([[0, 0]])
        meta = [{"type": "Query", "cluster_name": "my-cluster", "hover_text": "q", "query_id": "Q1"}]
        _save_embedding_projections(coords, meta, LocalStorageBackend(tmp_path), "viz","umap")
        data = json.loads((tmp_path / "viz" / "embedding_projections_umap.json").read_text())
        assert data["points"][0]["cluster_id"] == "my-cluster"

    def test_nan_points_filtered_out(self, tmp_path: Path) -> None:
        """NaN/inf coordinates should be silently dropped (H3 fix)."""
        coords = np.array([
            [1.0, 2.0],
            [float("nan"), 3.0],
            [4.0, float("nan")],
            [float("inf"), 5.0],
            [6.0, float("-inf")],
            [7.0, 8.0],
        ])
        meta = [
            {"type": "Query", "cluster_name": "c1", "hover_text": "ok1", "query_id": "Q1"},
            {"type": "Query", "cluster_name": "c1", "hover_text": "nan-x", "query_id": "Q2"},
            {"type": "Citation", "cluster_name": "c1", "hover_text": "nan-y"},
            {"type": "Citation", "cluster_name": "c1", "hover_text": "inf-x"},
            {"type": "Company", "cluster_name": "Company", "hover_text": "-inf-y"},
            {"type": "Company", "cluster_name": "Company", "hover_text": "ok2"},
        ]
        _save_embedding_projections(coords, meta, LocalStorageBackend(tmp_path), "viz","umap")
        data = json.loads((tmp_path / "viz" / "embedding_projections_umap.json").read_text())
        # Only the 2 valid points should survive
        assert data["point_count"] == 2
        assert len(data["points"]) == 2
        labels = [p["label"] for p in data["points"]]
        assert "ok1" in labels
        assert "ok2" in labels
        # Verify no NaN values leaked through
        for p in data["points"]:
            assert p["x"] == p["x"]  # NaN != NaN
            assert p["y"] == p["y"]


class TestCollectTypedEmbeddingsQueryId:
    """Verify query_id is included in metadata."""

    def test_query_id_in_metadata(self) -> None:
        queries = [_make_query("Q-1", "c1", "test query")]
        embeddings, meta = _collect_typed_embeddings(queries, [], [])
        assert len(meta) == 1
        assert meta[0]["query_id"] == "Q-1"


class TestGenerateVisualizationsProjections:
    """Verify generate_visualizations() produces projection JSON files."""

    @patch("core.gap_analysis.steps.s7_visualize._reduce_embeddings")
    def test_generate_visualizations_includes_projections(
        self, mock_reduce: object, tmp_path: Path
    ) -> None:
        # Mock _reduce_embeddings to return deterministic 2D coords
        def fake_reduce(emb: np.ndarray, method: str) -> np.ndarray:
            return np.random.RandomState(42).randn(len(emb), 2)

        mock_reduce.side_effect = fake_reduce  # type: ignore[attr-defined]

        queries = [
            _make_query("Q1", "c1", "query one"),
            _make_query("Q2", "c2", "query two"),
        ]
        citations = [
            _make_citation("http://ex1.com", "Q1", "c1"),
            _make_citation("http://ex2.com", "Q2", "c2"),
        ]
        company_units = [_make_company_unit("http://company.com")]
        analysis = _make_analysis()

        result = generate_visualizations(
            queries, citations, company_units, analysis,
            storage=LocalStorageBackend(tmp_path), prefix="viz",
        )

        # JSON projections should be in the returned paths
        assert "umap_projections_json" in result
        assert "tsne_projections_json" in result

        # Files should exist
        umap_file = tmp_path / "viz" / "embedding_projections_umap.json"
        tsne_file = tmp_path / "viz" / "embedding_projections_tsne.json"
        assert umap_file.exists()
        assert tsne_file.exists()

        # Validate structure
        umap_data = json.loads(umap_file.read_text())
        assert umap_data["method"] == "umap"
        assert umap_data["point_count"] > 0
        assert all(p["type"] in {"query", "citation", "company"} for p in umap_data["points"])

    def test_no_projections_with_empty_data(self, tmp_path: Path) -> None:
        analysis = _make_analysis()
        result = generate_visualizations([], [], [], analysis, storage=LocalStorageBackend(tmp_path), prefix="viz")
        assert "umap_projections_json" not in result
        assert not (tmp_path / "viz" / "embedding_projections_umap.json").exists()
