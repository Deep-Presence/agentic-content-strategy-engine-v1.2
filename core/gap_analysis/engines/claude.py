from __future__ import annotations

import asyncio
from typing import Any, List, Optional, Tuple

from core.gap_analysis.engines.base import SearchEngine
from core.models.gap_analysis import CitationRef, PlatformResult
from core.config.settings import settings


def _extract_claude_output(message: Any) -> Tuple[str, List[str]]:
    text_parts: List[str] = []
    citations: List[str] = []
    for block in getattr(message, "content", []) or []:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            text_parts.append(getattr(block, "text", "") or "")
            for citation in getattr(block, "citations", []) or []:
                url = getattr(citation, "url", None)
                if url:
                    citations.append(url)
        if block_type == "tool_result":
            content = getattr(block, "content", None)
            if isinstance(content, list):
                for item in content:
                    url = item.get("url") if isinstance(item, dict) else None
                    if url:
                        citations.append(url)
    return "\n".join([t for t in text_parts if t]).strip(), citations


class ClaudeEngine(SearchEngine):
    engine_name = "claude"

    def __init__(self, model: Optional[str] = None) -> None:
        super().__init__(model=model or settings.gap_analysis_claude_engine_model)

    async def search(self, query_text: str, query_id: Optional[str] = None) -> PlatformResult:
        def _run() -> tuple[str, List[str]]:
            import anthropic

            api_key = settings.anthropic_api_key
            if not api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY is not set. Add it to .env.local to enable Claude search."
                )
            client = anthropic.Anthropic(api_key=api_key)
            try:
                response = client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": query_text}],
                    tools=[{"type": "web_search"}],
                )
                return _extract_claude_output(response)
            except Exception:
                response = client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": query_text}],
                )
                return _extract_claude_output(response)

        response_text, citations = await asyncio.to_thread(_run)
        citation_refs: List[CitationRef] = []
        for index, url in enumerate(citations, start=1):
            try:
                citation_refs.append(
                    CitationRef(url=url, rank=index, source="claude")
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
