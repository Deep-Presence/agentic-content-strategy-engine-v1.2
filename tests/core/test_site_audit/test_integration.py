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
            _make_finding(severity=AuditCheckSeverity.critical, finding_type="issue_a"),  # -10
            _make_finding(severity=AuditCheckSeverity.high, finding_type="issue_b"),  # -5
            _make_finding(severity=AuditCheckSeverity.medium, finding_type="issue_c"),  # -2
        ]
        score = compute_dimension_score(AuditDimension.crawlability, findings)
        assert score.score == 83.0

    def test_score_clamped_at_zero(self) -> None:
        # 15 critical findings = -150, but clamped to 0
        findings = [
            _make_finding(severity=AuditCheckSeverity.critical, finding_type=f"issue_{i}")
            for i in range(15)
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
# PAGE-NORMALISED SCORING TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestPageNormalisedScoring:
    """Tests for page-normalised penalty accumulation (T-SA-08)."""

    def test_200_page_and_2_page_comparable_scores(self) -> None:
        """Same per-page issue rate → scores within 15 points."""
        # 1 low finding per page on every page
        findings_200 = [
            _make_finding(
                severity=AuditCheckSeverity.low,
                url=f"https://example.com/page{i}",
                finding_type="missing_thing",
            )
            for i in range(200)
        ]
        findings_2 = [
            _make_finding(
                severity=AuditCheckSeverity.low,
                url=f"https://example.com/page{i}",
                finding_type="missing_thing",
            )
            for i in range(2)
        ]

        score_200 = compute_dimension_score(
            AuditDimension.crawlability, findings_200, pages_crawled=200,
        )
        score_2 = compute_dimension_score(
            AuditDimension.crawlability, findings_2, pages_crawled=2,
        )
        # Both sites: 100% pages affected, 1 low per page → penalty=1.0 → score=99
        assert abs(score_200.score - score_2.score) <= 15.0
        # In fact they should be identical
        assert score_200.score == score_2.score == 99.0

    def test_single_finding_200_page_site_minor_penalty(self) -> None:
        """1 low finding on 200 pages → score >= 95 (tiny average penalty)."""
        findings = [
            _make_finding(
                severity=AuditCheckSeverity.low,
                url="https://example.com/page1",
                finding_type="minor_issue",
            ),
        ]
        score = compute_dimension_score(
            AuditDimension.crawlability, findings, pages_crawled=200,
        )
        # penalty = 1.0 / 200 = 0.005 → score = 99.995
        assert score.score >= 95.0

    def test_all_pages_affected_full_penalty(self) -> None:
        """200/200 pages with critical → penalty = 10, score ≈ 90."""
        findings = [
            _make_finding(
                severity=AuditCheckSeverity.critical,
                url=f"https://example.com/page{i}",
                finding_type="blocked_resource",
            )
            for i in range(200)
        ]
        score = compute_dimension_score(
            AuditDimension.crawlability, findings, pages_crawled=200,
        )
        # All 200 pages have penalty 10 → mean = 10 → score = 90
        assert score.score == 90.0

    def test_zero_pages_no_crash(self) -> None:
        """pages_crawled=0 handled by max(1, ...) — no ZeroDivisionError."""
        findings = [
            _make_finding(severity=AuditCheckSeverity.critical),
        ]
        score = compute_dimension_score(
            AuditDimension.crawlability, findings, pages_crawled=0,
        )
        # Degrades gracefully to pages_crawled=1 behaviour
        assert score.score == 90.0

    def test_site_level_finding_not_divided_by_pages(self) -> None:
        """Findings with url="" apply full flat penalty regardless of page count."""
        site_finding = AuditFinding(
            finding_type="robots_blocks_all",
            dimension=AuditDimension.crawlability,
            severity=AuditCheckSeverity.critical,
            message="robots.txt blocks all bots",
            recommendation="Fix robots.txt",
            url="",  # site-level
        )
        score = compute_dimension_score(
            AuditDimension.crawlability, [site_finding], pages_crawled=200,
        )
        # Site-level penalty = 10, not divided by 200 → score = 90
        assert score.score == 90.0

    def test_mixed_severity_same_finding_type_takes_worst(self) -> None:
        """Same finding_type at low + critical on same page → uses critical penalty."""
        findings = [
            _make_finding(
                severity=AuditCheckSeverity.low,
                url="https://example.com/page1",
                finding_type="dup_issue",
            ),
            _make_finding(
                severity=AuditCheckSeverity.critical,
                url="https://example.com/page1",
                finding_type="dup_issue",
            ),
        ]
        score = compute_dimension_score(
            AuditDimension.crawlability, findings, pages_crawled=1,
        )
        # Dedup takes max(1, 10) = 10 → score = 90 (not 89)
        assert score.score == 90.0


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

    def test_contains_performance_overview(self) -> None:
        """Performance Overview appears when pages have html_bytes."""
        page = _make_page_result()
        page.html_bytes = 50_000
        page.external_script_count = 3
        page.external_css_count = 2
        page.blocking_script_count = 1
        page.blocking_css_count = 1
        result = aggregate_results(
            page_results=[page],
            ai_bot_access=AIBotAccessResult(),
            sitemap_health=SitemapHealthResult(),
        )
        md = generate_markdown_report(result)
        assert "Performance Overview" in md
        assert "Average HTML size:" in md
        assert "render-blocking" in md
        assert "external resources" in md

    def test_no_performance_overview_without_data(self) -> None:
        """No Performance Overview when html_bytes is None."""
        result = self._make_result()
        md = generate_markdown_report(result)
        assert "Performance Overview" not in md


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
                output_dir=tmp_path,
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
        assert page.schema_result.has_schema is False
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


# ═══════════════════════════════════════════════════════════════════════════
# DEGRADED PIPELINE TESTS (T-SA-09)
# ═══════════════════════════════════════════════════════════════════════════


class TestDegradedPipeline:
    """Tests for partial-step failure tracking and degraded status."""

    def _mock_discovery(self) -> Any:
        """Create a standard mock discovery for degraded tests."""
        from core.site_audit.steps.s1_discover import S1DiscoveryOutput

        html = "<html><head><title>Test</title></head><body><h1>Test</h1><p>Content here for analysis.</p></body></html>"
        return S1DiscoveryOutput(
            pages_with_html=[
                ("https://example.com/", html),
                ("https://example.com/about", html),
            ],
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

    @pytest.mark.asyncio
    async def test_s3_failure_produces_degraded_status(self) -> None:
        """When s3 (schema) fails catastrophically, status is 'degraded'."""
        with patch(
            "core.site_audit.pipeline.discover_site",
            new_callable=AsyncMock,
            return_value=self._mock_discovery(),
        ), patch(
            "core.site_audit.pipeline.detect_schema",
            side_effect=RuntimeError("Schema parser crash"),
        ):
            from core.site_audit.pipeline import run_site_audit

            result = await run_site_audit(
                SiteAuditInput(company_name="Test", domain="example.com"),
                skip_steps=[6],
            )

        assert result.status == "degraded"
        assert 3 in result.failed_steps
        assert "schema_markup" in result.degraded_dimensions

    @pytest.mark.asyncio
    async def test_s4_failure_produces_degraded_status(self) -> None:
        """When s4 (AEO) fails catastrophically, status is 'degraded'."""
        with patch(
            "core.site_audit.pipeline.discover_site",
            new_callable=AsyncMock,
            return_value=self._mock_discovery(),
        ), patch(
            "core.site_audit.pipeline.analyze_aeo_readiness",
            side_effect=RuntimeError("AEO crash"),
        ):
            from core.site_audit.pipeline import run_site_audit

            result = await run_site_audit(
                SiteAuditInput(company_name="Test", domain="example.com"),
                skip_steps=[6],
            )

        assert result.status == "degraded"
        assert 4 in result.failed_steps
        assert "extractability" in result.degraded_dimensions

    @pytest.mark.asyncio
    async def test_s3_and_s4_both_fail_degraded(self) -> None:
        """When both s3 and s4 fail, both dimensions are degraded."""
        with patch(
            "core.site_audit.pipeline.discover_site",
            new_callable=AsyncMock,
            return_value=self._mock_discovery(),
        ), patch(
            "core.site_audit.pipeline.detect_schema",
            side_effect=RuntimeError("Schema crash"),
        ), patch(
            "core.site_audit.pipeline.analyze_aeo_readiness",
            side_effect=RuntimeError("AEO crash"),
        ):
            from core.site_audit.pipeline import run_site_audit

            result = await run_site_audit(
                SiteAuditInput(company_name="Test", domain="example.com"),
                skip_steps=[6],
            )

        assert result.status == "degraded"
        assert 3 in result.failed_steps
        assert 4 in result.failed_steps
        assert "schema_markup" in result.degraded_dimensions
        assert "extractability" in result.degraded_dimensions

    @pytest.mark.asyncio
    async def test_degraded_dimension_score_is_zero(self) -> None:
        """Failed dimension scores are overridden to 0.0."""
        with patch(
            "core.site_audit.pipeline.discover_site",
            new_callable=AsyncMock,
            return_value=self._mock_discovery(),
        ), patch(
            "core.site_audit.pipeline.detect_schema",
            side_effect=RuntimeError("Schema crash"),
        ):
            from core.site_audit.pipeline import run_site_audit

            result = await run_site_audit(
                SiteAuditInput(company_name="Test", domain="example.com"),
                skip_steps=[6],
            )

        # Find the schema_markup dimension score
        schema_dim = next(
            ds for ds in result.dimension_scores
            if ds.dimension.value == "schema_markup"
        )
        assert schema_dim.score == 0.0
        assert schema_dim.weighted_score == 0.0

    @pytest.mark.asyncio
    async def test_no_failures_status_completed(self) -> None:
        """Normal run without failures → status='completed', empty failed_steps."""
        with patch(
            "core.site_audit.pipeline.discover_site",
            new_callable=AsyncMock,
            return_value=self._mock_discovery(),
        ):
            from core.site_audit.pipeline import run_site_audit

            result = await run_site_audit(
                SiteAuditInput(company_name="Test", domain="example.com"),
                skip_steps=[6],
            )

        assert result.status == "completed"
        assert result.failed_steps == []
        assert result.degraded_dimensions == []

    @pytest.mark.asyncio
    async def test_s3_per_page_resilience(self) -> None:
        """One bad page in s3 doesn't fail the whole step."""
        call_count = 0

        def _flaky_detect(html: str, url: str) -> Any:
            nonlocal call_count
            call_count += 1
            if "about" in url:
                raise ValueError("Bad HTML on about page")
            from core.site_audit.steps.s3_check_schema import detect_schema
            return detect_schema(html, url)

        with patch(
            "core.site_audit.pipeline.discover_site",
            new_callable=AsyncMock,
            return_value=self._mock_discovery(),
        ), patch(
            "core.site_audit.pipeline.detect_schema",
            side_effect=_flaky_detect,
        ):
            from core.site_audit.pipeline import run_site_audit

            result = await run_site_audit(
                SiteAuditInput(company_name="Test", domain="example.com"),
                skip_steps=[6],
            )

        # Step 3 did NOT fail as a whole — individual page failure handled
        assert result.status == "completed"
        assert 3 not in result.failed_steps
        assert call_count == 2  # Both pages attempted

    @pytest.mark.asyncio
    async def test_degraded_result_serialises_with_new_fields(self) -> None:
        """Degraded result JSON roundtrips with failed_steps/degraded_dimensions."""
        with patch(
            "core.site_audit.pipeline.discover_site",
            new_callable=AsyncMock,
            return_value=self._mock_discovery(),
        ), patch(
            "core.site_audit.pipeline.detect_schema",
            side_effect=RuntimeError("Schema crash"),
        ):
            from core.site_audit.pipeline import run_site_audit

            result = await run_site_audit(
                SiteAuditInput(company_name="Test", domain="example.com"),
                skip_steps=[6],
            )

        # Roundtrip through JSON
        data = json.loads(result.model_dump_json())
        restored = SiteAuditResult(**data)
        assert restored.status == "degraded"
        assert restored.failed_steps == [3]
        assert "schema_markup" in restored.degraded_dimensions


# ---------------------------------------------------------------------------
# Config flags wiring tests (T-SA-21)
# ---------------------------------------------------------------------------

class TestConfigFlagsWired:
    """Verify that SiteAuditInput config flags control pipeline behaviour."""

    def _mock_discovery(self) -> "S1DiscoveryOutput":
        from core.site_audit.steps.s1_discover import S1DiscoveryOutput

        return S1DiscoveryOutput(
            pages_with_html=[
                (
                    "https://example.com/",
                    "<html><head><title>Test</title></head>"
                    "<body><h1>Test</h1><p>Content here.</p>"
                    "<noscript>No JS content fallback</noscript></body></html>",
                ),
            ],
            ai_bot_access=AIBotAccessResult(
                gptbot_allowed=True,
                robots_txt_exists=True,
            ),
            crawl_depth_map={"https://example.com/": 0},
            status_code_map={"https://example.com/": 200},
            redirect_map={},
            discovered_urls={"https://example.com/"},
        )

    @pytest.mark.asyncio
    async def test_schema_validation_false_skips_s3(self) -> None:
        """check_schema_validation=False → no schema findings produced."""
        mock_disc = self._mock_discovery()

        with patch(
            "core.site_audit.pipeline.discover_site",
            new_callable=AsyncMock,
            return_value=mock_disc,
        ):
            from core.site_audit.pipeline import run_site_audit

            result = await run_site_audit(
                SiteAuditInput(
                    company_name="Test",
                    domain="example.com",
                    check_schema_validation=False,
                ),
                skip_steps=[6],
            )

        assert result.status in ("completed", "degraded")
        # No schema_result should be set on any page
        for page in result.page_results:
            assert page.schema_result is None or page.schema_result == SchemaDetectionResult()

    @pytest.mark.asyncio
    async def test_schema_validation_true_runs_s3(self) -> None:
        """check_schema_validation=True (default) → schema detection runs."""
        mock_disc = self._mock_discovery()

        with patch(
            "core.site_audit.pipeline.discover_site",
            new_callable=AsyncMock,
            return_value=mock_disc,
        ):
            from core.site_audit.pipeline import run_site_audit

            result = await run_site_audit(
                SiteAuditInput(
                    company_name="Test",
                    domain="example.com",
                    check_schema_validation=True,
                ),
                skip_steps=[6],
            )

        assert result.status in ("completed", "degraded")
        # Schema detection should have run — schema_result populated
        # (even if no schema found, the detect_schema call was made)
        assert len(result.page_results) > 0

    @pytest.mark.asyncio
    async def test_ai_bot_access_false_skips_parsing(self) -> None:
        """check_ai_bot_access=False → discover_site called with flag."""
        mock_disc = self._mock_discovery()

        with patch(
            "core.site_audit.pipeline.discover_site",
            new_callable=AsyncMock,
            return_value=mock_disc,
        ) as mock_discover:
            from core.site_audit.pipeline import run_site_audit

            await run_site_audit(
                SiteAuditInput(
                    company_name="Test",
                    domain="example.com",
                    check_ai_bot_access=False,
                ),
                skip_steps=[6],
            )

        # Verify the flag was passed through to discover_site
        mock_discover.assert_called_once()
        call_kwargs = mock_discover.call_args.kwargs
        assert call_kwargs["check_ai_bot_access"] is False

    @pytest.mark.asyncio
    async def test_core_web_vitals_false_skips_ssr_check(self) -> None:
        """check_core_web_vitals=False → no possible_csr_page finding."""
        # Use HTML that would trigger CSR detection (noscript with content,
        # minimal body text)
        from core.site_audit.steps.s1_discover import S1DiscoveryOutput

        csr_html = (
            "<html><head><title>SPA App</title></head>"
            "<body><div id='root'></div>"
            "<noscript>Enable JavaScript to run this app.</noscript>"
            "</body></html>"
        )
        mock_disc = S1DiscoveryOutput(
            pages_with_html=[("https://example.com/", csr_html)],
            crawl_depth_map={"https://example.com/": 0},
            status_code_map={"https://example.com/": 200},
            redirect_map={},
            discovered_urls={"https://example.com/"},
        )

        with patch(
            "core.site_audit.pipeline.discover_site",
            new_callable=AsyncMock,
            return_value=mock_disc,
        ):
            from core.site_audit.pipeline import run_site_audit

            result = await run_site_audit(
                SiteAuditInput(
                    company_name="Test",
                    domain="example.com",
                    check_core_web_vitals=False,
                ),
                skip_steps=[6],
            )

        # No SSR/CSR performance finding should be present
        for page in result.page_results:
            ssr_findings = [
                f for f in page.findings
                if f.finding_type == "possible_csr_page"
            ]
            assert len(ssr_findings) == 0, "SSR check should be skipped when check_core_web_vitals=False"

    @pytest.mark.asyncio
    async def test_output_dir_uses_tmp_path(self, tmp_path: Path) -> None:
        """When output_dir is provided, report files go there instead of artifacts/."""
        from core.site_audit.steps.s1_discover import S1DiscoveryOutput

        mock_discovery = S1DiscoveryOutput(
            pages_with_html=[
                ("https://example.com/", "<html><head><title>Test</title></head><body><h1>Test</h1><p>Content.</p></body></html>"),
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
                output_dir=tmp_path,
            )

        assert result.status == "completed"
        # Report files should be inside tmp_path
        report_files = list(tmp_path.iterdir())
        assert len(report_files) > 0, "Report should write files to output_dir"

    @pytest.mark.asyncio
    async def test_output_dir_default_uses_artifacts(self) -> None:
        """When output_dir is None, default path is computed from effective_slug."""
        from core.site_audit.steps.s1_discover import S1DiscoveryOutput

        mock_discovery = S1DiscoveryOutput(
            pages_with_html=[
                ("https://example.com/", "<html><head><title>Test</title></head><body><h1>Test</h1><p>Content.</p></body></html>"),
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
        ), patch(
            "core.site_audit.pipeline.generate_report",
            new_callable=AsyncMock,
        ) as mock_report:
            from core.site_audit.pipeline import run_site_audit

            result = await run_site_audit(
                SiteAuditInput(
                    company_name="Test",
                    domain="example.com",
                    company_slug="test-co",
                ),
            )

        assert result.status == "completed"
        # Default path should be artifacts/site_audit/{slug}/{audit_id}
        call_args = mock_report.call_args
        report_path = call_args[0][1]
        assert "artifacts" in str(report_path)
        assert "test-co" in str(report_path)
