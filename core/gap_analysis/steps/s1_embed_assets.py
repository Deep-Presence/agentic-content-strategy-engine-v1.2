from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from core.models.gap_analysis import GapAnalysisInput, SemanticUnit
from core.config.settings import settings

_CONTENT_ENGINE_ROOT = Path(__file__).resolve().parents[2]


def _ensure_output_dir(company_slug: str) -> Path:
    path = _CONTENT_ENGINE_ROOT / "artifacts" / "gap_analysis" / company_slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    normalized = parsed._replace(fragment="")
    cleaned = urlunparse(normalized).rstrip("/")
    return cleaned


def _same_host(url: str, domain: str) -> bool:
    return urlparse(url).netloc.endswith(domain)


def _build_robot_parser(base_url: str) -> RobotFileParser:
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    try:
        rp.set_url(robots_url)
        rp.read()
    except Exception:
        rp = RobotFileParser()
        rp.parse("")
    return rp


def _extract_links(html: str, base_url: str, domain: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: List[str] = []
    for tag in soup.find_all("a", href=True):
        href = tag.get("href", "").strip()
        if not href or href.startswith("#"):
            continue
        absolute = urljoin(base_url, href)
        absolute = _normalize_url(absolute)
        if _same_host(absolute, domain):
            links.append(absolute)
    return links


def _extract_paragraphs(html: str) -> Tuple[str, List[str]]:
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string or "").strip() if soup.title else ""
    elements = soup.find_all(["p", "li", "h2", "h3"])
    paragraphs: List[str] = []
    for el in elements:
        text = " ".join(el.get_text(" ", strip=True).split())
        if text and len(text) >= 50:
            paragraphs.append(text)
    return title, paragraphs


def _chunk_paragraphs(paragraphs: Iterable[str], min_words: int = 80, max_words: int = 220) -> List[str]:
    chunks: List[str] = []
    buffer: List[str] = []
    word_count = 0
    for para in paragraphs:
        words = para.split()
        if not words:
            continue
        if word_count + len(words) > max_words and buffer:
            chunks.append(" ".join(buffer))
            buffer = []
            word_count = 0
        buffer.append(para)
        word_count += len(words)
        if word_count >= min_words:
            chunks.append(" ".join(buffer))
            buffer = []
            word_count = 0
    if buffer:
        chunks.append(" ".join(buffer))
    return chunks


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


def crawl_company_assets(
    domain: str,
    seed_urls: List[str],
    max_pages: int,
    max_depth: int,
) -> List[Tuple[str, str]]:
    if not domain:
        raise ValueError("domain is required for crawling")
    base_url = seed_urls[0] if seed_urls else f"https://{domain}"
    rp = _build_robot_parser(base_url)
    visited: Set[str] = set()
    queue: List[Tuple[str, int]] = [(base_url, 0)]
    pages: List[Tuple[str, str]] = []

    with httpx.Client(timeout=20, follow_redirects=True) as client:
        while queue and len(pages) < max_pages:
            url, depth = queue.pop(0)
            url = _normalize_url(url)
            if url in visited or depth > max_depth:
                continue
            if not rp.can_fetch("*", url):
                visited.add(url)
                continue
            visited.add(url)
            try:
                resp = client.get(url)
                if resp.status_code >= 400:
                    continue
                html = resp.text or ""
            except Exception:
                continue
            pages.append((url, html))
            if depth < max_depth:
                for link in _extract_links(html, url, domain):
                    if link not in visited:
                        queue.append((link, depth + 1))
            time.sleep(0.2)
    return pages


def build_semantic_units(
    pages: List[Tuple[str, str]],
) -> List[SemanticUnit]:
    units: List[SemanticUnit] = []
    counter = 0
    for url, html in pages:
        title, paragraphs = _extract_paragraphs(html)
        chunks = _chunk_paragraphs(paragraphs)
        for chunk in chunks:
            counter += 1
            text = chunk.strip()
            units.append(
                SemanticUnit(
                    unit_id=f"unit_{counter}",
                    url=url,
                    title=title or None,
                    text=text,
                    char_count=len(text),
                    word_count=len(text.split()),
                )
            )
    return units


def embed_company_assets(input_data: GapAnalysisInput) -> List[SemanticUnit]:
    company_slug = input_data.company_slug or re.sub(
        r"[^a-z0-9]+", "-", input_data.company_name.lower()
    ).strip("-")
    out_dir = _ensure_output_dir(company_slug)
    max_pages = input_data.max_crawl_pages or settings.gap_analysis_max_crawl_pages
    max_depth = input_data.max_crawl_depth or settings.gap_analysis_max_crawl_depth

    seed_urls = [str(u) for u in input_data.seed_urls]
    pages = crawl_company_assets(
        domain=input_data.domain or "",
        seed_urls=seed_urls,
        max_pages=max_pages,
        max_depth=max_depth,
    )
    units = build_semantic_units(pages)
    texts = [u.text for u in units]
    embeddings = _embed_texts(texts)
    for unit, embedding in zip(units, embeddings):
        unit.embedding = embedding

    output_path = out_dir / "company_embeddings.json"
    payload = [u.model_dump(mode="json") for u in units]
    output_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return units
