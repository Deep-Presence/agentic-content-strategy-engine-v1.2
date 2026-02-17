"use client";

import Link from "next/link";
import { Search, BarChart3, FileText, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { StatusBadge } from "./StatusBadge";
import { PIPELINE_LABELS } from "@/lib/constants";
import { cancelTask } from "@/lib/api";
import type { TaskSummary, PipelineType } from "@/types/api";

const PIPELINE_ICONS: Record<PipelineType, typeof Search> = {
  research: Search,
  gap_analysis: BarChart3,
  content: FileText,
};

const PIPELINE_ROUTES: Record<PipelineType, string> = {
  research: "/research",
  gap_analysis: "/gap-analysis",
  content: "/content",
};

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

interface TaskCardProps {
  task: TaskSummary;
  onCancel?: () => void;
}

export function TaskCard({ task, onCancel }: TaskCardProps) {
  const Icon = PIPELINE_ICONS[task.pipeline] || FileText;
  const route = PIPELINE_ROUTES[task.pipeline] || "/";
  const canCancel = task.status === "running" || task.status === "pending_approval";

  const handleCancel = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm("Cancel this pipeline run?")) return;
    try {
      await cancelTask(task.run_id);
      onCancel?.();
    } catch (err: any) {
      alert(err.detail || "Failed to cancel task");
    }
  };

  return (
    <Link
      href={`${route}?task=${task.run_id}`}
      className="flex items-center gap-4 px-5 py-4 rounded-xl border border-canvas-muted bg-canvas hover:bg-canvas-subtle transition-colors duration-150 group"
    >
      {/* Pipeline icon */}
      <div className="w-9 h-9 rounded-lg bg-terracotta-50 flex items-center justify-center flex-shrink-0">
        <Icon size={18} className="text-terracotta-500" />
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-body font-semibold text-[0.9375rem] text-ink truncate">
            {task.company_slug}
          </span>
          <span className="font-mono text-[0.6875rem] text-ink-tertiary">
            {PIPELINE_LABELS[task.pipeline]}
          </span>
        </div>
        {task.current_step && (
          <p className="font-mono text-[0.75rem] text-ink-secondary mt-0.5 truncate">
            {task.current_step}
          </p>
        )}
      </div>

      {/* Status badge */}
      <StatusBadge status={task.status} />

      {/* Timestamp */}
      <span className="font-mono text-[0.6875rem] text-ink-tertiary whitespace-nowrap">
        {timeAgo(task.updated_at)}
      </span>

      {/* Cancel button */}
      {canCancel && (
        <button
          onClick={handleCancel}
          className="p-1.5 rounded-md opacity-0 group-hover:opacity-100 hover:bg-canvas-muted transition-all text-ink-tertiary hover:text-status-failed"
          title="Cancel task"
        >
          <X size={14} />
        </button>
      )}
    </Link>
  );
}
