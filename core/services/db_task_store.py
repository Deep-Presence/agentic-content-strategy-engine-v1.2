"""DB-backed TaskStore with write-through in-memory cache.

Satisfies TaskStoreProtocol. Uses a session_factory (not request-scoped)
for per-operation sessions. Process-local state (semaphore, queues, handles,
slug locks) stays in-memory only.

Durability guarantees (Session 3):
- ``create_task()`` + ``ensure_created()`` — DB INSERT awaited before
  returning task_id to client. Process crash after create → task survives.
- Terminal ``update_task()`` + ``flush_terminal()`` — DB UPDATE awaited
  before runner cleanup. Process crash after terminal → correct status in DB.
- ``drain_pending()`` — graceful shutdown drains all pending writes.
- ``recover_from_db()`` — scoped to this worker's tasks (worker_id).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.tasks.models import ApprovalRecord, PipelineTask
from core.shared_tools.task_status import TaskStatus
from core.services.task_store import ApprovalDeliveryError, ApprovalWindowError, TaskConflictError, TaskNotFoundError

logger = logging.getLogger(__name__)


def _generate_worker_id() -> str:
    """Unique per-process worker ID: hostname:pid."""
    return f"{socket.gethostname()}:{os.getpid()}"


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

    # Lua script: ownership-safe lock TTL renewal (compare-and-expire)
    # Atomic: prevents race where lock expires between GET and EXPIRE.
    _RENEW_LOCK_LUA = """\
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("EXPIRE", KEYS[1], ARGV[2])
else
    return 0
end
"""

    # Heartbeat interval: renew leases every ~60 BRPOP iterations (~60s)
    _LEASE_RENEWAL_INTERVAL = 60

    def __init__(
        self,
        session_factory: Callable[..., AsyncSession],
        max_concurrent: int = 10,
        redis_client: Optional[Any] = None,
        worker_id: Optional[str] = None,
    ) -> None:
        self._tasks: Dict[str, PipelineTask] = {}
        self._session_factory = session_factory
        self._slug_locks: Dict[str, str] = {}  # "pipeline:effective_slug" -> task_id
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._approval_queues: Dict[str, asyncio.Queue] = {}
        self._task_handles: Dict[str, asyncio.Task] = {}
        self._max_concurrent = max_concurrent
        self._worker_id = worker_id or _generate_worker_id()
        # Pending DB writes for durability (Session 3 — Fix 1d)
        self._pending_creates: Dict[str, asyncio.Task] = {}
        self._pending_terminals: Dict[str, asyncio.Task] = {}
        # Redis for distributed slug locks (sync client, sub-ms ops)
        self._redis_sync = redis_client
        self._release_script = (
            redis_client.register_script(self._RELEASE_LOCK_LUA)
            if redis_client is not None
            else None
        )
        self._renew_lock_script = (
            redis_client.register_script(self._RENEW_LOCK_LUA)
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
        """Load non-terminal tasks and mark THIS worker's orphans as failed_restart.

        Called once at app startup. Instance-aware: only marks tasks belonging
        to this worker_id (+ legacy NULL worker_id rows) as failed. Other
        workers' running tasks are left untouched.

        Falls back to blanket orphan recovery if the worker_id column hasn't
        been migrated yet (migration 0022).

        Returns the number of orphans recovered.
        """
        from sqlalchemy.exc import ProgrammingError

        from core.db.repositories.task_repo import TaskRepository

        async with self._session_factory() as session:
            repo = TaskRepository(session)
            try:
                orphan_count, orphan_task_ids = await repo.mark_worker_orphans_failed(
                    self._worker_id
                )
            except ProgrammingError:
                # worker_id column not yet migrated — roll back the failed
                # statement and fall back to blanket (non-scoped) recovery.
                await session.rollback()
                logger.warning(
                    "worker_id column missing — falling back to blanket "
                    "orphan recovery. Run migration 0022 to enable "
                    "multi-worker scoped recovery."
                )
                orphan_count = await repo.mark_orphans_failed()
                orphan_task_ids = []

            # Load all tasks into memory cache (not just this worker's —
            # needed for cross-worker lock status checks)
            all_tasks = await repo.list_tasks()
            for row in all_tasks:
                task = self._row_to_pipeline_task(row)
                self._tasks[task.task_id] = task

            await session.commit()

        # Clean up orphaned Redis locks (checks task status in _tasks)
        orphan_locks_cleaned = 0
        semaphore_cleared = 0
        if self._redis_sync is not None:
            try:
                orphan_locks_cleaned = self._cleanup_orphan_locks()
            except Exception:
                logger.warning("Failed to clean orphan Redis locks", exc_info=True)
            # Scoped semaphore cleanup: only remove THIS worker's orphaned
            # task_ids (replaces blanket force_clear for multi-worker safety)
            if self._redis_semaphore is not None and orphan_task_ids:
                try:
                    semaphore_cleared = self._cleanup_semaphore_entries(
                        orphan_task_ids
                    )
                except Exception:
                    logger.warning(
                        "Failed to clear stale semaphore entries", exc_info=True
                    )

        logger.info(
            "DbTaskStore[%s] recovered: %d tasks loaded, %d orphans marked "
            "failed_restart, %d orphan Redis locks cleaned, "
            "%d stale semaphore entries cleared",
            self._worker_id,
            len(self._tasks),
            orphan_count,
            orphan_locks_cleaned,
            semaphore_cleared,
        )
        return orphan_count

    def _cleanup_semaphore_entries(self, task_ids: list[str]) -> int:
        """Remove specific task_ids from the pipeline semaphore.

        Used during startup recovery to clean only THIS worker's orphaned
        slots, leaving other workers' legitimate entries intact.
        """
        if not task_ids:
            return 0
        cleaned = 0
        for tid in task_ids:
            try:
                self._redis_semaphore.release(tid)
                cleaned += 1
            except Exception:
                logger.warning(
                    "Failed to release semaphore for %s", tid, exc_info=True
                )
        return cleaned

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

        # Schedule DB INSERT — caller MUST await ensure_created() before
        # returning task_id to client (durability guarantee).
        self._pending_creates[task_id] = asyncio.create_task(self._db_create(task))
        return task

    async def ensure_created(self, task_id: str) -> None:
        """Await the DB INSERT for a recently created task.

        Called by routers immediately after ``create_task()`` to guarantee the
        task_id returned to the client survives a process restart.
        Raises if the DB write failed — caller should roll back via
        ``rollback_create()``.
        """
        pending = self._pending_creates.pop(task_id, None)
        if pending is not None:
            await pending  # Re-raises if _db_create failed

    def rollback_create(self, task_id: str) -> None:
        """Undo an in-memory create when DB persistence fails.

        Removes the task from memory and releases the slug lock so the
        pipeline slot is not permanently consumed.
        """
        task = self._tasks.pop(task_id, None)
        if task:
            effective = task.effective_slug or task.company_slug
            lock_key = f"{task.pipeline}:{effective}"
            self.release_slug_lock(lock_key)
        self._pending_creates.pop(task_id, None)

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

        # Schedule DB write. Terminal status changes are tracked so runners
        # can await them via flush_terminal() before cleanup.
        status_val = kwargs.get("status")
        is_terminal = isinstance(status_val, TaskStatus) and status_val in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.FAILED_RESTART,
        )

        db_task = asyncio.create_task(self._db_update(task_id, **kwargs))
        if is_terminal:
            self._pending_terminals[task_id] = db_task
        return task

    async def flush_terminal(self, task_id: str) -> None:
        """Await DB persistence of a terminal status change.

        Called by runners in their finally blocks to guarantee the terminal
        status persists before the asyncio.Task completes. Swallows exceptions
        (best-effort) so cleanup continues even if DB is down.
        """
        pending = self._pending_terminals.pop(task_id, None)
        if pending is not None:
            try:
                await pending
            except Exception:
                logger.exception(
                    "DbTaskStore: terminal flush failed for %s — "
                    "task may show as running after restart",
                    task_id,
                )

    async def drain_pending(self) -> None:
        """Await all pending DB writes. Called during graceful shutdown."""
        tasks = list(self._pending_creates.values()) + list(self._pending_terminals.values())
        if tasks:
            logger.info("Draining %d pending DB writes...", len(tasks))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    logger.warning("Pending write failed during drain: %s", r)
        self._pending_creates.clear()
        self._pending_terminals.clear()

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
        """Poll Redis BRPOP in short intervals until approval arrives or timeout expires.

        Uses 1s BRPOP intervals to stay within the sync client's socket_timeout
        and to remain cancellable via asyncio.

        On persistent Redis failure (10 consecutive errors), falls back to an
        asyncio.Queue so the frontend can still deliver approvals via the
        in-memory path rather than silently auto-rejecting.
        """
        key = f"approval:{task_id}"
        flag_key = f"approval:flag:{task_id}"
        nonce_key = f"approval:nonce:{task_id}"

        import time

        _MAX_CONSECUTIVE_ERRORS = 10
        deadline = time.monotonic() + timeout
        result = None
        consecutive_errors = 0
        redis_gave_up = False
        iterations_since_heartbeat = 0
        while time.monotonic() < deadline:
            # Periodic lease renewal (~every 60s)
            iterations_since_heartbeat += 1
            if iterations_since_heartbeat >= self._LEASE_RENEWAL_INTERVAL:
                iterations_since_heartbeat = 0
                try:
                    await asyncio.to_thread(self._renew_leases, task_id)
                except Exception:
                    logger.warning(
                        "Heartbeat: renewal call failed for %s",
                        task_id,
                        exc_info=True,
                    )

            try:
                result = await asyncio.to_thread(
                    self._redis_sync.brpop, key, timeout=1
                )
                consecutive_errors = 0  # reset on success (incl. None = no item)
                if result is not None:
                    break
            except Exception:
                consecutive_errors += 1
                if consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                    logger.exception(
                        "Redis BRPOP failed %d times for task %s — falling back to Queue",
                        consecutive_errors,
                        task_id,
                    )
                    redis_gave_up = True
                    break
                backoff = min(2 ** (consecutive_errors - 1), 10)
                logger.warning(
                    "Redis BRPOP transient error for task %s (attempt %d) — retrying in %.0fs",
                    task_id,
                    consecutive_errors,
                    backoff,
                )
                await asyncio.sleep(backoff)

        if redis_gave_up:
            # Fall back to asyncio.Queue — frontend submit_approval() also
            # pushes to the in-memory queue as a hybrid safety net.
            logger.info(
                "BRPOP fallback: waiting on asyncio.Queue for task %s", task_id
            )
            if task_id not in self._approval_queues:
                self._approval_queues[task_id] = asyncio.Queue(maxsize=1)
            remaining = max(1.0, deadline - time.monotonic())
            try:
                data = await asyncio.wait_for(
                    self._approval_queues[task_id].get(), timeout=remaining
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
        elif result is None:
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

    def _renew_leases(self, task_id: str) -> None:
        """Renew TTL on slug lock and semaphore during HITL wait.

        Called every ~60s from the BRPOP polling loop. All operations are
        best-effort: failures are logged but never abort the wait.
        """
        task = self._tasks.get(task_id)
        if task is None or self._redis_sync is None:
            return

        effective = task.effective_slug or task.company_slug

        # 1. Slug lock — atomic compare-and-expire (skip if allow_parallel / no lock)
        lock_slug = f"{task.pipeline}:{effective}"
        if lock_slug in self._slug_locks and self._renew_lock_script is not None:
            lock_key = self._lock_key(lock_slug)
            try:
                renewed = self._renew_lock_script(
                    keys=[lock_key],
                    args=[task_id, 7200],
                )
                if renewed:
                    logger.debug("Heartbeat: renewed lock %s", lock_key)
                else:
                    logger.warning(
                        "Heartbeat: lock ownership lost %s (task=%s)",
                        lock_key, task_id,
                    )
            except Exception:
                logger.warning(
                    "Heartbeat: lock renewal failed %s", lock_key, exc_info=True
                )

        # 2. Semaphore — atomic Lua renewal (ZSCORE + ZADD)
        if self._redis_semaphore is not None:
            try:
                renewed = self._redis_semaphore.renew(task_id)
                if renewed:
                    logger.debug("Heartbeat: renewed semaphore for %s", task_id)
                else:
                    logger.warning(
                        "Heartbeat: semaphore slot missing for %s", task_id
                    )
            except Exception:
                logger.warning(
                    "Heartbeat: semaphore renewal failed %s",
                    task_id,
                    exc_info=True,
                )

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

        # Construct payload BEFORE delivery attempt
        payload = approval_data if approval_data is not None else {"decision": decision, "revision_note": revision_note}

        # ── Deliver payload (must succeed before recording history) ──
        if self._redis_sync is not None:
            key = f"approval:{task_id}"
            try:
                self._redis_sync.lpush(key, json.dumps(payload))
            except Exception:
                logger.exception(
                    "Redis LPUSH failed for task %s — clearing flag for retry",
                    task_id,
                )
                try:
                    self._redis_sync.delete(f"approval:flag:{task_id}")
                except Exception:
                    pass
                raise ApprovalDeliveryError(task_id)
            # LPUSH succeeded — EXPIRE is best-effort (non-fatal)
            try:
                self._redis_sync.expire(key, 86400)
            except Exception:
                logger.warning(
                    "Redis EXPIRE failed for approval:%s (non-fatal)", task_id
                )
            # Hybrid safety net: also push to local queue so BRPOP→Queue
            # fallback path can still receive the payload (CX-3).
            if task_id not in self._approval_queues:
                self._approval_queues[task_id] = asyncio.Queue(maxsize=1)
            try:
                self._approval_queues[task_id].put_nowait(payload)
            except asyncio.QueueFull:
                pass  # BRPOP path will handle it
        else:
            if task_id not in self._approval_queues:
                self._approval_queues[task_id] = asyncio.Queue(maxsize=1)
            try:
                self._approval_queues[task_id].put_nowait(payload)
            except asyncio.QueueFull:
                raise ApprovalWindowError(
                    f"Approval already submitted for task {task_id} — queue full"
                )

        # ── Record approval history (only after successful delivery) ──
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

    # ── DB write-through helpers ──────────────────────────────────────

    async def _db_create(self, task: PipelineTask) -> None:
        """Insert a new task row into DB.

        Exceptions propagate to ``ensure_created()`` — the caller decides
        whether to abort (HTTP 503) or proceed.
        """
        from core.db.repositories.task_repo import TaskRepository

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
                worker_id=self._worker_id,
            )
            await session.commit()

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
