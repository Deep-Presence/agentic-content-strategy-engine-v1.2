"use client";

import { cn } from "@/lib/utils";
import { STATUS_COLORS } from "@/lib/constants";
import type { TaskStatus } from "@/types/api";

const STATUS_LABELS: Record<TaskStatus, string> = {
  running: "Running",
  pending_approval: "Pending Approval",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
  failed_restart: "Interrupted",
};

export function StatusBadge({ status }: { status: TaskStatus }) {
  const colors = STATUS_COLORS[status] || STATUS_COLORS.cancelled;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[0.75rem] font-mono font-medium",
        colors.bg,
        colors.text,
      )}
    >
      <span className={cn("w-1.5 h-1.5 rounded-full", colors.dot)} />
      {STATUS_LABELS[status] || status}
    </span>
  );
}
