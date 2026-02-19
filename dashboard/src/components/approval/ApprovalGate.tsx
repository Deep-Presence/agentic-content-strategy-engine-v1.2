"use client";

import { useState } from "react";
import { Check, RotateCcw, XCircle, MessageSquare } from "lucide-react";
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

type TextareaMode = "edit" | "reject_comments" | null;

export function ApprovalGate({
  stage,
  artifactMd,
  taskId,
  pipeline,
  briefId,
}: ApprovalGateProps) {
  const [textareaMode, setTextareaMode] = useState<TextareaMode>(null);
  const [revisionNote, setRevisionNote] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState<string | null>(null);
  const { close } = useArtifactStore();

  const handleDecision = async (
    decision: "approve" | "revise" | "reject",
  ) => {
    setIsSubmitting(true);
    try {
      if (pipeline === "content" && briefId) {
        await submitContentApproval(taskId, {
          brief_id: briefId,
          decision: decision === "revise" ? "edit" : decision as "approve" | "reject",
          editor_notes: revisionNote || undefined,
        });
      } else {
        await submitResearchApproval(taskId, {
          decision,
          revision_note: revisionNote || undefined,
        });
      }
      setSubmitted(decision === "revise" ? "revision requested" : decision);
      setTimeout(() => close(), 1000);
    } catch (err: any) {
      console.error("Approval failed:", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleTextareaSubmit = () => {
    if (textareaMode === "edit") {
      handleDecision("revise");
    } else if (textareaMode === "reject_comments") {
      handleDecision("reject");
    }
  };

  const toggleTextareaMode = (mode: TextareaMode) => {
    if (textareaMode === mode) {
      setTextareaMode(null);
      setRevisionNote("");
    } else {
      setTextareaMode(mode);
      setRevisionNote("");
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Markdown content — scrollable */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {artifactMd ? (
          <MarkdownViewer content={artifactMd} />
        ) : (
          <div className="flex items-center justify-center h-full text-ink-tertiary font-body text-[0.875rem]">
            Draft content unavailable. Check server logs.
          </div>
        )}
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
            {/* Textarea — shown when Request Edit or Reject with Comments is active */}
            {textareaMode && (
              <div className="space-y-2">
                <label className="block font-mono text-[0.6875rem] text-ink-secondary uppercase tracking-wider">
                  {textareaMode === "edit"
                    ? "Describe what changes you'd like"
                    : "Reason for rejection"}
                </label>
                <textarea
                  value={revisionNote}
                  onChange={(e) => setRevisionNote(e.target.value)}
                  placeholder={
                    textareaMode === "edit"
                      ? "e.g., Add more detail about the competitive landscape..."
                      : "e.g., This doesn't match our company's positioning..."
                  }
                  className="w-full px-3 py-2.5 rounded-lg border border-canvas-muted bg-canvas-subtle font-body text-[0.875rem] text-ink placeholder:text-ink-tertiary focus:outline-none focus:ring-2 focus:ring-terracotta-300 resize-none"
                  rows={3}
                  autoFocus
                />
                <div className="flex justify-between items-center">
                  <span className="text-[0.75rem] font-mono text-ink-tertiary">
                    {revisionNote.length} characters
                  </span>
                  <button
                    onClick={handleTextareaSubmit}
                    disabled={isSubmitting || !revisionNote.trim()}
                    className={cn(
                      "px-4 py-2 rounded-lg font-body font-semibold text-[0.875rem] transition-colors",
                      textareaMode === "edit"
                        ? "bg-terracotta-500 text-white hover:bg-terracotta-600"
                        : "bg-clay text-white hover:bg-clay/90",
                      "disabled:opacity-50 disabled:cursor-not-allowed",
                    )}
                  >
                    {textareaMode === "edit" ? "Submit Revision Request" : "Submit Rejection"}
                  </button>
                </div>
              </div>
            )}

            {/* Action buttons */}
            <div className="flex gap-2">
              {/* Approve */}
              <button
                onClick={() => handleDecision("approve")}
                disabled={isSubmitting}
                className={cn(
                  "flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-lg font-body font-semibold text-[0.8125rem] transition-colors",
                  "bg-sage text-white hover:bg-sage/90",
                  "disabled:opacity-50",
                )}
              >
                <Check size={15} />
                Approve
              </button>

              {/* Request Edit */}
              <button
                onClick={() => toggleTextareaMode("edit")}
                disabled={isSubmitting}
                className={cn(
                  "flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-lg font-body font-semibold text-[0.8125rem] transition-colors",
                  textareaMode === "edit"
                    ? "bg-terracotta-600 text-white"
                    : "bg-terracotta-500 text-white hover:bg-terracotta-600",
                  "disabled:opacity-50",
                )}
              >
                <RotateCcw size={15} />
                Request Edit
              </button>

              {/* Reject with Comments */}
              <button
                onClick={() => toggleTextareaMode("reject_comments")}
                disabled={isSubmitting}
                className={cn(
                  "flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-lg font-body font-semibold text-[0.8125rem] transition-colors",
                  textareaMode === "reject_comments"
                    ? "bg-clay text-white"
                    : "bg-canvas-subtle text-clay border border-clay/30 hover:bg-clay-light",
                  "disabled:opacity-50",
                )}
              >
                <MessageSquare size={15} />
                Reject w/ Comments
              </button>

              {/* Reject */}
              <button
                onClick={() => handleDecision("reject")}
                disabled={isSubmitting}
                className={cn(
                  "flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-lg font-body font-semibold text-[0.8125rem] transition-colors",
                  "bg-canvas-subtle text-ink-secondary border border-canvas-muted hover:bg-red-50 hover:text-status-failed hover:border-status-failed/30",
                  "disabled:opacity-50",
                )}
              >
                <XCircle size={15} />
                Reject
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
