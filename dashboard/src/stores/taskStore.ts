import { create } from "zustand";
import type { TaskSummary, TaskResponse, PipelineType, TaskStatus } from "@/types/api";
import { listTasks, getTaskDetail } from "@/lib/api";

interface TaskStoreState {
  /* Task list */
  tasks: TaskSummary[];
  isLoading: boolean;
  error: string | null;

  /* Active task (pipeline in progress) */
  activeTaskId: string | null;
  activeTask: TaskResponse | null;

  /* SSE-derived live state */
  liveStatus: TaskStatus | null;
  liveStep: string | null;
  liveError: string | null;
  approvalPayload: Record<string, any> | null;

  /* Actions */
  fetchTasks: (pipeline?: string, status?: string) => Promise<void>;
  fetchTaskDetail: (taskId: string) => Promise<void>;
  setActiveTask: (taskId: string | null) => void;
  updateLive: (updates: {
    status?: TaskStatus;
    step?: string | null;
    error?: string | null;
  }) => void;
  setApprovalPayload: (payload: Record<string, any> | null) => void;
  clearLive: () => void;
}

export const useTaskStore = create<TaskStoreState>((set) => ({
  tasks: [],
  isLoading: false,
  error: null,
  activeTaskId: null,
  activeTask: null,
  liveStatus: null,
  liveStep: null,
  liveError: null,
  approvalPayload: null,

  fetchTasks: async (pipeline?, status?) => {
    set({ isLoading: true, error: null });
    try {
      const res = await listTasks({ pipeline, status });
      set({ tasks: res.tasks, isLoading: false });
    } catch (err: any) {
      set({ error: err.message || "Failed to fetch tasks", isLoading: false });
    }
  },

  fetchTaskDetail: async (taskId: string) => {
    try {
      const task = await getTaskDetail(taskId);
      set({ activeTask: task, activeTaskId: taskId });
    } catch (err: any) {
      set({ error: err.message });
    }
  },

  setActiveTask: (taskId) =>
    set({ activeTaskId: taskId, activeTask: null }),

  updateLive: (updates) =>
    set((state) => ({
      liveStatus: updates.status ?? state.liveStatus,
      liveStep: updates.step !== undefined ? updates.step : state.liveStep,
      liveError: updates.error !== undefined ? updates.error : state.liveError,
    })),

  setApprovalPayload: (payload) => set({ approvalPayload: payload }),

  clearLive: () =>
    set({
      liveStatus: null,
      liveStep: null,
      liveError: null,
      approvalPayload: null,
    }),
}));
