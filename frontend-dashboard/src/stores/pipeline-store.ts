import { create } from 'zustand';
import type { TaskStatus } from '@/types/common';
import type { GapReport, ClusterSpec, GapBrief, GapAnalysisStep } from '@/types/gap-analysis';

interface StepState {
  key: GapAnalysisStep;
  status: 'waiting' | 'active' | 'completed' | 'failed';
  startedAt?: number;
  completedAt?: number;
}

interface PipelineState {
  activeRunId: string | null;
  activeRunStatus: TaskStatus | null;
  steps: StepState[];
  currentStep: GapAnalysisStep | null;

  gapReport: GapReport | null;
  clusterSpecs: ClusterSpec[];
  gapBriefs: GapBrief[];

  selectedCluster: string | null;
  briefClassificationFilter: string;
  briefSortField: string;
  briefSortDirection: 'asc' | 'desc';

  setActiveRun: (runId: string, status: TaskStatus) => void;
  updateStep: (step: GapAnalysisStep, status: 'completed' | 'active' | 'failed') => void;
  setResults: (report: GapReport, specs: ClusterSpec[], briefs: GapBrief[]) => void;
  setSelectedCluster: (cluster: string | null) => void;
  setBriefClassificationFilter: (filter: string) => void;
  setBriefSort: (field: string, direction: 'asc' | 'desc') => void;
  reset: () => void;
}

const INITIAL_STEPS: StepState[] = [
  { key: 's1_embed_assets', status: 'waiting' },
  { key: 's2_generate_queries', status: 'waiting' },
  { key: 's3_search_platforms', status: 'waiting' },
  { key: 's4_enrich_citations', status: 'waiting' },
  { key: 's5_embed_content', status: 'waiting' },
  { key: 's6_analyze', status: 'waiting' },
  { key: 's7_visualize', status: 'waiting' },
  { key: 's8_generate_report', status: 'waiting' },
];

export const usePipelineStore = create<PipelineState>((set) => ({
  activeRunId: null,
  activeRunStatus: null,
  steps: [...INITIAL_STEPS],
  currentStep: null,

  gapReport: null,
  clusterSpecs: [],
  gapBriefs: [],

  selectedCluster: null,
  briefClassificationFilter: 'all',
  briefSortField: 'gap_score',
  briefSortDirection: 'desc',

  setActiveRun: (runId, status) =>
    set({
      activeRunId: runId,
      activeRunStatus: status,
      steps: status === 'running' ? [...INITIAL_STEPS] : undefined,
    }),

  updateStep: (step, status) =>
    set((state) => {
      const now = Date.now();
      const steps = state.steps.map((s) => {
        if (s.key === step) {
          return {
            ...s,
            status,
            ...(status === 'active' && !s.startedAt ? { startedAt: now } : {}),
            ...(status === 'completed' ? { completedAt: now } : {}),
          };
        }
        return s;
      });
      return {
        steps,
        currentStep: status === 'active' ? step : state.currentStep,
      };
    }),

  setResults: (report, specs, briefs) =>
    set({
      gapReport: report,
      clusterSpecs: specs,
      gapBriefs: briefs,
    }),

  setSelectedCluster: (cluster) => set({ selectedCluster: cluster }),
  setBriefClassificationFilter: (filter) => set({ briefClassificationFilter: filter }),
  setBriefSort: (field, direction) =>
    set({ briefSortField: field, briefSortDirection: direction }),

  reset: () =>
    set({
      activeRunId: null,
      activeRunStatus: null,
      steps: [...INITIAL_STEPS],
      currentStep: null,
      gapReport: null,
      clusterSpecs: [],
      gapBriefs: [],
      selectedCluster: null,
      briefClassificationFilter: 'all',
      briefSortField: 'gap_score',
      briefSortDirection: 'desc',
    }),
}));
