"""Integration tests for content pipeline write-then-read boundary.

Verifies that artifacts written by the content pipeline (v1.3) can be
correctly read by the JSON service layer (content_data_service.py).
This is the #1 source of deployment failures: pipeline writes JSON to
filesystem, service parses it for the API.

Each test writes production-shaped artifacts to tmp_path, then calls
the service function and verifies the response.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from api.schemas.content_data import ContentBriefListResponse
from api.services.content_data_service import (
    _CACHE,
    _infer_brief_status,
    get_brief_detail,
    get_brief_stage_content,
    get_briefs,
)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear mtime cache before each test."""
    _CACHE.clear()
    yield
    _CACHE.clear()


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sample_blueprints(count: int = 3) -> List[Dict[str, Any]]:
    """Generate production-shaped blueprints.json entries."""
    return [
        {
            "brief_id": f"brief-{i + 1:03d}",
            "title": f"How to optimize {['SEO', 'content', 'AI'][i % 3]} for B2B",
            "target_cluster": f"cluster-{i % 2}",
            "content_format": ["long_blog", "short_faq", "how_to"][i % 3],
            "word_count_range": [1200, 2000],
            "key_topics": [f"topic-{i}"],
            "key_angles": [f"angle-{i}"],
            "priority_score": 0.85 - (i * 0.1),
        }
        for i in range(count)
    ]


def _sample_run_metadata(
    pieces: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Generate production-shaped run_metadata_v13.json."""
    return {
        "run_metadata": {
            "session_id": "sess-abc-123",
            "pipeline_version": "1.3",
        },
        "pieces": pieces or [],
    }


def _sample_pipeline_state(
    brief_statuses: Dict[str, str],
    task_ids: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    """Generate production-shaped pipeline_state.json."""
    state: Dict[str, Any] = dict(brief_statuses)
    if task_ids:
        state["__task_ids__"] = task_ids
    return state


# ── Phase 0: pipeline_state.json status inference ────────────────────


class TestPipelineStateInference:
    """Test that pipeline_state.json overrides all other status sources."""

    def test_pipeline_state_overrides_file_status(self, tmp_path: Path):
        """Phase 0 has highest priority — even if stage files exist."""
        slug = "test-co"
        content_root = tmp_path / "content" / slug
        _write_json(
            content_root / "blueprints.json",
            _sample_blueprints(1),
        )
        # Write a draft file (would normally infer "drafting")
        _write_text(
            content_root / "content" / "brief-001" / "draft.md",
            "# Draft content",
        )
        # But pipeline_state says "pending_brief_approval"
        _write_json(
            content_root / "pipeline_state.json",
            _sample_pipeline_state({"brief-001": "pending_brief_approval"}),
        )

        with patch("api.services.content_data_service.load_analysis_json", return_value=None):
            result = get_briefs(tmp_path, slug)

        assert result.total == 1
        assert result.briefs[0].status == "pending_brief_approval"

    def test_task_id_mapping_from_pipeline_state(self, tmp_path: Path):
        """__task_ids__ in pipeline_state.json maps brief_id → task_id."""
        slug = "test-co"
        content_root = tmp_path / "content" / slug
        _write_json(
            content_root / "blueprints.json",
            _sample_blueprints(2),
        )
        _write_json(
            content_root / "pipeline_state.json",
            _sample_pipeline_state(
                {"brief-001": "drafting", "brief-002": "outlining"},
                task_ids={"brief-001": "task-aaa", "brief-002": "task-bbb"},
            ),
        )

        with patch("api.services.content_data_service.load_analysis_json", return_value=None):
            result = get_briefs(tmp_path, slug)

        assert result.briefs[0].task_id == "task-aaa"
        assert result.briefs[1].task_id == "task-bbb"


# ── Phase 1: run_metadata_v13 status mapping ────────────────────────


class TestRunMetadataStatusMapping:
    """Test status inference from run_metadata_v13.json pieces."""

    @pytest.mark.parametrize(
        "piece_status, expected",
        [
            ("approved", "completed"),
            ("edited", "completed"),
            ("rejected", "rejected"),
            ("pending", "review"),
            ("unknown_status", "review"),  # fallback
        ],
    )
    def test_piece_status_to_brief_status(
        self, tmp_path: Path, piece_status: str, expected: str
    ):
        slug = "test-co"
        content_root = tmp_path / "content" / slug
        _write_json(
            content_root / "blueprints.json",
            _sample_blueprints(1),
        )
        _write_json(
            content_root / "run_metadata_v13.json",
            _sample_run_metadata(
                pieces=[{"brief_id": "brief-001", "status": piece_status}]
            ),
        )

        with patch("api.services.content_data_service.load_analysis_json", return_value=None):
            result = get_briefs(tmp_path, slug)

        assert result.briefs[0].status == expected

    def test_session_id_propagated_as_cycle_id(self, tmp_path: Path):
        slug = "test-co"
        content_root = tmp_path / "content" / slug
        _write_json(content_root / "blueprints.json", _sample_blueprints(1))
        _write_json(
            content_root / "run_metadata_v13.json",
            _sample_run_metadata(),
        )

        with patch("api.services.content_data_service.load_analysis_json", return_value=None):
            result = get_briefs(tmp_path, slug)

        assert result.briefs[0].cycle_id == "sess-abc-123"


# ── Phase 2: file-based status inference ─────────────────────────────


class TestFileBasedStatusInference:
    """Test status inference from stage file existence on disk."""

    @pytest.mark.parametrize(
        "files, expected_status",
        [
            ({}, "suggested"),  # no files
            ({"outline.json": '{"sections": []}'}, "outlining"),
            ({"outline.json": '{}', "draft.md": "# Draft"}, "drafting"),
            (
                {"outline.json": '{}', "draft.md": "x", "enriched.md": "x"},
                "enriching",
            ),
            (
                {
                    "outline.json": '{}',
                    "draft.md": "x",
                    "enriched.md": "x",
                    "eval_history.json": '{"final_passed": false, "cycles": []}',
                },
                "evaluating",
            ),
            (
                {
                    "outline.json": '{}',
                    "draft.md": "x",
                    "eval_history.json": '{"final_passed": true}',
                },
                "review",
            ),
            (
                {
                    "outline.json": '{}',
                    "draft.md": "x",
                    "final.md": "# Final content",
                },
                "completed",
            ),
        ],
    )
    def test_stage_file_to_status(
        self, tmp_path: Path, files: Dict[str, str], expected_status: str
    ):
        slug = "test-co"
        content_root = tmp_path / "content" / slug
        _write_json(content_root / "blueprints.json", _sample_blueprints(1))

        brief_dir = content_root / "content" / "brief-001"
        for filename, content in files.items():
            _write_text(brief_dir / filename, content)

        with patch("api.services.content_data_service.load_analysis_json", return_value=None):
            result = get_briefs(tmp_path, slug)

        assert result.briefs[0].status == expected_status


# ── Blueprints and planner_selections ────────────────────────────────


class TestBriefSources:
    """Test that briefs can be read from blueprints.json or planner_selections.json."""

    def test_blueprints_json_is_primary(self, tmp_path: Path):
        slug = "test-co"
        content_root = tmp_path / "content" / slug
        blueprints = _sample_blueprints(3)
        _write_json(content_root / "blueprints.json", blueprints)

        with patch("api.services.content_data_service.load_analysis_json", return_value=None):
            result = get_briefs(tmp_path, slug)

        assert result.total == 3
        assert result.briefs[0].id == "brief-001"
        assert result.briefs[0].title == blueprints[0]["title"]

    def test_planner_selections_fallback(self, tmp_path: Path):
        """When no blueprints.json, planner_selections.json is used."""
        slug = "test-co"
        content_root = tmp_path / "content" / slug
        _write_json(
            content_root / "planner_selections.json",
            {
                "selections": [
                    {"query_texts": ["AI search optimization"], "cluster_name": "seo"},
                    {"query_texts": ["B2B content strategy"], "cluster_name": "content"},
                ],
            },
        )

        with patch("api.services.content_data_service.load_analysis_json", return_value=None):
            result = get_briefs(tmp_path, slug)

        assert result.total == 2
        assert result.briefs[0].id == "brief-001"
        assert result.briefs[0].title == "AI search optimization"
        assert result.briefs[1].title == "B2B content strategy"

    def test_empty_content_dir_returns_empty_list(self, tmp_path: Path):
        """No content directory at all → empty response, not 404."""
        result = get_briefs(tmp_path, "test-co")
        assert result.total == 0
        assert result.briefs == []

    def test_content_format_to_type_mapping(self, tmp_path: Path):
        """Backend content_format maps to frontend content_type."""
        slug = "test-co"
        content_root = tmp_path / "content" / slug
        _write_json(
            content_root / "blueprints.json",
            [
                {"brief_id": "brief-001", "title": "A", "content_format": "long_blog", "word_count_range": [0, 0]},
                {"brief_id": "brief-002", "title": "B", "content_format": "pillar_page", "word_count_range": [0, 0]},
                {"brief_id": "brief-003", "title": "C", "content_format": "how_to", "word_count_range": [0, 0]},
            ],
        )

        with patch("api.services.content_data_service.load_analysis_json", return_value=None):
            result = get_briefs(tmp_path, slug)

        assert result.briefs[0].content_type == "blog"
        assert result.briefs[1].content_type == "guide"
        assert result.briefs[2].content_type == "guide"


# ── Brief detail ─────────────────────────────────────────────────────


class TestBriefDetail:
    """Test get_brief_detail reads all stages and metadata."""

    def test_detail_returns_all_fields(self, tmp_path: Path):
        slug = "test-co"
        content_root = tmp_path / "content" / slug
        blueprints = _sample_blueprints(1)
        blueprints[0]["exemplar_summaries"] = [
            {"url": "https://example.com", "word_count": 1500, "authority_type": "expert",
             "content_type": "blog", "snippet": "Sample snippet"},
        ]
        _write_json(content_root / "blueprints.json", blueprints)

        # Write stage files
        brief_dir = content_root / "content" / "brief-001"
        _write_json(brief_dir / "outline.json", {"sections": [{"title": "Intro"}]})
        _write_text(brief_dir / "draft.md", "# Draft\nContent here")
        _write_json(
            brief_dir / "eval_history.json",
            {
                "final_passed": True,
                "cycles": [
                    {
                        "cycle": 1,
                        "overall_passed": True,
                        "overall_score": 0.87,
                        "dimensions": [
                            {"dimension": "eeat", "passed": True, "score": 0.9, "feedback": "Good"},
                        ],
                    },
                ],
            },
        )

        with patch("api.services.content_data_service.load_analysis_json", return_value=None):
            detail = get_brief_detail(tmp_path, slug, "brief-001")

        assert detail.id == "brief-001"
        assert detail.final_passed is True
        assert detail.citability_score == 87.0
        assert len(detail.eval_history) == 1
        assert detail.eval_history[0].overall_score == 0.87
        assert len(detail.exemplars) == 1
        assert "outline" in detail.available_stages
        assert "draft" in detail.available_stages

    def test_detail_missing_brief_raises_404(self, tmp_path: Path):
        slug = "test-co"
        content_root = tmp_path / "content" / slug
        _write_json(content_root / "blueprints.json", _sample_blueprints(1))

        with pytest.raises(Exception) as exc_info:
            get_brief_detail(tmp_path, slug, "brief-999")
        assert exc_info.value.status_code == 404


# ── Stage content ────────────────────────────────────────────────────


class TestStageContent:
    """Test get_brief_stage_content reads correct file."""

    def test_read_json_stage(self, tmp_path: Path):
        slug = "test-co"
        content_root = tmp_path / "content" / slug
        _write_json(content_root / "blueprints.json", _sample_blueprints(1))
        brief_dir = content_root / "content" / "brief-001"
        _write_json(brief_dir / "outline.json", {"sections": [{"title": "Intro"}]})

        result = get_brief_stage_content(tmp_path, slug, "brief-001", "outline")

        assert result.brief_id == "brief-001"
        assert result.stage == "outline"
        assert result.content_type == "application/json"
        assert isinstance(result.content, dict)

    def test_read_markdown_stage(self, tmp_path: Path):
        slug = "test-co"
        content_root = tmp_path / "content" / slug
        _write_json(content_root / "blueprints.json", _sample_blueprints(1))
        brief_dir = content_root / "content" / "brief-001"
        _write_text(brief_dir / "draft.md", "# My Draft\n\nContent here.")

        result = get_brief_stage_content(tmp_path, slug, "brief-001", "draft")

        assert result.content_type == "text/markdown"
        assert "My Draft" in result.content

    def test_missing_stage_raises_404(self, tmp_path: Path):
        slug = "test-co"
        content_root = tmp_path / "content" / slug
        _write_json(content_root / "blueprints.json", _sample_blueprints(1))
        (content_root / "content" / "brief-001").mkdir(parents=True)

        with pytest.raises(Exception) as exc_info:
            get_brief_stage_content(tmp_path, slug, "brief-001", "outline")
        assert exc_info.value.status_code == 404

    def test_invalid_stage_raises_400(self, tmp_path: Path):
        slug = "test-co"
        content_root = tmp_path / "content" / slug
        _write_json(content_root / "blueprints.json", _sample_blueprints(1))

        with pytest.raises(Exception) as exc_info:
            get_brief_stage_content(tmp_path, slug, "brief-001", "nonexistent")
        assert exc_info.value.status_code == 400


# ── Malformed / edge cases ───────────────────────────────────────────


class TestEdgeCases:
    """Test graceful handling of malformed or missing artifacts."""

    def test_corrupted_blueprints_returns_empty(self, tmp_path: Path):
        slug = "test-co"
        content_root = tmp_path / "content" / slug
        content_root.mkdir(parents=True)
        (content_root / "blueprints.json").write_text("not valid json{{{", encoding="utf-8")

        result = get_briefs(tmp_path, slug)
        assert result.total == 0

    def test_corrupted_eval_history_handled_gracefully(self, tmp_path: Path):
        slug = "test-co"
        content_root = tmp_path / "content" / slug
        _write_json(content_root / "blueprints.json", _sample_blueprints(1))
        brief_dir = content_root / "content" / "brief-001"
        _write_text(brief_dir / "eval_history.json", "corrupted{{{")

        # Should not crash — eval_history is optional enrichment
        with patch("api.services.content_data_service.load_analysis_json", return_value=None):
            result = get_briefs(tmp_path, slug)

        assert result.total == 1
        assert result.briefs[0].citability_score is None

    def test_effective_slug_with_product(self, tmp_path: Path):
        """Effective slug uses double-underscore: company__product."""
        slug = "ramp__card"
        content_root = tmp_path / "content" / slug
        _write_json(content_root / "blueprints.json", _sample_blueprints(1))

        with patch("api.services.content_data_service.load_analysis_json", return_value=None):
            result = get_briefs(tmp_path, slug)

        assert result.total == 1
        assert result.briefs[0].id == "brief-001"
