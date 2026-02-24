import { create } from 'zustand';
import type { ContentBriefItem, ContentBriefStatus, ContentType, Cycle } from '@/types/content';

interface ContentState {
  activeView: 'board' | 'table' | 'calendar' | 'cycles' | 'roadmap';
  setActiveView: (view: ContentState['activeView']) => void;

  statusFilter: ContentBriefStatus | 'all';
  typeFilter: ContentType | 'all';
  clusterFilter: string | 'all';
  cycleFilter: string | 'all';
  searchQuery: string;
  setFilter: (key: string, value: string) => void;

  briefs: ContentBriefItem[];
  setBriefs: (briefs: ContentBriefItem[]) => void;
  updateBrief: (id: string, updates: Partial<ContentBriefItem>) => void;

  activeCycle: Cycle | null;
  pastCycles: Cycle[];
  setCycles: (active: Cycle | null, past: Cycle[]) => void;

  activeBriefId: string | null;
  setActiveBrief: (id: string | null) => void;
}

export const useContentStore = create<ContentState>((set) => ({
  activeView: 'board',
  setActiveView: (view) => set({ activeView: view }),

  statusFilter: 'all',
  typeFilter: 'all',
  clusterFilter: 'all',
  cycleFilter: 'all',
  searchQuery: '',
  setFilter: (key, value) => set({ [key]: value }),

  briefs: [],
  setBriefs: (briefs) => set({ briefs }),
  updateBrief: (id, updates) =>
    set((state) => ({
      briefs: state.briefs.map((b) => (b.id === id ? { ...b, ...updates } : b)),
    })),

  activeCycle: null,
  pastCycles: [],
  setCycles: (active, past) => set({ activeCycle: active, pastCycles: past }),

  activeBriefId: null,
  setActiveBrief: (id) => set({ activeBriefId: id }),
}));
