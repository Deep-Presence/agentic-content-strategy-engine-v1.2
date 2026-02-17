"use client";

import { useEffect, useState } from "react";
import { Plus, RefreshCw } from "lucide-react";
import { useTaskStore } from "@/stores/taskStore";
import { TaskCard } from "@/components/pipeline/TaskCard";
import { NewPipelineDialog } from "@/components/pipeline/NewPipelineDialog";
import { cn } from "@/lib/utils";

const PIPELINE_FILTERS = [
  { value: "", label: "All Pipelines" },
  { value: "research", label: "Research" },
  { value: "gap_analysis", label: "Gap Analysis" },
  { value: "content", label: "Content" },
];

const STATUS_FILTERS = [
  { value: "", label: "All Statuses" },
  { value: "running", label: "Running" },
  { value: "pending_approval", label: "Pending Approval" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
];

export default function DashboardPage() {
  const { tasks, isLoading, error, fetchTasks } = useTaskStore();
  const [pipelineFilter, setPipelineFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);

  useEffect(() => {
    fetchTasks(pipelineFilter || undefined, statusFilter || undefined);
  }, [pipelineFilter, statusFilter]);

  const handleRefresh = () => {
    fetchTasks(pipelineFilter || undefined, statusFilter || undefined);
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-[2.25rem] text-ink tracking-tight leading-tight">
            Dashboard
          </h1>
          <p className="text-ink-secondary mt-2 text-[0.9375rem]">
            Pipeline runs, status, and task management.
          </p>
        </div>
        <button
          onClick={() => setDialogOpen(true)}
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-terracotta-500 text-white font-body font-semibold text-[0.875rem] hover:bg-terracotta-600 transition-colors"
        >
          <Plus size={16} />
          New Pipeline
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mt-6">
        {PIPELINE_FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setPipelineFilter(f.value)}
            className={cn(
              "px-3 py-1.5 rounded-md font-mono text-[0.75rem] transition-colors",
              pipelineFilter === f.value
                ? "bg-terracotta-50 text-terracotta-700 font-medium"
                : "text-ink-secondary hover:text-ink hover:bg-canvas-subtle",
            )}
          >
            {f.label}
          </button>
        ))}

        <div className="w-px h-5 bg-canvas-muted mx-1" />

        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setStatusFilter(f.value)}
            className={cn(
              "px-3 py-1.5 rounded-md font-mono text-[0.75rem] transition-colors",
              statusFilter === f.value
                ? "bg-terracotta-50 text-terracotta-700 font-medium"
                : "text-ink-secondary hover:text-ink hover:bg-canvas-subtle",
            )}
          >
            {f.label}
          </button>
        ))}

        <button
          onClick={handleRefresh}
          className="ml-auto p-2 rounded-lg text-ink-tertiary hover:text-ink hover:bg-canvas-subtle transition-colors"
          title="Refresh"
        >
          <RefreshCw size={16} className={isLoading ? "animate-spin" : ""} />
        </button>
      </div>

      {/* Task list */}
      <div className="mt-6 space-y-2">
        {error && (
          <div className="rounded-xl border border-status-failed/20 bg-red-50 p-4 text-center">
            <p className="font-mono text-[0.8125rem] text-status-failed">{error}</p>
          </div>
        )}

        {isLoading && tasks.length === 0 && (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="flex items-center gap-4 px-5 py-4 rounded-xl border border-canvas-muted bg-canvas"
              >
                <div className="w-9 h-9 rounded-lg bg-canvas-muted animate-pulse" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 w-32 rounded bg-canvas-muted animate-pulse" />
                  <div className="h-3 w-48 rounded bg-canvas-muted animate-pulse" />
                </div>
                <div className="h-6 w-20 rounded-full bg-canvas-muted animate-pulse" />
              </div>
            ))}
          </div>
        )}

        {!isLoading && tasks.length === 0 && !error && (
          <div className="rounded-xl border border-canvas-muted bg-canvas-subtle p-12 text-center">
            <p className="font-display text-[1.25rem] text-ink-secondary">
              No pipeline runs yet
            </p>
            <p className="font-body text-[0.875rem] text-ink-tertiary mt-2">
              Click &quot;New Pipeline&quot; to get started.
            </p>
          </div>
        )}

        {tasks.map((task) => (
          <TaskCard key={task.run_id} task={task} onCancel={handleRefresh} />
        ))}
      </div>

      {/* New Pipeline Dialog */}
      <NewPipelineDialog isOpen={dialogOpen} onClose={() => setDialogOpen(false)} />
    </div>
  );
}
