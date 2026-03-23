"""Global exception handlers for the FastAPI application."""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from api.tasks.store import ApprovalDeliveryError, TaskConflictError, TaskNotFoundError


async def task_not_found_handler(request: Request, exc: TaskNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc), "error_code": "task_not_found"},
    )


async def task_conflict_handler(request: Request, exc: TaskConflictError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"detail": str(exc), "error_code": "task_conflict"},
    )


class PipelineError(Exception):
    """Raised when a pipeline encounters an error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


async def pipeline_error_handler(request: Request, exc: PipelineError) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "error_code": "pipeline_error"},
    )


async def approval_delivery_error_handler(
    request: Request, exc: ApprovalDeliveryError
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Approval delivery temporarily unavailable — please retry",
            "error_code": "approval_delivery_failed",
            "task_id": exc.task_id,
        },
        headers={"Retry-After": "5"},
    )
