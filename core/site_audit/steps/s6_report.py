"""Step 6 — Generate audit report (Markdown + JSON).

Produces a human-readable Markdown executive summary and persists the full
:class:`SiteAuditResult` as JSON.  All output is deterministic — no LLM calls.

Public API::

    await generate_report(
        result=site_audit_result,
        output_dir=Path("artifacts/site_audit/acme-corp/abc123"),
    )
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from core.models.site_audit import DimensionScore, SiteAuditResult

logger = logging.getLogger(__name__)


def _grade_emoji(grade: str) -> str:
    """Map a letter grade to a display emoji.

    Args:
        grade: Letter grade (A–F).

    Returns:
        Emoji string.
    """
    return {
        "A": "🟢",
        "B": "🔵",
        "C": "🟡",
        "D": "🟠",
        "F": "🔴",
    }.get(grade, "⚪")


def _format_dimension_row(ds: DimensionScore) -> str:
    """Format a single dimension score as a Markdown table row.

    Args:
        ds: Dimension score to format.

    Returns:
        Pipe-delimited Markdown table row string.
    """
    label = ds.dimension.value.replace("_", " ").title()
    return (
        f"| {label} | {ds.score:.0f} | {ds.weight:.0%} | "
        f"{ds.weighted_score:.1f} | {ds.finding_count} |"
    )


def generate_markdown_report(result: SiteAuditResult) -> str:
    """Generate a Markdown executive summary from the audit result.

    Sections:
        1. Overall score + grade header
        2. Dimension score table
        3. AI bot access summary
        4. Sitemap health summary
        5. AEO readiness summary
        6. Top findings (actionable recommendations)
        7. Page-level summary stats

    Args:
        result: Complete site audit result from s5_aggregate.

    Returns:
        Markdown string ready for file persistence or API response.
    """
    lines: list[str] = []
    emoji = _grade_emoji(result.grade)

    # Header
    lines.append(f"# Site Audit Report — {result.domain}")
    lines.append("")
    lines.append(
        f"**Overall Score: {result.overall_score:.0f}/100 "
        f"{emoji} Grade {result.grade}**"
    )
    lines.append("")
    lines.append(f"- Pages crawled: {result.pages_crawled}")
    lines.append(f"- Pages discovered: {result.pages_discovered}")
    lines.append(f"- Total findings: {result.total_findings}")
    if result.duration_seconds > 0:
        lines.append(f"- Duration: {result.duration_seconds:.1f}s")
    lines.append("")

    # Dimension scores table
    lines.append("## Dimension Scores")
    lines.append("")
    lines.append("| Dimension | Score | Weight | Weighted | Findings |")
    lines.append("|-----------|-------|--------|----------|----------|")
    for ds in result.dimension_scores:
        lines.append(_format_dimension_row(ds))
    lines.append("")

    # AI bot access
    lines.append("## AI Bot Access")
    lines.append("")
    bot = result.ai_bot_access
    bot_rows = [
        ("GPTBot (OpenAI)", bot.gptbot_allowed),
        ("ClaudeBot (Anthropic)", bot.claudebot_allowed),
        ("PerplexityBot", bot.perplexitybot_allowed),
        ("Google-Extended", bot.google_extended_allowed),
        ("CCBot (Common Crawl)", bot.ccbot_allowed),
    ]
    lines.append("| Bot | Allowed |")
    lines.append("|-----|---------|")
    for name, allowed in bot_rows:
        status = "Yes" if allowed else "**BLOCKED**"
        lines.append(f"| {name} | {status} |")
    lines.append("")
    lines.append(f"- robots.txt present: {'Yes' if bot.robots_txt_exists else 'No'}")
    lines.append(f"- llms.txt present: {'Yes' if bot.has_llms_txt else 'No'}")
    lines.append("")

    # Sitemap health
    lines.append("## Sitemap Health")
    lines.append("")
    sm = result.sitemap_health
    lines.append(f"- Sitemap found: {'Yes' if sm.has_sitemap else 'No'}")
    lines.append(f"- URLs in sitemap: {sm.sitemap_url_count}")
    if sm.has_sitemap_index:
        lines.append("- Sitemap index: Yes")
    if sm.sitemap_errors:
        lines.append(f"- Errors: {len(sm.sitemap_errors)}")
    lines.append("")

    # AEO readiness
    lines.append("## AEO Readiness")
    lines.append("")
    lines.append(f"- Average snippet readiness: {result.avg_snippet_readiness:.1f}/100")
    lines.append(
        f"- Pages with structured data: {result.pages_with_schema}/{result.pages_crawled}"
    )
    lines.append(
        f"- Average question heading ratio: {result.avg_question_heading_ratio:.1%}"
    )
    lines.append("")

    # Performance overview
    pages_with_data = [
        p for p in result.page_results if p.html_bytes is not None
    ]
    if pages_with_data:
        lines.append("## Performance Overview")
        lines.append("")
        avg_html_kb = (
            sum(p.html_bytes for p in pages_with_data) / len(pages_with_data) / 1024
        )
        lines.append(f"- Average HTML size: {avg_html_kb:.0f}KB")

        pages_with_blocking = sum(
            1 for p in pages_with_data
            if (p.blocking_script_count or 0) + (p.blocking_css_count or 0) > 0
        )
        lines.append(
            f"- Pages with render-blocking resources: "
            f"{pages_with_blocking}/{len(pages_with_data)}"
        )

        avg_resources = (
            sum(
                (p.external_script_count or 0) + (p.external_css_count or 0)
                for p in pages_with_data
            )
            / len(pages_with_data)
        )
        lines.append(f"- Average external resources per page: {avg_resources:.0f}")
        lines.append("")

    # Top findings
    if result.top_findings:
        lines.append("## Top Findings")
        lines.append("")
        for i, tf in enumerate(result.top_findings, 1):
            sev = tf.get("severity", "info").upper()
            msg = tf.get("message", "")
            rec = tf.get("recommendation", "")
            count = tf.get("count", 1)
            dim = tf.get("dimension", "").replace("_", " ").title()
            lines.append(f"### {i}. [{sev}] {msg}")
            lines.append("")
            lines.append(f"- **Dimension:** {dim}")
            lines.append(f"- **Affected pages:** {count}")
            if rec:
                lines.append(f"- **Recommendation:** {rec}")
            lines.append("")

    # Severity summary
    if result.findings_by_severity:
        lines.append("## Findings by Severity")
        lines.append("")
        for sev in ("critical", "high", "medium", "low", "info"):
            count = result.findings_by_severity.get(sev, 0)
            if count > 0:
                lines.append(f"- **{sev.title()}:** {count}")
        lines.append("")

    return "\n".join(lines)


async def generate_report(
    result: SiteAuditResult,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Persist the audit result as both Markdown and JSON files.

    Creates ``output_dir`` if it doesn't exist.  Files written:
        - ``report.md`` — Human-readable executive summary.
        - ``audit_result.json`` — Full machine-readable result.

    Args:
        result: Complete site audit result from s5_aggregate.
        output_dir: Directory to write report files into.

    Returns:
        Tuple of (markdown_path, json_path).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Markdown report
    md_content = generate_markdown_report(result)
    md_path = output_dir / "report.md"
    md_path.write_text(md_content, encoding="utf-8")
    logger.info("Wrote Markdown report to %s", md_path)

    # JSON result
    json_path = output_dir / "audit_result.json"
    json_content = result.model_dump(mode="json")
    json_path.write_text(
        json.dumps(json_content, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("Wrote JSON result to %s", json_path)

    return md_path, json_path
