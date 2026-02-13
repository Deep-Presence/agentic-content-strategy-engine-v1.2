from __future__ import annotations

import asyncio
from typing import Any, List, Optional, Tuple

from core.gap_analysis.engines.base import SearchEngine
from core.models.gap_analysis import CitationRef, PlatformResult
from core.config.settings import settings


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
        super().__init__(model=model or "gpt-4o")

    async def search(self, query_text: str, query_id: Optional[str] = None) -> PlatformResult:
        def _run() -> tuple[str, List[str]]:
            from openai import OpenAI

            api_key = settings.openai_api_key
            if not api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY is not set. Add it to .env.local to enable OpenAI search."
                )
            client = OpenAI(api_key=api_key)
            try:
                response = client.responses.create(
                    model=self.model,
                    input=query_text,
                    tools=[{"type": "web_search"}],
                )
                output = getattr(response, "output", None) or []
                return _extract_openai_output(output)
            except Exception:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": query_text}],
                )
                content = ""
                if response.choices:
                    msg = response.choices[0].message
                    content = getattr(msg, "content", None) or ""
                return content, []

        response_text, citations = await asyncio.to_thread(_run)
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
