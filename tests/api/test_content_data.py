"""Tests for content data endpoints (Phase 3).

Covers 3 GET endpoints under /api/v1/companies/{slug}/content/:
  - /briefs              (brief list with inferred statuses)
  - /briefs/{brief_id}   (full brief detail)
  - /briefs/{brief_id}/{stage}  (stage-specific file content)

Plus 1 GET endpoint under /api/v1/companies/{slug}/gap-analysis/:
  - /embeddings          (2D UMAP/t-SNE projections)

Tests both file-based and piece-based status inference, backward compatibility
scenarios, security (path traversal), and edge cases.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient


# ── Fixture builders ─────────────────────────────────────────────────


def _make_brief(
    idx: int,
    content_format: str = "long_blog",
    cluster: str = "Product Comparisons",
    word_count_range: Optional[List[int]] = None,
    priority_score: float = 0.8,
    key_topics: Optional[List[str]] = None,
    key_angles: Optional[List[str]] = None,
    exemplar_summaries: Optional[List[Dict[str, Any]]] = None,
    structural_targets: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a single brief entry for briefs.json."""
    return {
        "brief_id": f"brief-{idx}",
        "title": f"Test Brief {idx}",
        "content_format": content_format,
        "target_cluster": cluster,
        "word_count_range": word_count_range or [1000, 2000],
        "priority_score": priority_score,
        "key_topics": key_topics or [f"topic-{idx}a", f"topic-{idx}b"],
        "key_angles": key_angles or [f"angle-{idx}"],
        "exemplar_summaries": exemplar_summaries or [
            {
                "url": f"https://example.com/article-{idx}",
                "word_count": 1500,
                "authority_type": "industry_expert",
                "content_type": "blog",
                "snippet": f"Example snippet {idx}",
            }
        ],
        "structural_targets": structural_targets or {"h2_count": 5, "list_count": 3},
    }


def _make_briefs_json(count: int = 3, formats: Optional[List[str]] = None) -> Dict[str, Any]:
    """Build a briefs.json (PlannerOutput) with N briefs."""
    fmts = formats or ["long_blog"] * count
    briefs = [_make_brief(i, content_format=fmts[i % len(fmts)]) for i in range(count)]
    return {"briefs": briefs}


def _make_run_metadata(
    session_id: str = "sess-abc123",
    pieces: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build a run_metadata.json (ContentGenerationOutput)."""
    return {
        "run_metadata": {
            "session_id": session_id,
            "total_time_s": 120.5,
            "skip_stages": [],
            "auto_approve": False,
        },
        "pieces": pieces or [],
    }


def _make_eval_history(
    cycles: int = 2,
    final_passed: bool = True,
    overall_score: float = 0.85,
) -> Dict[str, Any]:
    """Build an eval_history.json (RevisionHistory)."""
    cycle_list = []
    for i in range(cycles):
        cycle_list.append({
            "cycle": i + 1,
            "dimensions": [
                {"dimension": "structural", "passed": True, "score": 0.9, "feedback": "Good structure"},
                {"dimension": "semantic", "passed": True, "score": 0.8, "feedback": "Good semantics"},
                {"dimension": "style", "passed": i > 0, "score": 0.7 + i * 0.1, "feedback": "Style feedback"},
                {"dimension": "factual", "passed": True, "score": 0.85, "feedback": "Factual check ok"},
            ],
            "overall_passed": i == cycles - 1 and final_passed,
            "overall_score": overall_score - (cycles - 1 - i) * 0.1,
        })
    return {"cycles": cycle_list, "final_passed": final_passed}


def _make_embedding_projection(
    method: str = "umap",
    points: int = 5,
) -> Dict[str, Any]:
    """Build an embedding_projections_{method}.json."""
    point_list = []
    for i in range(points):
        t = ["query", "citation", "company"][i % 3]
        prefix = {"query": "q", "citation": "c", "company": "co"}[t]
        point_list.append({
            "x": round(i * 0.1, 4),
            "y": round(i * 0.2, 4),
            "type": t,
            "id": f"{prefix}-{i // 3}",
            "label": f"Point {i}",
            "cluster": "Product Comparisons",
            "cluster_id": "c1",
            "query_id": f"q-{i}" if t == "query" else None,
        })
    return {"method": method, "point_count": len(point_list), "points": point_list}


# ── Content dir setup helpers ────────────────────────────────────────


def _setup_content_dir(
    artifacts_root: Path,
    slug: str = "test-co",
    briefs_data: Optional[Dict[str, Any]] = None,
    run_metadata: Optional[Dict[str, Any]] = None,
    brief_stages: Optional[Dict[str, Dict[str, str]]] = None,
    eval_histories: Optional[Dict[str, Dict[str, Any]]] = None,
    pipeline_state: Optional[Dict[str, str]] = None,
) -> Path:
    """Create content/{slug}/ directory structure with optional files.

    Args:
        brief_stages: {brief_id: {stage_filename: content}} e.g.
            {"brief-0": {"draft.md": "# Draft content", "outline.json": '{"sections": []}'}}
        eval_histories: {brief_id: eval_data_dict}
        pipeline_state: {brief_id: phase_string} for pipeline_state.json
    """
    content_dir = artifacts_root / "content" / slug
    content_dir.mkdir(parents=True, exist_ok=True)

    if briefs_data is not None:
        # Write as blueprints.json (v1.3 format: flat list of briefs)
        briefs_list = briefs_data.get("briefs", [])
        (content_dir / "blueprints.json").write_text(json.dumps(briefs_list))

    if run_metadata is not None:
        (content_dir / "run_metadata_v13.json").write_text(json.dumps(run_metadata))

    if pipeline_state is not None:
        (content_dir / "pipeline_state.json").write_text(json.dumps(pipeline_state))

    if brief_stages:
        for brief_id, stages in brief_stages.items():
            brief_dir = content_dir / "content" / brief_id
            brief_dir.mkdir(parents=True, exist_ok=True)
            for filename, content in stages.items():
                (brief_dir / filename).write_text(content)

    if eval_histories:
        for brief_id, eval_data in eval_histories.items():
            brief_dir = content_dir / "content" / brief_id
            brief_dir.mkdir(parents=True, exist_ok=True)
            (brief_dir / "eval_history.json").write_text(json.dumps(eval_data))

    return content_dir


def _setup_gap_dir(
    artifacts_root: Path,
    slug: str = "test-co",
    embedding_projections: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Path:
    """Create gap_analysis/{slug}/visualizations/ with optional projection files."""
    viz_dir = artifacts_root / "gap_analysis" / slug / "visualizations"
    viz_dir.mkdir(parents=True, exist_ok=True)

    if embedding_projections:
        for method, data in embedding_projections.items():
            (viz_dir / f"embedding_projections_{method}.json").write_text(
                json.dumps(data)
            )

    return viz_dir.parent


# ── Clear service caches between tests ───────────────────────────────


@pytest.fixture(autouse=True)
def _clear_caches():
    """Clear module-level caches before each test."""
    import api.services.content_data_service as cds
    import api.services.gap_data_service as gds

    cds._CACHE.clear()
    gds._CACHE.clear()
    yield
    cds._CACHE.clear()
    gds._CACHE.clear()


# ═══════════════════════════════════════════════════════════════════════
# Brief List Tests
# ═══════════════════════════════════════════════════════════════════════


class TestBriefList:
    """Tests for GET /api/v1/companies/{slug}/content/briefs."""

    def test_list_briefs_basic(self, client: TestClient, artifacts_root: Path):
        """Returns brief list with correct structure."""
        _setup_content_dir(artifacts_root, briefs_data=_make_briefs_json(3))
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["briefs"]) == 3
        assert data["briefs"][0]["id"] == "brief-0"
        assert data["briefs"][0]["title"] == "Test Brief 0"

    def test_list_briefs_empty_dir(self, client: TestClient, artifacts_root: Path):
        """Returns 200 with empty list when no content dir exists."""
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["briefs"] == []

    def test_list_briefs_no_briefs_json(self, client: TestClient, artifacts_root: Path):
        """Returns 200 empty when content dir exists but no briefs.json."""
        content_dir = artifacts_root / "content" / "test-co"
        content_dir.mkdir(parents=True)
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_list_briefs_format_mapping(self, client: TestClient, artifacts_root: Path):
        """content_format maps correctly to content_type."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(
                5, formats=["long_blog", "short_faq", "pillar_page", "comparison", "how_to"]
            ),
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        types = [b["content_type"] for b in resp.json()["briefs"]]
        assert types == ["blog", "blog", "guide", "guide", "guide"]

    def test_list_briefs_unknown_format_defaults_blog(
        self, client: TestClient, artifacts_root: Path
    ):
        """Unknown content_format defaults to 'blog'."""
        briefs = _make_briefs_json(1)
        briefs["briefs"][0]["content_format"] = "unknown_format"
        _setup_content_dir(artifacts_root, briefs_data=briefs)
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["content_type"] == "blog"

    def test_list_briefs_word_count_uses_max(self, client: TestClient, artifacts_root: Path):
        """target_word_count uses max of word_count_range."""
        briefs = _make_briefs_json(1)
        briefs["briefs"][0]["word_count_range"] = [800, 1500]
        _setup_content_dir(artifacts_root, briefs_data=briefs)
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["target_word_count"] == 1500

    def test_list_briefs_citability_score(self, client: TestClient, artifacts_root: Path):
        """citability_score derived from eval overall_score × 100."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            eval_histories={"brief-0": _make_eval_history(cycles=2, overall_score=0.85)},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        score = resp.json()["briefs"][0]["citability_score"]
        assert score == 85.0

    def test_list_briefs_citability_null_no_eval(
        self, client: TestClient, artifacts_root: Path
    ):
        """citability_score is null when no eval history exists."""
        _setup_content_dir(artifacts_root, briefs_data=_make_briefs_json(1))
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["citability_score"] is None

    def test_list_briefs_cycle_id(self, client: TestClient, artifacts_root: Path):
        """cycle_id comes from run_metadata session_id."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            run_metadata=_make_run_metadata(session_id="sess-xyz"),
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["cycle_id"] == "sess-xyz"

    def test_list_briefs_cycle_id_null_no_metadata(
        self, client: TestClient, artifacts_root: Path
    ):
        """cycle_id is null when no run_metadata exists."""
        _setup_content_dir(artifacts_root, briefs_data=_make_briefs_json(1))
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["cycle_id"] is None

    def test_list_briefs_status_suggested(self, client: TestClient, artifacts_root: Path):
        """Brief with no stage files has status 'suggested'."""
        _setup_content_dir(artifacts_root, briefs_data=_make_briefs_json(1))
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["status"] == "suggested"

    def test_list_briefs_status_from_files(self, client: TestClient, artifacts_root: Path):
        """Status inferred from existing stage files."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            brief_stages={"brief-0": {"draft.md": "# Draft"}},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["status"] == "drafting"

    def test_list_briefs_status_from_pieces(self, client: TestClient, artifacts_root: Path):
        """Piece-based status overrides file-based inference."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            run_metadata=_make_run_metadata(pieces=[
                {"brief_id": "brief-0", "status": "approved"}
            ]),
            brief_stages={"brief-0": {"draft.md": "# Draft"}},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["status"] == "completed"

    def test_list_briefs_timestamps_are_strings(
        self, client: TestClient, artifacts_root: Path
    ):
        """created_at and updated_at are ISO timestamp strings."""
        _setup_content_dir(artifacts_root, briefs_data=_make_briefs_json(1))
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        brief = resp.json()["briefs"][0]
        assert isinstance(brief["created_at"], str)
        assert isinstance(brief["updated_at"], str)

    def test_list_briefs_invalid_slug(self, client: TestClient, artifacts_root: Path):
        """Invalid slug doesn't match authenticated user's company → 403."""
        resp = client.get("/api/v1/companies/INVALID_SLUG!/content/briefs")
        assert resp.status_code == 403

    def test_list_briefs_cluster_field(self, client: TestClient, artifacts_root: Path):
        """cluster field comes from target_cluster."""
        briefs = _make_briefs_json(1)
        briefs["briefs"][0]["target_cluster"] = "Pricing FAQs"
        _setup_content_dir(artifacts_root, briefs_data=briefs)
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["cluster"] == "Pricing FAQs"

    def test_list_briefs_empty_briefs_array(self, client: TestClient, artifacts_root: Path):
        """Returns empty list when briefs array is empty."""
        _setup_content_dir(artifacts_root, briefs_data={"briefs": []})
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["total"] == 0

    # ── Pipeline State (Phase 0) Tests ──────────────────────────────

    def test_list_briefs_status_from_pipeline_state(
        self, client: TestClient, artifacts_root: Path,
    ):
        """pipeline_state.json overrides file-based inference (Phase 0 > Phase 2)."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(2),
            pipeline_state={"brief-0": "approved", "brief-1": "in_progress"},
            brief_stages={"brief-0": {"draft.md": "# Draft"}},  # would be "drafting" without pipeline_state
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        briefs = {b["id"]: b["status"] for b in resp.json()["briefs"]}
        assert briefs["brief-0"] == "approved"
        assert briefs["brief-1"] == "in_progress"

    def test_list_briefs_pipeline_state_overrides_pieces(
        self, client: TestClient, artifacts_root: Path,
    ):
        """pipeline_state.json (Phase 0) has higher priority than pieces (Phase 1)."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            run_metadata=_make_run_metadata(pieces=[
                {"brief_id": "brief-0", "status": "approved"},
            ]),
            pipeline_state={"brief-0": "review"},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["status"] == "review"

    def test_list_briefs_pipeline_state_partial(
        self, client: TestClient, artifacts_root: Path,
    ):
        """Briefs not in pipeline_state fall through to Phase 1/2."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(2),
            pipeline_state={"brief-0": "in_progress"},
            # brief-1 not in pipeline_state → falls through to "suggested"
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        briefs = {b["id"]: b["status"] for b in resp.json()["briefs"]}
        assert briefs["brief-0"] == "in_progress"
        assert briefs["brief-1"] == "suggested"

    def test_list_briefs_pipeline_state_completed(
        self, client: TestClient, artifacts_root: Path,
    ):
        """pipeline_state 'completed' status is returned correctly."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            pipeline_state={"brief-0": "completed"},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["status"] == "completed"

    def test_list_briefs_no_pipeline_state_file(
        self, client: TestClient, artifacts_root: Path,
    ):
        """Without pipeline_state.json, status inference works via Phase 1/2."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            brief_stages={"brief-0": {"outline.json": '{"sections": []}'}},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["status"] == "research"

    # ── Namespaced Metadata (Manual Mode) Tests ─────────────────────

    def test_list_briefs_namespaced_metadata_pieces(
        self, client: TestClient, artifacts_root: Path,
    ):
        """Pieces from run_metadata_v13_{brief}.json are loaded."""
        content_dir = _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(2),
        )
        # Write namespaced metadata (manual mode parallel run)
        namespaced = {
            "pieces": [{"brief_id": "brief-0", "status": "approved"}],
            "run_metadata": {"session_id": "sess-manual"},
        }
        (content_dir / "run_metadata_v13_brief-0.json").write_text(
            json.dumps(namespaced)
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        briefs = {b["id"]: b["status"] for b in resp.json()["briefs"]}
        assert briefs["brief-0"] == "completed"  # approved piece → completed
        assert briefs["brief-1"] == "suggested"  # no piece → suggested

    def test_list_briefs_standard_metadata_takes_priority(
        self, client: TestClient, artifacts_root: Path,
    ):
        """Standard file pieces take priority over namespaced file pieces."""
        content_dir = _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            run_metadata=_make_run_metadata(pieces=[
                {"brief_id": "brief-0", "status": "rejected"},
            ]),
        )
        # Namespaced file also has brief-0 — should be deduped
        namespaced = {
            "pieces": [{"brief_id": "brief-0", "status": "approved"}],
            "run_metadata": {},
        }
        (content_dir / "run_metadata_v13_brief-0.json").write_text(
            json.dumps(namespaced)
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        # Standard file has "rejected" → takes priority
        assert resp.json()["briefs"][0]["status"] == "rejected"


# ═══════════════════════════════════════════════════════════════════════
# Brief Detail Tests
# ═══════════════════════════════════════════════════════════════════════


class TestBriefDetail:
    """Tests for GET /api/v1/companies/{slug}/content/briefs/{brief_id}."""

    def test_detail_basic(self, client: TestClient, artifacts_root: Path):
        """Returns full brief detail with correct fields."""
        _setup_content_dir(artifacts_root, briefs_data=_make_briefs_json(2))
        resp = client.get("/api/v1/companies/test-co/content/briefs/brief-0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "brief-0"
        assert data["title"] == "Test Brief 0"
        assert data["content_type"] == "blog"
        assert data["cluster"] == "Product Comparisons"

    def test_detail_word_count_range(self, client: TestClient, artifacts_root: Path):
        """target_word_count is {min, max} dict in detail view."""
        _setup_content_dir(artifacts_root, briefs_data=_make_briefs_json(1))
        resp = client.get("/api/v1/companies/test-co/content/briefs/brief-0")
        wc = resp.json()["target_word_count"]
        assert wc == {"min": 1000, "max": 2000}

    def test_detail_structural_targets(self, client: TestClient, artifacts_root: Path):
        """structural_targets passed through from brief data."""
        _setup_content_dir(artifacts_root, briefs_data=_make_briefs_json(1))
        resp = client.get("/api/v1/companies/test-co/content/briefs/brief-0")
        assert resp.json()["structural_targets"] == {"h2_count": 5, "list_count": 3}

    def test_detail_key_topics_and_angles(self, client: TestClient, artifacts_root: Path):
        """key_topics and key_angles populated."""
        _setup_content_dir(artifacts_root, briefs_data=_make_briefs_json(1))
        resp = client.get("/api/v1/companies/test-co/content/briefs/brief-0")
        data = resp.json()
        assert data["key_topics"] == ["topic-0a", "topic-0b"]
        assert data["key_angles"] == ["angle-0"]

    def test_detail_priority_score(self, client: TestClient, artifacts_root: Path):
        """priority_score from brief data."""
        briefs = _make_briefs_json(1)
        briefs["briefs"][0]["priority_score"] = 0.92
        _setup_content_dir(artifacts_root, briefs_data=briefs)
        resp = client.get("/api/v1/companies/test-co/content/briefs/brief-0")
        assert resp.json()["priority_score"] == 0.92

    def test_detail_eval_history(self, client: TestClient, artifacts_root: Path):
        """eval_history populated from eval_history.json."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            eval_histories={"brief-0": _make_eval_history(cycles=2)},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs/brief-0")
        data = resp.json()
        assert len(data["eval_history"]) == 2
        assert data["eval_history"][0]["cycle"] == 1
        assert len(data["eval_history"][0]["dimensions"]) == 4
        assert data["final_passed"] is True

    def test_detail_exemplars(self, client: TestClient, artifacts_root: Path):
        """exemplars populated from exemplar_summaries."""
        _setup_content_dir(artifacts_root, briefs_data=_make_briefs_json(1))
        resp = client.get("/api/v1/companies/test-co/content/briefs/brief-0")
        exemplars = resp.json()["exemplars"]
        assert len(exemplars) == 1
        assert exemplars[0]["url"] == "https://example.com/article-0"
        assert exemplars[0]["word_count"] == 1500

    def test_detail_available_stages(self, client: TestClient, artifacts_root: Path):
        """available_stages lists stages with files on disk."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            brief_stages={"brief-0": {
                "outline.json": '{"sections": []}',
                "draft.md": "# Draft",
                "formatted.md": "# Formatted",
            }},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs/brief-0")
        stages = resp.json()["available_stages"]
        assert "outline" in stages
        assert "draft" in stages
        assert "formatted" in stages
        assert "enriched" not in stages

    def test_detail_nonexistent_brief(self, client: TestClient, artifacts_root: Path):
        """Returns 404 for non-existent brief_id."""
        _setup_content_dir(artifacts_root, briefs_data=_make_briefs_json(1))
        resp = client.get("/api/v1/companies/test-co/content/briefs/brief-99")
        assert resp.status_code == 404

    def test_detail_no_content_dir(self, client: TestClient, artifacts_root: Path):
        """Returns 404 when content dir doesn't exist."""
        resp = client.get("/api/v1/companies/test-co/content/briefs/brief-0")
        assert resp.status_code == 404

    def test_detail_no_eval_history(self, client: TestClient, artifacts_root: Path):
        """eval_history is empty list when no eval_history.json."""
        _setup_content_dir(artifacts_root, briefs_data=_make_briefs_json(1))
        resp = client.get("/api/v1/companies/test-co/content/briefs/brief-0")
        data = resp.json()
        assert data["eval_history"] == []
        assert data["final_passed"] is False
        assert data["citability_score"] is None

    def test_detail_citability_score(self, client: TestClient, artifacts_root: Path):
        """citability_score derived from max overall_score across cycles."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            eval_histories={"brief-0": _make_eval_history(cycles=2, overall_score=0.92)},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs/brief-0")
        assert resp.json()["citability_score"] == 92.0

    def test_detail_invalid_brief_id_format(self, client: TestClient, artifacts_root: Path):
        """Returns 400 for invalid brief_id format."""
        _setup_content_dir(artifacts_root, briefs_data=_make_briefs_json(1))
        resp = client.get("/api/v1/companies/test-co/content/briefs/invalid-id")
        assert resp.status_code == 400

    def test_detail_no_briefs_json(self, client: TestClient, artifacts_root: Path):
        """Returns 404 when briefs.json missing."""
        content_dir = artifacts_root / "content" / "test-co"
        content_dir.mkdir(parents=True)
        resp = client.get("/api/v1/companies/test-co/content/briefs/brief-0")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# Brief Stage Content Tests
# ═══════════════════════════════════════════════════════════════════════


class TestBriefStage:
    """Tests for GET /api/v1/companies/{slug}/content/briefs/{brief_id}/{stage}."""

    def test_stage_draft_markdown(self, client: TestClient, artifacts_root: Path):
        """Returns markdown content for draft stage."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            brief_stages={"brief-0": {"draft.md": "# My Draft\n\nContent here."}},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs/brief-0/draft")
        assert resp.status_code == 200
        data = resp.json()
        assert data["brief_id"] == "brief-0"
        assert data["stage"] == "draft"
        assert data["content_type"] == "text/markdown"
        assert "# My Draft" in data["content"]

    def test_stage_outline_json(self, client: TestClient, artifacts_root: Path):
        """Returns parsed dict for JSON stages (not double-encoded string)."""
        outline = {"sections": [{"title": "Intro"}, {"title": "Body"}]}
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            brief_stages={"brief-0": {"outline.json": json.dumps(outline)}},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs/brief-0/outline")
        assert resp.status_code == 200
        data = resp.json()
        assert data["content_type"] == "application/json"
        assert isinstance(data["content"], dict)
        assert data["content"]["sections"][0]["title"] == "Intro"

    def test_stage_eval_history_json(self, client: TestClient, artifacts_root: Path):
        """eval_history stage returns parsed JSON."""
        eval_data = _make_eval_history(cycles=1)
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            eval_histories={"brief-0": eval_data},
        )
        resp = client.get(
            "/api/v1/companies/test-co/content/briefs/brief-0/eval_history"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["content_type"] == "application/json"
        assert isinstance(data["content"], dict)
        assert "cycles" in data["content"]

    def test_stage_enriched_markdown(self, client: TestClient, artifacts_root: Path):
        """enriched stage returns markdown."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            brief_stages={"brief-0": {"enriched.md": "# Enriched\n\nWith facts."}},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs/brief-0/enriched")
        assert resp.status_code == 200
        assert resp.json()["content_type"] == "text/markdown"

    def test_stage_formatted_markdown(self, client: TestClient, artifacts_root: Path):
        """formatted stage returns markdown."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            brief_stages={"brief-0": {"formatted.md": "# Formatted"}},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs/brief-0/formatted")
        assert resp.status_code == 200
        assert resp.json()["content_type"] == "text/markdown"

    def test_stage_final_markdown(self, client: TestClient, artifacts_root: Path):
        """final stage returns markdown."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            brief_stages={"brief-0": {"final.md": "# Final Version"}},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs/brief-0/final")
        assert resp.status_code == 200
        assert "Final Version" in resp.json()["content"]

    def test_stage_missing_file(self, client: TestClient, artifacts_root: Path):
        """Returns 404 when stage file doesn't exist."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            brief_stages={"brief-0": {"draft.md": "# Draft"}},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs/brief-0/final")
        assert resp.status_code == 404

    def test_stage_invalid_stage_name(self, client: TestClient, artifacts_root: Path):
        """Returns 400 for invalid stage name."""
        _setup_content_dir(artifacts_root, briefs_data=_make_briefs_json(1))
        resp = client.get(
            "/api/v1/companies/test-co/content/briefs/brief-0/nonexistent"
        )
        assert resp.status_code == 400

    def test_stage_invalid_brief_id(self, client: TestClient, artifacts_root: Path):
        """Returns 400 for invalid brief_id format."""
        _setup_content_dir(artifacts_root, briefs_data=_make_briefs_json(1))
        resp = client.get(
            "/api/v1/companies/test-co/content/briefs/../../etc/passwd/draft"
        )
        # FastAPI may resolve this differently, but the regex check should catch it
        assert resp.status_code in (400, 404, 422)


# ═══════════════════════════════════════════════════════════════════════
# Embedding Projection Tests
# ═══════════════════════════════════════════════════════════════════════


class TestEmbeddingProjection:
    """Tests for GET /api/v1/companies/{slug}/gap-analysis/embeddings."""

    def test_embeddings_umap(self, client: TestClient, artifacts_root: Path):
        """Returns UMAP projection with correct structure."""
        # Need gap_analysis dir for slug validation
        gap_dir = artifacts_root / "gap_analysis" / "test-co"
        gap_dir.mkdir(parents=True)
        _setup_gap_dir(
            artifacts_root,
            embedding_projections={"umap": _make_embedding_projection("umap", 6)},
        )
        resp = client.get("/api/v1/companies/test-co/gap-analysis/embeddings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["method"] == "umap"
        assert data["point_count"] == 6
        assert len(data["points"]) == 6

    def test_embeddings_tsne(self, client: TestClient, artifacts_root: Path):
        """Returns t-SNE projection when method=tsne."""
        gap_dir = artifacts_root / "gap_analysis" / "test-co"
        gap_dir.mkdir(parents=True)
        _setup_gap_dir(
            artifacts_root,
            embedding_projections={"tsne": _make_embedding_projection("tsne", 4)},
        )
        resp = client.get(
            "/api/v1/companies/test-co/gap-analysis/embeddings?method=tsne"
        )
        assert resp.status_code == 200
        assert resp.json()["method"] == "tsne"

    def test_embeddings_point_structure(self, client: TestClient, artifacts_root: Path):
        """Each point has required fields."""
        gap_dir = artifacts_root / "gap_analysis" / "test-co"
        gap_dir.mkdir(parents=True)
        _setup_gap_dir(
            artifacts_root,
            embedding_projections={"umap": _make_embedding_projection("umap", 3)},
        )
        resp = client.get("/api/v1/companies/test-co/gap-analysis/embeddings")
        point = resp.json()["points"][0]
        assert "x" in point
        assert "y" in point
        assert "type" in point
        assert "id" in point
        assert "label" in point
        assert "cluster" in point
        assert "cluster_id" in point

    def test_embeddings_type_lowercase(self, client: TestClient, artifacts_root: Path):
        """Point types are lowercase."""
        gap_dir = artifacts_root / "gap_analysis" / "test-co"
        gap_dir.mkdir(parents=True)
        _setup_gap_dir(
            artifacts_root,
            embedding_projections={"umap": _make_embedding_projection("umap", 6)},
        )
        resp = client.get("/api/v1/companies/test-co/gap-analysis/embeddings")
        types = {p["type"] for p in resp.json()["points"]}
        assert types <= {"query", "citation", "company"}

    def test_embeddings_missing_projection(self, client: TestClient, artifacts_root: Path):
        """Returns 404 when projection file doesn't exist."""
        gap_dir = artifacts_root / "gap_analysis" / "test-co"
        gap_dir.mkdir(parents=True)
        resp = client.get("/api/v1/companies/test-co/gap-analysis/embeddings")
        assert resp.status_code == 404

    def test_embeddings_missing_slug_dir(self, client: TestClient, artifacts_root: Path):
        """Returns 404 when gap_analysis/{slug}/ doesn't exist."""
        resp = client.get("/api/v1/companies/test-co/gap-analysis/embeddings")
        assert resp.status_code == 404

    def test_embeddings_invalid_slug(self, client: TestClient, artifacts_root: Path):
        """Invalid slug doesn't match authenticated user's company → 403."""
        resp = client.get("/api/v1/companies/INVALID!/gap-analysis/embeddings")
        assert resp.status_code == 403

    def test_embeddings_default_method_umap(
        self, client: TestClient, artifacts_root: Path
    ):
        """Default method is umap when not specified."""
        gap_dir = artifacts_root / "gap_analysis" / "test-co"
        gap_dir.mkdir(parents=True)
        _setup_gap_dir(
            artifacts_root,
            embedding_projections={"umap": _make_embedding_projection("umap", 2)},
        )
        resp = client.get("/api/v1/companies/test-co/gap-analysis/embeddings")
        assert resp.status_code == 200
        assert resp.json()["method"] == "umap"

    def test_embeddings_point_count_matches(
        self, client: TestClient, artifacts_root: Path
    ):
        """point_count equals actual number of points."""
        gap_dir = artifacts_root / "gap_analysis" / "test-co"
        gap_dir.mkdir(parents=True)
        _setup_gap_dir(
            artifacts_root,
            embedding_projections={"umap": _make_embedding_projection("umap", 10)},
        )
        resp = client.get("/api/v1/companies/test-co/gap-analysis/embeddings")
        data = resp.json()
        assert data["point_count"] == len(data["points"])


# ═══════════════════════════════════════════════════════════════════════
# Status Inference Tests
# ═══════════════════════════════════════════════════════════════════════


class TestStatusInference:
    """Tests for the 2-phase status inference logic."""

    def test_status_suggested_no_files(self, client: TestClient, artifacts_root: Path):
        """No stage files → suggested."""
        _setup_content_dir(artifacts_root, briefs_data=_make_briefs_json(1))
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["status"] == "suggested"

    def test_status_research_outline_only(self, client: TestClient, artifacts_root: Path):
        """Only outline.json → research."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            brief_stages={"brief-0": {"outline.json": '{"sections": []}'}},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["status"] == "research"

    def test_status_drafting(self, client: TestClient, artifacts_root: Path):
        """draft.md exists → drafting."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            brief_stages={"brief-0": {"draft.md": "# Draft"}},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["status"] == "drafting"

    def test_status_enriching(self, client: TestClient, artifacts_root: Path):
        """enriched.md exists → enriching."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            brief_stages={"brief-0": {"enriched.md": "# Enriched"}},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["status"] == "enriching"

    def test_status_formatting_removed_v13(self, client: TestClient, artifacts_root: Path):
        """M3-fix: formatted.md is a v1.0-only stage — no longer inferred as 'formatting'.

        v1.3 pipeline skips the Formatter stage. A brief with only formatted.md
        (legacy artifact) falls through to 'suggested' since no v1.3 stage
        files are present.
        """
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            brief_stages={"brief-0": {"formatted.md": "# Formatted"}},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["status"] == "suggested"

    def test_status_enriched_to_evaluating(self, client: TestClient, artifacts_root: Path):
        """M3-fix: enriched.md + eval_history.json → evaluating (not stuck at formatting)."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            brief_stages={"brief-0": {"enriched.md": "# Enriched"}},
            eval_histories={"brief-0": _make_eval_history(cycles=1, final_passed=False)},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["status"] == "evaluating"

    def test_status_evaluating(self, client: TestClient, artifacts_root: Path):
        """eval_history.json exists but final_passed=False → evaluating."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            eval_histories={"brief-0": _make_eval_history(cycles=1, final_passed=False)},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["status"] == "evaluating"

    def test_status_review_eval_passed(self, client: TestClient, artifacts_root: Path):
        """eval_history with final_passed=True → review."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            eval_histories={"brief-0": _make_eval_history(cycles=2, final_passed=True)},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["status"] == "review"

    def test_status_published_final(self, client: TestClient, artifacts_root: Path):
        """final.md exists → published."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            brief_stages={"brief-0": {"final.md": "# Final"}},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["status"] == "published"

    def test_status_piece_approved(self, client: TestClient, artifacts_root: Path):
        """Piece status 'approved' → completed (Published column, not Brief)."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            run_metadata=_make_run_metadata(pieces=[
                {"brief_id": "brief-0", "status": "approved"}
            ]),
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["status"] == "completed"

    def test_status_piece_edited_completed(self, client: TestClient, artifacts_root: Path):
        """Piece status 'edited' → completed (Published column)."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            run_metadata=_make_run_metadata(pieces=[
                {"brief_id": "brief-0", "status": "edited"}
            ]),
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["status"] == "completed"

    def test_status_piece_rejected(self, client: TestClient, artifacts_root: Path):
        """Piece status 'rejected' → rejected."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            run_metadata=_make_run_metadata(pieces=[
                {"brief_id": "brief-0", "status": "rejected"}
            ]),
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["status"] == "rejected"

    def test_status_piece_pending_review(self, client: TestClient, artifacts_root: Path):
        """Piece status 'pending' → review."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            run_metadata=_make_run_metadata(pieces=[
                {"brief_id": "brief-0", "status": "pending"}
            ]),
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["status"] == "review"

    def test_status_piece_overrides_file(self, client: TestClient, artifacts_root: Path):
        """Piece-based status takes precedence over file-based."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            run_metadata=_make_run_metadata(pieces=[
                {"brief_id": "brief-0", "status": "rejected"}
            ]),
            brief_stages={"brief-0": {"final.md": "# Final"}},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        # piece says rejected, files say published — piece wins
        assert resp.json()["briefs"][0]["status"] == "rejected"

    def test_status_unknown_piece_status_defaults_review(
        self, client: TestClient, artifacts_root: Path
    ):
        """Unknown piece status falls back to 'review'."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            run_metadata=_make_run_metadata(pieces=[
                {"brief_id": "brief-0", "status": "some_new_status"}
            ]),
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.json()["briefs"][0]["status"] == "review"


# ═══════════════════════════════════════════════════════════════════════
# Security Tests
# ═══════════════════════════════════════════════════════════════════════


class TestSecurity:
    """Path traversal and injection protection tests."""

    def test_brief_id_traversal_dots(self, client: TestClient, artifacts_root: Path):
        """brief_id with .. is rejected."""
        _setup_content_dir(artifacts_root, briefs_data=_make_briefs_json(1))
        resp = client.get(
            "/api/v1/companies/test-co/content/briefs/../../../etc/passwd"
        )
        assert resp.status_code in (400, 404, 422)

    def test_brief_id_absolute_path(self, client: TestClient, artifacts_root: Path):
        """brief_id with absolute path is rejected."""
        _setup_content_dir(artifacts_root, briefs_data=_make_briefs_json(1))
        resp = client.get("/api/v1/companies/test-co/content/briefs//etc/passwd")
        assert resp.status_code in (400, 404, 422)

    def test_slug_with_dots(self, client: TestClient, artifacts_root: Path):
        """Slug with dots is rejected."""
        resp = client.get("/api/v1/companies/../admin/content/briefs")
        assert resp.status_code in (400, 404, 422)

    def test_brief_id_valid_format_only(self, client: TestClient, artifacts_root: Path):
        """Only brief-N format is accepted."""
        _setup_content_dir(artifacts_root, briefs_data=_make_briefs_json(1))
        for bad_id in ["brief", "brief-", "brief-abc", "BRIEF-1", "brief-12345"]:
            resp = client.get(
                f"/api/v1/companies/test-co/content/briefs/{bad_id}"
            )
            assert resp.status_code in (400, 404), f"Expected 400/404 for {bad_id}"


# ═══════════════════════════════════════════════════════════════════════
# Backward Compatibility Tests
# ═══════════════════════════════════════════════════════════════════════


class TestBackwardCompat:
    """Backward compatibility with partial/missing artifacts."""

    def test_no_run_metadata(self, client: TestClient, artifacts_root: Path):
        """Works without run_metadata.json — cycle_id is null."""
        _setup_content_dir(artifacts_root, briefs_data=_make_briefs_json(1))
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.status_code == 200
        assert resp.json()["briefs"][0]["cycle_id"] is None

    def test_partial_stages(self, client: TestClient, artifacts_root: Path):
        """Works with only some stage files present."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(2),
            brief_stages={
                "brief-0": {"draft.md": "# Draft"},
                # brief-1 has no stage files
            },
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        statuses = [b["status"] for b in resp.json()["briefs"]]
        assert statuses[0] == "drafting"
        assert statuses[1] == "suggested"

    def test_empty_briefs_list(self, client: TestClient, artifacts_root: Path):
        """Empty briefs array returns 200 with empty list."""
        _setup_content_dir(artifacts_root, briefs_data={"briefs": []})
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_missing_brief_fields_use_defaults(
        self, client: TestClient, artifacts_root: Path
    ):
        """Brief with missing optional fields uses defaults."""
        minimal_brief = {"briefs": [{"brief_id": "brief-0"}]}
        _setup_content_dir(artifacts_root, briefs_data=minimal_brief)
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.status_code == 200
        brief = resp.json()["briefs"][0]
        assert brief["title"] == ""
        assert brief["content_type"] == "blog"
        assert brief["cluster"] == ""
        assert brief["target_word_count"] == 0

    def test_corrupted_eval_history(self, client: TestClient, artifacts_root: Path):
        """Handles corrupted eval_history.json gracefully."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
        )
        # Write invalid JSON to eval_history
        brief_dir = artifacts_root / "content" / "test-co" / "content" / "brief-0"
        brief_dir.mkdir(parents=True, exist_ok=True)
        (brief_dir / "eval_history.json").write_text("not valid json{{{")
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.status_code == 200
        # Should still get the brief, just with evaluating status (file exists but parse fails)
        assert resp.json()["briefs"][0]["status"] == "evaluating"

    def test_json_stage_returns_dict(self, client: TestClient, artifacts_root: Path):
        """JSON stages return dict, not double-encoded string."""
        outline = {"sections": [{"title": "Intro"}]}
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            brief_stages={"brief-0": {"outline.json": json.dumps(outline)}},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs/brief-0/outline")
        content = resp.json()["content"]
        assert isinstance(content, dict)  # Not a string
        assert content == outline


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CX Regression Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestCX1SymlinkPathTraversal:
    """CX-1: Symlink brief directories should be rejected."""

    def test_symlink_brief_dir_rejected(self, client: TestClient, artifacts_root: Path):
        """A symlinked brief dir should return 400, not serve attacker content."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
        )
        content_dir = artifacts_root / "content" / "test-co"

        # Create an outside directory with a file
        outside = artifacts_root / "outside" / "secret"
        outside.mkdir(parents=True, exist_ok=True)
        (outside / "draft.md").write_text("# SECRET CONTENT")

        # Symlink brief-0 -> outside/secret
        brief_dir = content_dir / "content" / "brief-0"
        brief_dir.parent.mkdir(parents=True, exist_ok=True)
        brief_dir.symlink_to(outside)

        resp = client.get("/api/v1/companies/test-co/content/briefs/brief-0/draft")
        assert resp.status_code == 400

    def test_normal_brief_dir_works(self, client: TestClient, artifacts_root: Path):
        """Non-symlinked brief directories should still work fine."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            brief_stages={"brief-0": {"draft.md": "# Normal content"}},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs/brief-0/draft")
        assert resp.status_code == 200
        assert resp.json()["content"] == "# Normal content"


class TestCX4NullCitabilityScore:
    """CX-4: null overall_score should not crash citability computation."""

    def test_null_overall_score_handled(self, client: TestClient, artifacts_root: Path):
        """Cycles with null overall_score should be skipped, not crash."""
        eval_data = {
            "cycles": [
                {
                    "cycle": 1,
                    "dimensions": [],
                    "overall_passed": False,
                    "overall_score": None,  # null!
                },
                {
                    "cycle": 2,
                    "dimensions": [],
                    "overall_passed": True,
                    "overall_score": 0.85,
                },
            ],
            "final_passed": True,
        }
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            eval_histories={"brief-0": eval_data},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.status_code == 200
        brief = resp.json()["briefs"][0]
        assert brief["citability_score"] == 85.0  # 0.85 * 100

    def test_all_null_scores_returns_none(self, client: TestClient, artifacts_root: Path):
        """All-null cycles should return null citability, not crash."""
        eval_data = {
            "cycles": [
                {"cycle": 1, "dimensions": [], "overall_passed": False, "overall_score": None},
            ],
            "final_passed": False,
        }
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            eval_histories={"brief-0": eval_data},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs")
        assert resp.status_code == 200
        assert resp.json()["briefs"][0]["citability_score"] is None


class TestCX8CorruptedJsonStage:
    """CX-8: Corrupted JSON stage files should return 422, not raw string."""

    def test_corrupted_outline_returns_422(self, client: TestClient, artifacts_root: Path):
        """Corrupted outline.json should return 422, not raw string with application/json."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            brief_stages={"brief-0": {"outline.json": "{ not valid json !!!"}},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs/brief-0/outline")
        assert resp.status_code == 422

    def test_corrupted_eval_history_stage_returns_422(
        self, client: TestClient, artifacts_root: Path,
    ):
        """Corrupted eval_history.json via stage endpoint should return 422."""
        _setup_content_dir(
            artifacts_root,
            briefs_data=_make_briefs_json(1),
            brief_stages={"brief-0": {"eval_history.json": "broken{{{{"}},
        )
        resp = client.get("/api/v1/companies/test-co/content/briefs/brief-0/eval_history")
        assert resp.status_code == 422


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Phase 5: product_slug query param for all 3 content-data endpoints
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestContentDataProductSlug:
    """?product_slug= query param routes to content/{slug}__{product_slug} dir."""

    def test_briefs_with_product_slug_reads_product_dir(
        self, client: TestClient, artifacts_root: Path,
    ) -> None:
        briefs = _make_briefs_json(count=2)
        _setup_content_dir(artifacts_root, slug="test-co__card", briefs_data=briefs)

        r = client.get("/api/v1/companies/test-co/content/briefs?product_slug=card")
        assert r.status_code == 200
        assert len(r.json()["briefs"]) == 2

    def test_company_and_product_briefs_independent(
        self, client: TestClient, artifacts_root: Path,
    ) -> None:
        company_briefs = _make_briefs_json(count=5)
        product_briefs = _make_briefs_json(count=2)
        _setup_content_dir(artifacts_root, slug="test-co", briefs_data=company_briefs)
        _setup_content_dir(artifacts_root, slug="test-co__card", briefs_data=product_briefs)

        r_company = client.get("/api/v1/companies/test-co/content/briefs")
        r_product = client.get("/api/v1/companies/test-co/content/briefs?product_slug=card")

        assert len(r_company.json()["briefs"]) == 5
        assert len(r_product.json()["briefs"]) == 2

    def test_missing_product_content_dir_returns_200_empty(
        self, client: TestClient, artifacts_root: Path,
    ) -> None:
        """Missing product content dir returns 200 with empty briefs list."""
        r = client.get("/api/v1/companies/test-co/content/briefs?product_slug=nonexistent")
        assert r.status_code == 200
        assert r.json()["briefs"] == []

    def test_brief_detail_with_product_slug(
        self, client: TestClient, artifacts_root: Path,
    ) -> None:
        briefs = _make_briefs_json(count=1)
        _setup_content_dir(artifacts_root, slug="test-co__card", briefs_data=briefs)

        r = client.get("/api/v1/companies/test-co/content/briefs/brief-0?product_slug=card")
        assert r.status_code == 200
        assert r.json()["id"] == "brief-0"

    def test_stage_content_with_product_slug(
        self, client: TestClient, artifacts_root: Path,
    ) -> None:
        briefs = _make_briefs_json(count=1)
        _setup_content_dir(
            artifacts_root,
            slug="test-co__card",
            briefs_data=briefs,
            brief_stages={"brief-0": {"draft.md": "# Product draft content"}},
        )

        r = client.get(
            "/api/v1/companies/test-co/content/briefs/brief-0/draft?product_slug=card"
        )
        assert r.status_code == 200
        assert r.json()["content"] == "# Product draft content"

    def test_no_product_slug_uses_company_dir(
        self, client: TestClient, artifacts_root: Path,
    ) -> None:
        """Without ?product_slug=, endpoint reads company-level dir."""
        company_briefs = _make_briefs_json(count=3)
        _setup_content_dir(artifacts_root, slug="test-co", briefs_data=company_briefs)

        r = client.get("/api/v1/companies/test-co/content/briefs")
        assert r.status_code == 200
        assert len(r.json()["briefs"]) == 3
