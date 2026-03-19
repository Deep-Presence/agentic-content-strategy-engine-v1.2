import { create } from 'zustand';

interface ThemeState {
  mode: 'light' | 'dark';
  toggle: () => void;
  hydrate: () => void;
}

export const useThemeStore = create<ThemeState>((set) => ({
  mode: 'light',
  toggle: () =>
    set((s) => {
      const next = s.mode === 'light' ? 'dark' : 'light';
      try { localStorage.setItem('dp_theme', next); } catch { /* SSR-safe */ }
      return { mode: next };
    }),
  hydrate: () => {
    try {
      const saved = localStorage.getItem('dp_theme');
      if (saved === 'dark' || saved === 'light') {
        set({ mode: saved });
      }
    } catch { /* SSR-safe */ }
  },
}));
