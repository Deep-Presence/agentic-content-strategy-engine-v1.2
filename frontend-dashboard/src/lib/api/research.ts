import { api } from './client';
import type { PipelineRunResponse } from '@/types/common';
import type { ResearchStartInput, ResearchApproval } from '@/types/research';

export const research = {
  start(input: ResearchStartInput): Promise<PipelineRunResponse> {
    return api.post('/api/v1/research/start', input);
  },

  getStatus(runId: string): Promise<PipelineRunResponse> {
    return api.get(`/api/v1/research/${runId}/status`);
  },

  approve(runId: string, approval: ResearchApproval): Promise<{ status: string }> {
    return api.post(`/api/v1/research/${runId}/approve`, approval);
  },
};
