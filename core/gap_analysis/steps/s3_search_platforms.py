from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from core.gap_analysis.engines import (
    ClaudeEngine,
    GeminiEngine,
    OpenAIEngine,
    PerplexityEngine,
    SearchEngine,
)
from core.models.gap_analysis import GeneratedQuery, PlatformResult


def _engine_registry() -> Dict[str, SearchEngine]:
    return {
        "perplexity": PerplexityEngine(),
        "openai": OpenAIEngine(),
        "gemini": GeminiEngine(),
        "claude": ClaudeEngine(),
    }


def _select_engines(names: Iterable[str]) -> List[SearchEngine]:
    registry = _engine_registry()
    engines: List[SearchEngine] = []
    for name in names:
        key = name.strip().lower()
        if key in registry:
            engines.append(registry[key])
    return engines


async def _run_one(engine: SearchEngine, query: GeneratedQuery, semaphore: asyncio.Semaphore) -> PlatformResult:
    async with semaphore:
        try:
            return await engine.search(query.query_text, query.query_id)
        except Exception as exc:
            return PlatformResult(
                engine=engine.engine_name,
                model=getattr(engine, "model", None),
                query_id=query.query_id,
                query_text=query.query_text,
                response_text=f"ERROR: {exc}",
                citations=[],
            )


async def search_platforms(
    queries: List[GeneratedQuery],
    platform_names: List[str],
    concurrency: int = 6,
) -> List[PlatformResult]:
    engines = _select_engines(platform_names)
    semaphore = asyncio.Semaphore(concurrency)
    tasks: List[asyncio.Task[PlatformResult]] = []
    for query in queries:
        for engine in engines:
            tasks.append(asyncio.create_task(_run_one(engine, query, semaphore)))
    return await asyncio.gather(*tasks)


def save_platform_results(results: List[PlatformResult], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    by_engine: Dict[str, List[PlatformResult]] = {}
    for result in results:
        by_engine.setdefault(result.engine, []).append(result)

    for engine, items in by_engine.items():
        path = output_dir / f"{engine}_results.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item.model_dump(mode="json"), default=str) + "\n")
