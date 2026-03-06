"""Tests for core.shared_tools.task_status — CX-1 architecture fix."""
from __future__ import annotations


class TestTaskStatus:
    """Verify TaskStatus enum is importable from core and re-exported by api."""

    def test_importable_from_core(self) -> None:
        from core.shared_tools.task_status import TaskStatus

        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.PENDING_APPROVAL.value == "pending_approval"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"
        assert TaskStatus.FAILED_RESTART.value == "failed_restart"

    def test_reexport_from_api_is_same_class(self) -> None:
        """api.tasks.models.TaskStatus re-exports the same class."""
        from api.tasks.models import TaskStatus as ApiTaskStatus
        from core.shared_tools.task_status import TaskStatus as CoreTaskStatus

        assert ApiTaskStatus is CoreTaskStatus
