"""Shared helpers for router endpoints."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException

from api.tasks.models import PipelineTask
from core.services.task_store import TaskStoreProtocol

logger = logging.getLogger(__name__)


async def create_task_durable(
    task_store: TaskStoreProtocol,
    pipeline: str,
    company_slug: str,
    product_slug: Optional[str] = None,
    allow_parallel: bool = False,
) -> PipelineTask:
    """Create task + await DB persistence. Rolls back on failure (HTTP 503).

    Wraps ``task_store.create_task()`` + ``task_store.ensure_created()``
    into a single durable operation. If the DB INSERT fails, cleans up
    the in-memory state and raises HTTP 503.
    """
    task = task_store.create_task(pipeline, company_slug, product_slug, allow_parallel)
    try:
        await task_store.ensure_created(task.task_id)
    except Exception:
        logger.exception(
            "Task persistence failed for %s:%s — rolling back",
            pipeline, company_slug,
        )
        if hasattr(task_store, "rollback_create"):
            task_store.rollback_create(task.task_id)
        raise HTTPException(
            status_code=503,
            detail="Task persistence failed — retry later",
        )
    return task
