"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { X, Search, BarChart3, FileText, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { startResearch, startGapAnalysis, startContent, ApiError } from "@/lib/api";

type PipelineChoice = "research" | "gap_analysis" | "content";

interface NewPipelineDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

const PIPELINES = [
  {
    id: "research" as PipelineChoice,
    label: "Research",
    description: "Company context, personas, and style guide",
    icon: Search,
  },
  {
    id: "gap_analysis" as PipelineChoice,
    label: "Gap Analysis",
    description: "AI citation gap analysis across platforms",
    icon: BarChart3,
  },
  {
    id: "content" as PipelineChoice,
    label: "Content Generation",
    description: "Generate optimized content from research + analysis",
    icon: FileText,
  },
];

const ROUTES: Record<PipelineChoice, string> = {
  research: "/research",
  gap_analysis: "/gap-analysis",
  content: "/content",
};

export function NewPipelineDialog({ isOpen, onClose }: NewPipelineDialogProps) {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2>(1);
  const [selectedPipeline, setSelectedPipeline] = useState<PipelineChoice | null>(null);
  const [companyName, setCompanyName] = useState("");
  const [domain, setDomain] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleClose = () => {
    setStep(1);
    setSelectedPipeline(null);
    setCompanyName("");
    setDomain("");
    setError(null);
    onClose();
  };

  const handleSubmit = async () => {
    if (!selectedPipeline || !companyName.trim() || !domain.trim()) return;

    setIsSubmitting(true);
    setError(null);

    try {
      let runId: string;

      switch (selectedPipeline) {
        case "research": {
          const res = await startResearch({ company_name: companyName, domain });
          runId = res.run_id;
          break;
        }
        case "gap_analysis": {
          const res = await startGapAnalysis({ company_name: companyName, domain });
          runId = res.run_id;
          break;
        }
        case "content": {
          const res = await startContent({
            company_name: companyName,
            domain,
          });
          runId = res.run_id;
          break;
        }
      }

      handleClose();
      router.push(`${ROUTES[selectedPipeline]}?task=${runId}`);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Failed to start pipeline");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-ink/20 z-50"
        onClick={handleClose}
      />

      {/* Dialog */}
      <div className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[480px] bg-canvas rounded-2xl border border-canvas-muted shadow-panel z-50">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-canvas-muted">
          <h2 className="font-display text-[1.25rem] text-ink">
            {step === 1 ? "New Pipeline" : "Company Details"}
          </h2>
          <button
            onClick={handleClose}
            className="p-2 rounded-lg hover:bg-canvas-subtle text-ink-tertiary hover:text-ink transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5">
          {step === 1 && (
            <div className="space-y-3">
              {PIPELINES.map((p) => (
                <button
                  key={p.id}
                  onClick={() => {
                    setSelectedPipeline(p.id);
                    setStep(2);
                  }}
                  className="w-full flex items-center gap-4 p-4 rounded-xl border border-canvas-muted hover:border-terracotta-300 hover:bg-terracotta-50/50 transition-all text-left group"
                >
                  <div className="w-10 h-10 rounded-lg bg-terracotta-50 flex items-center justify-center flex-shrink-0 group-hover:bg-terracotta-100">
                    <p.icon size={20} className="text-terracotta-500" />
                  </div>
                  <div className="flex-1">
                    <p className="font-body font-semibold text-[0.9375rem] text-ink">
                      {p.label}
                    </p>
                    <p className="font-body text-[0.8125rem] text-ink-secondary">
                      {p.description}
                    </p>
                  </div>
                  <ArrowRight
                    size={16}
                    className="text-ink-tertiary group-hover:text-terracotta-500 transition-colors"
                  />
                </button>
              ))}
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <div>
                <label className="block font-mono text-[0.75rem] text-ink-secondary mb-1.5 uppercase tracking-wider">
                  Company Name
                </label>
                <input
                  type="text"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  placeholder="e.g., Ramp"
                  className="w-full px-3 py-2.5 rounded-lg border border-canvas-muted bg-canvas font-body text-[0.9375rem] text-ink placeholder:text-ink-tertiary focus:outline-none focus:ring-2 focus:ring-terracotta-300"
                  autoFocus
                />
              </div>
              <div>
                <label className="block font-mono text-[0.75rem] text-ink-secondary mb-1.5 uppercase tracking-wider">
                  Domain
                </label>
                <input
                  type="text"
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  placeholder="e.g., ramp.com"
                  className="w-full px-3 py-2.5 rounded-lg border border-canvas-muted bg-canvas font-body text-[0.9375rem] text-ink placeholder:text-ink-tertiary focus:outline-none focus:ring-2 focus:ring-terracotta-300"
                />
              </div>

              {error && (
                <p className="font-mono text-[0.8125rem] text-status-failed bg-red-50 px-3 py-2 rounded-lg">
                  {error}
                </p>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => setStep(1)}
                  className="px-4 py-2.5 rounded-lg font-body text-[0.875rem] text-ink-secondary hover:bg-canvas-subtle border border-canvas-muted transition-colors"
                >
                  Back
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={isSubmitting || !companyName.trim() || !domain.trim()}
                  className={cn(
                    "flex-1 px-4 py-2.5 rounded-lg font-body font-semibold text-[0.875rem] transition-colors",
                    "bg-terracotta-500 text-white hover:bg-terracotta-600",
                    "disabled:opacity-50 disabled:cursor-not-allowed",
                  )}
                >
                  {isSubmitting ? "Starting..." : "Start Pipeline"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
