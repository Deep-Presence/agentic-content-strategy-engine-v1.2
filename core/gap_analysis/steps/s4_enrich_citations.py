"""Step 4 — Crawl cited URLs, extract text & structural signals, produce EnrichedCitation objects.

Async-first: uses httpx.AsyncClient with Semaphore-based concurrency control.
URL deduplication ensures each unique URL is fetched only once.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import statistics
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup

from core.config.settings import settings
from core.models.gap_analysis import (
    EnrichedCitation,
    GeneratedQuery,
    PlatformResult,
    StructuralSignals,
)

logger = logging.getLogger(__name__)


def _infer_authority_type(domain: str) -> str:
    domain = domain.lower()
    if domain.endswith(".gov"):
        return "government"
    if domain.endswith(".edu"):
        return "academic"
    if domain.endswith(".org"):
        return "nonprofit"
    return "commercial_or_media"


def _infer_content_type(url: str) -> Optional[str]:
    path = urlparse(url).path.lower()
    if any(key in path for key in ("blog", "article", "news")):
        return "blog_or_article"
    if any(key in path for key in ("guide", "playbook", "handbook")):
        return "guide"
    if "faq" in path:
        return "faq"
    if any(key in path for key in ("docs", "documentation", "api")):
        return "docs"
    if any(key in path for key in ("research", "report", "whitepaper")):
        return "research"
    if "case-study" in path or "case_study" in path:
        return "case_study"
    return None


_SEMANTIC_SELECTORS = ["article", "main", "[role='main']", ".post-content", ".entry-content"]
_MIN_TRAFILATURA_LEN = 200

# Serialize trafilatura.extract() calls — lxml releases the GIL and its
# internal global state is not thread-safe under concurrent access.
_TRAFILATURA_LOCK = threading.Lock()


def _extract_main_content(html: str) -> str:
    """Extract main content from HTML, stripping nav/footer/sidebar chrome.

    Three-tier fallback:
      1. trafilatura — research-grade boilerplate removal (if result > 200 chars)
      2. BeautifulSoup semantic tags — article, main, [role="main"], .post-content, .entry-content
      3. Full page fallback — return original HTML unchanged

    Returns the best HTML for paragraph text extraction.
    For structural element counting, use _extract_structural_html() instead.
    """
    # Tier 1: trafilatura (serialized — lxml is not thread-safe)
    try:
        with _TRAFILATURA_LOCK:
            extracted = trafilatura.extract(
                html,
                output_format="html",
                include_tables=True,
                include_links=True,
            )
        if extracted and len(extracted) >= _MIN_TRAFILATURA_LEN:
            return extracted
    except Exception:
        logger.debug("trafilatura extraction failed, falling back to BS4 semantic tags")

    # Tier 2: BeautifulSoup semantic selectors
    soup = BeautifulSoup(html, "html.parser")
    for selector in _SEMANTIC_SELECTORS:
        element = soup.select_one(selector)
        if element:
            inner = str(element)
            if len(inner) >= _MIN_TRAFILATURA_LEN:
                return inner

    # Tier 3: Full page fallback
    return html


def _extract_structural_html(html: str) -> str:
    """Extract the structural HTML for element counting (preserves ol/dl/table/details).

    Trafilatura flattens structural elements, so this function uses only
    semantic tag scoping (article/main) or full-page fallback — never trafilatura.
    """
    soup = BeautifulSoup(html, "html.parser")
    for selector in _SEMANTIC_SELECTORS:
        element = soup.select_one(selector)
        if element:
            inner = str(element)
            if len(inner) >= _MIN_TRAFILATURA_LEN:
                return inner
    return html


# ---------------------------------------------------------------------------
# Sentence splitting (English-only)
# ---------------------------------------------------------------------------
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
_REFERENTIAL_PRONOUNS = {"this", "that", "these", "those", "it", "they", "he", "she", "such"}
_RESEARCH_ATTRIBUTION_RE = re.compile(
    r"according to|as reported by|research shows|study finds|data from|survey by|analysis by",
    re.IGNORECASE,
)
_DATA_POINT_RE = re.compile(r"\d+\.?\d*\s*%|\$[\d,.]+|\d{4}\s*(study|report|survey|research)|\d{2,}")
_EXPERT_QUOTE_RE = re.compile(r'(?:says|said|according to)\s+\w+\s+\w+', re.IGNORECASE)
_FAQ_HEADING_RE = re.compile(r"faq|frequently asked|common questions", re.IGNORECASE)
_TAKEAWAY_HEADING_RE = re.compile(r"key takeaway|takeaway|tl;?dr|summary|highlights?|main points?", re.IGNORECASE)
_STEP_HEADING_RE = re.compile(r"step[- ]by[- ]step|how to|steps? \d|step \d", re.IGNORECASE)
_TOC_HEADING_RE = re.compile(r"table of contents|contents|in this (article|guide|post)", re.IGNORECASE)


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences using regex heuristic (English-centric)."""
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]


def _safe_float(value: float) -> float:
    """Return 0.0 if value is NaN or inf."""
    if math.isnan(value) or math.isinf(value):
        return 0.0
    return value


def _compute_self_contained_ratio(paragraphs: List[str]) -> float:
    """Fraction of paragraphs that are self-contained (20-150 words, no referential opening, contains fact)."""
    if not paragraphs:
        return 0.0
    self_contained = 0
    for p in paragraphs:
        words = p.split()
        wc = len(words)
        if wc < 20 or wc > 150:
            continue
        first_word = words[0].lower().rstrip(".,;:")
        if first_word in _REFERENTIAL_PRONOUNS:
            continue
        # Contains a stat, entity-like pattern, or definition marker
        if _DATA_POINT_RE.search(p) or " is " in p or " are " in p or " refers to " in p:
            self_contained += 1
    return _safe_float(self_contained / len(paragraphs))


def _detect_content_patterns(soup: BeautifulSoup, all_text: str) -> dict:
    """Detect content pattern booleans from HTML structure and text."""
    headings_text = " ".join(
        h.get_text(" ", strip=True)
        for h in soup.find_all(["h1", "h2", "h3", "h4"])
    )

    has_faq_section = bool(
        _FAQ_HEADING_RE.search(headings_text)
        or soup.find("details")
        or soup.find("dl")
    )
    has_key_takeaways = bool(_TAKEAWAY_HEADING_RE.search(headings_text))
    has_step_by_step = bool(
        _STEP_HEADING_RE.search(headings_text)
        or (soup.find("ol") and any(
            re.search(r"step\s*\d", li.get_text(), re.IGNORECASE)
            for li in soup.find_all("li")[:10]
        ))
    )
    has_toc = bool(
        _TOC_HEADING_RE.search(headings_text)
        or soup.find("nav", class_=re.compile(r"toc|table-of-contents", re.IGNORECASE))
    )
    has_comparison_table = bool(
        soup.find("table") and any(
            re.search(r"vs\.?|compar|feature|plan|pricing", th.get_text(), re.IGNORECASE)
            for th in soup.find_all("th")[:10]
        )
    )
    has_research_refs = bool(_RESEARCH_ATTRIBUTION_RE.search(all_text))
    has_expert_quotes = bool(
        soup.find("blockquote") and _EXPERT_QUOTE_RE.search(all_text)
    )
    has_definition_opening = bool(
        re.search(r"^[A-Z][^.]*\b(is|are|refers to|means)\b", all_text[:500])
    )

    return {
        "has_faq_section": has_faq_section,
        "has_key_takeaways": has_key_takeaways,
        "has_step_by_step": has_step_by_step,
        "has_toc": has_toc,
        "has_comparison_table": has_comparison_table,
        "has_research_refs": has_research_refs,
        "has_expert_quotes": has_expert_quotes,
        "has_definition_opening": has_definition_opening,
    }


def _compute_factual_density(soup: BeautifulSoup, all_text: str, word_count: int) -> dict:
    """Compute factual density metrics."""
    data_point_count = len(_DATA_POINT_RE.findall(all_text))
    link_count = len(soup.find_all("a", href=True))
    citation_density = _safe_float(link_count / (word_count / 1000)) if word_count > 0 else 0.0
    # Named entity density approximation: capitalized multi-word phrases
    named_entities = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+", all_text)
    named_entity_density = _safe_float(len(named_entities) / (word_count / 1000)) if word_count > 0 else 0.0

    return {
        "data_point_count": data_point_count,
        "citation_density": round(citation_density, 2),
        "named_entity_density": round(named_entity_density, 2),
    }


def _extract_paragraphs(html: str) -> Tuple[List[str], StructuralSignals]:
    """Extract paragraphs and compute enriched structural signals from HTML.

    Uses two HTML sources:
      - trafilatura output for paragraph text extraction (best text quality)
      - semantic HTML for structural element counting (preserves ol/dl/table/etc)
    Computes ~45 structural signals across 4 categories.
    """
    text_html = _extract_main_content(html)
    structural_html = _extract_structural_html(html)
    soup = BeautifulSoup(text_html, "html.parser")
    struct_soup = BeautifulSoup(structural_html, "html.parser")

    # --- Extract paragraph texts ---
    elements = soup.find_all(["p", "li", "h2", "h3"])
    paragraphs: List[str] = []
    for el in elements:
        text = " ".join(el.get_text(" ", strip=True).split())
        if text and len(text) >= 50:
            paragraphs.append(text)

    # --- Original signals (backward compat) ---
    # Use struct_soup for element counts (preserves ol/dl/table/etc)
    h1_count = len(struct_soup.find_all("h1"))
    h2_count = len(struct_soup.find_all("h2"))
    h3_count = len(struct_soup.find_all("h3"))
    h4_count = len(struct_soup.find_all("h4"))
    header_count = h1_count + h2_count + h3_count + h4_count
    list_item_count = len(struct_soup.find_all("li"))
    per_paragraph_word_counts = [len(p.split()) for p in paragraphs]
    word_count = sum(per_paragraph_word_counts)
    all_text = " ".join(paragraphs)
    stat_count = len(re.findall(r"\d+\.?\d*\s*%|\$\d+|\d{2,}", all_text))
    citation_count = len(struct_soup.find_all("a", href=True))

    # --- Category A: Text Composition ---
    sentences = _split_sentences(all_text)
    sentence_count = len(sentences)
    avg_paragraph_length = _safe_float(
        statistics.mean(per_paragraph_word_counts)
    ) if per_paragraph_word_counts else 0.0
    median_paragraph_length = _safe_float(
        statistics.median(per_paragraph_word_counts)
    ) if per_paragraph_word_counts else 0.0
    max_paragraph_word_count = max(per_paragraph_word_counts) if per_paragraph_word_counts else 0

    avg_sentence_length = 0.0
    if sentences:
        sentence_word_counts = [len(s.split()) for s in sentences]
        avg_sentence_length = _safe_float(statistics.mean(sentence_word_counts))

    avg_sentence_count_per_paragraph = 0.0
    if paragraphs:
        para_sentence_counts = [len(_split_sentences(p)) for p in paragraphs]
        avg_sentence_count_per_paragraph = _safe_float(statistics.mean(para_sentence_counts))

    reading_level = 0.0
    if word_count > 30:  # Need meaningful text for reading level
        try:
            import textstat
            reading_level = _safe_float(textstat.flesch_kincaid_grade(all_text))
        except Exception:
            pass

    self_contained_ratio = _compute_self_contained_ratio(paragraphs)

    # --- Category B: Structural Elements (from struct_soup to preserve HTML structure) ---
    ul_tags = struct_soup.find_all("ul")
    ol_tags = struct_soup.find_all("ol")
    unordered_list_count = len(ul_tags)
    ordered_list_count = len(ol_tags)
    list_block_count = unordered_list_count + ordered_list_count
    table_count = len(struct_soup.find_all("table"))
    definition_list_count = len(struct_soup.find_all("dl"))
    blockquote_count = len(struct_soup.find_all("blockquote"))
    code_block_count = len(struct_soup.find_all("pre"))

    # List block bullet metrics
    bullets_per_block: List[int] = []
    for list_tag in ul_tags + ol_tags:
        direct_items = list_tag.find_all("li", recursive=False)
        bullets_per_block.append(len(direct_items))
    bullets_per_list_block = _safe_float(
        statistics.mean(bullets_per_block)
    ) if bullets_per_block else 0.0
    min_bullets_per_list = min(bullets_per_block) if bullets_per_block else 0

    # --- Category C: Content Patterns (struct_soup for elements, all_text for text patterns) ---
    patterns = _detect_content_patterns(struct_soup, all_text)

    # --- Category D: Factual Density (struct_soup for links, all_text for text patterns) ---
    density = _compute_factual_density(struct_soup, all_text, word_count)

    signals = StructuralSignals(
        # Original fields
        word_count=word_count,
        paragraph_count=len(paragraphs),
        header_count=header_count,
        list_item_count=list_item_count,
        stat_count=stat_count,
        citation_count=citation_count,
        has_headers=header_count > 0,
        has_lists=list_item_count > 0,
        has_numbers=stat_count > 0,
        # Category A
        main_content_word_count=word_count,
        sentence_count=sentence_count,
        avg_paragraph_length=round(avg_paragraph_length, 1),
        median_paragraph_length=round(median_paragraph_length, 1),
        max_paragraph_word_count=max_paragraph_word_count,
        avg_sentence_length=round(avg_sentence_length, 1),
        avg_sentence_count_per_paragraph=round(avg_sentence_count_per_paragraph, 1),
        reading_level=round(reading_level, 1),
        self_contained_ratio=round(self_contained_ratio, 3),
        per_paragraph_word_counts=per_paragraph_word_counts,
        # Category B
        h1_count=h1_count,
        h2_count=h2_count,
        h3_count=h3_count,
        h4_count=h4_count,
        ordered_list_count=ordered_list_count,
        unordered_list_count=unordered_list_count,
        table_count=table_count,
        definition_list_count=definition_list_count,
        blockquote_count=blockquote_count,
        code_block_count=code_block_count,
        list_block_count=list_block_count,
        bullets_per_list_block=round(bullets_per_list_block, 1),
        min_bullets_per_list=min_bullets_per_list,
        # Category C
        **patterns,
        # Category D
        **density,
    )
    return paragraphs, signals


async def _fetch_html(
    url: str,
    client: httpx.AsyncClient | None = None,
    semaphore: asyncio.Semaphore | None = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Fetch HTML from a URL asynchronously.

    Args:
        url: The URL to fetch.
        client: Shared httpx.AsyncClient instance.
        semaphore: Optional semaphore for concurrency control.

    Returns:
        Tuple of (html, resolved_url). resolved_url is the final URL after
        any redirects (e.g. Vertex AI Search wrappers → real destination).
        Both are None on error/non-HTML response.
    """
    async def _do_fetch() -> Tuple[Optional[str], Optional[str]]:
        owned_client: httpx.AsyncClient | None = None
        try:
            if client is not None:
                target = client
            else:
                owned_client = httpx.AsyncClient(timeout=20, follow_redirects=True)
                target = owned_client
            resp = await target.get(url)
            if resp.status_code >= 400:
                return None, None
            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type.lower():
                return None, None
            return resp.text, str(resp.url)
        except Exception:
            return None, None
        finally:
            if owned_client is not None:
                await owned_client.aclose()

    if semaphore:
        async with semaphore:
            return await _do_fetch()
    return await _do_fetch()


async def enrich_citations(
    results: List[PlatformResult],
    query_lookup: Optional[Dict[str, GeneratedQuery]] = None,
    concurrency: Optional[int] = None,
    parse_workers: Optional[int] = None,
) -> List[EnrichedCitation]:
    """Enrich citations by fetching HTML and extracting structural signals.

    Two-phase pipeline:
      Phase 1 — Fetch: async HTTP with semaphore-based throttling
      Phase 2 — Parse: thread-offloaded _extract_paragraphs (CPU-bound)

    Deduplicates URLs so each is fetched only once.
    Preserves original citation ordering.

    Args:
        results: Platform search results containing citations.
        query_lookup: Optional mapping of query_id -> GeneratedQuery for cluster info.
        concurrency: Max concurrent HTTP requests (default: settings).
        parse_workers: Max concurrent parse threads (default: settings).

    Returns:
        List of EnrichedCitation objects in the same order as input citations.
    """
    if not results:
        return []

    fetch_concurrency = concurrency if concurrency is not None else settings.gap_analysis_s4_fetch_concurrency
    thread_workers = parse_workers if parse_workers is not None else settings.gap_analysis_s4_parse_workers

    # ── Phase 0: Collect unique URLs preserving input order ────────────
    citation_entries: List[Tuple[int, str, dict]] = []
    seen_urls: set[str] = set()

    for result in results:
        for citation in result.citations:
            url = str(citation.url)
            if url in seen_urls:
                continue
            seen_urls.add(url)
            citation_entries.append((
                len(citation_entries),
                url,
                {
                    "title": citation.title,
                    "snippet": citation.snippet,
                    "query_id": result.query_id,
                    "engine": result.engine,
                    "is_company_citation": citation.is_company_citation,
                },
            ))

    if not citation_entries:
        return []

    # ── Phase 1: Fetch all unique URLs concurrently ───────────────────
    semaphore = asyncio.Semaphore(fetch_concurrency)

    async with httpx.AsyncClient(
        timeout=20,
        follow_redirects=True,
        limits=httpx.Limits(
            max_connections=settings.gap_analysis_s4_http_pool_size,
            max_keepalive_connections=20,
        ),
    ) as client:
        fetch_tasks = [
            _fetch_html(url, client=client, semaphore=semaphore)
            for _, url, _ in citation_entries
        ]
        fetch_results_raw = await asyncio.gather(*fetch_tasks, return_exceptions=True)

    # Normalize any escaped exceptions to (None, None)
    fetch_results = []
    for result in fetch_results_raw:
        if isinstance(result, BaseException):
            logger.warning("Unexpected fetch error: %s", result)
            fetch_results.append((None, None))
        else:
            fetch_results.append(result)

    # ── Phase 2: Parse HTMLs in thread pool (CPU-bound offload) ───────
    parse_sem = asyncio.Semaphore(thread_workers)

    async def _parse_one(html: str) -> Tuple[List[str], StructuralSignals]:
        async with parse_sem:
            return await asyncio.to_thread(_extract_paragraphs, html)

    fetchable_entries: List[Tuple[int, str, dict, str]] = []
    parse_tasks_list: List[asyncio.Task] = []
    for (idx, original_url, meta), (html, resolved_url) in zip(citation_entries, fetch_results):
        if not html:
            continue
        final_url = resolved_url or original_url
        fetchable_entries.append((idx, original_url, meta, final_url))
        parse_tasks_list.append(_parse_one(html))

    parse_results_raw = await asyncio.gather(*parse_tasks_list, return_exceptions=True)

    # ── Phase 3: Assemble EnrichedCitation objects ────────────────────
    enriched: List[EnrichedCitation] = []
    resolved_count = 0
    for (idx, original_url, meta, final_url), result in zip(
        fetchable_entries, parse_results_raw
    ):
        if isinstance(result, BaseException):
            logger.warning("Parse failed for %s: %s", final_url, result)
            continue
        paragraphs, signals = result
        if final_url != original_url:
            resolved_count += 1
        domain = urlparse(final_url).netloc
        signals.authority_type = _infer_authority_type(domain)
        signals.content_type = _infer_content_type(final_url)

        cluster_name = None
        query_id = meta["query_id"]
        if query_lookup and query_id in query_lookup:
            cluster_name = query_lookup[query_id].cluster_name

        enriched.append(
            EnrichedCitation(
                url=final_url,
                domain=domain,
                title=meta["title"],
                query_id=query_id,
                cluster_name=cluster_name,
                engine=meta["engine"],
                anchor_text=meta["snippet"] or meta["title"],
                paragraphs=paragraphs,
                best_paragraphs=[],
                structural_signals=signals,
                is_company_citation=meta.get("is_company_citation", False),
            )
        )

    logger.info("Enriched %d citations from %d unique URLs.", len(enriched), len(citation_entries))
    if resolved_count:
        logger.info("Resolved %d redirect URLs to final destinations.", resolved_count)
    return enriched


def compute_structural_signals(html: str) -> Tuple[List[str], StructuralSignals]:
    """Public API for structural signal extraction from HTML.

    Reusable by other steps (e.g. s1 for company page analysis).
    Returns (paragraph_texts, StructuralSignals).
    """
    return _extract_paragraphs(html)


def save_enriched_citations(enriched: List[EnrichedCitation], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [item.model_dump(mode="json") for item in enriched]
    output_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
