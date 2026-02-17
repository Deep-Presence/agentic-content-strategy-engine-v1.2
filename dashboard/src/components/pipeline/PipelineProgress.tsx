"use client";

import { cn } from "@/lib/utils";
import { Check } from "lucide-react";
import type { TaskStatus } from "@/types/api";

interface Stage {
  name: string;
  label: string;
}

interface PipelineProgressProps {
  stages: Stage[];
  currentStep: string | null;
  status: TaskStatus | null;
  statusText?: string;
}

function getStageState(
  stage: Stage,
  currentStep: string | null,
  stages: Stage[],
): "inactive" | "active" | "complete" {
  if (!currentStep) return "inactive";

  // Check if this stage is marked as done
  if (currentStep === `${stage.name}_done`) return "complete";

  // Find indices
  const stageIdx = stages.findIndex((s) => s.name === stage.name);
  const currentIdx = stages.findIndex(
    (s) => s.name === currentStep || currentStep === `${s.name}_done`,
  );

  // If current step's done variant is found, that stage and all before are complete
  const doneIdx = stages.findIndex(
    (s) => currentStep === `${s.name}_done`,
  );
  if (doneIdx >= 0 && stageIdx <= doneIdx) return "complete";

  // If current step matches this stage, it's active
  if (currentStep === stage.name) return "active";

  // If this stage is before the current step, it's complete
  if (currentIdx >= 0 && stageIdx < currentIdx) return "complete";

  return "inactive";
}

export function PipelineProgress({
  stages,
  currentStep,
  status,
  statusText,
}: PipelineProgressProps) {
  const isRunning = status === "running";
  const isComplete = status === "completed";
  const isFailed = status === "failed";

  // Calculate progress percentage
  const completedCount = stages.filter(
    (s) => getStageState(s, currentStep, stages) === "complete",
  ).length;
  const activeCount = stages.filter(
    (s) => getStageState(s, currentStep, stages) === "active",
  ).length;
  const progressPct = isComplete
    ? 100
    : ((completedCount + activeCount * 0.5) / stages.length) * 100;

  return (
    <div className="space-y-4">
      {/* Progress bar */}
      <div className="relative h-1.5 rounded-full bg-canvas-muted overflow-hidden">
        <div
          className={cn(
            "absolute inset-y-0 left-0 rounded-full transition-all duration-500 ease-out",
            isComplete
              ? "bg-sage"
              : isFailed
                ? "bg-status-failed"
                : "bg-gradient-to-r from-terracotta-400 to-terracotta-600",
          )}
          style={{ width: `${progressPct}%` }}
        />
        {/* Shimmer overlay while running */}
        {isRunning && (
          <div
            className="absolute inset-y-0 left-0 overflow-hidden rounded-full"
            style={{ width: `${progressPct}%` }}
          >
            <div
              className="absolute inset-0 bg-gradient-to-r from-transparent via-white/25 to-transparent"
              style={{ animation: "shimmer 1.5s infinite" }}
            />
          </div>
        )}
      </div>

      {/* Stage dots */}
      <div className="flex items-center justify-between">
        {stages.map((stage, idx) => {
          const state = isComplete
            ? "complete"
            : getStageState(stage, currentStep, stages);

          return (
            <div key={stage.name} className="flex items-center flex-1">
              {/* Dot */}
              <div className="flex flex-col items-center gap-1.5">
                <div
                  className={cn(
                    "w-7 h-7 rounded-full flex items-center justify-center transition-all duration-300",
                    state === "complete" && "bg-sage text-white",
                    state === "active" && "bg-terracotta-500 text-white",
                    state === "inactive" && "bg-canvas-muted text-ink-tertiary",
                    state === "active" && "shadow-[0_0_0_4px_rgba(201,107,48,0.15)]",
                  )}
                  style={
                    state === "active"
                      ? { animation: "pulse-ring 2s ease-out infinite" }
                      : undefined
                  }
                >
                  {state === "complete" ? (
                    <Check size={14} strokeWidth={2.5} />
                  ) : (
                    <span className="text-[0.625rem] font-mono font-medium">
                      {idx + 1}
                    </span>
                  )}
                </div>
                <span
                  className={cn(
                    "text-[0.6875rem] font-mono whitespace-nowrap",
                    state === "active"
                      ? "text-terracotta-600 font-medium"
                      : state === "complete"
                        ? "text-sage"
                        : "text-ink-tertiary",
                  )}
                >
                  {stage.label}
                </span>
              </div>

              {/* Connecting line */}
              {idx < stages.length - 1 && (
                <div
                  className={cn(
                    "flex-1 h-px mx-2 mt-[-1rem]",
                    state === "complete" ? "bg-sage" : "bg-canvas-muted",
                  )}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Status text */}
      {statusText && (
        <p className="text-[0.8125rem] font-mono text-ink-secondary">
          {statusText}
        </p>
      )}
    </div>
  );
}
