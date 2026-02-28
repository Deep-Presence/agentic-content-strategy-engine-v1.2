"""Integration tests for the site audit pipeline (scoring, aggregation, report, pipeline).

Tests cover:
- scoring.py: dimension scoring, overall score, grading
- s5_aggregate.py: result aggregation from page results
- s6_report.py: Markdown + JSON report generation
- pipeline.py: full orchestrator with mocked s1 discovery
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from core.models.site_audit import (
    AEOReadinessResult,
    AIBotAccessResult,
    AuditCheckSeverity,
    AuditDimension,
    AuditFinding,
    DimensionScore,
    PageAuditResult,
    SchemaDetectionResult,
    SiteAuditInput,
    SiteAuditResult,
    SitemapHealthResult,
)
from core.site_audit.config import AuditConfig, DEFAULT_AUDIT_CONFIG
from core.site_audit.scoring import (
    compute_all_dimension_scores,
    compute_dimension_score,
    compute_grade,
    compute_overall_score,
)
from core.site_audit.steps.s5_aggregate import (
    _collect_all_findings,
    _compute_top_findings,
    aggregate_results,
)
from core.site_audit.steps.s6_report import (
    generate_markdown_report,
    generate_report,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_HTML_BLOG = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>How to Optimize Your Website for AI Search Engines</title>
    <meta name="description" content="Learn how to optimize your website for AI search engines like ChatGPT, Perplexity, and Claude. This comprehensive guide covers structured data, content formatting, and AEO best practices for maximum visibility.">
    <link rel="canonical" href="https://example.com/blog/optimize-for-ai">
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "How to Optimize Your Website for AI Search Engines",
        "author": {"@type": "Person", "name": "Jane Doe"},
        "datePublished": "2026-02-01",
        "dateModified": "2026-02-15"
    }
    </script>
</head>
<body>
    <article>
        <h1>How to Optimize Your Website for AI Search Engines</h1>
        <p class="byline">By Jane Doe | February 1, 2026</p>

        <h2>What is Answer Engine Optimization?</h2>
        <p>Answer Engine Optimization (AEO) is the practice of structuring your website content so that AI-powered search engines can easily extract and cite your information. Unlike traditional SEO, AEO focuses on making your content machine-readable and snippet-friendly.</p>

        <h2>Why does AEO matter for B2B companies?</h2>
        <p>B2B companies that appear in AI search results gain significant credibility. When ChatGPT or Perplexity cites your content, it serves as a powerful form of third-party validation that can influence purchasing decisions.</p>

        <h2>How to Structure Your Content</h2>
        <p>The key to AEO success is structuring your content in self-contained paragraphs that can stand alone as answer snippets. Each paragraph should address a specific question or concept completely.</p>

        <h3>Use Question Headings</h3>
        <p>Phrasing your headings as questions helps AI engines match your content to user queries. This is a simple but highly effective technique.</p>

        <h3>Add Structured Data</h3>
        <p>JSON-LD structured data helps AI engines understand the type and context of your content. Article schema, FAQ schema, and Organization schema are particularly important.</p>

        <h2>Key Takeaways</h2>
        <ul>
            <li>Structure content as self-contained answer snippets</li>
            <li>Use question-format headings</li>
            <li>Implement JSON-LD structured data</li>
            <li>Keep paragraphs between 20 and 80 words</li>
        </ul>
    </article>
</body>
</html>"""


def _make_finding(
    dimension: AuditDimension = AuditDimension.crawlability,
    severity: AuditCheckSeverity = AuditCheckSeverity.medium,
    finding_type: str = "test_finding",
    message: str = "Test finding message",
    url: str = "https://example.com/page1",
) -> AuditFinding:
    """Create a test AuditFinding."""
    return AuditFinding(
        finding_type=finding_type,
        dimension=dimension,
        severity=severity,
        message=message,
        recommendation="Fix this issue",
        url=url,
    )


def _make_page_result(
    url: str = "https://example.com/page1",
    findings: list[AuditFinding] | None = None,
    snippet_score: float = 50.0,
    question_ratio: float = 0.3,
    has_schema: bool = False,
) -> PageAuditResult:
    """Create a test PageAuditResult."""
    return PageAuditResult(
        url=url,
        status_code=200,
        title="Test Page Title",
        title_length=15,
        meta_description="A good meta description for testing purposes that is long enough.",
        meta_description_length=65,
        h1_count=1,
        word_count=500,
        findings=findings or [],
        schema=SchemaDetectionResult(has_schema=has_schema),
        aeo=AEOReadinessResult(
            snippet_readiness_score=snippet_score,
            question_heading_ratio=question_ratio,
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════
# SCORING TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestComputeDimensionScore:
    """Tests for compute_dimension_score."""

    def test_no_findings_returns_100(self) -> None:
        score = compute_dimension_score(AuditDimension.crawlability, [])
        assert score.score == 100.0
        assert score.finding_count == 0

    def test_critical_finding_deducts_10(self) -> None:
        findings = [_make_finding(severity=AuditCheckSeverity.critical)]
        score = compute_dimension_score(AuditDimension.crawlability, findings)
        assert score.score == 90.0
        assert score.critical_count == 1

    def test_high_finding_deducts_5(self) -> None:
        findings = [_make_finding(severity=AuditCheckSeverity.high)]
        score = compute_dimension_score(AuditDimension.crawlability, findings)
        assert score.score == 95.0
        assert score.high_count == 1

    def test_medium_finding_deducts_2(self) -> None:
        findings = [_make_finding(severity=AuditCheckSeverity.medium)]
        score = compute_dimension_score(AuditDimension.crawlability, findings)
        assert score.score == 98.0
        assert score.medium_count == 1

    def test_low_finding_deducts_1(self) -> None:
        findings = [_make_finding(severity=AuditCheckSeverity.low)]
        score = compute_dimension_score(AuditDimension.crawlability, findings)
        assert score.score == 99.0
        assert score.low_count == 1

    def test_info_finding_deducts_0(self) -> None:
        findings = [_make_finding(severity=AuditCheckSeverity.info)]
        score = compute_dimension_score(AuditDimension.crawlability, findings)
        assert score.score == 100.0
        assert score.info_count == 1

    def test_multiple_findings_accumulate(self) -> None:
        findings = [
            _make_finding(severity=AuditCheckSeverity.critical),  # -10
            _make_finding(severity=AuditCheckSeverity.high),  # -5
            _make_finding(severity=AuditCheckSeverity.medium),  # -2
        ]
        score = compute_dimension_score(AuditDimension.crawlability, findings)
        assert score.score == 83.0

    def test_score_clamped_at_zero(self) -> None:
        # 15 critical findings = -150, but clamped to 0
        findings = [
            _make_finding(severity=AuditCheckSeverity.critical)
            for _ in range(15)
        ]
        score = compute_dimension_score(AuditDimension.crawlability, findings)
        assert score.score == 0.0

    def test_filters_by_dimension(self) -> None:
        findings = [
            _make_finding(dimension=AuditDimension.crawlability, severity=AuditCheckSeverity.critical),
            _make_finding(dimension=AuditDimension.security, severity=AuditCheckSeverity.critical),
        ]
        score = compute_dimension_score(AuditDimension.crawlability, findings)
        assert score.score == 90.0  # Only 1 finding counted
        assert score.finding_count == 1

    def test_weighted_score_computed(self) -> None:
        score = compute_dimension_score(AuditDimension.crawlability, [])
        # crawlability weight is 0.20
        assert score.weight == 0.20
        assert score.weighted_score == 20.0

    def test_weighted_score_with_penalty(self) -> None:
        findings = [_make_finding(severity=AuditCheckSeverity.critical)]  # -10 → 90
        score = compute_dimension_score(AuditDimension.crawlability, findings)
        assert score.weighted_score == 18.0  # 90 * 0.20


class TestComputeAllDimensionScores:
    """Tests for compute_all_dimension_scores."""

    def test_returns_eight_dimensions(self) -> None:
        scores = compute_all_dimension_scores([])
        assert len(scores) == 8

    def test_all_dimensions_represented(self) -> None:
        scores = compute_all_dimension_scores([])
        dims = {s.dimension for s in scores}
        assert dims == set(AuditDimension)

    def test_no_findings_all_100(self) -> None:
        scores = compute_all_dimension_scores([])
        for s in scores:
            assert s.score == 100.0


class TestComputeOverallScore:
    """Tests for compute_overall_score."""

    def test_all_perfect_returns_100(self) -> None:
        scores = compute_all_dimension_scores([])
        overall = compute_overall_score(scores)
        assert overall == 100.0

    def test_empty_scores_returns_0(self) -> None:
        overall = compute_overall_score([])
        assert overall == 0.0

    def test_partial_penalty(self) -> None:
        findings = [
            _make_finding(
                dimension=AuditDimension.crawlability,
                severity=AuditCheckSeverity.critical,
            ),
        ]
        scores = compute_all_dimension_scores(findings)
        overall = compute_overall_score(scores)
        # crawlability: 90 * 0.20 = 18.0
        # all others: 100 * their_weight
        # total = 18.0 + (100 * 0.80) = 98.0
        assert overall == 98.0


class TestComputeGrade:
    """Tests for compute_grade."""

    def test_grade_a(self) -> None:
        assert compute_grade(95.0) == "A"

    def test_grade_b(self) -> None:
        assert compute_grade(80.0) == "B"

    def test_grade_c(self) -> None:
        assert compute_grade(65.0) == "C"

    def test_grade_d(self) -> None:
        assert compute_grade(45.0) == "D"

    def test_grade_f(self) -> None:
        assert compute_grade(30.0) == "F"

    def test_boundary_a(self) -> None:
        assert compute_grade(90.0) == "A"

    def test_boundary_b(self) -> None:
        assert compute_grade(75.0) == "B"

    def test_boundary_c(self) -> None:
        assert compute_grade(60.0) == "C"

    def test_boundary_d(self) -> None:
        assert compute_grade(40.0) == "D"

    def test_zero_is_f(self) -> None:
        assert compute_grade(0.0) == "F"

    def test_100_is_a(self) -> None:
        assert compute_grade(100.0) == "A"


# ═══════════════════════════════════════════════════════════════════════════
# AGGREGATION TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestCollectAllFindings:
    """Tests for _collect_all_findings."""

    def test_empty_pages(self) -> None:
        assert _collect_all_findings([]) == []

    def test_single_page_no_findings(self) -> None:
        page = _make_page_result(findings=[])
        assert _collect_all_findings([page]) == []

    def test_flattens_findings(self) -> None:
        f1 = _make_finding(finding_type="f1")
        f2 = _make_finding(finding_type="f2")
        f3 = _make_finding(finding_type="f3")
        pages = [
            _make_page_result(url="https://a.com", findings=[f1, f2]),
            _make_page_result(url="https://b.com", findings=[f3]),
        ]
        result = _collect_all_findings(pages)
        assert len(result) == 3


class TestComputeTopFindings:
    """Tests for _compute_top_findings."""

    def test_empty_findings(self) -> None:
        assert _compute_top_findings([]) == []

    def test_sorted_by_severity(self) -> None:
        findings = [
            _make_finding(severity=AuditCheckSeverity.low, finding_type="low1"),
            _make_finding(severity=AuditCheckSeverity.critical, finding_type="crit1"),
            _make_finding(severity=AuditCheckSeverity.medium, finding_type="med1"),
        ]
        top = _compute_top_findings(findings)
        assert top[0]["severity"] == "critical"
        assert top[1]["severity"] == "medium"
        assert top[2]["severity"] == "low"

    def test_deduplicates_by_type(self) -> None:
        findings = [
            _make_finding(severity=AuditCheckSeverity.high, finding_type="dup"),
            _make_finding(severity=AuditCheckSeverity.high, finding_type="dup"),
            _make_finding(severity=AuditCheckSeverity.high, finding_type="dup"),
        ]
        top = _compute_top_findings(findings)
        assert len(top) == 1
        assert top[0]["count"] == 3

    def test_max_count_respected(self) -> None:
        findings = [
            _make_finding(finding_type=f"type_{i}") for i in range(20)
        ]
        top = _compute_top_findings(findings, max_count=5)
        assert len(top) == 5


class TestAggregateResults:
    """Tests for aggregate_results."""

    def test_empty_pages(self) -> None:
        result = aggregate_results(
            page_results=[],
            ai_bot_access=AIBotAccessResult(),
            sitemap_health=SitemapHealthResult(),
            domain="example.com",
            audit_id="test-123",
        )
        assert result.domain == "example.com"
        assert result.audit_id == "test-123"
        assert result.pages_crawled == 0
        assert result.overall_score == 100.0  # No findings
        assert result.grade == "A"
        assert result.status == "completed"

    def test_with_findings(self) -> None:
        findings = [
            _make_finding(
                dimension=AuditDimension.security,
                severity=AuditCheckSeverity.critical,
            ),
        ]
        pages = [_make_page_result(findings=findings)]
        result = aggregate_results(
            page_results=pages,
            ai_bot_access=AIBotAccessResult(),
            sitemap_health=SitemapHealthResult(),
        )
        assert result.total_findings == 1
        assert result.findings_by_severity["critical"] == 1
        assert result.findings_by_dimension["security"] == 1
        assert result.overall_score < 100.0

    def test_aeo_stats_computed(self) -> None:
        pages = [
            _make_page_result(snippet_score=80.0, question_ratio=0.5),
            _make_page_result(snippet_score=60.0, question_ratio=0.3, url="https://example.com/p2"),
        ]
        result = aggregate_results(
            page_results=pages,
            ai_bot_access=AIBotAccessResult(),
            sitemap_health=SitemapHealthResult(),
        )
        assert result.avg_snippet_readiness == 70.0
        assert result.avg_question_heading_ratio == 0.4

    def test_schema_coverage(self) -> None:
        pages = [
            _make_page_result(has_schema=True, url="https://example.com/p1"),
            _make_page_result(has_schema=False, url="https://example.com/p2"),
            _make_page_result(has_schema=True, url="https://example.com/p3"),
        ]
        result = aggregate_results(
            page_results=pages,
            ai_bot_access=AIBotAccessResult(),
            sitemap_health=SitemapHealthResult(),
        )
        assert result.pages_with_schema == 2

    def test_dimension_scores_populated(self) -> None:
        result = aggregate_results(
            page_results=[],
            ai_bot_access=AIBotAccessResult(),
            sitemap_health=SitemapHealthResult(),
        )
        assert len(result.dimension_scores) == 8

    def test_ai_bot_access_passed_through(self) -> None:
        bot = AIBotAccessResult(gptbot_allowed=False, has_llms_txt=True)
        result = aggregate_results(
            page_results=[],
            ai_bot_access=bot,
            sitemap_health=SitemapHealthResult(),
        )
        assert result.ai_bot_access.gptbot_allowed is False
        assert result.ai_bot_access.has_llms_txt is True

    def test_sitemap_health_passed_through(self) -> None:
        sm = SitemapHealthResult(has_sitemap=True, sitemap_url_count=50)
        result = aggregate_results(
            page_results=[],
            ai_bot_access=AIBotAccessResult(),
            sitemap_health=sm,
        )
        assert result.sitemap_health.has_sitemap is True
        assert result.sitemap_health.sitemap_url_count == 50


# ═══════════════════════════════════════════════════════════════════════════
# REPORT TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestGenerateMarkdownReport:
    """Tests for generate_markdown_report."""

    def _make_result(self) -> SiteAuditResult:
        return aggregate_results(
            page_results=[
                _make_page_result(
                    snippet_score=70.0,
                    question_ratio=0.4,
                    has_schema=True,
                    findings=[
                        _make_finding(
                            dimension=AuditDimension.on_page_seo,
                            severity=AuditCheckSeverity.high,
                            finding_type="missing_title",
                            message="Page is missing a title tag",
                        ),
                    ],
                ),
            ],
            ai_bot_access=AIBotAccessResult(
                gptbot_allowed=True,
                claudebot_allowed=False,
                robots_txt_exists=True,
                has_llms_txt=True,
            ),
            sitemap_health=SitemapHealthResult(
                has_sitemap=True,
                sitemap_url_count=42,
            ),
            domain="example.com",
            audit_id="test-report",
        )

    def test_contains_domain(self) -> None:
        md = generate_markdown_report(self._make_result())
        assert "example.com" in md

    def test_contains_overall_score(self) -> None:
        md = generate_markdown_report(self._make_result())
        assert "Overall Score:" in md
        assert "/100" in md

    def test_contains_grade(self) -> None:
        md = generate_markdown_report(self._make_result())
        assert "Grade" in md

    def test_contains_dimension_table(self) -> None:
        md = generate_markdown_report(self._make_result())
        assert "Dimension Scores" in md
        assert "Crawlability" in md
        assert "Performance" in md
        assert "Security" in md

    def test_contains_ai_bot_section(self) -> None:
        md = generate_markdown_report(self._make_result())
        assert "AI Bot Access" in md
        assert "GPTBot" in md
        assert "ClaudeBot" in md
        assert "**BLOCKED**" in md  # ClaudeBot is blocked

    def test_contains_sitemap_section(self) -> None:
        md = generate_markdown_report(self._make_result())
        assert "Sitemap Health" in md
        assert "42" in md

    def test_contains_aeo_section(self) -> None:
        md = generate_markdown_report(self._make_result())
        assert "AEO Readiness" in md
        assert "snippet readiness" in md

    def test_contains_top_findings(self) -> None:
        md = generate_markdown_report(self._make_result())
        assert "Top Findings" in md
        assert "missing_title" in md or "missing a title" in md

    def test_contains_llms_txt_status(self) -> None:
        md = generate_markdown_report(self._make_result())
        assert "llms.txt" in md


class TestGenerateReport:
    """Tests for generate_report (file persistence)."""

    @pytest.mark.asyncio
    async def test_creates_output_files(self, tmp_path: Path) -> None:
        result = aggregate_results(
            page_results=[_make_page_result()],
            ai_bot_access=AIBotAccessResult(),
            sitemap_health=SitemapHealthResult(),
            domain="test.com",
            audit_id="abc123",
        )
        md_path, json_path = await generate_report(result, tmp_path)
        assert md_path.exists()
        assert json_path.exists()

    @pytest.mark.asyncio
    async def test_markdown_file_content(self, tmp_path: Path) -> None:
        result = aggregate_results(
            page_results=[_make_page_result()],
            ai_bot_access=AIBotAccessResult(),
            sitemap_health=SitemapHealthResult(),
            domain="test.com",
        )
        md_path, _ = await generate_report(result, tmp_path)
        content = md_path.read_text()
        assert "test.com" in content
        assert "Site Audit Report" in content

    @pytest.mark.asyncio
    async def test_json_file_roundtrips(self, tmp_path: Path) -> None:
        result = aggregate_results(
            page_results=[_make_page_result()],
            ai_bot_access=AIBotAccessResult(),
            sitemap_health=SitemapHealthResult(),
            domain="test.com",
            audit_id="roundtrip-test",
        )
        _, json_path = await generate_report(result, tmp_path)
        data = json.loads(json_path.read_text())
        restored = SiteAuditResult(**data)
        assert restored.audit_id == "roundtrip-test"
        assert restored.domain == "test.com"
        assert restored.pages_crawled == 1

    @pytest.mark.asyncio
    async def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        deep_path = tmp_path / "a" / "b" / "c"
        result = aggregate_results(
            page_results=[],
            ai_bot_access=AIBotAccessResult(),
            sitemap_health=SitemapHealthResult(),
        )
        md_path, json_path = await generate_report(result, deep_path)
        assert md_path.exists()
        assert json_path.exists()


# ═══════════════════════════════════════════════════════════════════════════
# PIPELINE INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestPipelineIntegration:
    """End-to-end pipeline tests with mocked s1 discovery."""

    @pytest.mark.asyncio
    async def test_full_pipeline_with_mock_discovery(self, tmp_path: Path) -> None:
        """Run the full pipeline with mocked crawling."""
        from core.site_audit.steps.s1_discover import S1DiscoveryOutput

        mock_discovery = S1DiscoveryOutput(
            pages_with_html=[
                ("https://example.com/", SAMPLE_HTML_BLOG),
                ("https://example.com/about", "<html><head><title>About Us</title></head><body><h1>About Us</h1><p>We are a company.</p></body></html>"),
            ],
            ai_bot_access=AIBotAccessResult(
                gptbot_allowed=True,
                claudebot_allowed=True,
                robots_txt_exists=True,
            ),
            sitemap_health=SitemapHealthResult(
                has_sitemap=True,
                sitemap_url_count=10,
            ),
            crawl_depth_map={
                "https://example.com/": 0,
                "https://example.com/about": 1,
            },
            status_code_map={
                "https://example.com/": 200,
                "https://example.com/about": 200,
            },
            redirect_map={},
            discovered_urls={"https://example.com/", "https://example.com/about"},
        )

        with patch(
            "core.site_audit.pipeline.discover_site",
            new_callable=AsyncMock,
            return_value=mock_discovery,
        ):
            from core.site_audit.pipeline import run_site_audit

            progress_messages: list[str] = []

            result = await run_site_audit(
                SiteAuditInput(
                    company_name="Example Corp",
                    domain="example.com",
                    company_slug="example-corp",
                ),
                on_progress=progress_messages.append,
            )

        assert result.status == "completed"
        assert result.domain == "example.com"
        assert result.pages_crawled == 2
        assert result.pages_discovered == 2
        assert result.audit_id != ""
        assert result.overall_score >= 0.0
        assert result.overall_score <= 100.0
        assert result.grade in ("A", "B", "C", "D", "F")
        assert len(result.dimension_scores) == 8
        assert result.duration_seconds > 0
        assert result.started_at is not None
        assert result.completed_at is not None

        # Progress messages emitted
        assert any("Starting" in m for m in progress_messages)
        assert any("complete" in m.lower() for m in progress_messages)

    @pytest.mark.asyncio
    async def test_pipeline_skip_steps(self) -> None:
        """Skip steps 3 and 4 (schema + AEO)."""
        from core.site_audit.steps.s1_discover import S1DiscoveryOutput

        mock_discovery = S1DiscoveryOutput(
            pages_with_html=[
                ("https://example.com/", "<html><head><title>Test</title></head><body><h1>Test</h1><p>Content here.</p></body></html>"),
            ],
            crawl_depth_map={"https://example.com/": 0},
            status_code_map={"https://example.com/": 200},
            redirect_map={},
            discovered_urls={"https://example.com/"},
        )

        with patch(
            "core.site_audit.pipeline.discover_site",
            new_callable=AsyncMock,
            return_value=mock_discovery,
        ):
            from core.site_audit.pipeline import run_site_audit

            result = await run_site_audit(
                SiteAuditInput(company_name="Test", domain="example.com"),
                skip_steps=[3, 4, 6],  # Skip schema, AEO, report
            )

        assert result.status == "completed"
        assert result.pages_crawled == 1
        # Schema and AEO should be defaults (not enriched)
        page = result.page_results[0]
        assert page.schema.has_schema is False
        assert page.aeo.snippet_readiness_score == 0.0

    @pytest.mark.asyncio
    async def test_pipeline_s1_failure_returns_failed(self) -> None:
        """If s1 discover fails, pipeline returns failed status."""
        with patch(
            "core.site_audit.pipeline.discover_site",
            new_callable=AsyncMock,
            side_effect=ConnectionError("DNS resolution failed"),
        ):
            from core.site_audit.pipeline import run_site_audit

            result = await run_site_audit(
                SiteAuditInput(company_name="Bad", domain="nonexistent.invalid"),
            )

        assert result.status == "failed"
        assert "Discovery step failed" in result.error_message
        assert result.audit_id != ""

    @pytest.mark.asyncio
    async def test_pipeline_empty_crawl(self) -> None:
        """Pipeline handles 0 pages gracefully."""
        from core.site_audit.steps.s1_discover import S1DiscoveryOutput

        mock_discovery = S1DiscoveryOutput(
            pages_with_html=[],
            discovered_urls=set(),
        )

        with patch(
            "core.site_audit.pipeline.discover_site",
            new_callable=AsyncMock,
            return_value=mock_discovery,
        ):
            from core.site_audit.pipeline import run_site_audit

            result = await run_site_audit(
                SiteAuditInput(company_name="Empty", domain="empty.com"),
                skip_steps=[6],  # Skip report writing
            )

        assert result.status == "completed"
        assert result.pages_crawled == 0
        assert result.overall_score == 100.0  # No findings = perfect

    @pytest.mark.asyncio
    async def test_pipeline_on_progress_callback(self) -> None:
        """Verify progress callback is invoked at each step."""
        from core.site_audit.steps.s1_discover import S1DiscoveryOutput

        mock_discovery = S1DiscoveryOutput(
            pages_with_html=[
                ("https://example.com/", "<html><head><title>T</title></head><body><h1>T</h1><p>Content.</p></body></html>"),
            ],
            crawl_depth_map={"https://example.com/": 0},
            status_code_map={"https://example.com/": 200},
            redirect_map={},
            discovered_urls={"https://example.com/"},
        )

        with patch(
            "core.site_audit.pipeline.discover_site",
            new_callable=AsyncMock,
            return_value=mock_discovery,
        ):
            from core.site_audit.pipeline import run_site_audit

            messages: list[str] = []
            result = await run_site_audit(
                SiteAuditInput(company_name="Prog", domain="example.com"),
                on_progress=messages.append,
                skip_steps=[6],  # Skip report to avoid file writes
            )

        assert result.status == "completed"
        # Should have progress for steps 1-5 + final
        assert len(messages) >= 6  # Starting + 5 steps + final

    @pytest.mark.asyncio
    async def test_pipeline_skip_all_steps(self) -> None:
        """Skipping all steps returns a minimal result."""
        from core.site_audit.pipeline import run_site_audit

        result = await run_site_audit(
            SiteAuditInput(company_name="Skip", domain="skip.com"),
            skip_steps=[1, 2, 3, 4, 5, 6],
        )

        assert result.status == "completed"
        assert result.pages_crawled == 0
        assert result.audit_id != ""
