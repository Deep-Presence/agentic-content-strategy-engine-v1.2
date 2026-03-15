from __future__ import annotations

from typing import Any, List, Optional

from core.gap_analysis.engines.base import SearchEngine
from core.models.gap_analysis import CitationRef, PlatformResult
from core.config.settings import settings


class PerplexityEngine(SearchEngine):
    engine_name = "perplexity"

    def __init__(self, model: Optional[str] = None) -> None:
        super().__init__(model=model or settings.perplexity_search_model)

    async def search(self, query_text: str, query_id: Optional[str] = None, *, client: Any = None) -> PlatformResult:
        from perplexity import AsyncPerplexity

        api_key = settings.perplexity_api_key
        if not api_key:
            raise RuntimeError(
                "PERPLEXITY_API_KEY is not set. Get your key at https://perplexity.ai/account/api"
            )

        pplx_client = client if client is not None else AsyncPerplexity(api_key=api_key)
        completion = await pplx_client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful research assistant. Provide accurate, well-researched answers with citations to your sources. Always cite the sources you use.",
                },
                {"role": "user", "content": query_text},
            ],
            stream=False,
        )
        content = ""
        if completion.choices:
            msg = completion.choices[0].message
            content = getattr(msg, "content", None) or ""
        citations = getattr(completion, "citations", None) or []
        response_text = content
        citation_refs: List[CitationRef] = []
        for index, url in enumerate(citations, start=1):
            try:
                citation_refs.append(
                    CitationRef(url=url, rank=index, source="perplexity")
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
