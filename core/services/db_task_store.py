"""DB-backed TaskStore with write-through in-memory cache.

Satisfies TaskStoreProtocol. Uses a session_factory (not request-scoped)
for per-operation sessions. Process-local state (semaphore, queues, handles,
slug locks) stays in-memory only.

Single-instance durability scope: SSE streaming, asyncio queues, and task
handles are process-local. Horizontal scaling would require Redis pub/sub
or PG LISTEN/NOTIFY (future work).
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.tasks.models import ApprovalRecord, PipelineTask
from core.shared_tools.task_status import TaskStatus
from core.services.task_store import ApprovalWindowError, TaskConflictError, TaskNotFoundError

logger = logging.getLogger(__name__)


class DbTaskStore:
    """Write-through DB-backed task store.

    Architecture:
    - In-memory ``_tasks`` dict for fast sync reads (same as JSON TaskStore)
    - Write-through: state transitions write to DB first via
      ``asyncio.create_task(self._write_through(...))``, then update cache.
      For critical transitions (create, status change), use write-through.
      For progress updates (progress_pct), use fire-and-forget to avoid latency.
    - Startup: ``recover_from_db()`` loads all non-terminal tasks, marks orphans.
    - Process-local state (semaphore, queues, handles, slug locks) stays in-memory.
    """

    # Lua script: ownership-safe lock release (compare-and-delete)
    _RELEASE_LOCK_LUA = """\
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""

    def __init__(
        self,
        session_factory: Callable[..., AsyncSession],
        max_concurrent: int = 10,
        redis_client: Optional[Any] = None,
    ) -> None:
        self._tasks: Dict[str, PipelineTask] = {}
        self._session_factory = session_factory
        self._slug_locks: Dict[str, str] = {}  # "pipeline:effective_slug" -> task_id
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._approval_queues: Dict[str, asyncio.Queue] = {}
        self._task_handles: Dict[str, asyncio.Task] = {}
        self._max_concurrent = max_concurrent
        # Redis for distributed slug locks (sync client, sub-ms ops)
        self._redis_sync = redis_client
        self._release_script = (
            redis_client.register_script(self._RELEASE_LOCK_LUA)
            if redis_client is not None
            else None
        )
        # Redis distributed semaphore (global pipeline concurrency)
        self._redis_semaphore = None
        if redis_client is not None:
            from core.redis_semaphore import RedisSemaphore
            self._redis_semaphore = RedisSemaphore(
                redis_sync=redis_client,
                name="pipelines",
                max_concurrent=max_concurrent,
            )

    @property
    def semaphore(self) -> asyncio.Semaphore:
        return self._semaphore

    def pipeline_semaphore(self, task_id: str):
        """Return an async context manager for the pipeline concurrency semaphore.

        With Redis: returns RedisSemaphore context (distributed, atomic).
        Without Redis: returns asyncio.Semaphore (process-local fallback).
        """
        if self._redis_semaphore is not None:
            return self._redis_semaphore.acquire_context(task_id)
        return self._semaphore

    # ── Startup recovery ──────────────────────────────────────────────

    async def recover_from_db(self) -> int:
        """Load non-terminal tasks and mark orphans as failed_restart.

        Called once at app startup. Returns the number of orphans recovered.
        """
        from core.db.repositories.task_repo import TaskRepository

        async with self._session_factory() as session:
            repo = TaskRepository(session)
            orphan_count = await repo.mark_orphans_failed()

            # Load all tasks into memory cache
            all_tasks = await repo.list_tasks()
            for row in all_tasks:
                task = self._row_to_pipeline_task(row)
                self._tasks[task.task_id] = task

            await session.commit()

        # Clean up orphaned Redis locks from crashed workers
        orphan_locks_cleaned = 0
        if self._redis_sync is not None:
            try:
                orphan_locks_cleaned = self._cleanup_orphan_locks()
            except Exception:
                logger.warning("Failed to clean orphan Redis locks", exc_info=True)

        logger.info(
            "DbTaskStore recovered: %d tasks loaded, %d orphans marked failed_restart, "
            "%d orphan Redis locks cleaned",
            len(self._tasks),
            orphan_count,
            orphan_locks_cleaned,
        )
        return orphan_count

    # ── CRUD ──────────────────────────────────────────────────────────

    def create_task(
        self,
        pipeline: str,
        company_slug: str,
        product_slug: Optional[str] = None,
        allow_parallel: bool = False,
    ) -> PipelineTask:
        """Create a new task, optionally acquire slug lock, write to DB.

        Lock key is ``pipeline:effective_slug`` so different pipeline types
        can run concurrently for the same company.

        Args:
            allow_parallel: If True, skip slug lock acquisition. Used for
                manual content pipeline entries that can run in parallel.
        """
        effective = (
            f"{company_slug}__{product_slug}" if product_slug else company_slug
        )
        lock_key = f"{pipeline}:{effective}"

        # Generate task_id BEFORE acquiring lock (needed as lock value for Redis)
        task_id = str(_uuid.uuid4())

        if not allow_parallel:
            self.acquire_slug_lock(lock_key, task_id=task_id)

        now = datetime.now(timezone.utc)
        task = PipelineTask(
            task_id=task_id,
            pipeline=pipeline,
            company_slug=company_slug,
            product_slug=product_slug,
            effective_slug=effective,
            created_at=now,
            updated_at=now,
        )
        self._tasks[task_id] = task
        if not allow_parallel:
            self._slug_locks[lock_key] = task_id

        # Write-through to DB (critical: must persist before returning)
        asyncio.create_task(self._db_create(task))
        return task

    def get_task(self, task_id: str) -> PipelineTask:
        if task_id not in self._tasks:
            raise TaskNotFoundError(task_id)
        return self._tasks[task_id]

    def update_task(self, task_id: str, **kwargs: Any) -> PipelineTask:
        if task_id not in self._tasks:
            raise TaskNotFoundError(task_id)

        task = self._tasks[task_id]
        for key, value in kwargs.items():
            if hasattr(task, key):
                if key == "status" and isinstance(value, str) and not isinstance(value, TaskStatus):
                    value = TaskStatus(value)
                setattr(task, key, value)

        # Store/clear approval nonce in Redis for cross-worker validation
        if self._redis_sync is not None and "approval_payload" in kwargs:
            ap = kwargs["approval_payload"]
            nonce_key = f"approval:nonce:{task_id}"
            flag_key = f"approval:flag:{task_id}"
            if ap is not None:
                nonce = ap.get("checkpoint_nonce")
                if nonce:
                    try:
                        self._redis_sync.set(nonce_key, nonce, ex=86400)
                    except Exception:
                        logger.warning(
                            "Redis: failed to write nonce for %s", task_id, exc_info=True
                        )
            else:
                # Clearing approval_payload — remove nonce + flag for next checkpoint
                try:
                    self._redis_sync.delete(nonce_key, flag_key)
                except Exception:
                    logger.warning(
                        "Redis: failed to clear nonce/flag for %s", task_id, exc_info=True
                    )

        task.updated_at = datetime.now(timezone.utc)

        # Determine if this is a critical update (status change) or progress
        is_status_change = "status" in kwargs
        if is_status_change:
            asyncio.create_task(self._db_update(task_id, **kwargs))
        else:
            # Fire-and-forget for non-critical updates (progress_pct, current_step)
            asyncio.create_task(self._db_update(task_id, **kwargs))
        return task

    def list_tasks(
        self,
        pipeline: Optional[str] = None,
        status: Optional[str] = None,
        company_slug: Optional[str] = None,
        product_slug: Optional[str] = None,
    ) -> List[PipelineTask]:
        tasks = list(self._tasks.values())
        if pipeline:
            tasks = [t for t in tasks if t.pipeline == pipeline]
        if status:
            tasks = [t for t in tasks if t.status.value == status]
        if company_slug:
            tasks = [t for t in tasks if t.company_slug == company_slug]
        if product_slug:
            tasks = [t for t in tasks if t.product_slug == product_slug]
        return tasks

    # ── Slug Locks ────────────────────────────────────────────────────

    def acquire_slug_lock(self, slug: str, task_id: Optional[str] = None) -> None:
        """Acquire a per-slug lock. Redis when configured, in-memory otherwise.

        When Redis is configured (``redis_client`` provided), uses
        ``SET NX EX 7200`` for distributed locking. **Fail-closed**: Redis
        errors raise ``TaskConflictError`` rather than falling back to
        in-memory (prevents split-brain in multi-worker deployments).

        When Redis is NOT configured (``redis_client=None``), uses the
        existing in-memory ``_slug_locks`` dict.
        """
        if self._redis_sync is not None and task_id:
            try:
                return self._acquire_redis_lock(slug, task_id)
            except TaskConflictError:
                raise
            except Exception:
                # Fail-closed: Redis is configured but unavailable — refuse to start
                logger.error(
                    "Redis lock acquire failed — refusing to start pipeline "
                    "(fail-closed to prevent split-brain)",
                    exc_info=True,
                )
                raise TaskConflictError(
                    f"Cannot acquire lock for '{slug}': Redis is unavailable. "
                    f"Retry when Redis is back online."
                )
        # In-memory fallback (only when redis_client is None)
        if slug in self._slug_locks:
            existing_id = self._slug_locks[slug]
            if existing_id in self._tasks:
                existing = self._tasks[existing_id]
                if existing.status in (TaskStatus.RUNNING, TaskStatus.PENDING_APPROVAL):
                    raise TaskConflictError(
                        f"A pipeline is already running for company '{slug}' "
                        f"(task_id={existing_id})"
                    )
            del self._slug_locks[slug]

    def _cleanup_orphan_locks(self) -> int:
        """Remove Redis lock keys whose holder task is terminal or unknown.

        Called during startup recovery. SCAN for all ``lock:*`` keys, check
        each holder's status in ``_tasks``. If the holder is not active
        (RUNNING/PENDING_APPROVAL), delete the lock.
        """
        cleaned = 0
        cursor = 0
        while True:
            cursor, keys = self._redis_sync.scan(cursor, match="lock:*", count=100)
            for key in keys:
                holder = self._redis_sync.get(key)
                if holder is None:
                    continue  # Key expired between SCAN and GET
                task = self._tasks.get(holder)
                if task is None or task.status not in (
                    TaskStatus.RUNNING,
                    TaskStatus.PENDING_APPROVAL,
                ):
                    self._redis_sync.delete(key)
                    cleaned += 1
                    logger.info("Cleaned orphan Redis lock: %s (holder=%s)", key, holder)
            if cursor == 0:
                break
        return cleaned

    @staticmethod
    def _lock_key(slug: str) -> str:
        """Build validated Redis key for distributed lock."""
        if len(slug) > 256:
            raise ValueError(f"Slug too long for Redis lock key: {len(slug)}")
        return f"lock:{slug}"

    def _acquire_redis_lock(self, slug: str, task_id: str) -> None:
        """Acquire distributed lock via Redis SET NX EX.

        No stale detection — simply try to acquire. The 2h TTL handles
        dead workers. If the lock is held, raise TaskConflictError.
        """
        key = self._lock_key(slug)
        acquired = self._redis_sync.set(key, task_id, nx=True, ex=7200)
        if not acquired:
            raise TaskConflictError(
                f"A pipeline is already running for '{slug}'"
            )

    def release_slug_lock(self, slug: str) -> None:
        """Release a per-slug lock. Ownership-safe Redis delete + in-memory."""
        task_id = self._slug_locks.pop(slug, None)
        if self._redis_sync is not None and self._release_script is not None and task_id:
            try:
                self._release_script(
                    keys=[self._lock_key(slug)],
                    args=[task_id],
                )
            except Exception:
                logger.warning(
                    "Redis lock release failed for %s — TTL will expire",
                    slug,
                    exc_info=True,
                )

    # ── Task Handle Tracking ──────────────────────────────────────────

    def register_task_handle(self, task_id: str, handle: asyncio.Task) -> None:
        self._task_handles[task_id] = handle

    def cancel_task_handle(self, task_id: str) -> bool:
        handle = self._task_handles.pop(task_id, None)
        if handle and not handle.done():
            handle.cancel()
            return True
        return False

    def remove_task_handle(self, task_id: str) -> None:
        self._task_handles.pop(task_id, None)

    # ── HITL Approval ─────────────────────────────────────────────────

    async def wait_for_approval(
        self, task_id: str, timeout: float = 86400
    ) -> Dict[str, Any]:
        if self._redis_sync is not None:
            return await self._wait_for_approval_redis(task_id, timeout)
        # Fallback: existing asyncio.Queue logic
        if task_id not in self._approval_queues:
            self._approval_queues[task_id] = asyncio.Queue(maxsize=1)
        try:
            data = await asyncio.wait_for(
                self._approval_queues[task_id].get(), timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Approval timed out after %.0fs for task %s — auto-rejecting",
                timeout,
                task_id,
            )
            data = {
                "decision": "reject",
                "revision_note": f"Approval timed out after {int(timeout)}s",
            }
        self._approval_queues.pop(task_id, None)
        return data

    async def _wait_for_approval_redis(
        self, task_id: str, timeout: float
    ) -> Dict[str, Any]:
        """Block on Redis BRPOP until approval arrives or timeout expires."""
        key = f"approval:{task_id}"
        flag_key = f"approval:flag:{task_id}"
        nonce_key = f"approval:nonce:{task_id}"

        try:
            result = await asyncio.to_thread(
                self._redis_sync.brpop, key, timeout=max(1, int(timeout))
            )
        except Exception:
            logger.exception(
                "Redis BRPOP failed for task %s — falling back to reject", task_id
            )
            result = None

        if result is None:
            logger.warning(
                "Approval timed out after %.0fs for task %s — auto-rejecting",
                timeout,
                task_id,
            )
            data: Dict[str, Any] = {
                "decision": "reject",
                "revision_note": f"Approval timed out after {int(timeout)}s",
            }
        else:
            _, raw = result
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                logger.exception(
                    "Malformed approval payload for task %s — auto-rejecting", task_id
                )
                data = {
                    "decision": "reject",
                    "revision_note": "Malformed approval payload",
                }

        # Cleanup all approval keys
        try:
            self._redis_sync.delete(key, flag_key, nonce_key)
        except Exception:
            logger.warning(
                "Redis: failed to cleanup approval keys for %s",
                task_id,
                exc_info=True,
            )

        # Also clean local queue if it exists (hybrid safety)
        self._approval_queues.pop(task_id, None)

        return data

    def submit_approval(
        self,
        task_id: str,
        decision: str,
        revision_note: Optional[str] = None,
        stage: Optional[str] = None,
        approval_data: Optional[Dict[str, Any]] = None,
        expected_nonce: Optional[str] = None,
    ) -> None:
        if task_id not in self._tasks:
            raise TaskNotFoundError(task_id)

        task = self._tasks[task_id]

        # Nonce validation — Redis-first if available
        if expected_nonce is not None:
            if self._redis_sync is not None:
                try:
                    current_nonce = self._redis_sync.get(
                        f"approval:nonce:{task_id}"
                    )
                except Exception:
                    logger.warning(
                        "Redis nonce read failed for %s — falling back to local",
                        task_id,
                        exc_info=True,
                    )
                    current_nonce = (task.approval_payload or {}).get(
                        "checkpoint_nonce"
                    )
            else:
                current_nonce = (task.approval_payload or {}).get(
                    "checkpoint_nonce"
                )
            if current_nonce != expected_nonce:
                raise ApprovalWindowError(
                    f"Stale or replayed approval: nonce mismatch "
                    f"(expected {expected_nonce}, current {current_nonce})"
                )

        # Duplicate submission check — Redis flag (atomic SET NX)
        if self._redis_sync is not None:
            flag_key = f"approval:flag:{task_id}"
            try:
                was_set = self._redis_sync.set(flag_key, "1", nx=True, ex=86400)
                if not was_set:
                    raise ApprovalWindowError(
                        f"Approval already submitted for task {task_id}"
                    )
            except ApprovalWindowError:
                raise
            except Exception:
                logger.warning(
                    "Redis flag check failed for %s — proceeding",
                    task_id,
                    exc_info=True,
                )

        resolved_stage = (
            stage
            or (task.approval_payload or {}).get("stage")
            or task.current_step
            or "unknown"
        )
        record = ApprovalRecord(
            task_id=task_id,
            stage=resolved_stage,
            decision=decision,
            revision_note=revision_note,
        )
        task.approval_history.append(record)
        task.updated_at = datetime.now(timezone.utc)

        # Persist approval history to DB
        asyncio.create_task(
            self._db_update(
                task_id,
                approval_history=[r.model_dump(mode="json") for r in task.approval_history],
            )
        )

        # Queue the full approval data if provided, else generic payload
        payload = approval_data if approval_data is not None else {"decision": decision, "revision_note": revision_note}

        if self._redis_sync is not None:
            try:
                key = f"approval:{task_id}"
                self._redis_sync.lpush(key, json.dumps(payload))
                self._redis_sync.expire(key, 86400)
            except Exception:
                logger.exception("Redis LPUSH failed for task %s", task_id)
                # Clear the flag so the user can retry
                try:
                    self._redis_sync.delete(f"approval:flag:{task_id}")
                except Exception:
                    pass
        else:
            if task_id not in self._approval_queues:
                self._approval_queues[task_id] = asyncio.Queue(maxsize=1)
            try:
                self._approval_queues[task_id].put_nowait(payload)
            except asyncio.QueueFull:
                raise ApprovalWindowError(
                    f"Approval already submitted for task {task_id} — queue full"
                )

    # ── DB write-through helpers ──────────────────────────────────────

    async def _db_create(self, task: PipelineTask) -> None:
        """Insert a new task row into DB."""
        from core.db.repositories.task_repo import TaskRepository

        try:
            async with self._session_factory() as session:
                repo = TaskRepository(session)
                await repo.create_task(
                    task_id=task.task_id,
                    pipeline=task.pipeline,
                    status=task.status.value,
                    company_slug=task.company_slug,
                    product_slug=task.product_slug,
                    effective_slug=task.effective_slug,
                    current_step=task.current_step,
                    progress_pct=task.progress_pct,
                )
                await session.commit()
        except Exception:
            logger.exception("DbTaskStore: failed to persist create for %s", task.task_id)

    async def _db_update(self, task_id: str, **kwargs: Any) -> None:
        """Update a task row in DB."""
        from core.db.repositories.task_repo import TaskRepository

        # Convert TaskStatus enum to string for DB
        db_kwargs = {}
        for k, v in kwargs.items():
            if isinstance(v, TaskStatus):
                db_kwargs[k] = v.value
            else:
                db_kwargs[k] = v
        db_kwargs["updated_at"] = datetime.now(timezone.utc)

        try:
            async with self._session_factory() as session:
                repo = TaskRepository(session)
                await repo.update_by_task_id(task_id, **db_kwargs)
                await session.commit()
        except Exception:
            logger.exception("DbTaskStore: failed to persist update for %s", task_id)

    # ── Row → PipelineTask conversion ─────────────────────────────────

    @staticmethod
    def _row_to_pipeline_task(row: Any) -> PipelineTask:
        """Convert an ApiTaskModel ORM row to a PipelineTask Pydantic model."""
        return PipelineTask(
            task_id=row.task_id,
            pipeline=row.pipeline,
            status=TaskStatus(row.status),
            company_slug=row.company_slug or "",
            product_slug=row.product_slug,
            effective_slug=row.effective_slug,
            current_step=row.current_step,
            progress_pct=row.progress_pct,
            created_at=row.created_at,
            updated_at=row.updated_at,
            result=row.result,
            error=row.error,
            approval_payload=row.approval_payload,
            approval_history=[
                ApprovalRecord(**r) for r in (row.approval_history or [])
            ],
        )
