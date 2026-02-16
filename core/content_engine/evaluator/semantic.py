"""Semantic evaluator — embedding proximity check.

Embeds the content and compares cosine similarity to target query embeddings.
Reuses async_embed_texts from core/shared_tools/async_embedding_client.py.
"""
from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np

from core.config.settings import settings
from core.content_engine.tracing import create_span, end_span, log_score
from core.models.content_generation import ContentBrief, DimensionResult, FormattedContent
from core.shared_tools.async_embedding_client import async_embed_texts

logger = logging.getLogger(__name__)


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    va = np.array(a)
    vb = np.array(b)
    norm_a = np.linalg.norm(va)
    norm_b = np.linalg.norm(vb)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))


async def evaluate_semantic(
    content: FormattedContent,
    brief: ContentBrief,
    *,
    trace: Optional[object] = None,
) -> DimensionResult:
    """Evaluate semantic proximity of content to target queries.

    Embeds the content and each target query, computes average cosine
    similarity. Passes if avg similarity >= brief.semantic_threshold.

    Args:
        content: The formatted content to evaluate.
        brief: Content brief with target queries and threshold.
        trace: Langfuse trace for instrumentation.

    Returns:
        DimensionResult with semantic evaluation.
    """
    embedding_model = settings.embedding_model
    span = create_span(
        trace, "semantic_check",
        metadata={
            "brief_id": brief.brief_id,
            "model": embedding_model,
        },
        input={
            "brief_id": brief.brief_id,
            "query_count": len(brief.target_queries),
            "threshold": brief.semantic_threshold,
            "content_word_count": content.word_count,
        },
    )

    if not brief.target_queries:
        end_span(span, output="No target queries — skipping")
        return DimensionResult(
            dimension="semantic",
            passed=True,
            score=1.0,
            feedback="No target queries to compare against.",
        )

    # Collect texts to embed
    query_texts = [q.query_text for q in brief.target_queries]
    # Use first ~2000 words of content for embedding
    content_text = " ".join(content.markdown.split()[:2000])

    try:
        all_texts = query_texts + [content_text]
        embeddings = await async_embed_texts(all_texts)

        query_embeddings = embeddings[: len(query_texts)]
        content_embedding = embeddings[len(query_texts)]

        # Compute similarities
        similarities = [
            _cosine_similarity(content_embedding, qe) for qe in query_embeddings
        ]
        avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0

    except Exception as exc:
        logger.warning("Semantic evaluation failed: %s", exc)
        end_span(span, output=f"Failed: {exc}")
        return DimensionResult(
            dimension="semantic",
            passed=False,
            score=0.0,
            feedback=f"Embedding failed: {exc}",
        )

    threshold = brief.semantic_threshold
    passed = avg_similarity >= threshold

    feedback = ""
    if not passed:
        feedback = (
            f"Semantic similarity {avg_similarity:.3f} is below threshold {threshold}. "
            "Content may not address the target queries closely enough."
        )

    log_score(trace, "semantic_similarity", round(avg_similarity, 4))
    end_span(span, output={
        "avg_similarity": round(avg_similarity, 4),
        "threshold": threshold,
        "passed": passed,
        "per_query_similarities": {
            q.query_text: round(s, 4)
            for q, s in zip(brief.target_queries, similarities)
        },
    })

    logger.info(
        "Semantic: %s → avg_sim=%.3f (threshold=%.2f, %s)",
        brief.brief_id,
        avg_similarity,
        threshold,
        "PASSED" if passed else "FAILED",
    )

    return DimensionResult(
        dimension="semantic",
        passed=passed,
        score=round(avg_similarity, 4),
        feedback=feedback or "Content is semantically aligned with target queries.",
        details={
            "avg_similarity": round(avg_similarity, 4),
            "threshold": threshold,
            "per_query": {
                q.query_text: round(s, 4)
                for q, s in zip(brief.target_queries, similarities)
            },
        },
    )
