"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle, AlertCircle, FileText, Eye } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  startContent,
  getTaskDetail,
  getArtifactContent,
  listArtifacts,
  ApiError,
} from "@/lib/api";
import { useTaskStore } from "@/stores/taskStore";
import { useArtifactStore } from "@/stores/artifactStore";
import { useTaskStream } from "@/hooks/useTaskStream";
import { PipelineProgress } from "@/components/pipeline/PipelineProgress";
import { StatusBadge } from "@/components/pipeline/StatusBadge";
import { CONTENT_STAGES } from "@/lib/constants";
import type { TaskResponse, ArtifactFile } from "@/types/api";

type PageState = "idle" | "running" | "complete" | "failed";

export default function ContentPage() {
  return (
    <Suspense>
      <ContentPageInner />
    </Suspense>
  );
}

function ContentPageInner() {
  const searchParams = useSearchParams();
  const taskIdParam = searchParams.get("task");

  const { liveStatus, liveStep, liveError } = useTaskStore();
  const { open } = useArtifactStore();

  const [taskId, setTaskId] = useState<string | null>(taskIdParam);
  const [pageState, setPageState] = useState<PageState>(
    taskIdParam ? "running" : "idle",
  );
  const [completedTask, setCompletedTask] = useState<TaskResponse | null>(null);
  const [contentFiles, setContentFiles] = useState<ArtifactFile[]>([]);

  // Form state
  const [companyName, setCompanyName] = useState("");
  const [domain, setDomain] = useState("");
  const [maxBriefs, setMaxBriefs] = useState<number>(5);
  const [autoApprove, setAutoApprove] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // SSE streaming
  useTaskStream(taskId, "content");

  // React to SSE status changes — only when we have an active task
  useEffect(() => {
    if (!taskId) return;
    if (liveStatus === "completed") {
      setPageState("complete");
      getTaskDetail(taskId).then(setCompletedTask).catch(console.error);
    } else if (liveStatus === "failed" || liveStatus === "cancelled") {
      setPageState("failed");
    } else if (liveStatus === "running" || liveStatus === "pending_approval") {
      setPageState("running");
    }
  }, [liveStatus, taskId]);

  // If task ID from URL, fetch its status
  useEffect(() => {
    if (taskIdParam) {
      getTaskDetail(taskIdParam)
        .then((task) => {
          if (task.status === "completed") {
            setPageState("complete");
            setCompletedTask(task);
          } else if (task.status === "failed" || task.status === "cancelled" || task.status === "failed_restart") {
            setPageState("failed");
          } else {
            setPageState("running");
          }
        })
        .catch((err) => {
          console.error("Failed to fetch task:", err);
          setPageState("idle");
        });
    }
  }, [taskIdParam]);

  // Load content files on completion
  useEffect(() => {
    if (pageState !== "complete" || !completedTask) return;

    const slug = completedTask.company_slug;
    listArtifacts("content", slug)
      .then((res) => setContentFiles(res.files))
      .catch(() => {});
  }, [pageState, completedTask]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!companyName.trim() || !domain.trim()) return;

    setIsSubmitting(true);
    setFormError(null);

    try {
      const res = await startContent({
        company_name: companyName,
        domain,
        max_briefs: maxBriefs,
        auto_approve: autoApprove,
      });
      setTaskId(res.run_id);
      setPageState("running");
      window.history.replaceState(null, "", `/content?task=${res.run_id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        setFormError(err.detail);
      } else {
        setFormError("Failed to start content generation pipeline");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const getStatusText = (): string => {
    if (!liveStep) return "Starting...";
    const stage = CONTENT_STAGES.find((s) => s.name === liveStep);
    if (stage) return `${stage.label}...`;
    if (liveStep.endsWith("_done")) {
      const doneName = liveStep.replace("_done", "");
      const doneStage = CONTENT_STAGES.find((s) => s.name === doneName);
      return doneStage ? `${doneStage.label} complete` : liveStep;
    }
    return liveStep;
  };

  const handleViewFile = async (filename: string) => {
    if (!completedTask) return;
    try {
      const content = await getArtifactContent(
        "content",
        completedTask.company_slug,
        filename,
      );
      open({
        kind: filename.endsWith(".json") ? "json" : "markdown",
        title: filename,
        content,
      });
    } catch {
      open({ kind: "markdown", title: filename, content: "Failed to load file." });
    }
  };

  const handleReset = () => {
    setTaskId(null);
    setPageState("idle");
    setCompletedTask(null);
    setContentFiles([]);
    setCompanyName("");
    setDomain("");
    setFormError(null);
    window.history.replaceState(null, "", "/content");
  };

  return (
    <div>
      <h1 className="font-display text-[2.25rem] text-ink tracking-tight leading-tight">
        Content Generation
      </h1>
      <p className="text-ink-secondary mt-2 text-[0.9375rem]">
        AI-generated content optimized for citation in AI search results.
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
            <label className="block font-mono text-[0.75rem] text-ink-secondary mb-1.5 uppercase tracking-wider">
              Max Briefs
            </label>
            <input
              type="number"
              value={maxBriefs}
              onChange={(e) => setMaxBriefs(Number(e.target.value) || 5)}
              min={1}
              max={20}
              className="w-32 px-3 py-2.5 rounded-lg border border-canvas-muted bg-canvas font-mono text-[0.9375rem] text-ink focus:outline-none focus:ring-2 focus:ring-terracotta-300"
            />
          </div>

          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="content-auto-approve"
              checked={autoApprove}
              onChange={(e) => setAutoApprove(e.target.checked)}
              className="w-4 h-4 rounded border-canvas-muted accent-terracotta-500"
            />
            <label
              htmlFor="content-auto-approve"
              className="font-body text-[0.875rem] text-ink-secondary"
            >
              Auto-approve all briefs (skip HITL review)
            </label>
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
            {isSubmitting ? "Starting Generation..." : "Start Content Generation"}
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
                stages={[...CONTENT_STAGES]}
                currentStep={liveStep}
                status={liveStatus}
                statusText={getStatusText()}
              />
            </div>
            {liveStatus === "pending_approval" && (
              <p className="mt-4 font-body text-[0.875rem] text-clay">
                Review the content brief in the panel on the right. Approve, edit, or reject.
              </p>
            )}
          </div>
        </div>
      )}

      {/* Complete — Show summary + files */}
      {pageState === "complete" && (
        <div className="mt-8 space-y-6">
          <div className="rounded-xl border border-sage/30 bg-sage-light p-6 max-w-2xl">
            <div className="flex items-center gap-3 mb-2">
              <CheckCircle size={24} className="text-sage" />
              <h2 className="font-display text-[1.375rem] text-ink">
                Content Generation Complete
              </h2>
            </div>
            <button
              onClick={handleReset}
              className="px-4 py-2 rounded-lg font-body text-[0.875rem] text-terracotta-600 hover:bg-terracotta-50 transition-colors"
            >
              Start New Generation
            </button>
          </div>

          {/* Produced artifacts */}
          {completedTask?.result?.produced_artifacts && (
            <div className="max-w-2xl">
              <p className="font-mono text-[0.75rem] text-ink-secondary uppercase tracking-wider mb-2">
                Produced Artifacts
              </p>
              <div className="space-y-1.5">
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
            </div>
          )}

          {/* Content files */}
          {contentFiles.length > 0 && (
            <div className="max-w-2xl">
              <h3 className="font-display text-[1.125rem] text-ink mb-3">
                Generated Files
              </h3>
              <div className="space-y-2">
                {contentFiles.map((f) => (
                  <button
                    key={f.name}
                    onClick={() => handleViewFile(f.name)}
                    className="w-full flex items-center gap-3 px-4 py-3 rounded-xl border border-canvas-muted bg-canvas hover:bg-canvas-subtle transition-colors text-left group"
                  >
                    <FileText size={18} className="text-terracotta-500 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="font-mono text-[0.8125rem] text-ink truncate">
                        {f.name}
                      </p>
                      <p className="font-mono text-[0.6875rem] text-ink-tertiary">
                        {(f.size / 1024).toFixed(1)} KB
                      </p>
                    </div>
                    <Eye
                      size={16}
                      className="text-ink-tertiary opacity-0 group-hover:opacity-100 transition-opacity"
                    />
                  </button>
                ))}
              </div>
            </div>
          )}
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
