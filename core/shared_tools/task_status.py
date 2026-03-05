"""TaskStatus enum — shared across core/ and api/ layers.

Moved from api.tasks.models to resolve core/ → api/ architecture violation.
All core/ modules should import from here; api/ re-exports for backward compat.
"""
from __future__ import annotations

from enum import Enum


class TaskStatus(str, Enum):
    RUNNING = "running"
    PENDING_APPROVAL = "pending_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    FAILED_RESTART = "failed_restart"
