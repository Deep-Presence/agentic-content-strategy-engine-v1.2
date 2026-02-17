"use client";

import { useState } from "react";
import { Check, RotateCcw, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { submitResearchApproval, submitContentApproval } from "@/lib/api";
import { useArtifactStore } from "@/stores/artifactStore";
import { MarkdownViewer } from "@/components/artifacts/MarkdownViewer";
import type { PipelineType } from "@/types/api";

interface ApprovalGateProps {
  stage: string;
  artifactMd: string;
  taskId: string;
  pipeline: PipelineType;
  briefId?: string;
}

export function ApprovalGate({
  stage,
  artifactMd,
  taskId,
  pipeline,
  briefId,
}: ApprovalGateProps) {
  const [showRevision, setShowRevision] = useState(false);
  const [revisionNote, setRevisionNote] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState<string | null>(null);
  const { close } = useArtifactStore();

  const handleDecision = async (
    decision: "approve" | "revise" | "reject" | "edit",
  ) => {
    if (decision === "revise" || decision === "edit") {
      if (!showRevision) {
        setShowRevision(true);
        return;
      }
    }

    setIsSubmitting(true);
    try {
      if (pipeline === "content" && briefId) {
        await submitContentApproval(taskId, {
          brief_id: briefId,
          decision: decision as "approve" | "edit" | "reject",
          editor_notes: revisionNote || undefined,
        });
      } else {
        await submitResearchApproval(taskId, {
          decision: decision as "approve" | "revise" | "reject",
          revision_note: revisionNote || undefined,
        });
      }
      setSubmitted(decision);
      // Close panel after a brief delay
      setTimeout(() => close(), 1000);
    } catch (err: any) {
      console.error("Approval failed:", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const isContent = pipeline === "content";
  const reviseLabel = isContent ? "Edit" : "Revise";
  const reviseDecision = isContent ? "edit" : "revise";

  return (
    <div className="flex flex-col h-full">
      {/* Markdown content — scrollable */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <MarkdownViewer content={artifactMd} />
      </div>

      {/* Sticky bottom bar */}
      <div className="sticky bottom-0 border-t border-canvas-muted bg-canvas/95 backdrop-blur-sm px-6 py-4 space-y-3">
        {submitted ? (
          <div className="text-center">
            <p className="font-mono text-[0.875rem] text-sage font-medium">
              Decision submitted: {submitted}
            </p>
          </div>
        ) : (
          <>
            {showRevision && (
              <div className="space-y-2">
                <textarea
                  value={revisionNote}
                  onChange={(e) => setRevisionNote(e.target.value)}
                  placeholder="Describe what changes you'd like..."
                  className="w-full px-3 py-2.5 rounded-lg border border-canvas-muted bg-canvas-subtle font-body text-[0.875rem] text-ink placeholder:text-ink-tertiary focus:outline-none focus:ring-2 focus:ring-terracotta-300 resize-none"
                  rows={3}
                  autoFocus
                />
                <div className="flex justify-between items-center">
                  <span className="text-[0.75rem] font-mono text-ink-tertiary">
                    {revisionNote.length} characters
                  </span>
                  <button
                    onClick={() => handleDecision(reviseDecision as "revise" | "edit")}
                    disabled={isSubmitting || !revisionNote.trim()}
                    className={cn(
                      "px-4 py-2 rounded-lg font-body font-semibold text-[0.875rem] transition-colors",
                      "bg-terracotta-500 text-white hover:bg-terracotta-600",
                      "disabled:opacity-50 disabled:cursor-not-allowed",
                    )}
                  >
                    Submit {reviseLabel}
                  </button>
                </div>
              </div>
            )}

            <div className="flex gap-3">
              <button
                onClick={() => handleDecision("approve")}
                disabled={isSubmitting}
                className={cn(
                  "flex-1 flex items-center justify-center gap-2 px-6 py-2.5 rounded-lg font-body font-semibold text-[0.875rem] transition-colors",
                  "bg-sage text-white hover:bg-sage/90",
                  "disabled:opacity-50",
                )}
              >
                <Check size={16} />
                Approve
              </button>
              <button
                onClick={() => {
                  setShowRevision(!showRevision);
                }}
                disabled={isSubmitting}
                className={cn(
                  "flex-1 flex items-center justify-center gap-2 px-6 py-2.5 rounded-lg font-body font-semibold text-[0.875rem] transition-colors",
                  "bg-terracotta-500 text-white hover:bg-terracotta-600",
                  "disabled:opacity-50",
                )}
              >
                <RotateCcw size={16} />
                {reviseLabel}
              </button>
              <button
                onClick={() => handleDecision("reject")}
                disabled={isSubmitting}
                className={cn(
                  "flex-1 flex items-center justify-center gap-2 px-6 py-2.5 rounded-lg font-body font-semibold text-[0.875rem] transition-colors",
                  "bg-canvas-subtle text-ink-secondary border border-canvas-muted hover:bg-canvas-muted",
                  "disabled:opacity-50",
                )}
              >
                <XCircle size={16} />
                Reject
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
