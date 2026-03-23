from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from openai import AsyncOpenAI

from core.models.gap_analysis import GapAnalysisInput, GeneratedQuery, QueryCluster
from core.models.topic_discovery import TopicAssignment
from core.config.settings import settings
from core.gap_analysis.topic_cluster_map import (
    CLUSTER_NAMES,
    CLUSTER_INTENT_PATTERNS,
    get_cluster_brand_policy,
    get_cluster_mapping,
    is_excluded_combo,
)
from core.shared_tools.async_embedding_client import async_embed_texts
from core.shared_tools.tracing import log_generation

logger = logging.getLogger(__name__)

_CONTENT_ENGINE_ROOT = Path(__file__).resolve().parents[3]  # content-strategy-engine/
_DEFAULT_TAXONOMY_PATH = (
    Path(__file__).resolve().parent.parent  # core/gap_analysis/
    / "data"
    / "b2b_queries_180.json"
)


# ---------------------------------------------------------------------------
# Embedding helpers (self-contained to avoid cross-step import)
# ---------------------------------------------------------------------------


# _embed_texts replaced by async_embed_texts from shared utilities


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    a = np.array(vec_a, dtype=float)
    b = np.array(vec_b, dtype=float)
    if np.linalg.norm(a) == 0.0 or np.linalg.norm(b) == 0.0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------


def _extract_json(text: str) -> Dict[str, Any]:
    """Extract and parse JSON from LLM response text.

    Handles common LLM issues: truncated output, trailing commas,
    markdown fences, and control characters.
    """
    # Strip markdown code fences if present
    text = re.sub(r"```(?:json)?\s*", "", text)

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise RuntimeError("LLM response did not contain JSON payload.")
    raw = match.group(0)

    # Clean control characters (preserve \n and \t)
    raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw)

    # Remove trailing commas before } or ] (common LLM mistake)
    raw = re.sub(r",\s*([}\]])", r"\1", raw)

    # First attempt: parse as-is
    try:
        return json.loads(raw, strict=False)
    except json.JSONDecodeError:
        pass

    # Second attempt: repair truncated JSON by closing open brackets
    repaired = _repair_truncated_json(raw)
    try:
        return json.loads(repaired, strict=False)
    except json.JSONDecodeError as exc:
        logger.error("JSON parse failed even after repair. Error: %s", exc)
        raise RuntimeError(f"Failed to parse LLM JSON: {exc}") from exc


def _repair_truncated_json(raw: str) -> str:
    """Attempt to repair truncated JSON by closing open structures.

    When the LLM output is cut off by max_output_tokens, the JSON
    ends mid-stream. This tries to salvage the valid portion.
    """
    # Find the last complete entry (last valid }, or ])
    # Try trimming from the end to find a parseable prefix
    # Look for the last complete object in a "queries" array
    last_complete = raw.rfind("}")
    while last_complete > 0:
        candidate = raw[:last_complete + 1]
        # Count open/close braces and brackets
        open_braces = candidate.count("{") - candidate.count("}")
        open_brackets = candidate.count("[") - candidate.count("]")
        # Close them
        suffix = "]" * open_brackets + "}" * open_braces
        # Remove any trailing comma before our suffix
        candidate = re.sub(r",\s*$", "", candidate)
        try:
            return json.loads(candidate + suffix, strict=False) and (candidate + suffix)
        except (json.JSONDecodeError, TypeError):
            pass
        last_complete = raw.rfind("}", 0, last_complete)

    return raw


async def _call_openai(prompt: str, model: str) -> str:
    api_key = settings.openai_api_key
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to .env.local to enable query generation."
        )
    client = AsyncOpenAI(api_key=api_key)
    response = await client.responses.create(
        model=model,
        input=prompt,
        reasoning={"effort": "medium"},
        max_output_tokens=16384,
    )
    return getattr(response, "output_text", None) or ""


# ---------------------------------------------------------------------------
# Pass 1: Seed generation with improved prompt
# ---------------------------------------------------------------------------


_PRODUCT_CONTEXT_BLOCK = """\

SPECIFIC PRODUCT SCOPE — This gap analysis targets a single product, not the full company:
  Product name:        {product_name}
  Product domain:      {product_domain}
  Product description: {product_description}

CRITICAL INSTRUCTIONS FOR PRODUCT-SCOPED QUERIES:
- Treat this PRODUCT as the subject, not the parent company's full portfolio
- The "category" for these queries is the product's specific niche (e.g., "corporate spend \
cards" for Ramp Corporate Card, NOT "expense management software")
- Apply brand name exclusion rules to the PRODUCT category terms
- C8 (Branded Evaluation) and C2 (Boundary) queries may use the product name directly
- Generate queries that capture buyers researching THIS product's specific use case and \
competitive set, not the parent company's generic category
"""


_QUERY_GEN_PROMPT = """You are a search behavior expert for B2B buyers. Generate realistic search queries \
that a real person in this role would type into Google, Gemini, Claude, ChatGPT, or Perplexity.

PERSONA (condensed):
{persona_condensed}

COMPANY being analyzed:
- Name: {company_name}
- Domain: {company_domain}
- Category: {company_category}
- Key competitors: {competitor_names}
{product_context_block}
QUERY CLUSTER TAXONOMY:
Each cluster has an intent pattern and expected citation behavior. Your queries MUST match \
the intent and buyer stage of the cluster they belong to.

{clusters_with_citation_behavior}


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

────────────────────────────────────────────────
CRITICAL — Brand / Company Name Usage Rules:
────────────────────────────────────────────────

By default, queries must NOT contain any specific company or product brand names.
Instead, use the generic category term (e.g., "expense management software", "no-code website builder",
"cap table management tool", "sales intelligence platform", "AI video documentation tool").

Brand names are ONLY permitted in these two situations:
  1. Branded Evaluation (C8) — queries that are explicit head-to-head comparisons (e.g., "X vs Y vs Z").
  2. Boundary (C2) — ONLY when the query is specifically about a named product's known limitation
     or compliance issue (e.g., "What are Carta's limitations for international equity?").
     Generic boundary questions must stay unbranded (e.g., "What are the risks of managing equity on spreadsheets?").

All other clusters (C1, C3, C4, C5, C6, C7, C9) must use category-level language, never brand names.

This rule applies especially to Feature Verification (C9). Even though Feature Verification queries
ask about specific capabilities, they should be framed at the category level so they capture how
a real buyer researches features before narrowing to a vendor.

────────────────────────────────────────────
Per-Cluster Examples (✅ correct / ❌ avoid):
────────────────────────────────────────────

C1 — Mechanism ("How does X work?"):
  ✅ "How does automated receipt matching work in expense management?"
  ✅ "How does a visual CMS work for marketing teams without developer support?"
  ❌ "How does Ramp automate receipt matching?" (uses brand name)

C2 — Boundary ("What are limits/risks?"):
  ✅ "What are the limitations of corporate cards for startups scaling internationally?"
  ✅ "What compliance requirements apply to corporate expense management and reporting?"
  ✅ "What are Carta's limitations for managing international equity plans?" (brand OK — asking about a specific product's boundary)
  ❌ "What are Ramp's risks?" (too vague to justify branding)

C3 — Category Comparison ("How does X compare to category Y?"):
  ✅ "How does modern spend management software compare to traditional expense reporting?"
  ✅ "What's the difference between template-based website builders and visual development platforms?"
  ❌ "How does Webflow compare to custom development?" (uses brand name)

C4 — Decision Criteria ("How to choose / What to look for?"):
  ✅ "What factors should startups consider when choosing a corporate card provider?"
  ✅ "What criteria matter most when selecting a website builder for B2B SaaS?"
  ❌ "What should I consider before choosing Ramp?" (uses brand name)

C5 — Definition ("What is X?"):
  ✅ "What is spend management and why does it matter for growing companies?"
  ✅ "What does buyer intent data mean in B2B prospecting?"
  ❌ "What is Ramp?" (brand-centric definition)

C6 — Problem/Awareness ("How can I solve problem?"):
  ✅ "How can I reduce the time my team spends on expense reports?"
  ✅ "How can I create product demo videos without a video production team?"
  ❌ "How can Ramp help me reduce expense report time?" (uses brand name)

C7 — Best-of/Consideration ("Best X for Y"):
  ✅ "Best expense management software for startups in 2025"
  ✅ "Best AI tools for creating product documentation"
  ❌ "Best alternatives to Ramp for expense management" (uses brand name — that belongs in C8)

C8 — Branded Evaluation ("X vs Y vs Z"):
  ✅ "Ramp vs Brex vs Divvy comparison" (brand names required here)
  ✅ "Webflow vs Squarespace vs Wix for business websites"
  ✅ "Apollo alternatives for B2B prospecting"
  ❌ "How does expense management software compare?" (too generic — that belongs in C3)

C9 — Feature Verification ("Does X have Y?"):
  ✅ "Does expense management software typically integrate with QuickBooks and NetSuite?"
  ✅ "Can no-code website builders handle e-commerce and online stores?"
  ✅ "Do cap table management tools support international employees and global equity?"
  ✅ "Can AI documentation tools generate written guides from screen recordings?"
  ✅ "Do sales intelligence platforms provide verified mobile phone numbers?"
  ✅ "Does spend management software offer virtual cards for employee spending?"
  ❌ "Does Ramp integrate with QuickBooks and NetSuite?" (uses brand name)
  ❌ "Does Webflow support custom code?" (uses brand name)
  ❌ "Can Carta model waterfall scenarios?" (uses brand name)

The rationale for C9: Real buyers often search for feature capabilities at the category level first
("Can expense software integrate with NetSuite?") before narrowing to a specific vendor.
Category-level feature queries also surface more diverse citations (comparison articles, buyer guides,
feature roundups) rather than just one vendor's help docs.

Do Not Include or Use Emojies in your response.
────────────────────────────────────────────
"""


def _build_seed_prompt(
    company_context: str,
    persona_context: str,
    clusters: List[QueryCluster],
    max_queries: int,
    company_name: str,
    company_domain: Optional[str],
    product_context: Optional[str] = None,
) -> str:
    """Build the improved seed generation prompt.

    When ``product_context`` is provided (non-empty), it is injected between the
    COMPANY section and QUERY CLUSTER TAXONOMY. For company-level runs it is ``""``
    so the prompt is identical to before — no drift.
    """
    clusters_payload = []
    for c in clusters:
        entry = f"- {c.cluster_id} ({c.cluster_name}): intent={c.intent or 'N/A'}, "
        entry += f"buyer_stage={c.buyer_stage or 'N/A'}"
        if c.citation_behavior:
            entry += f", citation_behavior={c.citation_behavior}"
        clusters_payload.append(entry)

    # Extract competitor names from company context (best effort)
    competitor_names = "N/A"
    if company_context:
        # Look for common patterns
        for line in company_context.split("\n"):
            lower = line.lower()
            if any(kw in lower for kw in ("competitor", "rival", "alternative", "vs")):
                competitor_names = line.strip()[:200]
                break

    category = company_domain or "B2B SaaS"

    return _QUERY_GEN_PROMPT.format(
        persona_condensed=persona_context[:3000] if persona_context else "No persona provided.",
        company_name=company_name,
        company_name_lower=company_name.lower(),
        company_domain=company_domain or "N/A",
        company_category=category,
        competitor_names=competitor_names,
        product_context_block=product_context or "",
        clusters_with_citation_behavior="\n".join(clusters_payload),
        max_queries=max_queries,
    )


# ---------------------------------------------------------------------------
# Pass 2: Semantic deduplication
# ---------------------------------------------------------------------------


async def _deduplicate_queries(
    queries: List[GeneratedQuery],
    threshold: float = 0.85,
) -> List[GeneratedQuery]:
    """Remove semantically redundant queries within each cluster."""
    if not queries:
        return queries

    # Group by cluster
    cluster_groups: Dict[str, List[GeneratedQuery]] = defaultdict(list)
    for q in queries:
        cluster_groups[q.cluster_id].append(q)

    # Embed all query texts at once using async
    all_texts = [q.query_text for q in queries]
    all_embeddings = await async_embed_texts(all_texts)

    # Map query_id -> embedding
    emb_lookup: Dict[str, List[float]] = {}
    for q, emb in zip(queries, all_embeddings):
        emb_lookup[q.query_id] = emb

    # Greedy selection per cluster
    kept: List[GeneratedQuery] = []
    for cluster_id, cluster_queries in cluster_groups.items():
        selected: List[GeneratedQuery] = []
        selected_embs: List[List[float]] = []
        for q in cluster_queries:
            emb = emb_lookup.get(q.query_id)
            if emb is None:
                continue
            if not selected_embs:
                selected.append(q)
                selected_embs.append(emb)
                continue
            max_sim = max(_cosine_similarity(emb, s) for s in selected_embs)
            if max_sim < threshold:
                selected.append(q)
                selected_embs.append(emb)
        kept.extend(selected)

    logger.info(
        "Dedup: %d queries -> %d queries (threshold=%.2f)",
        len(queries), len(kept), threshold,
    )
    return kept


# ---------------------------------------------------------------------------
# Pass 3: Coverage validation
# ---------------------------------------------------------------------------


async def _validate_coverage(
    queries: List[GeneratedQuery],
    clusters: List[QueryCluster],
    max_queries: int,
    company_context: str,
    persona_context: str,
    model: str,
    *,
    trace_span: Optional[Any] = None,
) -> List[GeneratedQuery]:
    """Ensure balanced cluster distribution; generate fill-ins for underrepresented clusters."""
    if not queries or not clusters:
        return queries

    cluster_count = len(clusters)
    min_per_cluster = max(2, max_queries // cluster_count)
    max_per_cluster = int(max_queries * 0.3)

    # Count queries per cluster
    counts: Dict[str, int] = defaultdict(int)
    for q in queries:
        counts[q.cluster_id] += 1

    # Trim overrepresented clusters
    trimmed: List[GeneratedQuery] = []
    cluster_added: Dict[str, int] = defaultdict(int)
    for q in queries:
        if cluster_added[q.cluster_id] < max_per_cluster:
            trimmed.append(q)
            cluster_added[q.cluster_id] += 1
    queries = trimmed

    # Identify underrepresented clusters
    recount: Dict[str, int] = defaultdict(int)
    for q in queries:
        recount[q.cluster_id] += 1

    underrep = []
    for c in clusters:
        current = recount.get(c.cluster_id, 0)
        if current < min_per_cluster:
            needed = min_per_cluster - current
            underrep.append((c, needed))

    if not underrep:
        logger.info("Coverage OK: all clusters have >= %d queries.", min_per_cluster)
        return queries

    # Generate targeted fill-in queries for underrepresented clusters
    logger.info(
        "Generating fill-ins for %d underrepresented clusters.", len(underrep),
    )

    fill_descriptions = []
    total_fill = 0
    for cluster, needed in underrep:
        fill_descriptions.append(
            f"- {cluster.cluster_id} ({cluster.cluster_name}): "
            f"intent={cluster.intent or 'N/A'}, "
            f"buyer_stage={cluster.buyer_stage or 'N/A'}, "
            f"need {needed} more queries"
        )
        total_fill += needed

    fill_prompt = f"""Generate exactly {total_fill} additional search queries to fill gaps in cluster coverage.

These clusters need more queries:
{chr(10).join(fill_descriptions)}

Use natural buyer language. Return JSON only: {{ "queries": [ ... ] }}
Each query needs: cluster_id, cluster_name, query_text, buyer_stage, persona_tag ("icp").

Context:
{company_context[:2000]}
{persona_context[:1000]}"""

    try:
        t0 = time.monotonic()
        response_text = await _call_openai(fill_prompt, model)
        elapsed = time.monotonic() - t0
        logger.info("S2 fill-in LLM call: model=%s, elapsed=%.1fs", model, elapsed)
        if trace_span:
            log_generation(trace_span, "s2-fill-in-generation", model, fill_prompt[:500], response_text[:500], usage=None)
        payload = _extract_json(response_text)
        raw_fill = payload.get("queries", [])
        start_idx = len(queries) + 1
        for i, q in enumerate(raw_fill, start=start_idx):
            queries.append(
                GeneratedQuery(
                    query_id=q.get("query_id") or f"q_fill_{i}",
                    cluster_id=q.get("cluster_id") or "",
                    cluster_name=q.get("cluster_name") or "",
                    query_text=q.get("query_text") or "",
                    buyer_stage=q.get("buyer_stage"),
                    persona_tag=q.get("persona_tag"),
                )
            )
    except Exception as e:
        logger.warning("Fill-in query generation failed: %s", e)

    return queries


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def generate_queries(
    input_data: GapAnalysisInput,
    taxonomy_path: Optional[Path] = None,
    model: Optional[str] = None,
    *,
    trace_span: Optional[Any] = None,
) -> List[GeneratedQuery]:
    clusters = _load_taxonomy(taxonomy_path)
    company_context = _read_text(input_data.company_context_path)
    persona_context = "\n\n".join(
        _read_text(p) for p in input_data.persona_paths if p
    )
    model_name = model or settings.gap_analysis_query_gen_model

    # Build product context block (empty string for company-level runs — no drift)
    product_context: Optional[str] = None
    if input_data.product_slug and input_data.product_name:
        product_context = _PRODUCT_CONTEXT_BLOCK.format(
            product_name=input_data.product_name,
            product_domain=input_data.domain or "N/A",
            product_description=input_data.product_description or "N/A",
        )

    # Pass 1: Seed generation with improved prompt
    prompt = _build_seed_prompt(
        company_context=company_context,
        persona_context=persona_context,
        clusters=clusters,
        max_queries=input_data.max_queries,
        company_name=input_data.company_name,
        company_domain=input_data.domain,
        product_context=product_context,
    )

    t0 = time.monotonic()
    response_text = await _call_openai(prompt, model_name)
    elapsed = time.monotonic() - t0
    logger.info("S2 seed LLM call: model=%s, elapsed=%.1fs", model_name, elapsed)
    if trace_span:
        log_generation(trace_span, "s2-seed-generation", model_name, prompt[:500], response_text[:500], usage=None)
    payload = _extract_json(response_text)
    raw_queries = payload.get("queries", [])

    generated: List[GeneratedQuery] = []
    for index, q in enumerate(raw_queries, start=1):
        generated.append(
            GeneratedQuery(
                query_id=f"q_{index}",
                cluster_id=q.get("cluster_id") or "",
                cluster_name=q.get("cluster_name") or "",
                query_text=q.get("query_text") or "",
                buyer_stage=q.get("buyer_stage"),
                persona_tag=q.get("persona_tag"),
            )
        )

    logger.info("Pass 1 (seed): generated %d queries.", len(generated))

    # Pass 2: Semantic deduplication
    generated = await _deduplicate_queries(generated, threshold=0.85)

    # Pass 3: Coverage validation
    generated = await _validate_coverage(
        queries=generated,
        clusters=clusters,
        max_queries=input_data.max_queries,
        company_context=company_context,
        persona_context=persona_context,
        model=model_name,
        trace_span=trace_span,
    )

    # Re-assign sequential query IDs
    for i, q in enumerate(generated, start=1):
        q.query_id = f"q_{i}"

    logger.info("Final query count: %d", len(generated))
    return generated


# ---------------------------------------------------------------------------
# Topic-Scoped Query Generation (TD Integration)
# ---------------------------------------------------------------------------


_TOPIC_QUERY_GEN_PROMPT = """\
You are a search behavior expert for B2B buyers. Generate realistic search queries \
that a real person in this role would type into Google, Gemini, Claude, ChatGPT, or Perplexity.

TOPIC CONTEXT:
- Topic title: {topic_text}
- Subdomain: {subdomain_name}
- Audience: {audience_segment}
- Buyer stage: {buyer_stage}
- Intent type: {intent_type}

COMPANY being analyzed:
- Name: {company_name}
- Domain: {company_domain}
{product_context_block}
COMPANY CONTEXT (condensed):
{company_context}

PERSONA CONTEXT:
{persona_context}

TARGET CLUSTERS — Generate queries ONLY for these clusters:
{cluster_instructions}

Return JSON only, no prose. Format:
{{
  "queries": [
    {{
      "cluster_id": "C1",
      "cluster_name": "Mechanism",
      "query_text": "How does ...?",
      "buyer_stage": "{buyer_stage}",
      "persona_tag": "{audience_segment}"
    }}
  ]
}}

Constraints:
- Total queries: {min_queries}-{max_queries}
- Primary clusters get 3-5 queries each; secondary clusters get 1-2 queries each
- Every query MUST be grounded in the subdomain "{subdomain_name}", NOT the company's full category
- Queries should reflect how a {audience_segment} would phrase their search
- Each query must be unique and phrased as a real buyer would type it
- Use natural language, not keyword strings

{brand_rules}

Do Not Include or Use Emojis in your response.
"""


def _build_cluster_instructions(
    primary: tuple[str, ...],
    secondary: tuple[str, ...],
) -> str:
    """Build cluster instruction block for topic-scoped prompt."""
    lines: list[str] = []
    for cid in primary:
        name = CLUSTER_NAMES.get(cid, cid)
        pattern = CLUSTER_INTENT_PATTERNS.get(cid, "")
        policy = get_cluster_brand_policy(cid)
        lines.append(
            f"  PRIMARY: {cid} ({name}) — \"{pattern}\" [brand: {policy}]"
        )
    for cid in secondary:
        name = CLUSTER_NAMES.get(cid, cid)
        pattern = CLUSTER_INTENT_PATTERNS.get(cid, "")
        policy = get_cluster_brand_policy(cid)
        lines.append(
            f"  SECONDARY: {cid} ({name}) — \"{pattern}\" [brand: {policy}]"
        )
    return "\n".join(lines)


def _build_brand_rules(
    primary: tuple[str, ...],
    secondary: tuple[str, ...],
) -> str:
    """Build brand name usage rules for target clusters."""
    all_clusters = list(primary) + list(secondary)
    has_c8 = "C8" in all_clusters
    has_c2 = "C2" in all_clusters

    lines = [
        "────────────────────────────────────────────────",
        "CRITICAL — Brand / Company Name Usage Rules:",
        "────────────────────────────────────────────────",
        "",
        "By default, queries must NOT contain any specific company or product brand names.",
        "Use generic category terms instead.",
    ]
    if has_c8:
        lines.append(
            "EXCEPTION — C8 (Branded Evaluation): Brand names are REQUIRED "
            "(e.g., \"X vs Y vs Z\", \"X alternatives\")."
        )
    if has_c2:
        lines.append(
            "EXCEPTION — C2 (Boundary): Brand names ONLY when asking about a "
            "specific product's known limitation. Generic boundary questions stay unbranded."
        )
    lines.append("────────────────────────────────────────────────")
    return "\n".join(lines)


def _build_topic_prompt(
    topic: TopicAssignment,
    primary: tuple[str, ...],
    secondary: tuple[str, ...],
    queries_range: tuple[int, int],
    company_context: str,
    persona_context: str,
    company_name: str,
    company_domain: Optional[str],
    product_context: Optional[str] = None,
) -> str:
    """Build the topic-scoped query generation prompt for a single topic."""
    return _TOPIC_QUERY_GEN_PROMPT.format(
        topic_text=topic.topic_text,
        subdomain_name=topic.subdomain_name,
        audience_segment=topic.audience_segment,
        buyer_stage=topic.buyer_stage.value,
        intent_type=topic.intent_type.value,
        company_name=company_name,
        company_domain=company_domain or "N/A",
        product_context_block=product_context or "",
        company_context=company_context[:3000],
        persona_context=persona_context[:2000] if persona_context else "No persona provided.",
        cluster_instructions=_build_cluster_instructions(primary, secondary),
        min_queries=queries_range[0],
        max_queries=queries_range[1],
        brand_rules=_build_brand_rules(primary, secondary),
    )


async def _deduplicate_queries_cross_topic(
    queries: List[GeneratedQuery],
    threshold: float = 0.85,
) -> List[GeneratedQuery]:
    """Global (cross-topic, cross-cluster) dedup with source_topic_ids merge.

    Unlike ``_deduplicate_queries`` which deduplicates within each cluster,
    this function deduplicates across the entire query set. When a duplicate
    is dropped, its ``source_topic_ids`` are merged into the surviving query.
    """
    if not queries:
        return queries

    all_texts = [q.query_text for q in queries]
    all_embeddings = await async_embed_texts(all_texts)

    # Greedy global selection
    kept: List[GeneratedQuery] = []
    kept_embs: List[List[float]] = []

    for q, emb in zip(queries, all_embeddings):
        if emb is None:
            # M4 fix: keep query even if embedding fails — it's valid, just can't dedup
            logger.warning(
                "Embedding failed for query %s — keeping without dedup check",
                q.query_id,
            )
            kept.append(q)
            continue
        if not kept_embs:
            q.embedding = emb
            kept.append(q)
            kept_embs.append(emb)
            continue

        # Find closest existing query
        max_sim = 0.0
        max_idx = -1
        for idx, s_emb in enumerate(kept_embs):
            sim = _cosine_similarity(emb, s_emb)
            if sim > max_sim:
                max_sim = sim
                max_idx = idx

        if max_sim < threshold:
            q.embedding = emb
            kept.append(q)
            kept_embs.append(emb)
        else:
            # Merge source_topic_ids and cluster metadata into the surviving query
            survivor = kept[max_idx]
            for tid in q.source_topic_ids:
                if tid not in survivor.source_topic_ids:
                    survivor.source_topic_ids.append(tid)
            # H4 fix: merge cluster_id from dropped query
            if q.cluster_id and q.cluster_id not in survivor.merged_cluster_ids:
                survivor.merged_cluster_ids.append(q.cluster_id)
            logger.debug(
                "Cross-topic dedup: dropped '%s' (sim=%.3f with '%s')",
                q.query_text[:60], max_sim, survivor.query_text[:60],
            )

    logger.info(
        "Cross-topic dedup: %d queries -> %d queries (threshold=%.2f)",
        len(queries), len(kept), threshold,
    )
    return kept


async def generate_queries_from_topics(
    topics: List[TopicAssignment],
    company_context_path: Optional[str] = None,
    persona_paths: Optional[List[str]] = None,
    company_name: str = "",
    company_domain: Optional[str] = None,
    product_name: Optional[str] = None,
    product_slug: Optional[str] = None,
    product_description: Optional[str] = None,
    model: Optional[str] = None,
    *,
    trace_span: Optional[Any] = None,
) -> List[GeneratedQuery]:
    """Generate queries from approved TopicAssignments (TD → GA bridge).

    Two-pass flow:
      Pass 1: Topic-scoped generation (LLM call per topic batch)
      Pass 2: Cross-topic semantic dedup (global, merges source_topic_ids)

    No Pass 3 (coverage validation) — only relevant clusters matter.

    Returns:
        List of GeneratedQuery with source_topic_ids set.
    """
    if not topics:
        return []

    company_context = _read_text(company_context_path)
    persona_context = "\n\n".join(
        _read_text(p) for p in (persona_paths or []) if p
    )
    model_name = model or settings.gap_analysis_query_gen_model

    # Build product context block if applicable
    product_context: Optional[str] = None
    if product_slug and product_name:
        product_context = _PRODUCT_CONTEXT_BLOCK.format(
            product_name=product_name,
            product_domain=company_domain or "N/A",
            product_description=product_description or "N/A",
        )

    # Pass 1: Topic-scoped generation
    all_queries: List[GeneratedQuery] = []
    query_counter = 0

    for topic in topics:
        stage = topic.buyer_stage.value
        intent = topic.intent_type.value

        if is_excluded_combo(stage, intent):
            logger.info(
                "Skipping excluded combo %s × %s for topic '%s'",
                stage, intent, topic.topic_text[:50],
            )
            continue

        mapping = get_cluster_mapping(stage, intent)
        if mapping is None:
            continue

        prompt = _build_topic_prompt(
            topic=topic,
            primary=mapping.primary,
            secondary=mapping.secondary,
            queries_range=mapping.queries_range,
            company_context=company_context,
            persona_context=persona_context,
            company_name=company_name,
            company_domain=company_domain,
            product_context=product_context,
        )

        try:
            t0 = time.monotonic()
            response_text = await _call_openai(prompt, model_name)
            elapsed = time.monotonic() - t0
            logger.info(
                "S2 topic-scoped LLM call: model=%s, topic='%s', elapsed=%.1fs",
                model_name, topic.topic_text[:50], elapsed,
            )
            if trace_span:
                log_generation(trace_span, "s2-topic-scoped-generation", model_name, prompt[:500], response_text[:500], usage=None)
            payload = _extract_json(response_text)
            raw_queries = payload.get("queries", [])

            for q in raw_queries:
                query_counter += 1
                cid = q.get("cluster_id") or ""
                all_queries.append(
                    GeneratedQuery(
                        query_id=f"tq_{query_counter}",
                        cluster_id=cid,
                        cluster_name=q.get("cluster_name") or "",
                        query_text=q.get("query_text") or "",
                        buyer_stage=q.get("buyer_stage") or stage,
                        persona_tag=q.get("persona_tag") or topic.audience_segment,
                        source_topic_ids=[topic.id],
                        merged_cluster_ids=[cid] if cid else [],
                    )
                )
        except Exception as e:
            logger.error(
                "Topic query generation failed for '%s': %s",
                topic.topic_text[:50], e,
            )
            continue

    logger.info("Pass 1 (topic-scoped): generated %d queries from %d topics.",
                len(all_queries), len(topics))

    if not all_queries:
        return []

    # Pass 2: Cross-topic semantic dedup
    all_queries = await _deduplicate_queries_cross_topic(
        all_queries, threshold=0.85,
    )

    # Re-assign sequential query IDs
    for i, q in enumerate(all_queries, start=1):
        q.query_id = f"tq_{i}"

    logger.info("Final topic-scoped query count: %d", len(all_queries))
    return all_queries
