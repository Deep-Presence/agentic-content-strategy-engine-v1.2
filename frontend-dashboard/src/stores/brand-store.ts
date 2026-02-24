import { create } from 'zustand';
import type { TaskStatus } from '@/types/common';
import type { ResearchStage } from '@/types/research';
import type { Project, Persona, KnowledgeDoc } from '@/types/brand';

type ArtifactStatus = 'none' | 'draft' | 'approved';

interface BrandState {
  // Company context
  companyContext: string | null;
  companyContextStatus: ArtifactStatus;

  // Personas
  personas: Persona[];

  // Style guide
  styleGuide: string | null;
  styleGuideStatus: ArtifactStatus;

  // Knowledge docs
  knowledgeDocs: KnowledgeDoc[];

  // Projects
  projects: Project[];

  // Research pipeline state
  activeResearchRunId: string | null;
  activeResearchStatus: TaskStatus | null;
  activeResearchStage: ResearchStage | null;
  approvalPayload: Record<string, unknown> | null;

  // Loading
  loading: boolean;

  // Actions
  setCompanyContext: (content: string, status: ArtifactStatus) => void;
  setPersonas: (personas: Persona[]) => void;
  addPersona: (persona: Persona) => void;
  removePersona: (id: string) => void;
  setStyleGuide: (content: string, status: ArtifactStatus) => void;
  setKnowledgeDocs: (docs: KnowledgeDoc[]) => void;
  addKnowledgeDoc: (doc: KnowledgeDoc) => void;
  updateKnowledgeDoc: (id: string, updates: Partial<KnowledgeDoc>) => void;
  removeKnowledgeDoc: (id: string) => void;
  setProjects: (projects: Project[]) => void;
  addProject: (project: Project) => void;
  removeProject: (id: string) => void;
  setResearchRun: (runId: string, status: TaskStatus, stage: ResearchStage) => void;
  setApprovalPayload: (payload: Record<string, unknown> | null) => void;
  clearResearchRun: () => void;
  setLoading: (loading: boolean) => void;
  reset: () => void;
}

const initialState = {
  companyContext: null,
  companyContextStatus: 'none' as ArtifactStatus,
  personas: [],
  styleGuide: null,
  styleGuideStatus: 'none' as ArtifactStatus,
  knowledgeDocs: [],
  projects: [],
  activeResearchRunId: null,
  activeResearchStatus: null,
  activeResearchStage: null,
  approvalPayload: null,
  loading: false,
};

export const useBrandStore = create<BrandState>((set) => ({
  ...initialState,

  setCompanyContext: (content, status) =>
    set({ companyContext: content, companyContextStatus: status }),

  setPersonas: (personas) => set({ personas }),

  addPersona: (persona) =>
    set((state) => ({ personas: [...state.personas, persona] })),

  removePersona: (id) =>
    set((state) => ({ personas: state.personas.filter((p) => p.id !== id) })),

  setStyleGuide: (content, status) =>
    set({ styleGuide: content, styleGuideStatus: status }),

  setKnowledgeDocs: (docs) => set({ knowledgeDocs: docs }),

  addKnowledgeDoc: (doc) =>
    set((state) => ({ knowledgeDocs: [...state.knowledgeDocs, doc] })),

  updateKnowledgeDoc: (id, updates) =>
    set((state) => ({
      knowledgeDocs: state.knowledgeDocs.map((d) =>
        d.id === id ? { ...d, ...updates } : d
      ),
    })),

  removeKnowledgeDoc: (id) =>
    set((state) => ({
      knowledgeDocs: state.knowledgeDocs.filter((d) => d.id !== id),
    })),

  setProjects: (projects) => set({ projects }),

  addProject: (project) =>
    set((state) => ({ projects: [...state.projects, project] })),

  removeProject: (id) =>
    set((state) => ({ projects: state.projects.filter((p) => p.id !== id) })),

  setResearchRun: (runId, status, stage) =>
    set({
      activeResearchRunId: runId,
      activeResearchStatus: status,
      activeResearchStage: stage,
    }),

  setApprovalPayload: (payload) => set({ approvalPayload: payload }),

  clearResearchRun: () =>
    set({
      activeResearchRunId: null,
      activeResearchStatus: null,
      activeResearchStage: null,
      approvalPayload: null,
    }),

  setLoading: (loading) => set({ loading }),

  reset: () => set(initialState),
}));
