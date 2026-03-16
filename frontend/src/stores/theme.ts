import { create } from 'zustand';

interface ThemeState {
  mode: 'light' | 'dark';
  toggle: () => void;
}

export const useThemeStore = create<ThemeState>((set) => ({
  mode: 'light',
  toggle: () => set((s) => ({ mode: s.mode === 'light' ? 'dark' : 'light' })),
}));
