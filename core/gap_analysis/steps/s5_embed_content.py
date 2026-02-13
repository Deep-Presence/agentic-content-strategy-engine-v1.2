from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from core.models.gap_analysis import EnrichedCitation, GeneratedQuery, ParagraphMatch
from core.config.settings import settings


def _embed_texts(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    api_key = settings.openai_api_key
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to .env.local to enable embeddings."
        )
    model = settings.embedding_model
    if not model:
        raise RuntimeError("EMBEDDING_MODEL is not set. Add it to .env.local.")

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    batch_size = 64
    embeddings: List[List[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = client.embeddings.create(model=model, input=batch)
        embeddings.extend([row.embedding for row in response.data])
    return embeddings


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    a = np.array(vec_a, dtype=float)
    b = np.array(vec_b, dtype=float)
    if np.linalg.norm(a) == 0.0 or np.linalg.norm(b) == 0.0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def embed_queries(
    queries: List[GeneratedQuery],
) -> List[GeneratedQuery]:
    texts = [q.query_text for q in queries]
    embeddings = _embed_texts(texts)
    for q, emb in zip(queries, embeddings):
        q.embedding = emb
    return queries


def embed_enriched_citations(
    citations: List[EnrichedCitation],
    top_k: int = 3,
) -> List[EnrichedCitation]:
    for citation in citations:
        anchor_text = citation.anchor_text or ""
        if not anchor_text or not citation.paragraphs:
            continue
        paragraph_embeddings = _embed_texts(citation.paragraphs)
        anchor_embedding = _embed_texts([anchor_text])[0]
        scored: List[ParagraphMatch] = []
        for paragraph, embedding in zip(citation.paragraphs, paragraph_embeddings):
            similarity = _cosine_similarity(anchor_embedding, embedding)
            scored.append(
                ParagraphMatch(
                    paragraph=paragraph,
                    embedding=embedding,
                    similarity=similarity,
                )
            )
        scored.sort(key=lambda x: x.similarity or 0.0, reverse=True)
        citation.best_paragraphs = scored[:top_k]
    return citations


def save_embeddings(
    queries: List[GeneratedQuery],
    citations: List[EnrichedCitation],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    query_path = output_dir / "queries_with_embeddings.json"
    citation_path = output_dir / "citations_with_embeddings.json"
    query_path.write_text(
        json.dumps([q.model_dump(mode="json") for q in queries], indent=2, default=str), encoding="utf-8"
    )
    citation_path.write_text(
        json.dumps([c.model_dump(mode="json") for c in citations], indent=2, default=str), encoding="utf-8"
    )


def embed_all(
    queries: List[GeneratedQuery],
    citations: List[EnrichedCitation],
    top_k: int = 3,
) -> Tuple[List[GeneratedQuery], List[EnrichedCitation]]:
    return embed_queries(queries), embed_enriched_citations(citations, top_k=top_k)
