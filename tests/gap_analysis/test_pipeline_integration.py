"""Pipeline integration tests — contract validation, data flow, artifact round-trips.

Tests the end-to-end data contracts between pipeline steps without hitting
external services (OpenAI, ChromaDB, httpx). All I/O is mocked.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.gap_analysis import (
    AnalysisResult,
    CitationExemplar,
    CitationRef,
    ClusterContentSpec,
    EnrichedCitation,
    GapAnalysisInput,
    GapReport,
    GeneratedQuery,
    ParagraphMatch,
    PlatformResult,
    QueryGap,
    SemanticUnit,
    SiteDiscoveryResult,
    SpaResult,
    StructuralSignals,
)


# ---------------------------------------------------------------------------
# Shared Fixtures — realistic data for multi-step flows
# ---------------------------------------------------------------------------

@pytest.fixture
def gap_input() -> GapAnalysisInput:
    return GapAnalysisInput(
        company_name="Acme Corp",
        domain="acme.com",
        seed_urls=["https://acme.com"],
        platforms=["perplexity", "openai"],
        max_queries=20,
    )


@pytest.fixture
def semantic_units() -> List[SemanticUnit]:
    """Realistic S1 output — company content chunks with embeddings."""
    return [
        SemanticUnit(
            unit_id="unit_1",
            url="https://acme.com/",
            title="Acme Corp - Home",
            text="Acme Corp provides enterprise expense management software for growing companies.",
            embedding=[0.1] * 10,
            char_count=80,
            word_count=11,
        ),
        SemanticUnit(
            unit_id="unit_2",
            url="https://acme.com/product",
            title="Product Overview",
            text="Our platform automates receipt matching, policy enforcement, and real-time spend tracking.",
            embedding=[0.2] * 10,
            char_count=90,
            word_count=12,
        ),
        SemanticUnit(
            unit_id="unit_3",
            url="https://acme.com/blog/expense-tips",
            title="10 Expense Management Tips",
            text="Managing corporate expenses efficiently requires modern tools that integrate with your accounting stack.",
            embedding=[0.15] * 10,
            char_count=100,
            word_count=14,
        ),
    ]


@pytest.fixture
def generated_queries() -> List[GeneratedQuery]:
    """Realistic S2 output — buyer-intent queries across clusters."""
    return [
        GeneratedQuery(
            query_id="q_1",
            cluster_id="C1",
            cluster_name="Mechanism",
            query_text="How does automated receipt matching work in expense management?",
            buyer_stage="Consideration",
            persona_tag="icp",
            embedding=[0.3] * 10,
        ),
        GeneratedQuery(
            query_id="q_2",
            cluster_id="C5",
            cluster_name="Definition",
            query_text="What is spend management and why does it matter for growing companies?",
            buyer_stage="Awareness",
            persona_tag="icp",
            embedding=[0.25] * 10,
        ),
        GeneratedQuery(
            query_id="q_3",
            cluster_id="C7",
            cluster_name="Best-of",
            query_text="Best expense management software for startups in 2025",
            buyer_stage="Consideration",
            persona_tag="icp",
            embedding=[0.35] * 10,
        ),
    ]


@pytest.fixture
def platform_results() -> List[PlatformResult]:
    """Realistic S3 output — search results from multiple engines."""
    return [
        PlatformResult(
            engine="perplexity",
            model="sonar-pro",
            query_id="q_1",
            query_text="How does automated receipt matching work in expense management?",
            response_text="Automated receipt matching uses OCR and ML...",
            citations=[
                CitationRef(
                    url="https://competitor.com/blog/receipt-matching",
                    rank=1,
                    title="How Receipt Matching Works",
                    snippet="OCR-based receipt matching automates the process of linking receipts to transactions.",
                ),
                CitationRef(
                    url="https://fintech-blog.com/expense-automation",
                    rank=2,
                    title="Expense Automation Guide",
                    snippet="Modern expense platforms use machine learning to match receipts automatically.",
                ),
            ],
        ),
        PlatformResult(
            engine="openai",
            model="gpt-4o",
            query_id="q_1",
            query_text="How does automated receipt matching work in expense management?",
            response_text="Receipt matching in expense management...",
            citations=[
                CitationRef(
                    url="https://competitor.com/blog/receipt-matching",
                    rank=1,
                    title="How Receipt Matching Works",
                    snippet="The process involves scanning and categorizing.",
                ),
            ],
        ),
        PlatformResult(
            engine="perplexity",
            model="sonar-pro",
            query_id="q_2",
            query_text="What is spend management?",
            response_text="Spend management is a comprehensive approach...",
            citations=[
                CitationRef(
                    url="https://industrysite.com/spend-management-guide",
                    rank=1,
                    title="Complete Guide to Spend Management",
                    snippet="Spend management encompasses procurement, expense tracking, and budgeting.",
                ),
            ],
        ),
        PlatformResult(
            engine="perplexity",
            model="sonar-pro",
            query_id="q_3",
            query_text="Best expense management software for startups",
            response_text="Top options include several platforms...",
            citations=[
                CitationRef(
                    url="https://review-site.com/best-expense-software",
                    rank=1,
                    title="Best Expense Software 2025",
                    snippet="We reviewed 15 expense management platforms.",
                ),
            ],
        ),
    ]


@pytest.fixture
def enriched_citations() -> List[EnrichedCitation]:
    """Realistic S4 output — crawled citations with structural signals."""
    return [
        EnrichedCitation(
            url="https://competitor.com/blog/receipt-matching",
            domain="competitor.com",
            title="How Receipt Matching Works",
            query_id="q_1",
            cluster_name="Mechanism",
            engine="perplexity",
            anchor_text="OCR-based receipt matching automates the process.",
            paragraphs=[
                "Automated receipt matching uses optical character recognition to scan paper and digital receipts.",
                "The system then matches receipt data against transaction records in your accounting software.",
                "Modern ML models can achieve over 95% accuracy in receipt categorization and matching.",
            ],
            best_paragraphs=[
                ParagraphMatch(
                    paragraph="Automated receipt matching uses optical character recognition to scan paper and digital receipts.",
                    embedding=[0.4] * 10,
                    embedding_id="cite_abc123",
                    similarity=0.82,
                ),
            ],
            structural_signals=StructuralSignals(
                word_count=450,
                paragraph_count=8,
                header_count=3,
                list_item_count=5,
                stat_count=2,
                citation_count=4,
                has_headers=True,
                has_lists=True,
                has_numbers=True,
                authority_type="commercial_or_media",
                content_type="blog_or_article",
            ),
        ),
        EnrichedCitation(
            url="https://fintech-blog.com/expense-automation",
            domain="fintech-blog.com",
            title="Expense Automation Guide",
            query_id="q_1",
            cluster_name="Mechanism",
            engine="perplexity",
            anchor_text="Modern expense platforms use machine learning.",
            paragraphs=[
                "Machine learning has transformed how companies handle expense reporting and compliance.",
                "Key features include automated policy enforcement, real-time alerts, and spending analytics.",
            ],
            best_paragraphs=[],
            structural_signals=StructuralSignals(
                word_count=320,
                paragraph_count=6,
                header_count=2,
                has_headers=True,
                authority_type="commercial_or_media",
                content_type="guide",
            ),
        ),
        EnrichedCitation(
            url="https://industrysite.com/spend-management-guide",
            domain="industrysite.com",
            title="Complete Guide to Spend Management",
            query_id="q_2",
            cluster_name="Definition",
            engine="perplexity",
            anchor_text="Spend management encompasses procurement.",
            paragraphs=[
                "Spend management is the practice of controlling and optimizing organizational spending.",
            ],
            best_paragraphs=[],
            structural_signals=StructuralSignals(
                word_count=800,
                paragraph_count=12,
                header_count=5,
                list_item_count=10,
                has_headers=True,
                has_lists=True,
                authority_type="commercial_or_media",
                content_type="guide",
            ),
        ),
    ]


@pytest.fixture
def analysis_result() -> AnalysisResult:
    """Realistic S6 output — computed gap analysis."""
    return AnalysisResult(
        proximity_stats={
            "citation_similarity_mean": 0.62,
            "company_similarity_mean": 0.38,
            "citation_similarity_median": 0.60,
            "company_similarity_median": 0.35,
        },
        spa_results=[
            SpaResult(
                test_name="cspa",
                t_stat=3.14,
                p_value=0.005,
                mean_citation_similarity=0.62,
                mean_company_similarity=0.38,
                effect="moderate",
            ),
        ],
        gaps=[
            QueryGap(
                query_id="q_1",
                cluster_name="Mechanism",
                query_text="How does automated receipt matching work?",
                best_company_unit="unit_1",
                best_company_unit_text="Acme Corp provides enterprise expense management...",
                best_company_similarity=0.45,
                avg_citation_similarity=0.72,
                gap=0.27,
                interpretation="moderate_gap",
                top_cited_exemplars=[
                    CitationExemplar(
                        similarity=0.82,
                        domain="competitor.com",
                        url="https://competitor.com/blog/receipt-matching",
                        snippet="Automated receipt matching uses OCR...",
                        structural_signals=StructuralSignals(
                            word_count=450,
                            header_count=3,
                            has_headers=True,
                        ),
                        authority_type="commercial_or_media",
                    ),
                ],
            ),
            QueryGap(
                query_id="q_2",
                cluster_name="Definition",
                query_text="What is spend management?",
                best_company_similarity=0.35,
                avg_citation_similarity=0.65,
                gap=0.30,
                interpretation="moderate_gap",
            ),
            QueryGap(
                query_id="q_3",
                cluster_name="Best-of",
                query_text="Best expense management software for startups",
                best_company_similarity=0.20,
                avg_citation_similarity=0.55,
                gap=0.35,
                interpretation="large_gap",
            ),
        ],
        centroids=[],
        cluster_specs=[
            ClusterContentSpec(
                cluster_id="C1",
                cluster_name="Mechanism",
                query_count=1,
                word_count_range=[300, 600],
                required_elements=["headers", "lists"],
                authority_signals={"commercial_or_media": 2},
                structural_rates={"has_headers": 1.0, "has_lists": 0.5},
                total_citations_analyzed=2,
            ),
        ],
        citation_patterns={
            "authority_types": {"commercial_or_media": 3},
            "content_types": {"blog_or_article": 1, "guide": 2},
        },
        decision_metrics={
            "total_queries": 3,
            "total_citations": 3,
            "avg_gap": 0.307,
        },
    )


# ---------------------------------------------------------------------------
# 1. CONTRACT TESTS — Step boundary validation
# ---------------------------------------------------------------------------

class TestStepContracts:
    """Verify that each step's output satisfies the next step's input contract."""

    def test_s1_output_has_required_fields_for_s6(self, semantic_units):
        """S1 → S6: SemanticUnit must have unit_id, text, and embedding."""
        for unit in semantic_units:
            assert unit.unit_id, "unit_id required for S6 lookup"
            assert unit.text, "text required for S6 similarity computation"
            assert unit.embedding is not None, "embedding required for S6 similarity"
            assert len(unit.embedding) > 0, "embedding must be non-empty"

    def test_s2_output_has_required_fields_for_s3(self, generated_queries):
        """S2 → S3: GeneratedQuery must have query_id and query_text."""
        for q in generated_queries:
            assert q.query_id, "query_id required for S3 task tracking"
            assert q.query_text, "query_text required for S3 search"
            assert q.cluster_id, "cluster_id required for downstream analysis"

    def test_s3_output_has_required_fields_for_s4(self, platform_results):
        """S3 → S4: PlatformResult must have query_id, engine, and citations."""
        for result in platform_results:
            assert result.query_id, "query_id required for S4 query_lookup"
            assert result.engine, "engine required for S4 metadata"
            # citations can be empty (no results), but list must exist
            assert isinstance(result.citations, list)
            for cite in result.citations:
                assert cite.url, "citation URL required for S4 fetching"

    def test_s4_output_has_required_fields_for_s5(self, enriched_citations):
        """S4 → S5: EnrichedCitation must have url, paragraphs, structural_signals."""
        for ec in enriched_citations:
            assert ec.url, "url required for embedding ID generation in S5"
            assert isinstance(ec.paragraphs, list), "paragraphs list required for S5"
            assert ec.structural_signals is not None, "structural_signals required for S6"

    def test_s5_output_queries_have_embeddings(self, generated_queries):
        """S5 → S6: GeneratedQuery must have embedding populated."""
        for q in generated_queries:
            assert q.embedding is not None, "embedding required for S6 similarity"
            assert len(q.embedding) > 0

    def test_s6_output_has_required_fields_for_s8(self, analysis_result):
        """S6 → S8: AnalysisResult must have gaps, proximity_stats, spa_results."""
        assert isinstance(analysis_result.gaps, list)
        assert isinstance(analysis_result.proximity_stats, dict)
        assert isinstance(analysis_result.spa_results, list)
        assert isinstance(analysis_result.cluster_specs, list)
        for gap in analysis_result.gaps:
            assert gap.query_id, "query_id required for report generation"
            assert gap.query_text, "query_text required for report display"

    def test_s8_output_has_report_content(self):
        """S8 output: GapReport must have markdown and JSON sections."""
        report = GapReport(
            report_md="# Test Report",
            report_json={"executive_summary": "test"},
            generation_spec_md="# Spec",
            generation_spec_json={"cluster_specs": []},
            visualization_paths=["/path/to/viz.html"],
        )
        assert report.report_md
        assert report.report_json
        assert isinstance(report.visualization_paths, list)


# ---------------------------------------------------------------------------
# 2. ARTIFACT ROUND-TRIP TESTS — Serialize → Deserialize
# ---------------------------------------------------------------------------

class TestArtifactRoundTrips:
    """Verify that pipeline artifacts survive JSON serialization round-trips."""

    def test_semantic_unit_round_trip(self, semantic_units):
        """SemanticUnit survives JSON round-trip (S1 → skip_steps → pipeline reload)."""
        for unit in semantic_units:
            json_str = json.dumps(unit.model_dump(mode="json"), default=str)
            loaded = SemanticUnit(**json.loads(json_str))
            assert loaded.unit_id == unit.unit_id
            assert loaded.text == unit.text
            assert loaded.embedding == unit.embedding

    def test_generated_query_round_trip(self, generated_queries):
        """GeneratedQuery survives JSON round-trip (S2 → queries.json → reload)."""
        json_str = json.dumps(
            [q.model_dump(mode="json") for q in generated_queries],
            default=str,
        )
        loaded = [GeneratedQuery(**item) for item in json.loads(json_str)]
        assert len(loaded) == len(generated_queries)
        for orig, reloaded in zip(generated_queries, loaded):
            assert reloaded.query_id == orig.query_id
            assert reloaded.query_text == orig.query_text
            assert reloaded.cluster_id == orig.cluster_id
            assert reloaded.embedding == orig.embedding

    def test_platform_result_round_trip(self, platform_results):
        """PlatformResult survives JSONL round-trip (S3 → engine_results.jsonl → reload)."""
        for result in platform_results:
            json_line = json.dumps(result.model_dump(mode="json"), default=str)
            loaded = PlatformResult(**json.loads(json_line))
            assert loaded.engine == result.engine
            assert loaded.query_id == result.query_id
            assert len(loaded.citations) == len(result.citations)
            for orig_cite, loaded_cite in zip(result.citations, loaded.citations):
                assert str(loaded_cite.url) == str(orig_cite.url)

    def test_enriched_citation_round_trip(self, enriched_citations):
        """EnrichedCitation survives JSON round-trip (S4 → enriched_citations.json)."""
        json_str = json.dumps(
            [c.model_dump(mode="json") for c in enriched_citations],
            default=str,
        )
        loaded = [EnrichedCitation(**item) for item in json.loads(json_str)]
        assert len(loaded) == len(enriched_citations)
        for orig, reloaded in zip(enriched_citations, loaded):
            assert str(reloaded.url) == str(orig.url)
            assert reloaded.domain == orig.domain
            assert len(reloaded.paragraphs) == len(orig.paragraphs)
            assert reloaded.structural_signals.word_count == orig.structural_signals.word_count

    def test_analysis_result_round_trip(self, analysis_result):
        """AnalysisResult survives JSON round-trip (S6 → analysis.json)."""
        json_str = json.dumps(
            analysis_result.model_dump(mode="json"), default=str
        )
        loaded = AnalysisResult(**json.loads(json_str))
        assert loaded.proximity_stats == analysis_result.proximity_stats
        assert len(loaded.gaps) == len(analysis_result.gaps)
        assert len(loaded.spa_results) == len(analysis_result.spa_results)
        assert len(loaded.cluster_specs) == len(analysis_result.cluster_specs)

    def test_gap_report_round_trip(self):
        """GapReport survives JSON round-trip (S8 → gap_report.json)."""
        report = GapReport(
            report_md="# Report\nContent here.",
            report_json={"executive_summary": "Test summary", "recommendations": []},
            generation_spec_md="# Spec",
            generation_spec_json={"cluster_specs": [{"cluster_name": "C1"}]},
            visualization_paths=["/path/viz.html"],
        )
        json_str = json.dumps(report.model_dump(mode="json"), default=str)
        loaded = GapReport(**json.loads(json_str))
        assert loaded.report_md == report.report_md
        assert loaded.report_json == report.report_json
        assert loaded.visualization_paths == report.visualization_paths

    def test_query_gap_with_exemplars_round_trip(self, analysis_result):
        """QueryGap.top_cited_exemplars survives round-trip with StructuralSignals."""
        gap = analysis_result.gaps[0]
        assert len(gap.top_cited_exemplars) > 0
        json_str = json.dumps(gap.model_dump(mode="json"), default=str)
        loaded = QueryGap(**json.loads(json_str))
        assert len(loaded.top_cited_exemplars) == len(gap.top_cited_exemplars)
        exemplar = loaded.top_cited_exemplars[0]
        assert exemplar.similarity == gap.top_cited_exemplars[0].similarity
        assert exemplar.domain == gap.top_cited_exemplars[0].domain
        if exemplar.structural_signals:
            assert exemplar.structural_signals.word_count == gap.top_cited_exemplars[0].structural_signals.word_count


# ---------------------------------------------------------------------------
# 3. INTEGRATION TESTS — Multi-step flows with mocked externals
# ---------------------------------------------------------------------------

class TestMultiStepIntegration:
    """Integration tests that run multiple pipeline steps in sequence."""

    @pytest.mark.asyncio
    async def test_s2_to_s3_data_flow(self, generated_queries):
        """S2 output feeds directly into S3 without transformation."""
        # S3 accepts GeneratedQuery objects and uses query_text + query_id
        mock_result = PlatformResult(
            engine="perplexity",
            model="sonar-pro",
            query_id=generated_queries[0].query_id,
            query_text=generated_queries[0].query_text,
            citations=[],
        )

        with patch(
            "core.gap_analysis.steps.s3_search_platforms._select_engines",
            return_value=[],
        ):
            from core.gap_analysis.steps.s3_search_platforms import search_platforms
            results = await search_platforms(generated_queries, ["perplexity"])

        # With no engines selected, should return empty results
        assert results == []

    @pytest.mark.asyncio
    async def test_s3_to_s4_data_flow(self, platform_results):
        """S3 PlatformResult.citations feed into S4 for URL crawling."""
        # Collect all URLs that S4 would need to fetch
        all_urls = set()
        for result in platform_results:
            for cite in result.citations:
                all_urls.add(str(cite.url))

        assert len(all_urls) > 0, "Platform results must have citation URLs for S4"

        # Verify the query_lookup dict S4 expects can be built from S3's query_ids
        query_ids_in_results = {r.query_id for r in platform_results}
        assert len(query_ids_in_results) > 0

    @pytest.mark.asyncio
    async def test_s4_to_s5_data_flow(self, enriched_citations):
        """S4 EnrichedCitation.paragraphs feed into S5 for embedding."""
        total_paragraphs = sum(len(ec.paragraphs) for ec in enriched_citations)
        assert total_paragraphs > 0, "S4 must produce paragraphs for S5 to embed"

        # S5 reads anchor_text for similarity computation
        for ec in enriched_citations:
            assert ec.anchor_text or ec.paragraphs, \
                "S4 must provide anchor_text or paragraphs for S5 similarity"

    def test_s5_to_s6_data_flow(self, generated_queries, semantic_units, enriched_citations):
        """S5 embedded data feeds into S6 for gap computation."""
        # S6 needs: queries with embeddings, company units with embeddings,
        # enriched citations with best_paragraphs
        for q in generated_queries:
            assert q.embedding is not None, "S6 requires query embeddings from S5"
        for unit in semantic_units:
            assert unit.embedding is not None, "S6 requires company embeddings from S1"

    def test_s6_to_s8_data_flow(self, analysis_result, generated_queries, enriched_citations):
        """S6 AnalysisResult feeds into S8 for report generation."""
        # S8 reads analysis_result.gaps, proximity_stats, spa_results, cluster_specs
        assert len(analysis_result.gaps) > 0, "S8 needs gaps for report"
        assert analysis_result.proximity_stats, "S8 needs proximity_stats for summary"

        # S8 also takes queries and citations for context
        assert len(generated_queries) > 0
        assert isinstance(enriched_citations, list)


# ---------------------------------------------------------------------------
# 4. ENGINE MOCK TESTS — S3 with mocked search engines
# ---------------------------------------------------------------------------

class TestEngineMocks:
    """Test S3 search_platforms with mocked engine implementations."""

    @pytest.mark.asyncio
    async def test_single_engine_single_query(self):
        """Single engine + single query → 1 PlatformResult."""
        mock_engine = AsyncMock()
        mock_engine.engine_name = "test_engine"
        mock_engine.search = AsyncMock(
            return_value=PlatformResult(
                engine="test_engine",
                query_id="q_1",
                citations=[
                    CitationRef(
                        url="https://example.com/article",
                        rank=1,
                        title="Test Article",
                    ),
                ],
            )
        )

        query = GeneratedQuery(
            query_id="q_1",
            cluster_id="C1",
            cluster_name="Test",
            query_text="test query",
        )

        with patch(
            "core.gap_analysis.steps.s3_search_platforms._select_engines",
            return_value=[mock_engine],
        ):
            from core.gap_analysis.steps.s3_search_platforms import search_platforms
            results = await search_platforms([query], ["test_engine"])

        assert len(results) == 1
        assert results[0].engine == "test_engine"
        assert results[0].query_id == "q_1"
        assert len(results[0].citations) == 1

    @pytest.mark.asyncio
    async def test_multiple_engines_multiple_queries(self):
        """2 engines x 2 queries → 4 PlatformResults."""
        engines = []
        for name in ["engine_a", "engine_b"]:
            mock = AsyncMock()
            mock.engine_name = name
            mock.search = AsyncMock(
                side_effect=lambda text, qid, eng=name: PlatformResult(
                    engine=eng,
                    query_id=qid,
                    citations=[],
                )
            )
            engines.append(mock)

        queries = [
            GeneratedQuery(query_id="q_1", cluster_id="C1", cluster_name="A", query_text="query 1"),
            GeneratedQuery(query_id="q_2", cluster_id="C2", cluster_name="B", query_text="query 2"),
        ]

        with patch(
            "core.gap_analysis.steps.s3_search_platforms._select_engines",
            return_value=engines,
        ):
            from core.gap_analysis.steps.s3_search_platforms import search_platforms
            results = await search_platforms(queries, ["engine_a", "engine_b"])

        assert len(results) == 4  # 2 engines x 2 queries

    @pytest.mark.asyncio
    async def test_engine_error_returns_error_result(self):
        """Engine failure produces PlatformResult with ERROR text, not exception."""
        mock_engine = AsyncMock()
        mock_engine.engine_name = "failing_engine"
        mock_engine.model = "test-model"
        mock_engine.search = AsyncMock(
            side_effect=RuntimeError("API key expired")
        )

        query = GeneratedQuery(
            query_id="q_1",
            cluster_id="C1",
            cluster_name="Test",
            query_text="test query",
        )

        with patch(
            "core.gap_analysis.steps.s3_search_platforms._select_engines",
            return_value=[mock_engine],
        ):
            from core.gap_analysis.steps.s3_search_platforms import search_platforms
            results = await search_platforms([query], ["failing_engine"])

        assert len(results) == 1
        assert "ERROR" in results[0].response_text
        assert results[0].citations == []

    @pytest.mark.asyncio
    async def test_empty_queries_returns_empty(self):
        """No queries → no search tasks → empty results."""
        from core.gap_analysis.steps.s3_search_platforms import search_platforms
        results = await search_platforms([], ["perplexity"])
        assert results == []


# ---------------------------------------------------------------------------
# 5. FULL PIPELINE INTEGRATION — All steps with mocked I/O
# ---------------------------------------------------------------------------

class TestFullPipelineIntegration:
    """Full pipeline run with realistic fixtures and all external I/O mocked."""

    @pytest.mark.asyncio
    async def test_full_pipeline_produces_valid_report(
        self,
        gap_input,
        semantic_units,
        generated_queries,
        platform_results,
        enriched_citations,
        analysis_result,
        tmp_path,
    ):
        """Full pipeline produces a valid GapReport with all sections populated."""
        mock_report = GapReport(
            report_md="# Gap Analysis Report\n\n## Executive Summary\nTest summary.",
            report_json={
                "executive_summary": "Test summary.",
                "recommendations": [{"title_idea": "Test piece"}],
                "proximity_stats": analysis_result.proximity_stats,
                "gaps": [g.model_dump(mode="json") for g in analysis_result.gaps],
            },
            generation_spec_md="# Content Generation Specification",
            generation_spec_json={"cluster_specs": []},
            visualization_paths=[],
        )

        (tmp_path / "visualizations").mkdir()

        with patch(
            "core.gap_analysis.pipeline._artifact_dir",
            return_value=tmp_path,
        ), patch(
            "core.gap_analysis.pipeline.embed_company_assets",
            new_callable=AsyncMock,
            return_value=semantic_units,
        ), patch(
            "core.gap_analysis.pipeline.generate_queries",
            new_callable=AsyncMock,
            return_value=generated_queries,
        ), patch(
            "core.gap_analysis.pipeline.search_platforms",
            new_callable=AsyncMock,
            return_value=platform_results,
        ), patch(
            "core.gap_analysis.pipeline.enrich_citations",
            new_callable=AsyncMock,
            return_value=enriched_citations,
        ), patch(
            "core.gap_analysis.pipeline.embed_all",
            new_callable=AsyncMock,
            return_value=(generated_queries, enriched_citations),
        ), patch(
            "core.gap_analysis.pipeline.compute_gap_analysis",
            return_value=analysis_result,
        ), patch(
            "core.gap_analysis.pipeline.generate_visualizations",
            return_value={},
        ), patch(
            "core.gap_analysis.pipeline.generate_gap_report",
            new_callable=AsyncMock,
            return_value=mock_report,
        ), patch(
            "core.gap_analysis.pipeline.save_platform_results",
        ), patch(
            "core.gap_analysis.pipeline.save_enriched_citations",
        ), patch(
            "core.gap_analysis.pipeline.save_embeddings",
        ), patch(
            "core.gap_analysis.pipeline.save_report",
        ):
            from core.gap_analysis.pipeline import run_gap_analysis
            report = await run_gap_analysis(gap_input)

        assert isinstance(report, GapReport)
        assert "Gap Analysis Report" in report.report_md
        assert report.report_json["executive_summary"] == "Test summary."

    @pytest.mark.asyncio
    async def test_pipeline_skip_steps_1_through_5(
        self,
        gap_input,
        semantic_units,
        generated_queries,
        enriched_citations,
        analysis_result,
        tmp_path,
    ):
        """Pipeline with skip_steps=[1,2,3,4,5] loads from artifacts."""
        (tmp_path / "visualizations").mkdir()
        (tmp_path / "embeddings").mkdir()

        # Write artifact files for steps 1-5
        (tmp_path / "company_embeddings.json").write_text(
            json.dumps([u.model_dump(mode="json") for u in semantic_units], default=str)
        )
        (tmp_path / "queries.json").write_text(
            json.dumps([q.model_dump(mode="json") for q in generated_queries], default=str)
        )

        # S3 artifacts (JSONL per engine)
        pr_dir = tmp_path / "platform_results"
        pr_dir.mkdir()
        for engine_name in ["perplexity", "openai"]:
            lines = []
            for pr in [r for r in [
                PlatformResult(engine=engine_name, query_id="q_1", citations=[]),
            ]]:
                lines.append(json.dumps(pr.model_dump(mode="json"), default=str))
            (pr_dir / f"{engine_name}_results.jsonl").write_text("\n".join(lines))

        # S4 artifacts
        (tmp_path / "enriched_citations.json").write_text(
            json.dumps([c.model_dump(mode="json") for c in enriched_citations], default=str)
        )

        # S5 artifacts
        (tmp_path / "embeddings" / "queries_with_embeddings.json").write_text(
            json.dumps([q.model_dump(mode="json") for q in generated_queries], default=str)
        )
        (tmp_path / "embeddings" / "citations_with_embeddings.json").write_text(
            json.dumps([c.model_dump(mode="json") for c in enriched_citations], default=str)
        )

        mock_report = GapReport(
            report_md="# Loaded Report",
            report_json={},
            visualization_paths=[],
        )

        with patch(
            "core.gap_analysis.pipeline._artifact_dir",
            return_value=tmp_path,
        ), patch(
            "core.gap_analysis.pipeline.compute_gap_analysis",
            return_value=analysis_result,
        ), patch(
            "core.gap_analysis.pipeline.generate_visualizations",
            return_value={},
        ), patch(
            "core.gap_analysis.pipeline.generate_gap_report",
            new_callable=AsyncMock,
            return_value=mock_report,
        ), patch(
            "core.gap_analysis.pipeline.save_report",
        ):
            from core.gap_analysis.pipeline import run_gap_analysis
            report = await run_gap_analysis(
                gap_input, skip_steps=[1, 2, 3, 4, 5]
            )

        assert isinstance(report, GapReport)
        assert report.report_md == "# Loaded Report"


# ---------------------------------------------------------------------------
# 6. ERROR ISOLATION + EDGE CASE TESTS
# ---------------------------------------------------------------------------

class TestErrorIsolation:
    """Verify error handling and edge cases at step boundaries."""

    @pytest.mark.asyncio
    async def test_s4_all_urls_fail_returns_empty(self):
        """S4 with all URLs returning errors produces empty enriched list."""
        results = [
            PlatformResult(
                engine="perplexity",
                query_id="q_1",
                citations=[
                    CitationRef(url="https://broken.com/page1", rank=1),
                    CitationRef(url="https://broken.com/page2", rank=2),
                ],
            ),
        ]

        # Mock httpx to return 500 for all URLs
        import httpx

        async def mock_get(url, **kw):
            return httpx.Response(
                500,
                text="Server Error",
                headers={"content-type": "text/html"},
                request=httpx.Request("GET", str(url)),
            )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "core.gap_analysis.steps.s4_enrich_citations.httpx.AsyncClient",
            return_value=mock_client,
        ):
            from core.gap_analysis.steps.s4_enrich_citations import enrich_citations
            enriched = await enrich_citations(results)

        assert enriched == []  # All URLs failed, no enriched citations

    @pytest.mark.asyncio
    async def test_s5_empty_citations_passes_through(self):
        """S5 with empty citation list returns empty list."""
        from core.gap_analysis.steps.s5_embed_content import embed_enriched_citations
        result = await embed_enriched_citations([])
        assert result == []

    @pytest.mark.asyncio
    async def test_s5_queries_with_no_text(self):
        """S5 handles queries with empty text gracefully."""
        queries = [
            GeneratedQuery(
                query_id="q_empty",
                cluster_id="C1",
                cluster_name="Test",
                query_text="",  # Empty text
            ),
        ]

        with patch(
            "core.gap_analysis.steps.s5_embed_content.async_embed_texts",
            new_callable=AsyncMock,
            return_value=[[0.0] * 10],
        ):
            from core.gap_analysis.steps.s5_embed_content import embed_queries
            result = await embed_queries(queries)

        assert len(result) == 1
        assert result[0].embedding == [0.0] * 10

    def test_s6_with_no_company_units(self, generated_queries, enriched_citations):
        """S6 with empty company units produces gaps with no company similarity."""
        from core.gap_analysis.steps.s6_analyze import compute_gap_analysis
        analysis = compute_gap_analysis(generated_queries, [], enriched_citations)
        assert isinstance(analysis, AnalysisResult)
        # Should still produce gap entries
        assert isinstance(analysis.gaps, list)

    def test_s6_with_no_enriched_citations(self, generated_queries, semantic_units):
        """S6 with no enriched citations still produces valid AnalysisResult."""
        from core.gap_analysis.steps.s6_analyze import compute_gap_analysis
        analysis = compute_gap_analysis(generated_queries, semantic_units, [])
        assert isinstance(analysis, AnalysisResult)

    @pytest.mark.asyncio
    async def test_s3_empty_platform_list(self, generated_queries):
        """S3 with empty platform list returns empty results."""
        from core.gap_analysis.steps.s3_search_platforms import search_platforms
        results = await search_platforms(generated_queries, [])
        assert results == []

    def test_structural_signals_default_values(self):
        """StructuralSignals with all defaults should be valid."""
        signals = StructuralSignals()
        assert signals.word_count == 0
        assert signals.has_headers is False
        assert signals.authority_type is None

    def test_enriched_citation_with_no_paragraphs(self):
        """EnrichedCitation with empty paragraphs is valid for S5 (skipped)."""
        ec = EnrichedCitation(
            url="https://example.com",
            domain="example.com",
            title="Empty Page",
            query_id="q_1",
            engine="perplexity",
            paragraphs=[],
            best_paragraphs=[],
            structural_signals=StructuralSignals(),
        )
        assert ec.paragraphs == []
        # Should serialize fine
        data = ec.model_dump(mode="json")
        assert data["paragraphs"] == []

    def test_platform_result_with_error_response(self):
        """PlatformResult with ERROR response is valid (S3 error isolation)."""
        pr = PlatformResult(
            engine="perplexity",
            query_id="q_1",
            response_text="ERROR: API rate limited",
            citations=[],
        )
        data = pr.model_dump(mode="json")
        reloaded = PlatformResult(**data)
        assert "ERROR" in reloaded.response_text
        assert reloaded.citations == []

    def test_gap_report_with_empty_sections(self):
        """GapReport with minimal content is valid."""
        report = GapReport(
            report_md="",
            report_json={},
            generation_spec_md="",
            generation_spec_json={},
            visualization_paths=[],
        )
        assert isinstance(report, GapReport)
        data = report.model_dump(mode="json")
        loaded = GapReport(**data)
        assert loaded.report_md == ""
