from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.models.gap_analysis import (
    AnalysisResult,
    ClusterContentSpec,
    EnrichedCitation,
    GapReport,
    GeneratedQuery,
    QueryGap,
)
from core.config.settings import settings


def _call_openai(prompt: str, model: str) -> str:
    from openai import OpenAI

    api_key = settings.openai_api_key
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to .env.local to enable report generation."
        )
    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        input=prompt,
    )
    return getattr(response, "output_text", None) or ""


def _extract_json(text: str) -> Dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise RuntimeError("LLM response did not contain JSON payload.")
    raw = match.group(0)
    raw = raw.replace("\r\n", "\\n").replace("\r", "\\n")
    raw = re.sub(r"[\x00-\x1f](?<![\n\t])", "", raw)
    return json.loads(raw, strict=False)


# ---------------------------------------------------------------------------
# Phase A: Programmatic report builders
# ---------------------------------------------------------------------------


def _build_gap_report_md(
    analysis: AnalysisResult,
    queries: List[GeneratedQuery],
) -> str:
    """Build gap_report.md programmatically from computed AnalysisResult."""
    lines: List[str] = []

    # Header
    lines.append("# Gap Analysis Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")

    # Summary section
    lines.append("## Summary")
    lines.append("")

    prox = analysis.proximity_stats
    spa = analysis.spa_results[0] if analysis.spa_results else None
    spa_score = f"{spa.t_stat:.3f} (p={spa.p_value:.4f}, {spa.effect})" if spa else "N/A"

    lines.append(f"- **SPA Score:** {spa_score}")
    lines.append(f"- **Mean Citation Similarity:** {prox.get('citation_similarity_mean', 0):.4f}")
    lines.append(f"- **Mean Company Similarity:** {prox.get('company_similarity_mean', 0):.4f}")
    lines.append(f"- **Median Citation Similarity:** {prox.get('citation_similarity_median', 0):.4f}")
    lines.append(f"- **Median Company Similarity:** {prox.get('company_similarity_median', 0):.4f}")

    dm = analysis.decision_metrics
    lines.append(f"- **Total Queries:** {dm.get('total_queries', 0)}")
    lines.append(f"- **Total Citations:** {dm.get('total_citations', 0)}")
    lines.append(f"- **Average Gap:** {dm.get('avg_gap', 0):.4f}")

    # Top 5 gap query IDs
    sorted_gaps = sorted(analysis.gaps, key=lambda g: g.gap or 0.0, reverse=True)
    top_5_ids = [g.query_id for g in sorted_gaps[:5]]
    lines.append(f"- **Top Gap Queries:** {', '.join(top_5_ids)}")
    lines.append("")

    # Gap Briefs (top 10)
    lines.append("## Gap Briefs (Top 10)")
    lines.append("")
    for i, gap in enumerate(sorted_gaps[:10], 1):
        lines.append(f"### {i}. {gap.query_id} — {gap.query_text}")
        lines.append("")
        lines.append(f"- **Cluster:** {gap.cluster_name or 'N/A'}")
        lines.append(f"- **Best Company Unit:** {gap.best_company_unit or 'N/A'} (sim={gap.best_company_similarity or 0:.4f})")
        if gap.best_company_unit_text:
            lines.append(f"  - *\"{gap.best_company_unit_text[:150]}...\"*")
        lines.append(f"- **Avg Citation Similarity:** {gap.avg_citation_similarity or 0:.4f}")
        lines.append(f"- **Gap:** {gap.gap or 0:.4f} ({gap.interpretation})")
        lines.append("")

        if gap.top_cited_exemplars:
            lines.append("**Top Cited Exemplars:**")
            lines.append("")
            for ex in gap.top_cited_exemplars:
                lines.append(f"- **{ex.similarity:.4f}** | `{ex.domain}` | {ex.url}")
                if ex.snippet:
                    lines.append(f"  - *\"{ex.snippet[:250]}...\"*")
                ss = ex.structural_signals
                if ss:
                    lines.append(
                        f"  - Structure: words={ss.word_count}, "
                        f"paras={ss.paragraph_count}, "
                        f"headers={ss.header_count}, "
                        f"lists={ss.list_item_count}, "
                        f"stats={ss.stat_count}, "
                        f"citations={ss.citation_count}"
                    )
                lines.append(f"  - Authority: {ex.authority_type or 'unknown'}")
            lines.append("")

    # Appendix: all queries table
    lines.append("## Appendix: All Query Gaps")
    lines.append("")
    lines.append("| Query ID | Cluster | Query Text | Gap | Interpretation |")
    lines.append("|----------|---------|------------|-----|----------------|")
    for gap in sorted_gaps:
        text = gap.query_text[:60] + "..." if len(gap.query_text) > 60 else gap.query_text
        lines.append(
            f"| {gap.query_id} | {gap.cluster_name or 'N/A'} | {text} | "
            f"{gap.gap or 0:.4f} | {gap.interpretation} |"
        )
    lines.append("")

    return "\n".join(lines)


def _build_generation_spec_md(analysis: AnalysisResult) -> str:
    """Build generation_spec.md programmatically from cluster_specs."""
    lines: List[str] = []

    lines.append("# Content Generation Specification")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")

    if not analysis.cluster_specs:
        lines.append("*No cluster specifications available — run the full pipeline to generate.*")
        return "\n".join(lines)

    # Build a lookup for centroids
    centroid_lookup: Dict[str, Any] = {}
    for c in analysis.centroids:
        if c.cluster_name:
            centroid_lookup[c.cluster_name] = c

    for spec in analysis.cluster_specs:
        lines.append(f"## Cluster: {spec.cluster_name}")
        lines.append("")
        lines.append(f"- **Cluster ID:** {spec.cluster_id or 'N/A'}")
        lines.append(f"- **Queries in Cluster:** {spec.query_count}")
        lines.append(f"- **Citations Analyzed:** {spec.total_citations_analyzed}")
        lines.append("")

        # Centroid reference
        centroid = centroid_lookup.get(spec.cluster_name)
        if centroid and centroid.distance is not None:
            lines.append(f"- **Centroid Distance (query vs citation):** {centroid.distance:.4f}")

        if spec.min_similarity_threshold is not None:
            lines.append(f"- **Min Similarity Threshold:** {spec.min_similarity_threshold:.4f}")

        wc = spec.word_count_range
        lines.append(f"- **Word Count Range:** {wc[0]}–{wc[1]}")
        lines.append("")

        # Required elements
        if spec.required_elements:
            lines.append(f"- **Required Elements:** {', '.join(spec.required_elements)}")
        else:
            lines.append("- **Required Elements:** none meet 80% threshold")
        lines.append("")

        # Authority signals
        if spec.authority_signals:
            sorted_auth = sorted(spec.authority_signals.items(), key=lambda x: x[1], reverse=True)
            auth_str = ", ".join(f"{k} ({v})" for k, v in sorted_auth)
            lines.append(f"- **Authority Signals:** {auth_str}")
        lines.append("")

        # Structural rates
        if spec.structural_rates:
            rates = spec.structural_rates
            lines.append("- **Structural Rates:**")
            for name, rate in rates.items():
                lines.append(f"  - {name}: {rate:.2f}")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Phase B: LLM generates executive summary + recommendations only
# ---------------------------------------------------------------------------


def _build_llm_summary_prompt(analysis: AnalysisResult) -> str:
    """Build a focused prompt for the LLM to produce executive summary + recommendations."""
    prox = analysis.proximity_stats
    spa = analysis.spa_results[0] if analysis.spa_results else None

    # Top 10 gaps
    sorted_gaps = sorted(analysis.gaps, key=lambda g: g.gap or 0.0, reverse=True)
    top_gaps = [
        {
            "query_id": g.query_id,
            "query_text": g.query_text,
            "cluster": g.cluster_name,
            "gap": round(g.gap or 0, 4),
            "interpretation": g.interpretation,
        }
        for g in sorted_gaps[:10]
    ]

    # Cluster specs summary
    specs_summary = [
        {
            "cluster_name": s.cluster_name,
            "query_count": s.query_count,
            "word_count_range": s.word_count_range,
            "required_elements": s.required_elements,
            "authority_signals": s.authority_signals,
        }
        for s in analysis.cluster_specs
    ]

    context = {
        "spa_score": {
            "t_stat": round(spa.t_stat, 3) if spa and spa.t_stat else None,
            "p_value": round(spa.p_value, 4) if spa and spa.p_value else None,
            "effect": spa.effect if spa else None,
        },
        "proximity_stats": prox,
        "top_10_gaps": top_gaps,
        "cluster_specs": specs_summary,
        "authority_distribution": analysis.citation_patterns.get("authority_types", {}),
    }

    return f"""You are a senior content strategist analyzing a company's citation gap in AI search results.

Given the analysis data below, produce:
1. An executive summary (4-6 sentences) of the company's current citation position — strengths, weaknesses, and overall standing relative to what AI search engines cite.
2. Top 5 prioritized content recommendations, each with:
   - A specific content piece title idea
   - Target cluster name
   - Key structural signals to match (from the cluster specs)
   - Expected impact reasoning (1-2 sentences)

Return JSON only:
{{
  "executive_summary": "...",
  "recommendations": [
    {{
      "title_idea": "...",
      "target_cluster": "...",
      "structural_signals": "...",
      "expected_impact": "..."
    }}
  ]
}}

ANALYSIS DATA:
{json.dumps(context, indent=2, default=str)}
""".strip()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def generate_gap_report(
    analysis: AnalysisResult,
    queries: List[GeneratedQuery],
    citations: List[EnrichedCitation],
    model: Optional[str] = None,
) -> GapReport:
    model_name = model or settings.gap_analysis_report_model

    # Phase A: Build reports programmatically
    report_body = _build_gap_report_md(analysis, queries)
    spec_md = _build_generation_spec_md(analysis)

    # Phase B: LLM generates executive summary + recommendations
    llm_prompt = _build_llm_summary_prompt(analysis)
    try:
        llm_response = _call_openai(llm_prompt, model_name)
        llm_payload = _extract_json(llm_response)
        executive_summary = llm_payload.get("executive_summary", "")
        recommendations = llm_payload.get("recommendations", [])
    except Exception:
        executive_summary = ""
        recommendations = []

    # Prepend LLM summary to the programmatic report
    summary_lines: List[str] = []
    if executive_summary:
        summary_lines.append("## Executive Summary")
        summary_lines.append("")
        summary_lines.append(executive_summary)
        summary_lines.append("")

    if recommendations:
        summary_lines.append("## Prioritized Content Recommendations")
        summary_lines.append("")
        for i, rec in enumerate(recommendations, 1):
            summary_lines.append(f"### {i}. {rec.get('title_idea', 'Untitled')}")
            summary_lines.append(f"- **Target Cluster:** {rec.get('target_cluster', 'N/A')}")
            summary_lines.append(f"- **Structural Signals:** {rec.get('structural_signals', 'N/A')}")
            summary_lines.append(f"- **Expected Impact:** {rec.get('expected_impact', 'N/A')}")
            summary_lines.append("")

    if summary_lines:
        summary_lines.append("---")
        summary_lines.append("")

    final_report_md = "\n".join(summary_lines) + report_body

    # Build JSON payloads
    report_json = {
        "executive_summary": executive_summary,
        "recommendations": recommendations,
        "proximity_stats": analysis.proximity_stats,
        "spa_results": [s.model_dump(mode="json") for s in analysis.spa_results],
        "gaps": [g.model_dump(mode="json") for g in sorted(analysis.gaps, key=lambda g: g.gap or 0.0, reverse=True)],
        "decision_metrics": analysis.decision_metrics,
    }
    spec_json = {
        "cluster_specs": [s.model_dump(mode="json") for s in analysis.cluster_specs],
    }

    return GapReport(
        report_md=final_report_md,
        report_json=report_json,
        generation_spec_md=spec_md,
        generation_spec_json=spec_json,
        visualization_paths=[],
    )


def save_report(report: GapReport, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    if report.report_md:
        (output_dir / "gap_report.md").write_text(report.report_md, encoding="utf-8")
    (output_dir / "gap_report.json").write_text(
        json.dumps(report.report_json, indent=2, default=str), encoding="utf-8"
    )
    if report.generation_spec_md:
        (output_dir / "generation_spec.md").write_text(
            report.generation_spec_md, encoding="utf-8"
        )
    (output_dir / "generation_spec.json").write_text(
        json.dumps(report.generation_spec_json, indent=2, default=str), encoding="utf-8"
    )
