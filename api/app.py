"""FastAPI application factory."""
from __future__ import annotations

import asyncio
import logging
import os
import socket
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from api.config import api_settings
from api.exceptions import (
    PipelineError,
    approval_delivery_error_handler,
    pipeline_error_handler,
    task_conflict_handler,
    task_not_found_handler,
)
from api.tasks.exceptions import ApprovalDeliveryError
from api.auth.middleware import AuthMiddleware
from api.auth.store import AuthStore
from api.routers import analytics, artifacts, audience_persona, auth, brand_data, cms, companies, company_stream, content, content_data, content_inventory, content_performance, content_to_prompt, content_v13, cps, daily_tracker, events, gap_analysis, gap_data, health, knowledge_base, knowledge_docs, onboarding, research_orchestrator, settings, site_audit as site_audit_router, tasks, topic_discovery, voice_style_guide
from api.tasks.exceptions import TaskConflictError, TaskNotFoundError

logger = logging.getLogger(__name__)
middleware_logger = logging.getLogger("api.middleware")

_PROJECT_ROOT = Path(__file__).resolve().parents[1]  # content-strategy-engine/


def _init_structured_logging() -> None:
    """Configure structured logging once at startup."""
    from core.config.settings import settings as _s
    from core.shared_tools.structured_logging import configure_logging

    configure_logging(
        level=_s.log_level,
        log_format=_s.log_format,
        include_caller=_s.log_include_caller,
        database_echo=_s.database_echo,
    )


def _generate_worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


async def _init_task_store(app: FastAPI):
    """Initialize DbTaskStore. Requires DATABASE_URL."""
    from core.config.settings import settings

    if not settings.database_url:
        raise RuntimeError(
            "DATABASE_URL is required. Set it in your environment or .env file."
        )

    from core.db.engine import get_session_factory
    from core.services.db_task_store import DbTaskStore

    session_factory = get_session_factory()

    # Sync Redis for distributed slug locks
    redis_sync = None
    if settings.redis_pipeline_state and getattr(app.state, "redis_healthy", False):
        try:
            from core.redis import get_sync_redis_or_none

            redis_sync = get_sync_redis_or_none()
        except Exception:
            logger.warning("Sync Redis unavailable — locks will be in-memory")

    db_store = DbTaskStore(
        session_factory=session_factory,
        max_concurrent=api_settings.max_concurrent_pipelines,
        redis_client=redis_sync,
        worker_id=_generate_worker_id(),
    )
    orphan_count = await db_store.recover_from_db()
    logger.info(
        "Using DbTaskStore (recovered %d orphans)", orphan_count
    )
    return db_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize shared state on startup, cleanup on shutdown."""
    # Structured logging — idempotent, safe to call even if run_server.py called first
    _init_structured_logging()

    # ── Redis initialization (before EventBus — needed for selection) ──
    app.state.redis = None
    app.state.redis_healthy = False
    try:
        from core.redis import get_redis_or_none, redis_ping

        redis_client = get_redis_or_none()
        if redis_client is not None:
            healthy = await redis_ping()
            if healthy:
                app.state.redis = redis_client
                app.state.redis_healthy = True
                logger.info("Redis health check: connected")
            else:
                logger.warning(
                    "Redis health check: PING failed — Redis unavailable"
                )
        else:
            logger.info("Redis health check: skipped (no REDIS_URL)")
    except Exception:
        logger.exception(
            "Redis initialization failed — continuing without Redis"
        )

    # ── EventBus selection (Redis Streams required) ─────────────────────
    if not hasattr(app.state, "event_bus") or app.state.event_bus is None:
        redis_client = getattr(app.state, "redis", None)
        if redis_client is None or not getattr(app.state, "redis_healthy", False):
            raise RuntimeError(
                "REDIS_URL is required and Redis must be healthy. "
                "Set REDIS_URL in your environment or .env file."
            )

        from api.tasks.redis_event_bus import RedisEventBus

        app.state.event_bus = RedisEventBus(
            redis=redis_client,
            max_history=200,
            loop=asyncio.get_running_loop(),
        )
        logger.info("Using RedisEventBus (Redis Streams)")

    # Only set defaults if not already overridden (e.g., by tests)
    if not hasattr(app.state, "task_store") or app.state.task_store is None:
        app.state.task_store = await _init_task_store(app)
    if not hasattr(app.state, "artifacts_root") or app.state.artifacts_root is None:
        app.state.artifacts_root = _PROJECT_ROOT / "artifacts"
    if not hasattr(app.state, "storage_backend") or app.state.storage_backend is None:
        from core.storage import get_storage_backend
        _backend = get_storage_backend(app.state.artifacts_root)
        if getattr(app.state, "redis_healthy", False):
            from core.storage.cached_backend import CachedStorageBackend
            _backend = CachedStorageBackend(_backend)
            logger.info("StorageBackend wrapped with CachedStorageBackend")
        app.state.storage_backend = _backend
    if not hasattr(app.state, "auth_store") or app.state.auth_store is None:
        app.state.auth_store = AuthStore(base_dir=app.state.artifacts_root)

    # Expose the JWT secret key for the ASGI middleware (decoupled from AuthStore)
    if not hasattr(app.state, "secret_key") or app.state.secret_key is None:
        app.state.secret_key = app.state.auth_store._secret_key

    # Expose DB session factory for per-request DbService construction (Phase 4)
    if not hasattr(app.state, "db_session_factory") or app.state.db_session_factory is None:
        try:
            from core.config.settings import settings as _settings

            if _settings.database_url:
                from core.db.engine import get_session_factory

                app.state.db_session_factory = get_session_factory()
                logger.info("DB session factory exposed on app.state")
        except Exception:
            logger.debug("DB session factory not available — using JSON services")

    # Layer 7: Initialize audit logging sink
    from core.audit.logger import set_sink
    from core.audit.sink import DbAuditSink, NoOpAuditSink

    db_sf = getattr(app.state, "db_session_factory", None)
    if db_sf:
        set_sink(DbAuditSink(db_sf))
        logger.info("Audit sink: DbAuditSink")
    else:
        set_sink(NoOpAuditSink())

    # ── Startup DB health checks ───────────────────────────────────────
    app.state.db_healthy = False
    app.state.pgvector_available = False
    db_sf = getattr(app.state, "db_session_factory", None)
    if db_sf is not None:
        try:
            async with db_sf() as session:
                # 1. Basic connectivity
                result = await session.execute(
                    __import__("sqlalchemy").text("SELECT 1")
                )
                result.scalar_one()
                app.state.db_healthy = True
                logger.info("DB health check: PostgreSQL connected")

                # 2. pgvector extension
                row = await session.execute(
                    __import__("sqlalchemy").text(
                        "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
                    )
                )
                ext = row.scalar_one_or_none()
                if ext:
                    app.state.pgvector_available = True
                    logger.info("DB health check: pgvector v%s available", ext)
                else:
                    logger.warning("DB health check: pgvector extension NOT installed")
        except Exception:
            logger.exception("DB health check failed — DB may be unreachable")
    else:
        logger.info("DB health check: skipped (no DATABASE_URL)")

    logger.info(
        "API started — task store: %s", type(app.state.task_store).__name__
    )
    yield

    # Shutdown
    # Drain pending DB writes before shutdown
    task_store = getattr(app.state, "task_store", None)
    if task_store is not None and hasattr(task_store, "drain_pending"):
        await task_store.drain_pending()

    from core.redis import close_redis

    await close_redis()
    logger.info("API shutting down")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs method, path, status code, and duration for every request.

    Binds structured context (correlation_id, user_id, company_slug) so all
    downstream log calls automatically include these fields.

    SSE endpoints (/events) are excluded: BaseHTTPMiddleware buffers the
    response body before returning, which would break streaming delivery.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        from core.shared_tools.structured_logging import bind_context, clear_context

        # SSE endpoints — pass through without buffering
        if request.url.path.endswith("/events"):
            return await call_next(request)

        # Server-generated request ID (always fresh UUID4)
        request_id = str(uuid.uuid4())

        # Correlation ID: forwarded from upstream, or defaults to request_id
        raw_corr = request.headers.get("X-Correlation-ID", "")
        correlation_id = raw_corr[:128] if raw_corr else request_id

        # Bind request-scoped context
        clear_context()
        bind_context(
            request_id=request_id,
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
        )

        # Auth middleware runs before us — user_id/company_slug may be set
        user_id = getattr(request.state, "user_id", None)
        company_slug = getattr(request.state, "company_slug", None)
        if user_id:
            bind_context(user_id=user_id)
        if company_slug:
            bind_context(company_slug=company_slug)

        start = time.monotonic()
        try:
            response = await call_next(request)
            duration_ms = round((time.monotonic() - start) * 1000, 1)

            middleware_logger.info(
                "request_completed",
                extra={
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )

            # Propagate IDs to client
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Request-ID"] = request_id

            return response
        finally:
            clear_context()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Content Strategy Engine API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Middleware — add_middleware wraps in reverse order (last added = outermost).
    # Execution: CORSMiddleware → AuthMiddleware → RequestLoggingMiddleware → Router
    # CORS outermost so OPTIONS preflight is handled before auth.
    # Auth rewritten as pure ASGI middleware (not BaseHTTPMiddleware) for SSE safety.
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=api_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    app.add_exception_handler(TaskNotFoundError, task_not_found_handler)
    app.add_exception_handler(TaskConflictError, task_conflict_handler)
    app.add_exception_handler(PipelineError, pipeline_error_handler)
    app.add_exception_handler(ApprovalDeliveryError, approval_delivery_error_handler)

    # Routers
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(companies.router)
    app.include_router(gap_analysis.router)
    app.include_router(gap_data.router)
    app.include_router(events.router)
    app.include_router(artifacts.router)
    app.include_router(content.router)
    app.include_router(content_v13.router)
    app.include_router(cps.router)
    app.include_router(content_data.router)
    app.include_router(brand_data.router)
    app.include_router(settings.router)
    app.include_router(knowledge_base.router)
    app.include_router(knowledge_docs.router)
    app.include_router(audience_persona.router)
    app.include_router(voice_style_guide.router)
    app.include_router(topic_discovery.router)
    app.include_router(research_orchestrator.router)
    app.include_router(onboarding.router)
    app.include_router(site_audit_router.router)
    app.include_router(daily_tracker.router)
    app.include_router(cms.router)
    app.include_router(analytics.router)
    app.include_router(content_inventory.router)
    app.include_router(content_performance.router)
    app.include_router(content_to_prompt.router)
    app.include_router(tasks.router)
    app.include_router(company_stream.router)

    return app
