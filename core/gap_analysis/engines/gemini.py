from __future__ import annotations

import asyncio
from typing import List, Optional

from core.gap_analysis.engines.base import SearchEngine
from core.models.gap_analysis import CitationRef, PlatformResult
from core.config.settings import settings


class GeminiEngine(SearchEngine):
    engine_name = "gemini"

    def __init__(self, model: Optional[str] = None) -> None:
        super().__init__(model=model or "gemini-2.0-flash")

    async def search(self, query_text: str, query_id: Optional[str] = None) -> PlatformResult:
        def _run() -> tuple[str, List[str]]:
            from google import genai

            api_key = settings.google_api_key_gap_analysis
            if not api_key:
                raise RuntimeError(
                    "GOOGLE_API_KEY_GAP_ANALYSIS is not set. Add it to .env.local to enable Gemini search."
                )
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=query_text,
                config={"tools": [{"google_search": {}}]},
            )
            text = getattr(response, "text", None) or ""
            citations: List[str] = []
            grounding = getattr(response, "grounding_metadata", None)
            chunks = getattr(grounding, "grounding_chunks", None) or []
            for chunk in chunks:
                url = getattr(chunk, "url", None)
                if not url and hasattr(chunk, "web"):
                    url = getattr(chunk.web, "uri", None)
                if url:
                    citations.append(url)
            return text, citations

        response_text, citations = await asyncio.to_thread(_run)
        citation_refs: List[CitationRef] = []
        for index, url in enumerate(citations, start=1):
            try:
                citation_refs.append(
                    CitationRef(url=url, rank=index, source="gemini")
                )
            except Exception:
                continue

        return PlatformResult(
            engine=self.engine_name,
            model=self.model,
            query_id=query_id or "",
            query_text=query_text,
            response_text=response_text,
            citations=citation_refs,
        )
