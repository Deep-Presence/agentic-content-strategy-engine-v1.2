from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.models.gap_analysis import AnalysisResult, EnrichedCitation, GapReport, GeneratedQuery
from core.config.settings import settings


def _call_openai(prompt: str, model: str) -> str:
    from openai import OpenAI

    api_key = settings.openai_api_key
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to .env.local to enable report generation."
        )
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    if not response.choices:
        return ""
    msg = response.choices[0].message
    return getattr(msg, "content", None) or ""


def _extract_json(text: str) -> Dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise RuntimeError("LLM response did not contain JSON payload.")
    return json.loads(match.group(0))


def _build_prompt(
    analysis: AnalysisResult,
    queries: List[GeneratedQuery],
    citations: List[EnrichedCitation],
) -> str:
    gap_samples = [
        {
            "query": g.query_text,
            "cluster": g.cluster_name,
            "gap": g.gap,
            "interpretation": g.interpretation,
        }
        for g in analysis.gaps[:30]
    ]
    citations_summary = [
        {
            "url": str(c.url),
            "domain": c.domain,
            "cluster": c.cluster_name,
            "authority_type": c.structural_signals.authority_type
            if c.structural_signals
            else None,
        }
        for c in citations[:50]
    ]
    return f"""
You are an expert content strategist. Produce two deliverables:
1) Gap Analysis Report (Markdown)
2) Content Generation Spec (Markdown)

Return JSON only, no prose. Format:
{{
  "report_md": "...",
  "report_json": {{...}},
  "generation_spec_md": "...",
  "generation_spec_json": {{...}}
}}

Use the analysis and examples below. Make the report executive-friendly and actionable.

Analysis summary:
{json.dumps(analysis.model_dump(mode="json"), indent=2, default=str)}

Gap samples:
{json.dumps(gap_samples, indent=2, default=str)}

Citation examples:
{json.dumps(citations_summary, indent=2, default=str)}
""".strip()


def generate_gap_report(
    analysis: AnalysisResult,
    queries: List[GeneratedQuery],
    citations: List[EnrichedCitation],
    model: Optional[str] = None,
) -> GapReport:
    model_name = model or "gpt-4o"
    prompt = _build_prompt(analysis, queries, citations)
    response_text = _call_openai(prompt, model_name)
    payload = _extract_json(response_text)

    return GapReport(
        report_md=payload.get("report_md"),
        report_json=payload.get("report_json") or {},
        generation_spec_md=payload.get("generation_spec_md"),
        generation_spec_json=payload.get("generation_spec_json") or {},
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
