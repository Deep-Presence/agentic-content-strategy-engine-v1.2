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
# Max texts per OpenAI embedding API call (well within their 2,048 limit).
_BATCH_SIZE = 256


# ---------------------------------------------------------------------------
# Paragraph sanitization — filter garbage, truncate long text
# ---------------------------------------------------------------------------


# Pre-compiled regex: control chars (except \n \r \t) and surrogates/non-chars above U+FFFD.
# Uses C-level matching — orders of magnitude faster than a Python char loop.
_NON_PRINTABLE_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")


def _is_garbage_text(text: str) -> bool:
    """Detect binary/non-text content that has no semantic value.

    Returns True for PDF binary, base64 blobs, and other non-prose content
    that S4 may have extracted from non-HTML responses.
    """
    if not text:
        return True

    # PDF binary signature (cheap string checks first)
    if "%PDF-" in text[:64] or "endstream" in text[:2000]:
        return True

    sample = text[:5000]

    # Count non-printable chars via C-level regex (not a Python char loop)
    non_printable = len(_NON_PRINTABLE_RE.findall(sample))
    ratio = non_printable / max(len(sample), 1)
    if ratio > 0.05:
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
# Embedding with bulk count-based batching
# ---------------------------------------------------------------------------


def _truncate_text(text: str) -> str:
    """Hard-truncate a single text to _MAX_CHARS_PER_TEXT."""
    if len(text) <= _MAX_CHARS_PER_TEXT:
        return text
    cut = text[:_MAX_CHARS_PER_TEXT]
    sp = cut.rfind(" ")
    if sp > _MAX_CHARS_PER_TEXT * 0.8:
        cut = cut[:sp]
    return cut


def _embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed texts in bulk using count-based batching (256 texts/batch).

    Each text is hard-truncated to _MAX_CHARS_PER_TEXT before embedding.
    On batch failure, retries one-by-one with zero-vector fallback.
    """
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

    safe_texts = [_truncate_text(t) for t in texts]

    embeddings: List[List[float]] = []
    total = len(safe_texts)
    total_batches = (total + _BATCH_SIZE - 1) // _BATCH_SIZE

    for i in range(0, total, _BATCH_SIZE):
        batch = safe_texts[i : i + _BATCH_SIZE]
        batch_num = i // _BATCH_SIZE + 1
        logger.info(
            "Embedding batch %d/%d (%d texts)...",
            batch_num, total_batches, len(batch),
        )
        try:
            response = client.embeddings.create(model=model, input=batch)
            embeddings.extend([row.embedding for row in response.data])
        except Exception as exc:
            if len(batch) == 1:
                logger.error(
                    "Embedding failed for text (%d chars): %s",
                    len(batch[0]), exc,
                )
                embeddings.append([0.0] * 3072)
                continue
            logger.warning(
                "Batch embedding failed (%d texts), retrying one-by-one: %s",
                len(batch), exc,
            )
            for single_text in batch:
                try:
                    resp = client.embeddings.create(
                        model=model, input=[single_text]
                    )
                    embeddings.extend([row.embedding for row in resp.data])
                except Exception as single_exc:
                    logger.error(
                        "Skipping un-embeddable text (%d chars): %s",
                        len(single_text), single_exc,
                    )
                    embeddings.append([0.0] * 3072)

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
# Citation embedding — bulk 3-phase approach
# ---------------------------------------------------------------------------


def _embedding_id(url: str, para_idx: int) -> str:
    """Generate a stable unique ID for a citation paragraph embedding."""
    h = hashlib.sha256(f"{url}_{para_idx}".encode()).hexdigest()[:24]
    return f"cite_{h}"


class _CitationWork:
    """Per-citation metadata collected in Phase 1 for use in Phase 3."""

    __slots__ = (
        "citation_idx", "clean_paragraphs", "original_indices",
        "para_text_indices", "anchor_text_idx",
    )

    def __init__(self) -> None:
        self.citation_idx: int = -1
        self.clean_paragraphs: List[str] = []
        self.original_indices: List[int] = []
        self.para_text_indices: List[int] = []  # indices into unique_texts
        self.anchor_text_idx: int = -1


def embed_enriched_citations(
    citations: List[EnrichedCitation],
    query_lookup: Optional[Dict[str, GeneratedQuery]] = None,
    company_slug: Optional[str] = None,
    top_k: int = 3,
) -> List[EnrichedCitation]:
    """Embed citation paragraphs using a bulk 3-phase approach.

    Phase 1: Collect — sanitize paragraphs, resolve anchors, deduplicate texts.
    Phase 2: Embed  — single bulk _embed_texts() call for all unique texts.
    Phase 3: Score  — cosine similarity, select top-k, deduplicate IDs, upsert.
    """

    # ------------------------------------------------------------------
    # Phase 1: Collect all texts to embed (deduplicated)
    # ------------------------------------------------------------------
    text_to_idx: Dict[str, int] = {}
    unique_texts: List[str] = []

    def _register_text(text: str) -> int:
        """Register a text for embedding; returns its index in unique_texts."""
        if text in text_to_idx:
            return text_to_idx[text]
        idx = len(unique_texts)
        unique_texts.append(text)
        text_to_idx[text] = idx
        return idx

    work_items: List[_CitationWork] = []
    total_citations = len(citations)
    logger.info("Phase 1: collecting texts from %d citations...", total_citations)

    for cite_idx, citation in enumerate(citations):
        if cite_idx % 500 == 0 and cite_idx > 0:
            logger.info(
                "  Phase 1 progress: %d/%d citations processed, %d unique texts so far.",
                cite_idx, total_citations, len(unique_texts),
            )

        if not citation.paragraphs:
            continue

        clean_paragraphs, original_indices = _sanitize_paragraphs(
            citation.paragraphs
        )
        if not clean_paragraphs:
            continue

        # Resolve anchor text: AI snippet > query text > first paragraph
        anchor_text = citation.anchor_text or ""
        if not anchor_text and query_lookup and citation.query_id:
            q = query_lookup.get(citation.query_id)
            if q and q.query_text:
                anchor_text = q.query_text
        if not anchor_text:
            anchor_text = clean_paragraphs[0][:2000]
        if not anchor_text:
            continue

        w = _CitationWork()
        w.citation_idx = cite_idx
        w.clean_paragraphs = clean_paragraphs
        w.original_indices = original_indices
        w.para_text_indices = [_register_text(p) for p in clean_paragraphs]
        w.anchor_text_idx = _register_text(anchor_text)
        work_items.append(w)

    if not unique_texts:
        return citations

    total_raw = sum(len(w.clean_paragraphs) + 1 for w in work_items)
    logger.info(
        "Phase 1 complete: %d citations with content, %d unique texts to embed "
        "(deduplicated from %d total).",
        len(work_items), len(unique_texts), total_raw,
    )

    # ------------------------------------------------------------------
    # Phase 2: Bulk embed all unique texts in one call
    # ------------------------------------------------------------------
    all_embeddings = _embed_texts(unique_texts)

    logger.info("Phase 2 complete: embedded %d texts.", len(all_embeddings))

    # ------------------------------------------------------------------
    # Phase 3: Score paragraphs, select top-k, deduplicate for ChromaDB
    # ------------------------------------------------------------------
    # Dict for deduplication: emb_id -> (document, embedding)
    chroma_map: Dict[str, Tuple[str, List[float]]] = {}

    for w in work_items:
        citation = citations[w.citation_idx]
        anchor_emb = all_embeddings[w.anchor_text_idx]

        scored: List[Tuple[ParagraphMatch, int]] = []
        for clean_idx, (paragraph, text_idx) in enumerate(
            zip(w.clean_paragraphs, w.para_text_indices)
        ):
            orig_idx = w.original_indices[clean_idx]
            para_emb = all_embeddings[text_idx]
            similarity = _cosine_similarity(anchor_emb, para_emb)
            scored.append(
                (
                    ParagraphMatch(
                        paragraph=paragraph,
                        embedding=para_emb,
                        similarity=similarity,
                    ),
                    orig_idx,
                )
            )

        scored.sort(key=lambda x: x[0].similarity or 0.0, reverse=True)
        best = scored[:top_k]
        url_str = str(citation.url)

        for pm, orig_idx in best:
            emb_id = _embedding_id(url_str, orig_idx)
            pm.embedding_id = emb_id
            # Deduplicate: same URL+paragraph from different queries
            if emb_id not in chroma_map:
                chroma_map[emb_id] = (pm.paragraph, pm.embedding or [])

        citation.best_paragraphs = [pm for pm, _ in best]

    # Upsert deduplicated embeddings to ChromaDB
    if company_slug and chroma_map:
        dedup_ids = list(chroma_map.keys())
        dedup_docs = [chroma_map[eid][0] for eid in dedup_ids]
        dedup_embs = [chroma_map[eid][1] for eid in dedup_ids]
        total_best = sum(
            len(citations[w.citation_idx].best_paragraphs) for w in work_items
        )
        logger.info(
            "Phase 3 complete: upserting %d unique embeddings to ChromaDB "
            "(deduplicated from %d total best-paragraphs).",
            len(dedup_ids), total_best,
        )
        upsert_citation_embeddings(
            company_slug=company_slug,
            embedding_ids=dedup_ids,
            documents=dedup_docs,
            embeddings=dedup_embs,
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
