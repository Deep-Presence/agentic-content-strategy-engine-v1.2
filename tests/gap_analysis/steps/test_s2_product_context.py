"""Tests for Phase 4 — product context injection in s2 and content planner.

Covers:
- _PRODUCT_CONTEXT_BLOCK constant exists and has expected slots
- _build_seed_prompt includes product block when provided, empty when not
- generate_queries() builds product_context from input_data.product_* fields
- build_planner_user_prompt includes product section when product_context_md set
- planner.plan_content builds product_context_md from input_data product fields
- Company-level runs have zero product context (no drift)
"""
from __future__ import annotations

from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.gap_analysis.steps.s2_generate_queries import (
    _PRODUCT_CONTEXT_BLOCK,
    _build_seed_prompt,
)
from core.models.gap_analysis import GapAnalysisInput, QueryCluster


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_clusters() -> list[QueryCluster]:
    return [
        QueryCluster(
            cluster_id="C1",
            cluster_name="Mechanism",
            intent="How does X work?",
            buyer_stage="Consideration",
        ),
        QueryCluster(
            cluster_id="C8",
            cluster_name="Branded Evaluation",
            intent="X vs Y",
            buyer_stage="Decision",
        ),
    ]


def _gap_input(
    product_slug: Optional[str] = None,
    product_name: Optional[str] = None,
    product_description: Optional[str] = None,
) -> GapAnalysisInput:
    return GapAnalysisInput(
        company_name="Ramp",
        domain="ramp.com",
        company_slug="ramp" if not product_slug else f"ramp__{product_slug}",
        product_slug=product_slug,
        product_name=product_name,
        product_description=product_description,
        max_queries=20,
    )


# ---------------------------------------------------------------------------
# _PRODUCT_CONTEXT_BLOCK constant
# ---------------------------------------------------------------------------


class TestProductContextBlockConstant:
    def test_has_product_name_slot(self) -> None:
        assert "{product_name}" in _PRODUCT_CONTEXT_BLOCK

    def test_has_product_domain_slot(self) -> None:
        assert "{product_domain}" in _PRODUCT_CONTEXT_BLOCK

    def test_has_product_description_slot(self) -> None:
        assert "{product_description}" in _PRODUCT_CONTEXT_BLOCK

    def test_formats_correctly(self) -> None:
        rendered = _PRODUCT_CONTEXT_BLOCK.format(
            product_name="Corporate Card",
            product_domain="ramp.com/card",
            product_description="B2B corporate spend card",
        )
        assert "Corporate Card" in rendered
        assert "ramp.com/card" in rendered
        assert "B2B corporate spend card" in rendered


# ---------------------------------------------------------------------------
# _build_seed_prompt — product block injection
# ---------------------------------------------------------------------------


class TestBuildSeedPromptProductContext:
    def test_no_product_context_empty_slot(self) -> None:
        """Company-level run: {product_context_block} slot renders as empty string."""
        clusters = _make_clusters()
        prompt = _build_seed_prompt(
            company_context="",
            persona_context="",
            style_guide="",
            clusters=clusters,
            max_queries=20,
            company_name="Ramp",
            company_domain="ramp.com",
            product_context=None,
        )
        assert "SPECIFIC PRODUCT SCOPE" not in prompt
        assert "product_context_block" not in prompt  # slot fully resolved

    def test_product_context_injected(self) -> None:
        """Product-level run: product block appears before cluster taxonomy."""
        clusters = _make_clusters()
        product_ctx = _PRODUCT_CONTEXT_BLOCK.format(
            product_name="Corporate Card",
            product_domain="ramp.com/card",
            product_description="Spend management card",
        )
        prompt = _build_seed_prompt(
            company_context="",
            persona_context="",
            style_guide="",
            clusters=clusters,
            max_queries=20,
            company_name="Ramp",
            company_domain="ramp.com",
            product_context=product_ctx,
        )
        assert "SPECIFIC PRODUCT SCOPE" in prompt
        assert "Corporate Card" in prompt

    def test_product_block_before_cluster_taxonomy(self) -> None:
        """Product block must appear before QUERY CLUSTER TAXONOMY."""
        clusters = _make_clusters()
        product_ctx = _PRODUCT_CONTEXT_BLOCK.format(
            product_name="Card",
            product_domain="ramp.com",
            product_description="desc",
        )
        prompt = _build_seed_prompt(
            company_context="",
            persona_context="",
            style_guide="",
            clusters=clusters,
            max_queries=20,
            company_name="Ramp",
            company_domain="ramp.com",
            product_context=product_ctx,
        )
        pos_product = prompt.index("SPECIFIC PRODUCT SCOPE")
        pos_cluster = prompt.index("QUERY CLUSTER TAXONOMY")
        assert pos_product < pos_cluster

    def test_company_level_prompt_identical_without_product(self) -> None:
        """Company-level prompt contains no product-specific text."""
        clusters = _make_clusters()
        prompt = _build_seed_prompt(
            company_context="ctx",
            persona_context="persona",
            style_guide="",
            clusters=clusters,
            max_queries=30,
            company_name="Ramp",
            company_domain="ramp.com",
            product_context="",
        )
        assert "SPECIFIC PRODUCT SCOPE" not in prompt
        assert "Product name:" not in prompt


# ---------------------------------------------------------------------------
# generate_queries() — product context from input_data
# ---------------------------------------------------------------------------


class TestGenerateQueriesProductContext:
    @pytest.mark.asyncio
    async def test_company_level_no_product_block_in_prompt(self) -> None:
        """Company-level GapAnalysisInput → prompt has no product block."""
        captured: list[str] = []

        async def fake_call(prompt: str, model: str) -> str:
            captured.append(prompt)
            return '{"queries": []}'

        with patch(
            "core.gap_analysis.steps.s2_generate_queries._call_openai",
            side_effect=fake_call,
        ), patch(
            "core.gap_analysis.steps.s2_generate_queries._load_taxonomy",
            return_value=_make_clusters(),
        ), patch(
            "core.gap_analysis.steps.s2_generate_queries._deduplicate_queries",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "core.gap_analysis.steps.s2_generate_queries._validate_coverage",
            new_callable=AsyncMock,
            return_value=[],
        ):
            from core.gap_analysis.steps.s2_generate_queries import generate_queries
            await generate_queries(input_data=_gap_input())

        assert len(captured) >= 1
        assert "SPECIFIC PRODUCT SCOPE" not in captured[0]

    @pytest.mark.asyncio
    async def test_product_level_injects_product_block(self) -> None:
        """Product GapAnalysisInput with product_name → prompt includes product block."""
        captured: list[str] = []

        async def fake_call(prompt: str, model: str) -> str:
            captured.append(prompt)
            return '{"queries": []}'

        with patch(
            "core.gap_analysis.steps.s2_generate_queries._call_openai",
            side_effect=fake_call,
        ), patch(
            "core.gap_analysis.steps.s2_generate_queries._load_taxonomy",
            return_value=_make_clusters(),
        ), patch(
            "core.gap_analysis.steps.s2_generate_queries._deduplicate_queries",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "core.gap_analysis.steps.s2_generate_queries._validate_coverage",
            new_callable=AsyncMock,
            return_value=[],
        ):
            from core.gap_analysis.steps.s2_generate_queries import generate_queries
            await generate_queries(
                input_data=_gap_input(
                    product_slug="corporate-card",
                    product_name="Ramp Corporate Card",
                    product_description="A spend management card",
                )
            )

        assert len(captured) >= 1
        assert "SPECIFIC PRODUCT SCOPE" in captured[0]
        assert "Ramp Corporate Card" in captured[0]

    @pytest.mark.asyncio
    async def test_product_slug_without_name_no_block(self) -> None:
        """product_slug set but product_name is None → no block (guard respected)."""
        captured: list[str] = []

        async def fake_call(prompt: str, model: str) -> str:
            captured.append(prompt)
            return '{"queries": []}'

        with patch(
            "core.gap_analysis.steps.s2_generate_queries._call_openai",
            side_effect=fake_call,
        ), patch(
            "core.gap_analysis.steps.s2_generate_queries._load_taxonomy",
            return_value=_make_clusters(),
        ), patch(
            "core.gap_analysis.steps.s2_generate_queries._deduplicate_queries",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "core.gap_analysis.steps.s2_generate_queries._validate_coverage",
            new_callable=AsyncMock,
            return_value=[],
        ):
            from core.gap_analysis.steps.s2_generate_queries import generate_queries
            await generate_queries(
                input_data=_gap_input(
                    product_slug="corporate-card",
                    product_name=None,  # no name → guard prevents injection
                )
            )

        assert len(captured) >= 1
        assert "SPECIFIC PRODUCT SCOPE" not in captured[0]


# ---------------------------------------------------------------------------
# build_planner_user_prompt — product section
# ---------------------------------------------------------------------------


class TestPlannerPromptProductContext:
    def test_no_product_context_no_section(self) -> None:
        from core.content_engine.prompts.planner_prompts import build_planner_user_prompt
        prompt = build_planner_user_prompt(
            company_name="Ramp",
            domain="ramp.com",
            company_context_md="Company context",
            style_guide_md="",
            gap_report_json={},
            generation_spec_json={},
            analysis_json={},
            persona_mds=[],
            max_briefs=5,
        )
        assert "Specific Product Focus" not in prompt

    def test_product_context_injected_after_company_section(self) -> None:
        from core.content_engine.prompts.planner_prompts import (
            _PRODUCT_FOCUS_BLOCK,
            build_planner_user_prompt,
        )
        product_ctx = _PRODUCT_FOCUS_BLOCK.format(
            product_name="Corporate Card",
            product_domain="ramp.com/card",
            product_description="B2B spend card",
        )
        prompt = build_planner_user_prompt(
            company_name="Ramp",
            domain="ramp.com",
            company_context_md="Company context",
            style_guide_md="",
            gap_report_json={},
            generation_spec_json={},
            analysis_json={},
            persona_mds=[],
            max_briefs=5,
            product_context_md=product_ctx,
        )
        assert "Specific Product Focus" in prompt
        assert "Corporate Card" in prompt
        # Must appear after ## Company section
        pos_company = prompt.index("## Company")
        pos_product = prompt.index("## Specific Product Focus")
        assert pos_company < pos_product

    def test_product_focus_block_constant_slots(self) -> None:
        from core.content_engine.prompts.planner_prompts import _PRODUCT_FOCUS_BLOCK
        assert "{product_name}" in _PRODUCT_FOCUS_BLOCK
        assert "{product_domain}" in _PRODUCT_FOCUS_BLOCK
        assert "{product_description}" in _PRODUCT_FOCUS_BLOCK

    def test_empty_product_context_no_section(self) -> None:
        from core.content_engine.prompts.planner_prompts import build_planner_user_prompt
        prompt = build_planner_user_prompt(
            company_name="Ramp",
            domain="ramp.com",
            company_context_md="ctx",
            style_guide_md="",
            gap_report_json={},
            generation_spec_json={},
            analysis_json={},
            persona_mds=[],
            max_briefs=3,
            product_context_md="",
        )
        assert "Specific Product Focus" not in prompt
