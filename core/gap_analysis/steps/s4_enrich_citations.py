from __future__ import annotations

import json
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


def _fetch_html(url: str) -> Optional[str]:
    with httpx.Client(timeout=20, follow_redirects=True) as client:
        try:
            resp = client.get(url)
            if resp.status_code >= 400:
                return None
            return resp.text
        except Exception:
            return None


def enrich_citations(
    results: List[PlatformResult],
    query_lookup: Optional[Dict[str, GeneratedQuery]] = None,
) -> List[EnrichedCitation]:
    enriched: List[EnrichedCitation] = []
    seen: Dict[str, EnrichedCitation] = {}

    for result in results:
        for citation in result.citations:
            url = str(citation.url)
            if url in seen:
                continue
            html = _fetch_html(url)
            if not html:
                continue
            paragraphs, signals = _extract_paragraphs(html)
            domain = urlparse(url).netloc
            signals.authority_type = _infer_authority_type(domain)
            signals.content_type = _infer_content_type(url)

            cluster_name = None
            query_id = result.query_id
            if query_lookup and query_id in query_lookup:
                cluster_name = query_lookup[query_id].cluster_name

            enriched_item = EnrichedCitation(
                url=url,
                domain=domain,
                title=citation.title,
                query_id=query_id,
                cluster_name=cluster_name,
                engine=result.engine,
                anchor_text=citation.snippet or citation.title,
                paragraphs=paragraphs,
                best_paragraphs=[],
                structural_signals=signals,
            )
            seen[url] = enriched_item
            enriched.append(enriched_item)
    return enriched


def save_enriched_citations(enriched: List[EnrichedCitation], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [item.model_dump(mode="json") for item in enriched]
    output_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
