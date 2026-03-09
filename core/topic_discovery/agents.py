"""Topic Discovery agents — S1 source generators, S2 merge, S3 expansion.

All agent functions are async, use litellm.acompletion() for LLM calls,
and return result objects (errors are captured, never fatal).

Statistical functions (capture-recapture, Chao1, sample coverage) are
pure Python — no LLM calls.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import litellm
except ImportError:
    litellm = None  # type: ignore[assignment]

from core.config.settings import settings
from core.models.topic_discovery import (
    BuyerStage,
    CaptureRecaptureResult,
    IntentType,
    RelevanceCell,
    SourceResult,
    SubdomainCandidate,
    SubdomainNode,
    TaxonomyTree,
    TDSource,
    TopicAssignment,
    TopicAssignmentMatrix,
    TopicDiscoveryStatus,
)
from core.topic_discovery.prompts.source_a_company import (
    build_source_a_user_prompt,
    get_source_a_system_prompt,
)
from core.topic_discovery.prompts.source_b_persona import (
    build_source_b_user_prompt,
    get_source_b_system_prompt,
)
from core.topic_discovery.prompts.source_c_sitemap import (
    build_source_c_user_prompt,
    get_source_c_system_prompt,
)
from core.topic_discovery.prompts.source_d_adversarial import (
    build_source_d_user_prompt,
    get_source_d_system_prompt,
)
from core.topic_discovery.prompts.hierarchy_construction import (
    build_hierarchy_user_prompt,
    get_hierarchy_system_prompt,
)
from core.topic_discovery.prompts.relevance_filtering import (
    build_relevance_user_prompt,
    get_relevance_system_prompt,
)
from core.topic_discovery.prompts.topic_generation import (
    build_topic_generation_user_prompt,
    get_topic_generation_system_prompt,
)

logger = logging.getLogger(__name__)

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)
_MAX_PAUSE_TURNS = 5
_EMBEDDING_BATCH_SIZE = 64


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences wrapping JSON output."""
    m = _CODE_FENCE_RE.match(text.strip())
    return m.group(1).strip() if m else text.strip()


def _extract_text_content(content: Any) -> str:
    """Normalize LiteLLM message.content into plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts).strip()
    return str(content)


def _extract_assistant_continuation_content(response: Any, fallback_text: str) -> Any:
    """Extract Anthropic-native assistant content blocks from LiteLLM response."""
    hidden = getattr(response, "_hidden_params", None)
    if isinstance(hidden, dict):
        original = hidden.get("original_response")
        if isinstance(original, list) and original:
            return original
    return fallback_text


async def _run_completion(
    *,
    model: str,
    messages: List[Dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 4096,
    timeout_s: float = 120.0,
) -> Tuple[Any, str]:
    """Run LiteLLM completion with pause_turn handling."""
    convo = list(messages)
    response: Any = None
    raw_text = ""

    for turn in range(_MAX_PAUSE_TURNS + 1):
        response = await asyncio.wait_for(
            litellm.acompletion(
                model=model,
                messages=convo,
                temperature=temperature,
                max_tokens=max_tokens,
            ),
            timeout=timeout_s,
        )
        choice = response.choices[0]
        raw_text = _extract_text_content(choice.message.content)
        finish_reason = getattr(choice, "finish_reason", None)
        if finish_reason != "pause_turn":
            return response, raw_text

        if turn >= _MAX_PAUSE_TURNS:
            logger.warning(
                "TD agent hit pause_turn limit (%d); returning partial.",
                _MAX_PAUSE_TURNS,
            )
            return response, raw_text

        assistant_content = _extract_assistant_continuation_content(response, raw_text)
        convo.append({"role": "assistant", "content": assistant_content})

    return response, raw_text


def _parse_json_response(raw_text: str) -> Any:
    """Parse JSON from LLM response, stripping code fences."""
    cleaned = _strip_code_fences(raw_text)
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# S1: Multi-Source Subdomain Generation
# ---------------------------------------------------------------------------


async def run_source_a_company_brainstorm(
    company_context: str,
    *,
    max_rounds: int = 4,
    model: Optional[str] = None,
    timeout_s: float = 120.0,
) -> SourceResult:
    """Source A: Company-perspective subdomain brainstorm (iterative expansion)."""
    model = model or settings.topic_discovery_brainstorm_model
    t0 = time.monotonic()
    all_candidates: List[SubdomainCandidate] = []
    previous_names: List[str] = []

    try:
        for round_num in range(1, max_rounds + 1):
            messages = [
                {"role": "system", "content": get_source_a_system_prompt()},
                {
                    "role": "user",
                    "content": build_source_a_user_prompt(
                        company_context,
                        round_number=round_num,
                        previous_subdomains=previous_names if round_num > 1 else None,
                    ),
                },
            ]
            _, raw_text = await _run_completion(
                model=model, messages=messages, timeout_s=timeout_s
            )
            parsed = _parse_json_response(raw_text)
            subdomains = parsed.get("subdomains", [])
            if not isinstance(subdomains, list):
                subdomains = []

            for sd in subdomains:
                if isinstance(sd, dict):
                    c = SubdomainCandidate(
                        name=sd.get("name", ""),
                        description=sd.get("description", ""),
                        source=TDSource.source_a,
                        round_number=round_num,
                        confidence=float(sd.get("confidence", 0.5)),
                    )
                    all_candidates.append(c)
                    previous_names.append(c.name)

            if not subdomains:
                break

        singletons, doubletons = _count_frequency_classes(all_candidates)
        return SourceResult(
            source=TDSource.source_a,
            candidates=all_candidates,
            total_rounds=max_rounds,
            singletons=singletons,
            doubletons=doubletons,
            execution_time_s=time.monotonic() - t0,
        )
    except Exception as exc:
        return SourceResult(
            source=TDSource.source_a,
            candidates=all_candidates,
            total_rounds=max_rounds,
            execution_time_s=time.monotonic() - t0,
            error=str(exc),
        )


async def run_source_b_persona_brainstorm(
    persona_profiles: str,
    company_context: str,
    *,
    max_rounds: int = 4,
    model: Optional[str] = None,
    timeout_s: float = 120.0,
) -> SourceResult:
    """Source B: Audience-perspective subdomain brainstorm (iterative expansion)."""
    model = model or settings.topic_discovery_brainstorm_model
    t0 = time.monotonic()
    all_candidates: List[SubdomainCandidate] = []
    previous_names: List[str] = []

    try:
        for round_num in range(1, max_rounds + 1):
            messages = [
                {"role": "system", "content": get_source_b_system_prompt()},
                {
                    "role": "user",
                    "content": build_source_b_user_prompt(
                        persona_profiles,
                        company_context,
                        round_number=round_num,
                        previous_subdomains=previous_names if round_num > 1 else None,
                    ),
                },
            ]
            _, raw_text = await _run_completion(
                model=model, messages=messages, timeout_s=timeout_s
            )
            parsed = _parse_json_response(raw_text)
            subdomains = parsed.get("subdomains", [])
            if not isinstance(subdomains, list):
                subdomains = []

            for sd in subdomains:
                if isinstance(sd, dict):
                    c = SubdomainCandidate(
                        name=sd.get("name", ""),
                        description=sd.get("description", ""),
                        source=TDSource.source_b,
                        round_number=round_num,
                        confidence=float(sd.get("confidence", 0.5)),
                    )
                    all_candidates.append(c)
                    previous_names.append(c.name)

            if not subdomains:
                break

        singletons, doubletons = _count_frequency_classes(all_candidates)
        return SourceResult(
            source=TDSource.source_b,
            candidates=all_candidates,
            total_rounds=max_rounds,
            singletons=singletons,
            doubletons=doubletons,
            execution_time_s=time.monotonic() - t0,
        )
    except Exception as exc:
        return SourceResult(
            source=TDSource.source_b,
            candidates=all_candidates,
            total_rounds=max_rounds,
            execution_time_s=time.monotonic() - t0,
            error=str(exc),
        )


async def run_source_c_competitor_sitemaps(
    sitemap_data: str,
    company_domain: str,
    *,
    model: Optional[str] = None,
    timeout_s: float = 120.0,
) -> SourceResult:
    """Source C: Extract subdomains from competitor sitemap/URL structure."""
    model = model or settings.topic_discovery_dedup_model
    t0 = time.monotonic()

    try:
        messages = [
            {"role": "system", "content": get_source_c_system_prompt()},
            {
                "role": "user",
                "content": build_source_c_user_prompt(sitemap_data, company_domain),
            },
        ]
        _, raw_text = await _run_completion(
            model=model, messages=messages, timeout_s=timeout_s
        )
        parsed = _parse_json_response(raw_text)
        subdomains = parsed.get("subdomains", [])
        if not isinstance(subdomains, list):
            subdomains = []

        candidates = []
        for sd in subdomains:
            if isinstance(sd, dict):
                candidates.append(
                    SubdomainCandidate(
                        name=sd.get("name", ""),
                        description=sd.get("description", ""),
                        source=TDSource.source_c,
                        round_number=1,
                        confidence=float(sd.get("confidence", 0.5)),
                    )
                )

        return SourceResult(
            source=TDSource.source_c,
            candidates=candidates,
            total_rounds=1,
            execution_time_s=time.monotonic() - t0,
        )
    except Exception as exc:
        return SourceResult(
            source=TDSource.source_c,
            total_rounds=1,
            execution_time_s=time.monotonic() - t0,
            error=str(exc),
        )


async def run_source_d_adversarial(
    company_context: str,
    existing_subdomains: List[str],
    *,
    specialist_lenses: Optional[List[str]] = None,
    max_rounds: int = 4,
    model: Optional[str] = None,
    timeout_s: float = 120.0,
) -> SourceResult:
    """Source D: Adversarial diversity pass using specialist lenses."""
    model = model or settings.topic_discovery_brainstorm_model
    t0 = time.monotonic()
    all_candidates: List[SubdomainCandidate] = []
    previous_names = list(existing_subdomains)

    if specialist_lenses is None:
        specialist_lenses = [
            "regulatory compliance expert",
            "enterprise procurement specialist",
            "accessibility advocate",
            "customer success advocate",
            "security & risk analyst",
        ]

    try:
        for round_num, lens in enumerate(specialist_lenses, 1):
            if round_num > max_rounds:
                break
            messages = [
                {"role": "system", "content": get_source_d_system_prompt()},
                {
                    "role": "user",
                    "content": build_source_d_user_prompt(
                        company_context,
                        lens,
                        round_number=round_num,
                        previous_subdomains=previous_names,
                    ),
                },
            ]
            _, raw_text = await _run_completion(
                model=model, messages=messages, timeout_s=timeout_s
            )
            parsed = _parse_json_response(raw_text)
            subdomains = parsed.get("subdomains", [])
            if not isinstance(subdomains, list):
                subdomains = []

            for sd in subdomains:
                if isinstance(sd, dict):
                    c = SubdomainCandidate(
                        name=sd.get("name", ""),
                        description=sd.get("description", ""),
                        source=TDSource.source_d,
                        round_number=round_num,
                        specialist_lens=lens,
                        confidence=float(sd.get("confidence", 0.5)),
                    )
                    all_candidates.append(c)
                    previous_names.append(c.name)

        singletons, doubletons = _count_frequency_classes(all_candidates)
        return SourceResult(
            source=TDSource.source_d,
            candidates=all_candidates,
            total_rounds=len(specialist_lenses),
            singletons=singletons,
            doubletons=doubletons,
            execution_time_s=time.monotonic() - t0,
        )
    except Exception as exc:
        return SourceResult(
            source=TDSource.source_d,
            candidates=all_candidates,
            total_rounds=len(specialist_lenses),
            execution_time_s=time.monotonic() - t0,
            error=str(exc),
        )


# ---------------------------------------------------------------------------
# S2: Deduplication + Hierarchy
# ---------------------------------------------------------------------------


async def deduplicate_subdomains(
    candidates: List[SubdomainCandidate],
    *,
    threshold: float = 0.85,
) -> List[SubdomainCandidate]:
    """Deduplicate subdomains via embedding cosine similarity.

    Uses text-embedding-3-small via core/shared_tools/embedding_client.
    Candidates with similarity >= threshold are merged (first occurrence kept).
    """
    if not candidates:
        return []

    from core.shared_tools.embedding_client import embed_texts

    names = [c.name for c in candidates]

    # Batch embeddings
    all_embeddings: List[List[float]] = []
    for i in range(0, len(names), _EMBEDDING_BATCH_SIZE):
        batch = names[i : i + _EMBEDDING_BATCH_SIZE]
        batch_embeddings = await asyncio.to_thread(embed_texts, batch)
        all_embeddings.extend(batch_embeddings)

    # Compute pairwise cosine similarity and mark duplicates
    n = len(candidates)
    is_duplicate = [False] * n
    for i in range(n):
        if is_duplicate[i]:
            continue
        for j in range(i + 1, n):
            if is_duplicate[j]:
                continue
            sim = _cosine_similarity(all_embeddings[i], all_embeddings[j])
            if sim >= threshold:
                is_duplicate[j] = True

    return [c for c, dup in zip(candidates, is_duplicate) if not dup]


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def run_hierarchy_construction(
    subdomains: List[str],
    company_domain: str,
    *,
    model: Optional[str] = None,
    timeout_s: float = 120.0,
) -> TaxonomyTree:
    """Organize flat subdomains into a hierarchical taxonomy tree via LLM."""
    model = model or settings.topic_discovery_brainstorm_model

    messages = [
        {"role": "system", "content": get_hierarchy_system_prompt()},
        {
            "role": "user",
            "content": build_hierarchy_user_prompt(subdomains, company_domain),
        },
    ]
    _, raw_text = await _run_completion(
        model=model, messages=messages, timeout_s=timeout_s
    )
    parsed = _parse_json_response(raw_text)

    root_nodes = _parse_hierarchy_nodes(parsed.get("taxonomy", []))
    total, max_depth = _count_tree_stats(root_nodes)

    return TaxonomyTree(
        domain_name=company_domain,
        root_nodes=root_nodes,
        total_subdomains=total,
        max_depth=max_depth,
        status=TopicDiscoveryStatus.draft,
    )


def _parse_hierarchy_nodes(
    nodes_data: List[Any], depth: int = 0
) -> List[SubdomainNode]:
    """Recursively parse hierarchy JSON into SubdomainNode list."""
    result = []
    if not isinstance(nodes_data, list):
        return result
    for i, nd in enumerate(nodes_data):
        if not isinstance(nd, dict):
            continue
        children = _parse_hierarchy_nodes(nd.get("children", []), depth + 1)
        node = SubdomainNode(
            name=nd.get("name", ""),
            description=nd.get("description", ""),
            depth=depth,
            sort_order=i,
            children=children,
            source_provenance=nd.get("source_provenance", {}),
            confidence=float(nd.get("confidence", 0.5)),
        )
        result.append(node)
    return result


def _count_tree_stats(
    nodes: List[SubdomainNode],
) -> Tuple[int, int]:
    """Count total nodes and max depth in the tree."""
    if not nodes:
        return 0, 0
    total = 0
    max_depth = 0
    for node in nodes:
        total += 1
        max_depth = max(max_depth, node.depth)
        child_total, child_depth = _count_tree_stats(node.children)
        total += child_total
        max_depth = max(max_depth, child_depth)
    return total, max_depth


# ---------------------------------------------------------------------------
# S3: Dimensionality Expansion
# ---------------------------------------------------------------------------


async def run_relevance_filtering(
    subdomain: str,
    dimensions: List[Dict[str, str]],
    company_context: str,
    *,
    model: Optional[str] = None,
    timeout_s: float = 120.0,
) -> List[Dict[str, Any]]:
    """Classify dimension combinations as relevant/marginal/irrelevant."""
    model = model or settings.topic_discovery_dedup_model

    messages = [
        {"role": "system", "content": get_relevance_system_prompt()},
        {
            "role": "user",
            "content": build_relevance_user_prompt(
                subdomain, dimensions, company_context
            ),
        },
    ]
    _, raw_text = await _run_completion(
        model=model, messages=messages, temperature=0.3, timeout_s=timeout_s
    )
    parsed = _parse_json_response(raw_text)
    results = parsed.get("classifications", [])
    if not isinstance(results, list):
        return []
    return results


async def run_topic_generation(
    subdomain: str,
    buyer_stage: str,
    intent_type: str,
    audience_segment: str,
    company_context: str,
    *,
    model: Optional[str] = None,
    timeout_s: float = 120.0,
) -> List[TopicAssignment]:
    """Generate 2-5 topic assignments for a relevant dimension cell."""
    model = model or settings.topic_discovery_brainstorm_model

    messages = [
        {"role": "system", "content": get_topic_generation_system_prompt()},
        {
            "role": "user",
            "content": build_topic_generation_user_prompt(
                subdomain, buyer_stage, intent_type, audience_segment,
                company_context,
            ),
        },
    ]
    _, raw_text = await _run_completion(
        model=model, messages=messages, timeout_s=timeout_s
    )
    parsed = _parse_json_response(raw_text)
    topics = parsed.get("topics", [])
    if not isinstance(topics, list):
        return []

    assignments = []
    for t in topics:
        if not isinstance(t, dict):
            continue
        assignments.append(
            TopicAssignment(
                subdomain_name=subdomain,
                topic_text=t.get("topic_text", t.get("title", "")),
                buyer_stage=BuyerStage(buyer_stage),
                intent_type=IntentType(intent_type),
                audience_segment=audience_segment,
                relevance=RelevanceCell.relevant,
                priority_score=float(t.get("priority_score", 0.5)),
                priority_factors=t.get("priority_factors", {}),
            )
        )
    return assignments


# ---------------------------------------------------------------------------
# Statistical Functions (pure Python)
# ---------------------------------------------------------------------------


def compute_capture_recapture(
    source_a_count: int,
    source_b_count: int,
    overlap: int,
) -> float:
    """Compute Lincoln-Petersen capture-recapture estimate.

    N̂ = (n₁ × n₂) / m  where m = overlap count.
    Returns 0.0 if overlap is 0 (undefined).
    """
    if overlap <= 0:
        return 0.0
    return (source_a_count * source_b_count) / overlap


def compute_chao1_lower_bound(
    observed: int,
    singletons: int,
    doubletons: int,
) -> float:
    """Compute Chao1 lower-bound species richness estimate.

    S_obs + (f₁² / 2f₂)  where f₁=singletons, f₂=doubletons.
    If doubletons==0, uses S_obs + f₁*(f₁-1)/2 (bias-corrected form).
    """
    if singletons == 0:
        return float(observed)
    if doubletons == 0:
        return observed + (singletons * (singletons - 1)) / 2.0
    return observed + (singletons ** 2) / (2.0 * doubletons)


def compute_sample_coverage(
    singletons: int,
    total: int,
) -> float:
    """Compute Good-Turing sample coverage estimate.

    Ĉ = 1 − (f₁ / N)  where f₁=singletons, N=total observations.
    Returns 0.0 if total is 0.
    """
    if total <= 0:
        return 0.0
    return 1.0 - (singletons / total)


def compute_all_coverage_metrics(
    source_results: List[SourceResult],
) -> CaptureRecaptureResult:
    """Compute all coverage metrics from source results.

    Performs pairwise capture-recapture across all source pairs,
    computes Chao1, and sample coverage from aggregated frequency data.
    """
    # Extract name sets per source
    source_sets: Dict[str, set[str]] = {}
    for sr in source_results:
        names = {c.name.lower().strip() for c in sr.candidates if c.name}
        source_sets[sr.source.value] = names

    # Pairwise CR estimates
    sources = list(source_sets.keys())
    pairwise: Dict[str, float] = {}
    for i in range(len(sources)):
        for j in range(i + 1, len(sources)):
            sa, sb = sources[i], sources[j]
            set_a, set_b = source_sets[sa], source_sets[sb]
            overlap = len(set_a & set_b)
            est = compute_capture_recapture(len(set_a), len(set_b), overlap)
            if est > 0:
                pairwise[f"{sa}_{sb}"] = est

    # Median estimate
    estimates = sorted(pairwise.values())
    median = 0.0
    if estimates:
        mid = len(estimates) // 2
        if len(estimates) % 2 == 0:
            median = (estimates[mid - 1] + estimates[mid]) / 2.0
        else:
            median = estimates[mid]

    # Observed unique count
    all_names: set[str] = set()
    for names in source_sets.values():
        all_names |= names
    observed = len(all_names)

    # Aggregate singletons and doubletons
    total_singletons = sum(sr.singletons for sr in source_results)
    total_doubletons = sum(sr.doubletons for sr in source_results)
    total_candidates = sum(len(sr.candidates) for sr in source_results)

    chao1 = compute_chao1_lower_bound(observed, total_singletons, total_doubletons)
    coverage = compute_sample_coverage(total_singletons, total_candidates)

    return CaptureRecaptureResult(
        pairwise_estimates=pairwise,
        median_estimate=median,
        estimate_range=[min(estimates, default=0.0), max(estimates, default=0.0)],
        chao1_lower_bound=chao1,
        sample_coverage=coverage,
        observed_count=observed,
        total_singletons=total_singletons,
        total_doubletons=total_doubletons,
        meets_target=coverage >= 0.95,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _count_frequency_classes(
    candidates: List[SubdomainCandidate],
) -> Tuple[int, int]:
    """Count singletons and doubletons from candidate names across rounds."""
    from collections import Counter

    name_counts = Counter(c.name.lower().strip() for c in candidates if c.name)
    singletons = sum(1 for v in name_counts.values() if v == 1)
    doubletons = sum(1 for v in name_counts.values() if v == 2)
    return singletons, doubletons
