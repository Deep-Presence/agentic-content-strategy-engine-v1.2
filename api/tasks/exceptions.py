"""Task-related exception classes.

These were originally defined in api.tasks.store. Moved here so they
can survive the deletion of the JSON TaskStore without breaking the
import chain used by api/exceptions.py, api/app.py, core/services/task_store.py,
and core/services/db_task_store.py.
"""
from __future__ import annotations


class TaskNotFoundError(Exception):
    """Raised when a task ID is not found."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"Task not found: {task_id}")


class TaskConflictError(Exception):
    """Raised when a conflicting operation is attempted (e.g., same slug running)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ApprovalWindowError(Exception):
    """Raised when an approval is submitted outside the valid window.

    Covers: stale nonce (TOCTOU/replay), or queue already consumed (duplicate).
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ApprovalDeliveryError(Exception):
    """Raised when the approval payload could not be delivered to the pipeline.

    The duplicate flag has been cleared so the caller can retry.
    Maps to HTTP 503 (Service Unavailable) at the router layer.
    """

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(
            f"Approval delivery failed for task {task_id} — please retry"
        )
