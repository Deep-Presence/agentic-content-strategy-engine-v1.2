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
from api.routers import artifacts, auth, brand_data, companies, content, content_data, events, gap_analysis, gap_data, health, knowledge_docs, research, settings, tasks
from api.tasks.event_bus import EventBus
from api.tasks.store import TaskConflictError, TaskNotFoundError, TaskStore

logger = logging.getLogger(__name__)
middleware_logger = logging.getLogger("api.middleware")

_PROJECT_ROOT = Path(__file__).resolve().parents[1]  # content-strategy-engine/


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize shared state on startup, cleanup on shutdown."""
    # Only set defaults if not already overridden (e.g., by tests)
    if not hasattr(app.state, "event_bus") or app.state.event_bus is None:
        app.state.event_bus = EventBus()
    if not hasattr(app.state, "task_store") or app.state.task_store is None:
        jobs_dir = _PROJECT_ROOT / "artifacts" / "_jobs"
        app.state.task_store = TaskStore(
            base_dir=jobs_dir,
            event_bus=app.state.event_bus,
            max_concurrent=api_settings.max_concurrent_pipelines,
        )
    if not hasattr(app.state, "artifacts_root") or app.state.artifacts_root is None:
        app.state.artifacts_root = _PROJECT_ROOT / "artifacts"
    if not hasattr(app.state, "auth_store") or app.state.auth_store is None:
        app.state.auth_store = AuthStore(base_dir=app.state.artifacts_root)

    logger.info("API started — jobs dir: %s", app.state.task_store._base_dir)
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
    app.include_router(research.router)
    app.include_router(content.router)
    app.include_router(content_data.router)
    app.include_router(brand_data.router)
    app.include_router(settings.router)
    app.include_router(knowledge_docs.router)
    app.include_router(tasks.router)

    return app
