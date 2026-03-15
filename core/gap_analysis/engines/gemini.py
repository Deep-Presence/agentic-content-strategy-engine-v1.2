from __future__ import annotations

import json
import logging
from typing import Any, List, Optional

import httpx

from core.gap_analysis.engines.base import SearchEngine
from core.models.gap_analysis import CitationRef, PlatformResult
from core.config.settings import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
_TEMPERATURE = 0
_MAX_OUTPUT_TOKENS = 2048


def _parse_gemini_response(data: dict) -> dict:
    """Extract response text and citations from Gemini API JSON response.

    groundingMetadata.groundingChunks contains web sources with web.uri.
    URIs may be Vertex AI redirect URLs (vertexaisearch.cloud.google.com).
    """
    response_text = ""
    citations: List[str] = []
    seen: set[str] = set()
    candidates = data.get("candidates") or []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            if isinstance(part, dict) and "text" in part:
                response_text += part.get("text", "") or ""
        grounding = candidate.get("groundingMetadata") or {}
        chunks = grounding.get("groundingChunks") or []
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            web = chunk.get("web")
            url = web.get("uri") if isinstance(web, dict) else None
            if url and isinstance(url, str) and url not in seen:
                if url.startswith("http://") or url.startswith("https://"):
                    seen.add(url)
                    citations.append(url)
    return {"response_text": response_text.strip(), "citations": citations}


def _safe_url(s: Any) -> Optional[str]:
    """Return a valid URL string or None."""
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    if not s or len(s) < 10 or not (s.startswith("http://") or s.startswith("https://")):
        return None
    return s


class GeminiEngine(SearchEngine):
    engine_name = "gemini"

    def __init__(self, model: Optional[str] = None) -> None:
        super().__init__(model=model or settings.gap_analysis_gemini_engine_model)

    async def search(self, query_text: str, query_id: Optional[str] = None, *, client: Any = None) -> PlatformResult:
        api_key = settings.google_api_key_gap_analysis
        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY_GAP_ANALYSIS is not set. Add it to .env.local to enable Gemini search."
            )

        url = f"{_BASE_URL}/models/{self.model}:generateContent"
        params = {"key": api_key}
        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "You are a helpful research assistant. Search the web to answer queries "
                            "accurately. Always cite your sources with proper references."
                        )
                    }
                ]
            },
            "contents": [{"role": "user", "parts": [{"text": query_text}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": {
                "temperature": _TEMPERATURE,
                "maxOutputTokens": _MAX_OUTPUT_TOKENS,
            },
        }

        logger.info("Gemini search request for query %s", query_id)

        async def _do_request(http_client: httpx.AsyncClient) -> dict:
            resp = await http_client.post(url, params=params, json=payload)
            if resp.status_code >= 400:
                logger.error(
                    "Gemini search error for query %s: status=%s body=%s",
                    query_id,
                    resp.status_code,
                    resp.text[:2000],
                )
                resp.raise_for_status()

            try:
                return resp.json()
            except json.JSONDecodeError as e:
                logger.error(
                    "Gemini search invalid JSON for query %s: %s body_preview=%s",
                    query_id,
                    e,
                    resp.text[:500],
                )
                raise RuntimeError(f"Gemini API returned invalid JSON: {e}") from e

        if client is not None:
            data = await _do_request(client)
        else:
            async with httpx.AsyncClient(timeout=90) as http_client:
                data = await _do_request(http_client)

        parsed = _parse_gemini_response(data)
        response_text = parsed["response_text"]
        citations = parsed["citations"]

        logger.info(
            "Gemini search response for query %s: citations=%d",
            query_id,
            len(citations),
        )

        citation_refs: List[CitationRef] = []
        for index, url in enumerate(citations, start=1):
            if not _safe_url(url):
                continue
            try:
                citation_refs.append(CitationRef(url=url, rank=index, source="gemini"))
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
