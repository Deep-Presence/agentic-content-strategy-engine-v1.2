import { create } from 'zustand';

export interface Workspace {
  id: string;
  name: string;
  color: string;
}

interface WorkspaceState {
  workspaces: Workspace[];
  activeWorkspaceId: string;
  companyName: string;
  projectName: string;
  setActiveWorkspace: (id: string) => void;
  addWorkspace: (name: string) => void;
  setCompany: (name: string) => void;
  setProject: (name: string) => void;
}

const defaultWorkspaces: Workspace[] = [
  { id: '1', name: 'Insight Health', color: '#5BA4C4' },
  { id: '2', name: 'Lovable', color: '#34B27B' },
];

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  workspaces: defaultWorkspaces,
  activeWorkspaceId: '1',
  companyName: 'Insight Health',
  projectName: 'insighthealth.com',
  setActiveWorkspace: (id) => {
    const workspace = get().workspaces.find((w) => w.id === id);
    set({
      activeWorkspaceId: id,
      companyName: workspace?.name ?? get().companyName,
    });
  },
  addWorkspace: (name) =>
    set((state) => {
      const newId = String(Date.now());
      return {
        workspaces: [
          ...state.workspaces,
          { id: newId, name, color: '#5BA4C4' },
        ],
        activeWorkspaceId: newId,
        companyName: name,
      };
    }),
  setCompany: (name) => set({ companyName: name }),
  setProject: (name) => set({ projectName: name }),
}));
