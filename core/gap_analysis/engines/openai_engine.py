from __future__ import annotations

import logging
from typing import Any, List, Optional, Tuple

from core.gap_analysis.engines.base import SearchEngine
from core.models.gap_analysis import CitationRef, PlatformResult
from core.config.settings import settings

logger = logging.getLogger(__name__)


def _extract_openai_output(output: List[Any]) -> Tuple[str, List[str]]:
    text_parts: List[str] = []
    citations: List[str] = []
    for item in output:
        if getattr(item, "type", None) == "message":
            for part in getattr(item, "content", []) or []:
                part_type = getattr(part, "type", None)
                if part_type in {"output_text", "text"}:
                    text_parts.append(getattr(part, "text", "") or "")
                    for ann in getattr(part, "annotations", []) or []:
                        if getattr(ann, "type", None) == "url_citation":
                            url = getattr(ann, "url", None) or getattr(
                                ann, "citation_url", None
                            )
                            if url:
                                citations.append(url)
    return "\n".join([t for t in text_parts if t]).strip(), citations


class OpenAIEngine(SearchEngine):
    engine_name = "openai"

    def __init__(self, model: Optional[str] = None) -> None:
        super().__init__(model=model or settings.gap_analysis_openai_engine_model)

    async def search(self, query_text: str, query_id: Optional[str] = None, *, client: Any = None) -> PlatformResult:
        from openai import AsyncOpenAI

        api_key = settings.openai_api_key
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Add it to .env.local to enable OpenAI search."
            )

        oai_client = client if client is not None else AsyncOpenAI(api_key=api_key)
        try:
            response = await oai_client.responses.create(
                model=self.model,
                reasoning={"effort": "low"},
                max_output_tokens=2048,  # Increased for detailed responses with citations
                tools=[{"type": "web_search"}],
                tool_choice={"type": "web_search"},
                include=["web_search_call.action.sources"],
                input=[
                    {
                        "role": "system",
                        "content": "You are a helpful research assistant. Search the web to answer queries accurately. Always cite your sources with proper references.",
                    },
                    {"role": "user", "content": query_text},
                ],
            )
            output = getattr(response, "output", None) or []
            response_text, citations = _extract_openai_output(output)
        except Exception as exc:
            logger.warning(
                "OpenAI web_search failed for query %s, falling back to plain response: %s",
                query_id,
                exc,
            )
            response = await oai_client.responses.create(
                model=self.model,
                input=query_text,
            )
            content = getattr(response, "output_text", None) or ""
            response_text, citations = content, []
        citation_refs: List[CitationRef] = []
        for index, url in enumerate(citations, start=1):
            try:
                citation_refs.append(
                    CitationRef(url=url, rank=index, source="openai")
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
