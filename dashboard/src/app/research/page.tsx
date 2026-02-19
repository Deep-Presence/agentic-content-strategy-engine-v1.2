"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { startResearch, getTaskDetail, ApiError } from "@/lib/api";
import { useTaskStore } from "@/stores/taskStore";
import { useArtifactStore } from "@/stores/artifactStore";
import { useTaskStream } from "@/hooks/useTaskStream";
import { PipelineProgress } from "@/components/pipeline/PipelineProgress";
import { StatusBadge } from "@/components/pipeline/StatusBadge";
import { RESEARCH_STAGES } from "@/lib/constants";
import type { TaskResponse, ResearchStage } from "@/types/api";

type PageState = "idle" | "running" | "complete" | "failed";

export default function ResearchPage() {
  return (
    <Suspense>
      <ResearchPageInner />
    </Suspense>
  );
}

function ResearchPageInner() {
  const searchParams = useSearchParams();
  const taskIdParam = searchParams.get("task");

  const { liveStatus, liveStep, liveError, approvalPayload } = useTaskStore();
  const { openApproval } = useArtifactStore();

  const [taskId, setTaskId] = useState<string | null>(taskIdParam);
  const [pageState, setPageState] = useState<PageState>(taskIdParam ? "running" : "idle");
  const [completedTask, setCompletedTask] = useState<TaskResponse | null>(null);

  // Form state
  const [companyName, setCompanyName] = useState("");
  const [domain, setDomain] = useState("");
  const [stages, setStages] = useState<ResearchStage[]>(["company", "persona", "style_guide"]);
  const [autoApprove, setAutoApprove] = useState(false);
  const [additionalConstraints, setAdditionalConstraints] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // SSE streaming
  useTaskStream(taskId, "research");

  // React to SSE status changes — only when we have an active task
  useEffect(() => {
    if (!taskId) return;
    if (liveStatus === "completed") {
      setPageState("complete");
      if (taskId) {
        getTaskDetail(taskId).then(setCompletedTask).catch(console.error);
      }
    } else if (liveStatus === "failed" || liveStatus === "cancelled") {
      setPageState("failed");
    } else if (liveStatus === "running" || liveStatus === "pending_approval") {
      setPageState("running");
    }
  }, [liveStatus, taskId]);

  // If task ID from URL, fetch its status
  useEffect(() => {
    if (taskIdParam) {
      getTaskDetail(taskIdParam).then((task) => {
        if (task.status === "completed") {
          setPageState("complete");
          setCompletedTask(task);
        } else if (task.status === "failed" || task.status === "cancelled" || task.status === "failed_restart") {
          setPageState("failed");
        } else {
          setPageState("running");
        }
      }).catch((err) => {
        console.error("Failed to fetch task:", err);
        setPageState("idle");
      });
    }
  }, [taskIdParam]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!companyName.trim() || !domain.trim()) return;

    setIsSubmitting(true);
    setFormError(null);

    try {
      const res = await startResearch({
        company_name: companyName,
        domain,
        stages,
        auto_approve: autoApprove,
        additional_constraints: additionalConstraints || undefined,
      });
      setTaskId(res.run_id);
      setPageState("running");
      window.history.replaceState(null, "", `/research?task=${res.run_id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        setFormError(err.detail);
      } else {
        setFormError("Failed to start research pipeline");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleStageToggle = (stage: ResearchStage) => {
    setStages((prev) =>
      prev.includes(stage) ? prev.filter((s) => s !== stage) : [...prev, stage],
    );
  };

  const getStatusText = (): string => {
    if (!liveStep) return "Starting...";
    const stage = RESEARCH_STAGES.find((s) => s.name === liveStep);
    if (stage) return `Researching ${stage.label}...`;
    if (liveStep.endsWith("_done")) {
      const doneName = liveStep.replace("_done", "");
      const doneStage = RESEARCH_STAGES.find((s) => s.name === doneName);
      return doneStage ? `${doneStage.label} complete` : liveStep;
    }
    return liveStep;
  };

  const handleReset = () => {
    setTaskId(null);
    setPageState("idle");
    setCompletedTask(null);
    setCompanyName("");
    setDomain("");
    setFormError(null);
    window.history.replaceState(null, "", "/research");
  };

  return (
    <div>
      <h1 className="font-display text-[2.25rem] text-ink tracking-tight leading-tight">
        Research Pipeline
      </h1>
      <p className="text-ink-secondary mt-2 text-[0.9375rem]">
        Company context, audience personas, and writing style guides.
      </p>

      {/* Idle — Show form */}
      {pageState === "idle" && (
        <form onSubmit={handleSubmit} className="mt-8 max-w-lg space-y-5">
          <div>
            <label className="block font-mono text-[0.75rem] text-ink-secondary mb-1.5 uppercase tracking-wider">
              Company Name *
            </label>
            <input
              type="text"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="e.g., Ramp"
              required
              className="w-full px-3 py-2.5 rounded-lg border border-canvas-muted bg-canvas font-body text-[0.9375rem] text-ink placeholder:text-ink-tertiary focus:outline-none focus:ring-2 focus:ring-terracotta-300"
            />
          </div>

          <div>
            <label className="block font-mono text-[0.75rem] text-ink-secondary mb-1.5 uppercase tracking-wider">
              Domain *
            </label>
            <input
              type="text"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="e.g., ramp.com"
              required
              className="w-full px-3 py-2.5 rounded-lg border border-canvas-muted bg-canvas font-body text-[0.9375rem] text-ink placeholder:text-ink-tertiary focus:outline-none focus:ring-2 focus:ring-terracotta-300"
            />
          </div>

          <div>
            <label className="block font-mono text-[0.75rem] text-ink-secondary mb-2 uppercase tracking-wider">
              Stages
            </label>
            <div className="flex gap-3">
              {(["company", "persona", "style_guide"] as ResearchStage[]).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => handleStageToggle(s)}
                  className={cn(
                    "px-3 py-2 rounded-lg text-[0.8125rem] font-mono border transition-colors",
                    stages.includes(s)
                      ? "bg-terracotta-50 border-terracotta-300 text-terracotta-700"
                      : "bg-canvas border-canvas-muted text-ink-tertiary hover:text-ink",
                  )}
                >
                  {s === "company" ? "Company" : s === "persona" ? "Persona" : "Style Guide"}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="auto-approve"
              checked={autoApprove}
              onChange={(e) => setAutoApprove(e.target.checked)}
              className="w-4 h-4 rounded border-canvas-muted accent-terracotta-500"
            />
            <label htmlFor="auto-approve" className="font-body text-[0.875rem] text-ink-secondary">
              Auto-approve all stages (skip HITL review)
            </label>
          </div>

          <div>
            <label className="block font-mono text-[0.75rem] text-ink-secondary mb-1.5 uppercase tracking-wider">
              Additional Constraints
            </label>
            <textarea
              value={additionalConstraints}
              onChange={(e) => setAdditionalConstraints(e.target.value)}
              placeholder="Optional: extra instructions for the research agents..."
              rows={3}
              className="w-full px-3 py-2.5 rounded-lg border border-canvas-muted bg-canvas font-body text-[0.875rem] text-ink placeholder:text-ink-tertiary focus:outline-none focus:ring-2 focus:ring-terracotta-300 resize-none"
            />
          </div>

          {formError && (
            <p className="font-mono text-[0.8125rem] text-status-failed bg-red-50 px-3 py-2 rounded-lg">
              {formError}
            </p>
          )}

          <button
            type="submit"
            disabled={isSubmitting || !companyName.trim() || !domain.trim()}
            className={cn(
              "w-full px-6 py-3 rounded-lg font-body font-semibold text-[0.9375rem] transition-colors",
              "bg-terracotta-500 text-white hover:bg-terracotta-600",
              "disabled:opacity-50 disabled:cursor-not-allowed",
            )}
          >
            {isSubmitting ? "Starting Research..." : "Start Research Pipeline"}
          </button>
        </form>
      )}

      {/* Running — Show progress */}
      {pageState === "running" && (
        <div className="mt-8 max-w-2xl">
          <div className="rounded-xl border border-canvas-muted bg-canvas-subtle p-6">
            {liveStatus && <StatusBadge status={liveStatus} />}
            <div className="mt-4">
              <PipelineProgress
                stages={[...RESEARCH_STAGES]}
                currentStep={liveStep}
                status={liveStatus}
                statusText={getStatusText()}
              />
            </div>
            {liveStatus === "pending_approval" && (
              <button
                onClick={() => {
                  if (approvalPayload && taskId) {
                    openApproval(approvalPayload, taskId, "research");
                  }
                }}
                className="mt-4 w-full text-left p-4 rounded-lg border border-clay/30 bg-clay-light/50 hover:bg-clay-light transition-colors group"
              >
                <div className="flex items-center gap-3">
                  <div className="w-3 h-3 rounded-full bg-clay animate-pulse" />
                  <div>
                    <p className="font-body text-[0.875rem] font-medium text-ink">
                      Draft ready for review
                    </p>
                    <p className="font-mono text-[0.75rem] text-ink-secondary mt-0.5">
                      {(() => {
                        const stage = RESEARCH_STAGES.find((s) => s.name === liveStep);
                        return stage ? stage.label : liveStep;
                      })()}
                      {" "}&mdash; Click to open review panel
                    </p>
                  </div>
                </div>
              </button>
            )}
          </div>
        </div>
      )}

      {/* Complete — Show summary */}
      {pageState === "complete" && (
        <div className="mt-8 max-w-2xl">
          <div className="rounded-xl border border-sage/30 bg-sage-light p-6">
            <div className="flex items-center gap-3 mb-4">
              <CheckCircle size={24} className="text-sage" />
              <h2 className="font-display text-[1.375rem] text-ink">
                Research Complete
              </h2>
            </div>
            {completedTask?.result?.produced_artifacts && (
              <div className="space-y-2">
                <p className="font-mono text-[0.75rem] text-ink-secondary uppercase tracking-wider">
                  Produced Artifacts
                </p>
                {completedTask.result.produced_artifacts.map((a: any) => (
                  <div
                    key={`${a.type}-${a.slug}`}
                    className="flex items-center gap-2 text-[0.875rem] font-body text-ink"
                  >
                    <span className="w-2 h-2 rounded-full bg-sage" />
                    {a.type} / {a.slug}
                  </div>
                ))}
              </div>
            )}
            <button
              onClick={handleReset}
              className="mt-4 px-4 py-2 rounded-lg font-body text-[0.875rem] text-terracotta-600 hover:bg-terracotta-50 transition-colors"
            >
              Start New Research
            </button>
          </div>
        </div>
      )}

      {/* Failed */}
      {pageState === "failed" && (
        <div className="mt-8 max-w-2xl">
          <div className="rounded-xl border border-status-failed/20 bg-red-50 p-6">
            <div className="flex items-center gap-3 mb-2">
              <AlertCircle size={24} className="text-status-failed" />
              <h2 className="font-display text-[1.375rem] text-ink">
                Pipeline Failed
              </h2>
            </div>
            <p className="font-mono text-[0.875rem] text-status-failed">
              {liveError || "An unknown error occurred"}
            </p>
            <button
              onClick={handleReset}
              className="mt-4 px-4 py-2 rounded-lg font-body text-[0.875rem] text-terracotta-600 hover:bg-terracotta-50 transition-colors"
            >
              Try Again
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
