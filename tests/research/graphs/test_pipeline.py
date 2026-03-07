"""Tests for the combined research pipeline orchestrator."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.models.artifacts import CompanyResearchInput
from core.models.style_guide import StyleGuideResearchInput
from core.research.graphs.pipeline import (
    _get_interrupt_value,
    _has_interrupt,
    run_company_stage,
    run_pipeline,
    run_style_stage,
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestHasInterrupt:
    def test_true_when_present(self):
        mock_interrupt = MagicMock()
        mock_interrupt.value = {"status": "pending_approval"}
        assert _has_interrupt({"__interrupt__": [mock_interrupt]}) is True

    def test_false_when_absent(self):
        assert _has_interrupt({"output_path": "/path"}) is False

    def test_false_for_empty_list(self):
        assert _has_interrupt({"__interrupt__": []}) is False


class TestGetInterruptValue:
    def test_extracts_first_value(self):
        mock_interrupt = MagicMock()
        mock_interrupt.value = {"status": "pending_approval", "draft_path": "/path"}
        result = _get_interrupt_value({"__interrupt__": [mock_interrupt]})
        assert result["status"] == "pending_approval"

    def test_empty_when_no_interrupts(self):
        assert _get_interrupt_value({}) == {}
        assert _get_interrupt_value({"__interrupt__": []}) == {}


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def _mock_stage_complete(**extra):
    """Create a mock stage result that looks like a completed graph."""
    return {"output_path": "/artifacts/company_context/acme-corp.md", "mirrored": True, **extra}


def _mock_stage_interrupt(stage: str):
    """Create a mock result that looks like an interrupted stage."""
    return {"status": "interrupt", "values": {"status": "pending_approval"}}


class TestRunPipeline:
    def test_full_pipeline_auto_approve(self, company_input, style_input):
        with patch("core.research.graphs.pipeline.run_company_stage") as mock_company, \
             patch("core.research.graphs.pipeline.run_style_stage") as mock_style:
            mock_company.return_value = _mock_stage_complete()
            mock_style.return_value = {"written_paths": ["/artifacts/style_guides/acme-corp.md"]}

            result = run_pipeline(
                company_input=company_input,
                style_input=style_input,
                auto_approve=True,
            )

        assert result["stage"] == "complete"
        assert result["company"] is not None
        assert result["style"] is not None

    def test_company_only(self, company_input):
        with patch("core.research.graphs.pipeline.run_company_stage") as mock_company:
            mock_company.return_value = _mock_stage_complete()

            result = run_pipeline(
                company_input=company_input,
                style_input=None,
                auto_approve=True,
            )

        assert result["stage"] == "complete"
        assert result["style"] is None

    def test_interrupt_at_company_stage(self, company_input, style_input):
        with patch("core.research.graphs.pipeline.run_company_stage") as mock_company:
            mock_company.return_value = _mock_stage_interrupt("company")

            result = run_pipeline(
                company_input=company_input,
                style_input=style_input,
            )

        assert result["stage"] == "company"
        assert result["status"] == "interrupt"

    def test_interrupt_at_style_stage(self, company_input, style_input):
        with patch("core.research.graphs.pipeline.run_company_stage") as mock_company, \
             patch("core.research.graphs.pipeline.run_style_stage") as mock_style:
            mock_company.return_value = _mock_stage_complete()
            mock_style.return_value = _mock_stage_interrupt("style")

            result = run_pipeline(
                company_input=company_input,
                style_input=style_input,
            )

        assert result["stage"] == "style"
        assert result["status"] == "interrupt"


# ---------------------------------------------------------------------------
# Context passing
# ---------------------------------------------------------------------------

class TestContextPassing:
    def test_company_output_passed_to_style(self, company_input, style_input):
        with patch("core.research.graphs.pipeline.run_company_stage") as mock_company, \
             patch("core.research.graphs.pipeline.run_style_stage") as mock_style:
            mock_company.return_value = {
                "output_path": "/artifacts/company_context/acme-corp.md",
            }
            mock_style.return_value = {"written_paths": []}

            run_pipeline(
                company_input=company_input,
                style_input=style_input,
                auto_approve=True,
            )

        actual_style_input = mock_style.call_args.args[0]
        assert actual_style_input.company_context_path == "/artifacts/company_context/acme-corp.md"


# ---------------------------------------------------------------------------
# Optional stages
# ---------------------------------------------------------------------------

class TestOptionalStages:
    def test_style_skipped_when_none(self, company_input):
        with patch("core.research.graphs.pipeline.run_company_stage") as mock_company, \
             patch("core.research.graphs.pipeline.run_style_stage") as mock_style:
            mock_company.return_value = _mock_stage_complete()

            run_pipeline(
                company_input=company_input,
                style_input=None,
                auto_approve=True,
            )

        mock_style.assert_not_called()


# ---------------------------------------------------------------------------
# Individual stage delegation
# ---------------------------------------------------------------------------

class TestIndividualStages:
    def test_run_company_stage_delegates(self, company_input):
        with patch("core.research.graphs.pipeline.build_company_graph") as mock_build:
            mock_graph = MagicMock()
            mock_graph.invoke.return_value = {"output_path": "/path"}
            mock_build.return_value = mock_graph

            result = run_company_stage(company_input, auto_approve=True)

        mock_build.assert_called_once()
        assert result.get("output_path") == "/path"
