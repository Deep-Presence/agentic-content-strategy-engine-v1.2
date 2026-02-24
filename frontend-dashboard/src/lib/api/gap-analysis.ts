import { api } from './client';
import type { PipelineRunResponse } from '@/types/common';
import type { GapAnalysisStartInput } from '@/types/gap-analysis';

export const gapAnalysis = {
  start(input: GapAnalysisStartInput): Promise<PipelineRunResponse> {
    return api.post('/api/v1/gap-analysis/start', input);
  },

  getStatus(runId: string): Promise<PipelineRunResponse> {
    return api.get(`/api/v1/gap-analysis/${runId}/status`);
  },
};
