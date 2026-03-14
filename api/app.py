"""FastAPI application factory."""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from api.config import api_settings
from api.exceptions import (
    PipelineError,
    pipeline_error_handler,
    task_conflict_handler,
    task_not_found_handler,
)
from api.auth.middleware import AuthMiddleware
from api.auth.store import AuthStore
from api.routers import artifacts, audience_persona, auth, brand_data, companies, content, content_data, content_v13, cps, daily_tracker, events, gap_analysis, gap_data, health, knowledge_base, knowledge_docs, onboarding, research_orchestrator, settings, site_audit as site_audit_router, tasks, topic_discovery, voice_style_guide
from api.tasks.event_bus import EventBus
from api.tasks.store import TaskConflictError, TaskNotFoundError, TaskStore

logger = logging.getLogger(__name__)
middleware_logger = logging.getLogger("api.middleware")

_PROJECT_ROOT = Path(__file__).resolve().parents[1]  # content-strategy-engine/


async def _init_task_store(app: FastAPI) -> TaskStore:
    """Try DbTaskStore when DATABASE_URL is set, fall back to JSON TaskStore."""
    from core.config.settings import settings

    if settings.database_url:
        try:
            from core.db.engine import get_session_factory
            from core.services.db_task_store import DbTaskStore

            session_factory = get_session_factory()
            db_store = DbTaskStore(
                session_factory=session_factory,
                max_concurrent=api_settings.max_concurrent_pipelines,
            )
            orphan_count = await db_store.recover_from_db()
            logger.info(
                "Using DbTaskStore (recovered %d orphans)", orphan_count
            )
            return db_store  # type: ignore[return-value]
        except Exception:
            logger.exception(
                "Failed to initialize DbTaskStore — falling back to JSON TaskStore"
            )

    jobs_dir = _PROJECT_ROOT / "artifacts" / "_jobs"
    return TaskStore(
        base_dir=jobs_dir,
        event_bus=app.state.event_bus,
        max_concurrent=api_settings.max_concurrent_pipelines,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize shared state on startup, cleanup on shutdown."""
    # Only set defaults if not already overridden (e.g., by tests)
    if not hasattr(app.state, "event_bus") or app.state.event_bus is None:
        app.state.event_bus = EventBus()
    if not hasattr(app.state, "task_store") or app.state.task_store is None:
        app.state.task_store = await _init_task_store(app)
    if not hasattr(app.state, "artifacts_root") or app.state.artifacts_root is None:
        app.state.artifacts_root = _PROJECT_ROOT / "artifacts"
    if not hasattr(app.state, "storage_backend") or app.state.storage_backend is None:
        from core.storage.backends import LocalStorageBackend
        app.state.storage_backend = LocalStorageBackend(app.state.artifacts_root)
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

    logger.info(
        "API started — task store: %s", type(app.state.task_store).__name__
    )
    yield
    logger.info("API shutting down")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs method, path, status code, and duration for every request.

    SSE endpoints (/events) are excluded: BaseHTTPMiddleware buffers the
    response body before returning, which would break streaming delivery.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # SSE endpoints — pass through without buffering
        if request.url.path.endswith("/events"):
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000
        middleware_logger.info(
            "%s %s %d %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response


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
    app.include_router(tasks.router)

    return app
