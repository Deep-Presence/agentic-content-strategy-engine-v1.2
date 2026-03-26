from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import random
import time
from typing import Any, Dict, Iterable, List, Optional

import httpx

from core.config.settings import settings
from core.storage.backends.base import StorageBackend
from core.gap_analysis.engines import (
    ClaudeEngine,
    GeminiEngine,
    OpenAIEngine,
    PerplexityEngine,
    SearchEngine,
)
from core.models.gap_analysis import GeneratedQuery, PlatformResult

logger = logging.getLogger(__name__)


def _fmt_duration(seconds: float) -> str:
    if seconds >= 60:
        m, s = divmod(seconds, 60)
        return f"{int(m)}m {s:.1f}s"
    return f"{seconds:.1f}s"

# Engines that use httpx directly (need shared httpx.AsyncClient)
_HTTPX_ENGINES = frozenset({"claude", "gemini"})


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


def _engine_concurrency_map() -> Dict[str, int]:
    """Build per-engine concurrency limits from settings."""
    return {
        "openai": settings.gap_analysis_s3_openai_concurrency,
        "claude": settings.gap_analysis_s3_claude_concurrency,
        "gemini": settings.gap_analysis_s3_gemini_concurrency,
        "perplexity": settings.gap_analysis_s3_perplexity_concurrency,
    }


# ---------------------------------------------------------------------------
# Retryable exception classifier
# ---------------------------------------------------------------------------

_RETRYABLE_CLASS_NAMES = frozenset({
    "RateLimitError",
    "APITimeoutError",
    "InternalServerError",
    "ServiceUnavailableError",
})


def _is_retryable(exc: BaseException) -> bool:
    """Return True if *exc* is a transient error worth retrying.

    Covers httpx status errors (429 / 5xx), timeouts, connect errors,
    and OpenAI / Perplexity SDK rate-limit / timeout classes (detected
    by class name to avoid importing optional SDK packages).
    """
    # httpx HTTP status errors — 429 or 5xx
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or code >= 500

    # httpx transport-level errors
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True

    # stdlib asyncio timeout
    if isinstance(exc, asyncio.TimeoutError):
        return True

    # SDK errors detected by class name (avoids importing openai/perplexity)
    if type(exc).__name__ in _RETRYABLE_CLASS_NAMES:
        return True

    return False


# ---------------------------------------------------------------------------
# Circuit breaker (batch-scoped, no half-open state)
# ---------------------------------------------------------------------------


class _CircuitBreaker:
    """Simple consecutive-failure counter.

    Created once per engine per pipeline run.  When *threshold*
    consecutive failures are recorded the breaker opens and
    ``is_open`` becomes ``True``.  A single success resets the
    counter.  ``tripped_count`` tracks how many queries were
    skipped while the breaker was open.
    """

    __slots__ = ("_threshold", "_consecutive_failures", "_open", "tripped_count")

    def __init__(self, threshold: int) -> None:
        self._threshold = threshold
        self._consecutive_failures = 0
        self._open = False
        self.tripped_count = 0

    @property
    def is_open(self) -> bool:
        return self._open

    def record_failure(self) -> bool:
        """Record a failure. Returns True if the breaker just opened."""
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._threshold:
            if not self._open:
                self.tripped_count = 1
                self._open = True
                return True
            self._open = True
        return False

    def record_success(self) -> None:
        self._consecutive_failures = 0


async def _run_one(
    engine: SearchEngine,
    query: GeneratedQuery,
    *,
    client: Any = None,
    max_retries: int = 0,
    retry_base_delay_s: float = 2.0,
) -> PlatformResult:
    """Execute a single search query against an engine with optional retry.

    Up to ``max_retries`` additional attempts are made for transient errors
    (as classified by ``_is_retryable``).  Delay between attempts follows
    exponential backoff: ``base * 2^attempt + uniform(0, 1)``.
    """
    t0 = time.monotonic()
    last_exc: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            result = await engine.search(query.query_text, query.query_id, client=client)
            logger.debug(
                "[%s] query %s done in %s — %d citations",
                engine.engine_name,
                query.query_id,
                _fmt_duration(time.monotonic() - t0),
                len(result.citations),
            )
            return result
        except Exception as exc:
            last_exc = exc
            # Non-retryable or final attempt → give up immediately
            if not _is_retryable(exc) or attempt == max_retries:
                break
            delay = retry_base_delay_s * (2 ** attempt) + random.uniform(0, 1)
            logger.info(
                "[%s] query %s retrying (attempt %d/%d) after %s — backoff %.1fs",
                engine.engine_name,
                query.query_id,
                attempt + 2,
                max_retries + 1,
                type(last_exc).__name__,
                delay,
            )
            await asyncio.sleep(delay)

    logger.warning(
        "[%s] query %s FAILED after %s: %s",
        engine.engine_name,
        query.query_id,
        _fmt_duration(time.monotonic() - t0),
        last_exc,
    )
    return PlatformResult(
        engine=engine.engine_name,
        model=getattr(engine, "model", None),
        query_id=query.query_id,
        query_text=query.query_text,
        response_text=f"ERROR: {last_exc}",
        citations=[],
    )


async def _run_engine_batch(
    engine: SearchEngine,
    queries: List[GeneratedQuery],
    engine_limit: int,
    global_sem: asyncio.Semaphore,
) -> List[PlatformResult]:
    """Run all queries for a single engine with per-engine + global throttling.

    Includes per-engine circuit breaker: after *threshold* consecutive
    failures the breaker opens and remaining queries get instant synthetic
    error results (no API call, no semaphore wait).
    """
    engine_sem = asyncio.Semaphore(engine_limit)
    cb = _CircuitBreaker(threshold=settings.gap_analysis_s3_circuit_breaker_threshold)
    max_retries = settings.gap_analysis_s3_max_retries
    retry_base = settings.gap_analysis_s3_retry_base_delay_s
    total = len(queries)
    completed = 0
    errors = 0
    total_citations = 0
    batch_start = time.monotonic()

    logger.info(
        "[%s] starting batch: %d queries, concurrency=%d",
        engine.engine_name,
        total,
        engine_limit,
    )

    async def _throttled_run(query: GeneratedQuery) -> PlatformResult:
        nonlocal completed, errors, total_citations

        # Circuit breaker check — skip API call entirely
        if cb.is_open:
            cb.tripped_count += 1
            completed += 1
            errors += 1
            return PlatformResult(
                engine=engine.engine_name,
                model=getattr(engine, "model", None),
                query_id=query.query_id,
                query_text=query.query_text,
                response_text="ERROR: circuit breaker open — engine skipped",
                citations=[],
            )

        async with global_sem:
            async with engine_sem:
                result = await _run_one(
                    engine, query,
                    client=shared_client,
                    max_retries=max_retries,
                    retry_base_delay_s=retry_base,
                )

        completed += 1
        is_error = (result.response_text or "").startswith("ERROR:")
        if is_error:
            errors += 1
            just_opened = cb.record_failure()
            if just_opened:
                logger.warning(
                    "[%s] circuit breaker OPENED after consecutive failures — skipping remaining queries",
                    engine.engine_name,
                )
        else:
            total_citations += len(result.citations)
            cb.record_success()

        # Log progress every 10% or every 25 queries, whichever is smaller
        interval = max(1, min(total // 10, 25))
        if completed % interval == 0 or completed == total:
            elapsed = time.monotonic() - batch_start
            logger.info(
                "[%s] progress: %d/%d done (%d errors) — %s elapsed",
                engine.engine_name,
                completed,
                total,
                errors,
                _fmt_duration(elapsed),
            )
        return result

    # Create shared client for connection reuse; lifecycle scoped to this batch
    async with contextlib.AsyncExitStack() as stack:
        shared_client: Any = None
        if engine.engine_name in _HTTPX_ENGINES:
            shared_client = await stack.enter_async_context(
                httpx.AsyncClient(
                    timeout=90,
                    limits=httpx.Limits(
                        max_connections=engine_limit,
                        max_keepalive_connections=engine_limit,
                    ),
                )
            )
        elif engine.engine_name == "openai":
            from openai import AsyncOpenAI

            shared_client = await stack.enter_async_context(
                AsyncOpenAI(api_key=settings.openai_api_key)
            )
        elif engine.engine_name == "perplexity":
            from perplexity import AsyncPerplexity

            shared_client = await stack.enter_async_context(
                AsyncPerplexity(api_key=settings.perplexity_api_key)
            )

        tasks = [asyncio.create_task(_throttled_run(q)) for q in queries]
        results = list(await asyncio.gather(*tasks))

    batch_elapsed = time.monotonic() - batch_start
    cb_msg = f", {cb.tripped_count} circuit-breaker skips" if cb.tripped_count else ""
    logger.info(
        "[%s] batch complete: %d/%d succeeded, %d errors%s, %d citations — %s",
        engine.engine_name,
        total - errors,
        total,
        errors,
        cb_msg,
        total_citations,
        _fmt_duration(batch_elapsed),
    )
    return results


async def search_platforms(
    queries: List[GeneratedQuery],
    platform_names: List[str],
    concurrency: int = 6,
    *,
    trace_span: Optional[Any] = None,
) -> List[PlatformResult]:
    """Search all platforms with per-engine concurrency pools.

    Two-level throttling:
      - Global semaphore caps total in-flight requests across all engines
      - Per-engine semaphore caps requests to each individual provider

    Results are sorted deterministically by (query_id, engine) to ensure
    stable URL dedup attribution in downstream steps.
    """
    engines = _select_engines(platform_names)
    if not engines or not queries:
        return []

    engine_limits = _engine_concurrency_map()
    global_sem = asyncio.Semaphore(settings.gap_analysis_s3_global_concurrency)
    total_calls = len(queries) * len(engines)

    logger.info(
        "S3 starting: %d queries x %d engines = %d API calls "
        "(global_concurrency=%d)",
        len(queries),
        len(engines),
        total_calls,
        settings.gap_analysis_s3_global_concurrency,
    )
    for engine in engines:
        limit = engine_limits.get(engine.engine_name, concurrency)
        logger.info(
            "  %-12s concurrency=%d  model=%s",
            engine.engine_name,
            limit,
            getattr(engine, "model", "?"),
        )

    s3_start = time.monotonic()

    # Run all engine batches in parallel
    engine_coros = [
        _run_engine_batch(
            engine,
            queries,
            engine_limits.get(engine.engine_name, concurrency),
            global_sem,
        )
        for engine in engines
    ]
    results_per_engine = await asyncio.gather(*engine_coros, return_exceptions=True)

    # Flatten and sort deterministically (prevents dedup attribution drift)
    all_results: List[PlatformResult] = []
    engine_errors = 0
    for engine, batch in zip(engines, results_per_engine):
        if isinstance(batch, BaseException):
            logger.error(
                "Engine batch '%s' CRASHED: %s", engine.engine_name, batch,
            )
            engine_errors += 1
            continue
        all_results.extend(batch)
    all_results.sort(key=lambda r: (r.query_id, r.engine))

    # Summary stats
    s3_elapsed = time.monotonic() - s3_start
    ok_count = sum(1 for r in all_results if not (r.response_text or "").startswith("ERROR:"))
    err_count = len(all_results) - ok_count
    cite_count = sum(len(r.citations) for r in all_results)

    logger.info(
        "S3 complete in %s: %d results (%d ok, %d query-level errors, "
        "%d engine crashes), %d total citations",
        _fmt_duration(s3_elapsed),
        len(all_results),
        ok_count,
        err_count,
        engine_errors,
        cite_count,
    )
    return all_results


def save_platform_results(results: List[PlatformResult], storage: StorageBackend, prefix: str) -> None:
    storage.mkdir(prefix)
    by_engine: Dict[str, List[PlatformResult]] = {}
    for result in results:
        by_engine.setdefault(result.engine, []).append(result)

    for engine, items in by_engine.items():
        lines = [json.dumps(item.model_dump(mode="json"), default=str) for item in items]
        storage.write(f"{prefix}/{engine}_results.jsonl", "\n".join(lines) + "\n")
