from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from core.models.gap_analysis import EnrichedCitation, GeneratedQuery, ParagraphMatch
from core.config.settings import settings
from core.shared_tools.chroma_client import upsert_citation_embeddings

logger = logging.getLogger(__name__)

# text-embedding-3-large: 8,191 token limit per text.
# Worst-case ratio is ~1:1 (binary/special content), so cap at 6,000 chars
# to guarantee safety even for non-English or noisy text.
_MAX_CHARS_PER_TEXT = 6_000
# Paragraphs above this are almost certainly binary garbage (PDF, images).
_GARBAGE_CHAR_THRESHOLD = 30_000
# Minimum paragraph length worth embedding.
_MIN_CHARS = 50
# Target total chars per API call (conservative; assumes worst-case 1:1 ratio).
_MAX_CHARS_PER_BATCH = 6_000


# ---------------------------------------------------------------------------
# Paragraph sanitization — filter garbage, truncate long text
# ---------------------------------------------------------------------------


def _is_garbage_text(text: str) -> bool:
    """Detect binary/non-text content that has no semantic value.

    Returns True for PDF binary, base64 blobs, and other non-prose content
    that S4 may have extracted from non-HTML responses.
    """
    if not text:
        return True

    sample = text[:5000]
    # Count non-printable / non-standard chars (excluding normal whitespace)
    non_printable = sum(
        1 for ch in sample
        if (ord(ch) < 32 and ch not in "\n\r\t") or ord(ch) > 65533
    )
    ratio = non_printable / max(len(sample), 1)
    if ratio > 0.05:
        return True

    # PDF binary signature
    if "%PDF-" in text[:64] or "endstream" in text[:2000]:
        return True

    # Base64-heavy content (long stretches without spaces)
    longest_no_space = max((len(seg) for seg in sample.split()), default=0)
    if longest_no_space > 500:
        return True

    return False


def _sanitize_paragraphs(
    paragraphs: List[str],
) -> Tuple[List[str], List[int]]:
    """Filter and prepare paragraphs for embedding.

    Returns:
        clean_paragraphs: List of texts safe to embed.
        original_indices: Corresponding indices in the original list
                          (for stable _embedding_id generation).
    """
    clean: List[str] = []
    indices: List[int] = []

    for idx, para in enumerate(paragraphs):
        # Skip empty or too-short paragraphs
        if len(para) < _MIN_CHARS:
            continue

        # Skip extremely long text (almost certainly garbage)
        if len(para) > _GARBAGE_CHAR_THRESHOLD:
            logger.warning(
                "Dropping oversized paragraph (%d chars) at index %d.",
                len(para), idx,
            )
            continue

        # Skip binary / non-text content
        if _is_garbage_text(para):
            logger.warning(
                "Dropping garbage paragraph (%d chars) at index %d.",
                len(para), idx,
            )
            continue

        # Truncate moderately long paragraphs to safe limit
        if len(para) > _MAX_CHARS_PER_TEXT:
            truncated = para[:_MAX_CHARS_PER_TEXT]
            last_space = truncated.rfind(" ")
            if last_space > _MAX_CHARS_PER_TEXT * 0.8:
                truncated = truncated[:last_space]
            para = truncated

        clean.append(para)
        indices.append(idx)

    return clean, indices


# ---------------------------------------------------------------------------
# Embedding with safe batching
# ---------------------------------------------------------------------------


def _embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed texts with adaptive batching and token-safe truncation."""
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

    # Hard-truncate every text to _MAX_CHARS_PER_TEXT (should already be
    # done by _sanitize_paragraphs, but defend in depth for direct callers).
    safe_texts: List[str] = []
    for t in texts:
        if len(t) > _MAX_CHARS_PER_TEXT:
            cut = t[:_MAX_CHARS_PER_TEXT]
            sp = cut.rfind(" ")
            if sp > _MAX_CHARS_PER_TEXT * 0.8:
                cut = cut[:sp]
            safe_texts.append(cut)
        else:
            safe_texts.append(t)

    # Adaptive batching: accumulate texts up to _MAX_CHARS_PER_BATCH.
    embeddings: List[List[float]] = []
    batch: List[str] = []
    batch_chars = 0

    def _flush_batch() -> None:
        nonlocal batch, batch_chars
        if not batch:
            return
        try:
            response = client.embeddings.create(model=model, input=batch)
            embeddings.extend([row.embedding for row in response.data])
        except Exception as exc:
            # Retry one-by-one on failure (handles edge cases where
            # a single text still exceeds token limit).
            if len(batch) == 1:
                logger.error(
                    "Embedding failed for text (%d chars): %s",
                    len(batch[0]), exc,
                )
                raise
            logger.warning(
                "Batch embedding failed (%d texts, %d chars), retrying one-by-one: %s",
                len(batch), batch_chars, exc,
            )
            for single_text in batch:
                try:
                    resp = client.embeddings.create(model=model, input=[single_text])
                    embeddings.extend([row.embedding for row in resp.data])
                except Exception as single_exc:
                    logger.error(
                        "Skipping un-embeddable text (%d chars): %s",
                        len(single_text), single_exc,
                    )
                    # Return zero vector so output length matches input length
                    embeddings.append([0.0] * 3072)
        batch = []
        batch_chars = 0

    for text in safe_texts:
        text_len = len(text)
        if batch and (batch_chars + text_len > _MAX_CHARS_PER_BATCH):
            _flush_batch()
        batch.append(text)
        batch_chars += text_len

    _flush_batch()
    return embeddings


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    a = np.array(vec_a, dtype=float)
    b = np.array(vec_b, dtype=float)
    if np.linalg.norm(a) == 0.0 or np.linalg.norm(b) == 0.0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


# ---------------------------------------------------------------------------
# Query embedding
# ---------------------------------------------------------------------------


def embed_queries(
    queries: List[GeneratedQuery],
) -> List[GeneratedQuery]:
    texts = [q.query_text for q in queries]
    embeddings = _embed_texts(texts)
    for q, emb in zip(queries, embeddings):
        q.embedding = emb
    return queries


# ---------------------------------------------------------------------------
# Citation embedding
# ---------------------------------------------------------------------------


def _embedding_id(url: str, para_idx: int) -> str:
    """Generate a stable unique ID for a citation paragraph embedding."""
    h = hashlib.sha256(f"{url}_{para_idx}".encode()).hexdigest()[:24]
    return f"cite_{h}"


def embed_enriched_citations(
    citations: List[EnrichedCitation],
    query_lookup: Optional[Dict[str, GeneratedQuery]] = None,
    company_slug: Optional[str] = None,
    top_k: int = 3,
) -> List[EnrichedCitation]:
    all_ids: List[str] = []
    all_docs: List[str] = []
    all_embeddings: List[List[float]] = []

    for citation in citations:
        if not citation.paragraphs:
            continue

        # Sanitize paragraphs: filter garbage, truncate long text.
        clean_paragraphs, original_indices = _sanitize_paragraphs(
            citation.paragraphs
        )
        if not clean_paragraphs:
            continue

        # Use anchor_text (AI snippet) when available; else fall back to query text
        anchor_text = citation.anchor_text or ""
        if not anchor_text and query_lookup and citation.query_id:
            q = query_lookup.get(citation.query_id)
            if q and q.query_text:
                anchor_text = q.query_text
        if not anchor_text:
            anchor_text = clean_paragraphs[0][:2000]
        if not anchor_text:
            continue

        paragraph_embeddings = _embed_texts(clean_paragraphs)
        anchor_embedding = _embed_texts([anchor_text])[0]

        scored: List[Tuple[ParagraphMatch, int]] = []
        for clean_idx, (paragraph, embedding) in enumerate(
            zip(clean_paragraphs, paragraph_embeddings)
        ):
            orig_idx = original_indices[clean_idx]
            similarity = _cosine_similarity(anchor_embedding, embedding)
            scored.append(
                (
                    ParagraphMatch(
                        paragraph=paragraph,
                        embedding=embedding,
                        similarity=similarity,
                    ),
                    orig_idx,
                )
            )
        scored.sort(key=lambda x: x[0].similarity or 0.0, reverse=True)
        best = scored[:top_k]
        url_str = str(citation.url)
        for rank, (pm, orig_idx) in enumerate(best):
            emb_id = _embedding_id(url_str, orig_idx)
            pm.embedding_id = emb_id
            all_ids.append(emb_id)
            all_docs.append(pm.paragraph)
            all_embeddings.append(pm.embedding or [])
        citation.best_paragraphs = [pm for pm, _ in best]

    if company_slug and all_ids:
        upsert_citation_embeddings(
            company_slug=company_slug,
            embedding_ids=all_ids,
            documents=all_docs,
            embeddings=all_embeddings,
        )
    return citations


# ---------------------------------------------------------------------------
# Save + orchestrator
# ---------------------------------------------------------------------------


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
    company_slug: Optional[str] = None,
    top_k: int = 3,
) -> Tuple[List[GeneratedQuery], List[EnrichedCitation]]:
    query_lookup = {q.query_id: q for q in queries}
    return embed_queries(queries), embed_enriched_citations(
        citations,
        query_lookup=query_lookup,
        company_slug=company_slug,
        top_k=top_k,
    )
