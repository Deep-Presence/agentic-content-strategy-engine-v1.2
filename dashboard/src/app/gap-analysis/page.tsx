"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle, AlertCircle, FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  startGapAnalysis,
  getTaskDetail,
  listArtifacts,
  getArtifactUrl,
  getArtifactContent,
  ApiError,
} from "@/lib/api";
import { useTaskStore } from "@/stores/taskStore";
import { useArtifactStore } from "@/stores/artifactStore";
import { useTaskStream } from "@/hooks/useTaskStream";
import { PipelineProgress } from "@/components/pipeline/PipelineProgress";
import { StatusBadge } from "@/components/pipeline/StatusBadge";
import { VisualizationGrid } from "@/components/artifacts/VisualizationGrid";
import { GAP_ANALYSIS_STEPS } from "@/lib/constants";
import type { TaskResponse, ArtifactFile } from "@/types/api";

const DEFAULT_PLATFORMS = ["openai", "claude", "gemini", "perplexity"];

type PageState = "idle" | "running" | "complete" | "failed";

export default function GapAnalysisPage() {
  return (
    <Suspense>
      <GapAnalysisPageInner />
    </Suspense>
  );
}

function GapAnalysisPageInner() {
  const searchParams = useSearchParams();
  const taskIdParam = searchParams.get("task");

  const { liveStatus, liveStep, liveError } = useTaskStore();
  const { open } = useArtifactStore();

  const [taskId, setTaskId] = useState<string | null>(taskIdParam);
  const [pageState, setPageState] = useState<PageState>(
    taskIdParam ? "running" : "idle",
  );
  const [completedTask, setCompletedTask] = useState<TaskResponse | null>(null);

  // Visualization files
  const [vizFiles, setVizFiles] = useState<{ name: string; url: string }[]>([]);
  const [hasReport, setHasReport] = useState(false);

  // Form state
  const [companyName, setCompanyName] = useState("");
  const [domain, setDomain] = useState("");
  const [platforms, setPlatforms] = useState<string[]>([...DEFAULT_PLATFORMS]);
  const [maxQueries, setMaxQueries] = useState<number>(50);
  const [seedUrls, setSeedUrls] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // SSE streaming
  useTaskStream(taskId, "gap_analysis");

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
    } else if (liveStatus === "running") {
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

  // Load visualizations when complete
  useEffect(() => {
    if (pageState !== "complete" || !completedTask) return;

    const slug = completedTask.company_slug;
    listArtifacts("gap_analysis", slug)
      .then((res) => {
        const vizs = res.files
          .filter((f: ArtifactFile) => f.name.startsWith("visualizations/") && f.name.endsWith(".html"))
          .map((f: ArtifactFile) => ({
            name: f.name.replace("visualizations/", ""),
            url: getArtifactUrl("gap_analysis", slug, f.name),
          }));
        setVizFiles(vizs);

        const report = res.files.find(
          (f: ArtifactFile) => f.name === "gap_report.md" || f.name.endsWith("gap_report.md"),
        );
        setHasReport(!!report);
      })
      .catch(() => {});
  }, [pageState, completedTask]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!companyName.trim() || !domain.trim()) return;

    setIsSubmitting(true);
    setFormError(null);

    try {
      const parsedSeeds = seedUrls
        .split("\n")
        .map((u) => u.trim())
        .filter(Boolean);

      const res = await startGapAnalysis({
        company_name: companyName,
        domain,
        platforms: platforms.length > 0 ? platforms : undefined,
        max_queries: maxQueries,
        seed_urls: parsedSeeds.length > 0 ? parsedSeeds : undefined,
      });
      setTaskId(res.run_id);
      setPageState("running");
      window.history.replaceState(null, "", `/gap-analysis?task=${res.run_id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        setFormError(err.detail);
      } else {
        setFormError("Failed to start gap analysis pipeline");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handlePlatformToggle = (platform: string) => {
    setPlatforms((prev) =>
      prev.includes(platform)
        ? prev.filter((p) => p !== platform)
        : [...prev, platform],
    );
  };

  const getStatusText = (): string => {
    if (!liveStep) return "Starting...";
    const step = GAP_ANALYSIS_STEPS.find((s) => s.name === liveStep);
    if (step) return `Running ${step.label}...`;
    if (liveStep.endsWith("_done")) {
      const doneName = liveStep.replace("_done", "");
      const doneStep = GAP_ANALYSIS_STEPS.find((s) => s.name === doneName);
      return doneStep ? `${doneStep.label} complete` : liveStep;
    }
    return liveStep;
  };

  const handleViewReport = async () => {
    if (!completedTask) return;
    try {
      const md = await getArtifactContent(
        "gap_analysis",
        completedTask.company_slug,
        "gap_report.md",
      );
      open({
        kind: "markdown",
        title: "Gap Analysis Report",
        content: md,
      });
    } catch {
      open({
        kind: "markdown",
        title: "Gap Analysis Report",
        content: "Failed to load report.",
      });
    }
  };

  const handleReset = () => {
    setTaskId(null);
    setPageState("idle");
    setCompletedTask(null);
    setVizFiles([]);
    setHasReport(false);
    setCompanyName("");
    setDomain("");
    setFormError(null);
    window.history.replaceState(null, "", "/gap-analysis");
  };

  return (
    <div>
      <h1 className="font-display text-[2.25rem] text-ink tracking-tight leading-tight">
        Gap Analysis
      </h1>
      <p className="text-ink-secondary mt-2 text-[0.9375rem]">
        AI citation gap analysis across search platforms.
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
              Platforms
            </label>
            <div className="flex flex-wrap gap-2">
              {DEFAULT_PLATFORMS.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => handlePlatformToggle(p)}
                  className={cn(
                    "px-3 py-2 rounded-lg text-[0.8125rem] font-mono border transition-colors capitalize",
                    platforms.includes(p)
                      ? "bg-terracotta-50 border-terracotta-300 text-terracotta-700"
                      : "bg-canvas border-canvas-muted text-ink-tertiary hover:text-ink",
                  )}
                >
                  {p === "openai" ? "ChatGPT" : p.charAt(0).toUpperCase() + p.slice(1)}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block font-mono text-[0.75rem] text-ink-secondary mb-1.5 uppercase tracking-wider">
              Max Queries
            </label>
            <input
              type="number"
              value={maxQueries}
              onChange={(e) => setMaxQueries(Number(e.target.value) || 50)}
              min={10}
              max={200}
              className="w-32 px-3 py-2.5 rounded-lg border border-canvas-muted bg-canvas font-mono text-[0.9375rem] text-ink focus:outline-none focus:ring-2 focus:ring-terracotta-300"
            />
          </div>

          <div>
            <label className="block font-mono text-[0.75rem] text-ink-secondary mb-1.5 uppercase tracking-wider">
              Seed URLs
            </label>
            <textarea
              value={seedUrls}
              onChange={(e) => setSeedUrls(e.target.value)}
              placeholder={"Optional: one URL per line\nhttps://ramp.com/blog/..."}
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
            {isSubmitting ? "Starting Analysis..." : "Start Gap Analysis"}
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
                stages={[...GAP_ANALYSIS_STEPS]}
                currentStep={liveStep}
                status={liveStatus}
                statusText={getStatusText()}
              />
            </div>
          </div>
        </div>
      )}

      {/* Complete — Show visualizations + report */}
      {pageState === "complete" && (
        <div className="mt-8 space-y-6">
          {/* Success banner */}
          <div className="rounded-xl border border-sage/30 bg-sage-light p-6 max-w-2xl">
            <div className="flex items-center gap-3 mb-2">
              <CheckCircle size={24} className="text-sage" />
              <h2 className="font-display text-[1.375rem] text-ink">
                Analysis Complete
              </h2>
            </div>
            <div className="flex items-center gap-3">
              {hasReport && (
                <button
                  onClick={handleViewReport}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg font-body text-[0.875rem] text-white bg-terracotta-500 hover:bg-terracotta-600 transition-colors"
                >
                  <FileText size={16} />
                  View Gap Report
                </button>
              )}
              <button
                onClick={handleReset}
                className="px-4 py-2 rounded-lg font-body text-[0.875rem] text-terracotta-600 hover:bg-terracotta-50 transition-colors"
              >
                Start New Analysis
              </button>
            </div>
          </div>

          {/* Visualization grid */}
          {vizFiles.length > 0 && (
            <div>
              <h3 className="font-display text-[1.125rem] text-ink mb-4">
                Visualizations
              </h3>
              <VisualizationGrid files={vizFiles} />
            </div>
          )}

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
