import { create } from 'zustand';

interface WorkspaceState {
  companyName: string;
  projectName: string;
  setCompany: (name: string) => void;
  setProject: (name: string) => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  companyName: 'Lovable',
  projectName: 'lovable.dev',
  setCompany: (name) => set({ companyName: name }),
  setProject: (name) => set({ projectName: name }),
}));
