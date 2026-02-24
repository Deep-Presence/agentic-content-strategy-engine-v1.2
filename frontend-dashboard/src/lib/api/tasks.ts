import { api } from './client';
import type { TaskResponse, TaskListResponse } from '@/types/common';

export const tasks = {
  list(params?: { status?: string }): Promise<TaskListResponse> {
    const query = params?.status ? `?status=${params.status}` : '';
    return api.get(`/api/v1/tasks${query}`);
  },

  get(taskId: string): Promise<TaskResponse> {
    return api.get(`/api/v1/tasks/${taskId}`);
  },

  cancel(taskId: string): Promise<{ status: string }> {
    return api.post(`/api/v1/tasks/${taskId}/cancel`);
  },
};
