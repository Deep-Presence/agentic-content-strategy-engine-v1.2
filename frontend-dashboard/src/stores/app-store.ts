import { create } from 'zustand';

interface AppState {
  currentCompany: string;
  setCurrentCompany: (slug: string) => void;
  companies: string[];
  setCompanies: (companies: string[]) => void;
  sidebarOpen: boolean;
  toggleSidebar: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  currentCompany: '',
  setCurrentCompany: (slug) => set({ currentCompany: slug }),
  companies: [],
  setCompanies: (companies) => set({ companies }),
  sidebarOpen: true,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
}));
