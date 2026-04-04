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
        from core.shared_tools.openrouter_client import get_async_client

        pplx_client = client if client is not None else get_async_client()
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
        # Cost tracking (never raises)
        from core.shared_tools.cost_tracker import track_llm_cost

        _usage = getattr(completion, "usage", None)
        _pt = getattr(_usage, "prompt_tokens", 0) or 0
        _ct = getattr(_usage, "completion_tokens", 0) or 0
        track_llm_cost(
            model=self.model,
            provider="openrouter",
            pipeline="gap_analysis",
            pipeline_step="s3_perplexity_engine",
            prompt_tokens=_pt,
            completion_tokens=_ct,
            call_site="core.gap_analysis.engines.perplexity",
            source="openrouter",
        )

        content = ""
        if completion.choices:
            msg = completion.choices[0].message
            content = getattr(msg, "content", None) or ""
        # Dual-source citation extraction: direct attr or model_extra fallback
        citations = getattr(completion, "citations", None) or []
        if not citations:
            extra = getattr(completion, "model_extra", {}) or {}
            citations = extra.get("citations", [])
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
            prompt_tokens=_pt,
            completion_tokens=_ct,
        )
