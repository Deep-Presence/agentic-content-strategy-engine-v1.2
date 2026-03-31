from __future__ import annotations

import json
import logging
from typing import Any, List, Optional, Tuple

import httpx

from core.gap_analysis.engines.base import SearchEngine
from core.models.gap_analysis import CitationRef, PlatformResult
from core.config.settings import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.anthropic.com"
_ANTHROPIC_VERSION = "2023-06-01"
_WEB_SEARCH_BETA = "web-search-2025-03-05"


def _safe_url(s: Any) -> Optional[str]:
    """Return a valid URL string or None."""
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    if not s or len(s) < 10:
        return None
    if not (s.startswith("http://") or s.startswith("https://")):
        return None
    return s


def _extract_url_from_item(item: Any) -> Optional[str]:
    """Extract URL from a citation/search result item (dict or object)."""
    if isinstance(item, dict):
        return _safe_url(item.get("url") or item.get("link"))
    return _safe_url(getattr(item, "url", None) or getattr(item, "link", None))


def _extract_claude_output_from_json(data: dict) -> Tuple[str, List[str]]:
    """Extract response text and citations from Claude API JSON response."""
    text_parts: List[str] = []
    citations: List[str] = []
    seen: set[str] = set()
    content_blocks = data.get("content")
    if not isinstance(content_blocks, list):
        return "", []

    for block in content_blocks:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")

        if block_type == "text":
            text_parts.append(block.get("text", "") or "")
            for citation in block.get("citations") or []:
                url = _extract_url_from_item(citation)
                if url and url not in seen:
                    seen.add(url)
                    citations.append(url)

        if block_type == "tool_result":
            content = block.get("content")
            if isinstance(content, list):
                for item in content:
                    url = _extract_url_from_item(item)
                    if url and url not in seen:
                        seen.add(url)
                        citations.append(url)
                    # Also check nested search_results
                    if isinstance(item, dict) and "search_results" in item:
                        for sr in item.get("search_results", []):
                            url = _extract_url_from_item(sr)
                            if url and url not in seen:
                                seen.add(url)
                                citations.append(url)
    return " ".join(t for t in text_parts if t).strip(), citations


class ClaudeEngine(SearchEngine):
    engine_name = "claude"

    def __init__(self, model: Optional[str] = None) -> None:
        super().__init__(model=model or settings.gap_analysis_claude_engine_model)

    async def search(self, query_text: str, query_id: Optional[str] = None, *, client: Any = None) -> PlatformResult:
        api_key = settings.anthropic_api_key
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it to .env.local to enable Claude search."
            )

        headers = {
            "x-api-key": api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "anthropic-beta": _WEB_SEARCH_BETA,
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": 2048,
            "temperature": 0.3,
            "system": (
                "You are a helpful research assistant. Search the web to answer queries "
                "accurately. Always cite your sources."
            ),
            "messages": [{"role": "user", "content": query_text}],
            "tools": [
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 2,
                }
            ],
        }

        logger.info("Claude search request for query %s", query_id)

        async def _do_request(http_client: httpx.AsyncClient) -> dict:
            resp = await http_client.post(
                f"{_BASE_URL}/v1/messages",
                headers=headers,
                json=payload,
            )
            if resp.status_code >= 400:
                logger.error(
                    "Claude search error for query %s: status=%s body=%s",
                    query_id,
                    resp.status_code,
                    resp.text[:2000],
                )
                resp.raise_for_status()

            try:
                return resp.json()
            except json.JSONDecodeError as e:
                logger.error(
                    "Claude search invalid JSON for query %s: %s body_preview=%s",
                    query_id,
                    e,
                    resp.text[:500],
                )
                raise RuntimeError(
                    f"Claude API returned invalid JSON: {e}"
                ) from e

        if client is not None:
            data = await _do_request(client)
        else:
            async with httpx.AsyncClient(timeout=90) as http_client:
                data = await _do_request(http_client)

        from core.shared_tools.cost_tracker import extract_usage_anthropic_http, track_llm_cost

        _pt, _ct = extract_usage_anthropic_http(data)
        track_llm_cost(
            model=self.model, provider="anthropic", pipeline="gap_analysis",
            pipeline_step="s3_claude_engine", prompt_tokens=_pt, completion_tokens=_ct,
            call_site="core.gap_analysis.engines.claude",
        )

        response_text, citations = _extract_claude_output_from_json(data)
        logger.info(
            "Claude search response for query %s: citations=%d",
            query_id,
            len(citations),
        )

        citation_refs: List[CitationRef] = []
        for index, url in enumerate(citations, start=1):
            if not url:
                continue
            try:
                citation_refs.append(CitationRef(url=url, rank=index, source="claude"))
            except Exception as e:
                logger.debug("Skipping invalid citation url for query %s: %s", query_id, e)
                continue

        return PlatformResult(
            engine=self.engine_name,
            model=self.model,
            query_id=query_id or "",
            query_text=query_text,
            response_text=response_text,
            citations=citation_refs,
        )
