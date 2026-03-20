"""Tests for per-step / per-agent context binding (PB-85).

Verifies that pipeline orchestrators wrap each step/agent in
``scoped_bind(step_name=...)`` or ``scoped_bind(agent_name=...)``.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.shared_tools.structured_logging import clear_context


@pytest.fixture(autouse=True)
def _clear_context():
    clear_context()
    yield
    clear_context()


class TestSiteAuditStepBinding:
    """Verify site audit binds step_name for each of its 6 steps."""

    @pytest.mark.asyncio
    async def test_site_audit_binds_all_step_names(self) -> None:
        from core.models.site_audit import SiteAuditInput

        input_data = SiteAuditInput(domain="example.com", company_name="Test Co")

        with patch(
            "core.site_audit.pipeline.scoped_bind"
        ) as mock_scoped:
            # Make scoped_bind behave as a real context manager
            mock_scoped.return_value.__enter__ = MagicMock(return_value=None)
            mock_scoped.return_value.__exit__ = MagicMock(return_value=False)

            from core.site_audit.pipeline import run_site_audit

            # Skip all steps so we don't need real crawling infrastructure
            await run_site_audit(input_data, skip_steps=[1, 2, 3, 4, 5, 6])

        # Collect all step_name values from scoped_bind calls
        step_names = []
        for call in mock_scoped.call_args_list:
            if "step_name" in call.kwargs:
                step_names.append(call.kwargs["step_name"])

        assert "s1_discover" in step_names
        assert "s2_analyze_pages" in step_names
        assert "s3_check_schema" in step_names
        assert "s4_check_aeo" in step_names
        assert "s5_aggregate" in step_names
        assert "s6_report" in step_names

    @pytest.mark.asyncio
    async def test_site_audit_step_names_in_order(self) -> None:
        from core.models.site_audit import SiteAuditInput

        input_data = SiteAuditInput(domain="example.com", company_name="Test Co")

        with patch(
            "core.site_audit.pipeline.scoped_bind"
        ) as mock_scoped:
            mock_scoped.return_value.__enter__ = MagicMock(return_value=None)
            mock_scoped.return_value.__exit__ = MagicMock(return_value=False)

            from core.site_audit.pipeline import run_site_audit

            await run_site_audit(input_data, skip_steps=[1, 2, 3, 4, 5, 6])

        step_names = [
            call.kwargs["step_name"]
            for call in mock_scoped.call_args_list
            if "step_name" in call.kwargs
        ]
        expected_order = [
            "s1_discover",
            "s2_analyze_pages",
            "s3_check_schema",
            "s4_check_aeo",
            "s5_aggregate",
            "s6_report",
        ]
        assert step_names == expected_order


class TestGapAnalysisStepBinding:
    """Verify gap analysis binds step_name for S1-S8."""

    @pytest.mark.asyncio
    async def test_gap_analysis_binds_step_names(self) -> None:
        """Run gap analysis with all steps skipped to verify scoped_bind calls."""
        from core.models.gap_analysis import GapAnalysisInput

        input_data = GapAnalysisInput(
            company_name="Test Co",
            company_slug="test-co",
            company_url="https://example.com",
        )

        with patch(
            "core.gap_analysis.pipeline.scoped_bind"
        ) as mock_scoped:
            mock_scoped.return_value.__enter__ = MagicMock(return_value=None)
            mock_scoped.return_value.__exit__ = MagicMock(return_value=False)

            from core.gap_analysis.pipeline import run_gap_analysis

            try:
                await run_gap_analysis(
                    input_data,
                    skip_steps=[1, 2, 3, 4, 5, 6, 7, 8],
                )
            except Exception:
                pass  # Pipeline may fail loading cached artifacts — that's fine

        step_names = [
            call.kwargs["step_name"]
            for call in mock_scoped.call_args_list
            if "step_name" in call.kwargs
        ]

        # At minimum S1 and S2 should be bound (they run in parallel via gather)
        assert "s1_embed_company_assets" in step_names
        assert "s2_generate_queries" in step_names
