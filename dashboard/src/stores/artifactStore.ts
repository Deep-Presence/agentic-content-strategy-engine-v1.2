import { create } from "zustand";
import type { PipelineType } from "@/types/api";

export type PanelContentType =
  | { kind: "markdown"; title: string; content: string }
  | { kind: "approval"; stage: string; artifactMd: string; taskId: string; pipeline: PipelineType; briefId?: string }
  | { kind: "visualization"; title: string; htmlUrl: string }
  | { kind: "json"; title: string; content: string };

interface ArtifactStoreState {
  isOpen: boolean;
  content: PanelContentType | null;

  open: (content: PanelContentType) => void;
  openApproval: (data: Record<string, any>, taskId: string, pipeline: PipelineType) => void;
  close: () => void;
}

export const useArtifactStore = create<ArtifactStoreState>((set) => ({
  isOpen: false,
  content: null,

  open: (content) => set({ isOpen: true, content }),

  openApproval: (data, taskId, pipeline) =>
    set({
      isOpen: true,
      content: {
        kind: "approval",
        stage: data.stage || data.brief_id || "review",
        artifactMd: data.artifact_md || data.content_preview || "",
        taskId,
        pipeline,
        briefId: data.brief_id,
      },
    }),

  close: () => set({ isOpen: false, content: null }),
}));
