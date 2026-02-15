"""Step 4 — Crawl cited URLs, extract text & structural signals, produce EnrichedCitation objects.

Async-first: uses httpx.AsyncClient with Semaphore-based concurrency control.
URL deduplication ensures each unique URL is fetched only once.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

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


def _extract_paragraphs(html: str) -> Tuple[List[str], StructuralSignals]:
    soup = BeautifulSoup(html, "html.parser")
    elements = soup.find_all(["p", "li", "h2", "h3"])
    paragraphs: List[str] = []
    for el in elements:
        text = " ".join(el.get_text(" ", strip=True).split())
        if text and len(text) >= 50:
            paragraphs.append(text)

    header_count = len(soup.find_all(["h1", "h2", "h3", "h4"]))
    list_item_count = len(soup.find_all("li"))
    word_count = sum(len(p.split()) for p in paragraphs)
    all_text = " ".join(paragraphs)
    stat_count = len(re.findall(r"\d+\.?\d*\s*%|\$\d+|\d{2,}", all_text))
    citation_count = len(soup.find_all("a", href=True))

    signals = StructuralSignals(
        word_count=word_count,
        paragraph_count=len(paragraphs),
        header_count=header_count,
        list_item_count=list_item_count,
        stat_count=stat_count,
        citation_count=citation_count,
        has_headers=header_count > 0,
        has_lists=list_item_count > 0,
        has_numbers=stat_count > 0,
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
        try:
            target = client or httpx.AsyncClient(timeout=20, follow_redirects=True)
            resp = await target.get(url)
            if resp.status_code >= 400:
                return None, None
            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type.lower():
                return None, None
            return resp.text, str(resp.url)
        except Exception:
            return None, None

    if semaphore:
        async with semaphore:
            return await _do_fetch()
    return await _do_fetch()


async def enrich_citations(
    results: List[PlatformResult],
    query_lookup: Optional[Dict[str, GeneratedQuery]] = None,
    concurrency: int = 20,
) -> List[EnrichedCitation]:
    """Enrich citations by fetching HTML and extracting structural signals.

    Async-first: fetches URLs concurrently with semaphore-based throttling.
    Deduplicates URLs so each is fetched only once.
    Preserves original citation ordering.

    Args:
        results: Platform search results containing citations.
        query_lookup: Optional mapping of query_id -> GeneratedQuery for cluster info.
        concurrency: Maximum number of concurrent HTTP requests.

    Returns:
        List of EnrichedCitation objects in the same order as input citations.
    """
    if not results:
        return []

    # Collect all unique URLs while preserving input order
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
                },
            ))

    if not citation_entries:
        return []

    # Fetch all unique URLs concurrently with connection limits (Codex)
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(
        timeout=20,
        follow_redirects=True,
        limits=httpx.Limits(max_connections=30, max_keepalive_connections=10),
    ) as client:
        fetch_tasks = [
            _fetch_html(url, client=client, semaphore=semaphore)
            for _, url, _ in citation_entries
        ]
        fetch_results = await asyncio.gather(*fetch_tasks)

    # Build enriched citations preserving original order
    enriched: List[EnrichedCitation] = []
    resolved_count = 0
    for (idx, original_url, meta), (html, resolved_url) in zip(citation_entries, fetch_results):
        if not html:
            continue
        # Use resolved URL (after redirects) instead of wrapper URLs
        # (e.g. vertexaisearch.cloud.google.com → actual destination)
        final_url = resolved_url or original_url
        if final_url != original_url:
            resolved_count += 1
        paragraphs, signals = _extract_paragraphs(html)
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
            )
        )

    logger.info("Enriched %d citations from %d unique URLs.", len(enriched), len(citation_entries))
    if resolved_count:
        logger.info("Resolved %d redirect URLs to final destinations.", resolved_count)
    return enriched


def save_enriched_citations(enriched: List[EnrichedCitation], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [item.model_dump(mode="json") for item in enriched]
    output_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
