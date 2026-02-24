import { api } from './client';
import type { PipelineRunResponse } from '@/types/common';
import type { ContentStartInput, ContentApproval } from '@/types/content';

export const content = {
  start(input: ContentStartInput): Promise<PipelineRunResponse> {
    return api.post('/api/v1/content/start', input);
  },

  getStatus(runId: string): Promise<PipelineRunResponse> {
    return api.get(`/api/v1/content/${runId}/status`);
  },

  approve(runId: string, approval: ContentApproval): Promise<{ status: string }> {
    return api.post(`/api/v1/content/${runId}/approve`, approval);
  },
};
