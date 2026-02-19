"use client";

import { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import { useArtifactStore } from "@/stores/artifactStore";
import { MarkdownViewer } from "@/components/artifacts/MarkdownViewer";
import { ApprovalGate } from "@/components/approval/ApprovalGate";
import { RESEARCH_STAGES } from "@/lib/constants";

export function ArtifactPanel() {
  const { isOpen, content, close } = useArtifactStore();

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    if (isOpen) {
      document.addEventListener("keydown", handler);
      return () => document.removeEventListener("keydown", handler);
    }
  }, [isOpen, close]);

  return (
    <AnimatePresence>
      {isOpen && content && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-ink/10 z-40"
            onClick={close}
          />

          {/* Panel */}
          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
            className="fixed right-0 top-0 bottom-0 w-[50vw] min-w-[480px] max-w-[720px] bg-canvas border-l border-canvas-muted shadow-panel z-50 flex flex-col"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-canvas-muted">
              <div>
                {content.kind === "approval" && (
                  <span className="inline-block px-2 py-0.5 rounded text-[0.6875rem] font-mono font-medium bg-clay-light text-clay mb-1">
                    Pending Review
                  </span>
                )}
                <h2 className="font-display text-[1.25rem] text-ink">
                  {content.kind === "markdown" && content.title}
                  {content.kind === "approval" && (() => {
                    const stageInfo = RESEARCH_STAGES.find(s => s.name === content.stage);
                    return `Review: ${stageInfo?.label || content.stage}`;
                  })()}
                  {content.kind === "visualization" && content.title}
                  {content.kind === "json" && content.title}
                </h2>
              </div>
              <button
                onClick={close}
                className="p-2 rounded-lg hover:bg-canvas-subtle transition-colors text-ink-tertiary hover:text-ink"
              >
                <X size={18} />
              </button>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto">
              {content.kind === "markdown" && (
                <div className="px-6 py-6">
                  <MarkdownViewer content={content.content} />
                </div>
              )}

              {content.kind === "approval" && (
                <ApprovalGate
                  stage={content.stage}
                  artifactMd={content.artifactMd}
                  taskId={content.taskId}
                  pipeline={content.pipeline}
                  briefId={content.briefId}
                />
              )}

              {content.kind === "visualization" && (
                <iframe
                  src={content.htmlUrl}
                  sandbox="allow-scripts allow-same-origin"
                  className="w-full h-full border-0"
                  title={content.title}
                />
              )}

              {content.kind === "json" && (
                <div className="px-6 py-6">
                  <pre className="font-mono text-[0.8125rem] text-ink bg-canvas-subtle p-4 rounded-lg overflow-x-auto whitespace-pre-wrap">
                    {(() => {
                      try {
                        return JSON.stringify(JSON.parse(content.content), null, 2);
                      } catch {
                        return content.content;
                      }
                    })()}
                  </pre>
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
