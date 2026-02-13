from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.models.gap_analysis import GapAnalysisInput, GeneratedQuery, QueryCluster
from core.config.settings import settings

_CONTENT_ENGINE_ROOT = Path(__file__).resolve().parents[3]  # content-strategy-engine/
_DEFAULT_TAXONOMY_PATH = (
    _CONTENT_ENGINE_ROOT.parent.parent  # Deep_Presence/
    / "research"
    / "Citation_Signal_Predictor"
    / "cps_model"
    / "b2b_queries_180.json"
)

def _resolve_virtual_path(vpath: str) -> Path:
    p = (vpath or "").strip()
    if not p.startswith("/"):
        return (_CONTENT_ENGINE_ROOT / p).resolve()
    return (_CONTENT_ENGINE_ROOT / p.lstrip("/")).resolve()


def _read_text(vpath: Optional[str], max_chars: int = 200_000) -> str:
    if not vpath:
        return ""
    p = _resolve_virtual_path(vpath)
    if not p.exists():
        return f"ERROR: path not found: {vpath}"
    return p.read_text(encoding="utf-8")[:max_chars]


def _load_taxonomy(path: Optional[Path]) -> List[QueryCluster]:
    taxonomy_path = path or _DEFAULT_TAXONOMY_PATH
    if not taxonomy_path.exists():
        raise RuntimeError(f"Query taxonomy not found: {taxonomy_path}")
    data = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    clusters = data.get("clusters", [])
    return [QueryCluster(**c) for c in clusters]


def _build_prompt(
    company_context: str,
    persona_context: str,
    style_guide: str,
    clusters: List[QueryCluster],
    max_queries: int,
) -> str:
    clusters_payload = [
        {
            "cluster_id": c.cluster_id,
            "cluster_name": c.cluster_name,
            "intent": c.intent,
            "citation_behavior": c.citation_behavior,
            "buyer_stage": c.buyer_stage,
        }
        for c in clusters
    ]
    return f"""
You are an expert B2B researcher. Generate buyer queries that reflect the personas and company context.

Return JSON only, no prose. Format:
{{
  "queries": [
    {{
      "cluster_id": "C1",
      "cluster_name": "Mechanism",
      "query_text": "How does ...?",
      "buyer_stage": "Consideration",
      "persona_tag": "icp"
    }}
  ]
}}

Constraints:
- Total queries <= {max_queries}
- Cover all clusters with balanced coverage
- Each query must be unique and actionable
- Use natural language a real buyer would use

Company context:
{company_context}

Persona context:
{persona_context}

Style guide:
{style_guide}

Cluster taxonomy:
{json.dumps(clusters_payload, indent=2)}
""".strip()


def _extract_json(text: str) -> Dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise RuntimeError("LLM response did not contain JSON payload.")
    return json.loads(match.group(0))


def _call_openai(prompt: str, model: str) -> str:
    from openai import OpenAI

    api_key = settings.openai_api_key
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to .env.local to enable query generation."
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


def generate_queries(
    input_data: GapAnalysisInput,
    taxonomy_path: Optional[Path] = None,
    model: Optional[str] = None,
) -> List[GeneratedQuery]:
    clusters = _load_taxonomy(taxonomy_path)
    company_context = _read_text(input_data.company_context_path)
    persona_context = "\n\n".join(
        _read_text(p) for p in input_data.persona_paths if p
    )
    style_guide = _read_text(input_data.style_guide_path)
    prompt = _build_prompt(
        company_context=company_context,
        persona_context=persona_context,
        style_guide=style_guide,
        clusters=clusters,
        max_queries=input_data.max_queries,
    )

    model_name = model or "gpt-4o"
    response_text = _call_openai(prompt, model_name)
    payload = _extract_json(response_text)
    raw_queries = payload.get("queries", [])

    generated: List[GeneratedQuery] = []
    for index, q in enumerate(raw_queries, start=1):
        generated.append(
            GeneratedQuery(
                query_id=q.get("query_id") or f"q_{index}",
                cluster_id=q.get("cluster_id") or "",
                cluster_name=q.get("cluster_name") or "",
                query_text=q.get("query_text") or "",
                buyer_stage=q.get("buyer_stage"),
                persona_tag=q.get("persona_tag"),
            )
        )
    return generated
