"use client";

import { useEffect, useRef } from "react";
import { useTaskStore } from "@/stores/taskStore";
import { useArtifactStore } from "@/stores/artifactStore";
import { streamTaskEvents } from "@/lib/sse";
import type { PipelineType } from "@/types/api";

export function useTaskStream(taskId: string | null, pipeline?: PipelineType) {
  const esRef = useRef<EventSource | null>(null);
  const { updateLive, setApprovalPayload, clearLive } = useTaskStore();
  const { openApproval } = useArtifactStore();

  // Always clear stale state when pipeline changes, even without a taskId
  useEffect(() => {
    clearLive();
  }, [pipeline]);

  useEffect(() => {
    if (!taskId) return;

    clearLive();

    esRef.current = streamTaskEvents(
      taskId,
      (type, data) => {
        switch (type) {
          case "pipeline_start":
            updateLive({ status: "running", step: data.pipeline });
            break;
          case "stage_start":
            updateLive({ status: "running", step: data.stage });
            break;
          case "pending_approval":
            updateLive({ status: "pending_approval", step: data.stage || data.brief_id });
            setApprovalPayload(data);
            if (pipeline) {
              openApproval(data, taskId, pipeline);
            }
            break;
          case "approval_received":
            updateLive({ status: "running", step: data.stage || data.brief_id });
            setApprovalPayload(null);
            break;
          case "stage_complete":
            updateLive({ step: `${data.stage}_done` });
            break;
          case "completed":
            updateLive({ status: "completed", step: null });
            break;
          case "failed":
            updateLive({ status: "failed", error: data.error });
            break;
          case "cancelled":
            updateLive({ status: "cancelled" });
            break;
        }
      },
      () => {
        esRef.current = null;
      },
    );

    return () => {
      esRef.current?.close();
      esRef.current = null;
    };
  }, [taskId, pipeline]);
}
