import { create } from 'zustand';

import { api } from '@/lib/api-client';

export interface Workspace {
  id: string;
  slug: string;
  name: string;
  color: string;
  role?: string;
  primaryDomain?: string;
}

interface WorkspaceState {
  workspaces: Workspace[];
  activeWorkspaceSlug: string;
  isLoading: boolean;
  isInitialized: boolean;
  fetchWorkspaces: () => Promise<void>;
  setActiveWorkspace: (slug: string) => void;
  createWorkspace: (payload: {
    name: string;
    primary_domain: string;
    slug?: string;
  }) => Promise<Workspace>;
  reset: () => void;
}

const STORAGE_KEY = 'dp_active_workspace_slug';

function readStoredSlug(): string {
  if (typeof window === 'undefined') return '';
  return window.sessionStorage.getItem(STORAGE_KEY) ?? '';
}

function writeStoredSlug(slug: string): void {
  if (typeof window === 'undefined') return;
  if (slug) {
    window.sessionStorage.setItem(STORAGE_KEY, slug);
  } else {
    window.sessionStorage.removeItem(STORAGE_KEY);
  }
}

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  workspaces: [],
  activeWorkspaceSlug: '',
  isLoading: false,
  isInitialized: false,

  fetchWorkspaces: async () => {
    set({ isLoading: true });
    try {
      const data = await api.get<{ workspaces: Array<Record<string, unknown>> }>(
        '/api/v1/workspaces',
      );
      const workspaces: Workspace[] = (data.workspaces ?? []).map((item) => ({
        id: String(item.id),
        slug: String(item.slug),
        name: String(item.name),
        color: String(item.color ?? '#5BA4C4'),
        role: item.role ? String(item.role) : undefined,
        primaryDomain: item.primary_domain ? String(item.primary_domain) : undefined,
      }));

      const storedSlug = readStoredSlug();
      const fallbackSlug = workspaces[0]?.slug ?? '';
      const activeWorkspaceSlug =
        workspaces.find((workspace) => workspace.slug === storedSlug)?.slug ??
        fallbackSlug;

      if (activeWorkspaceSlug) {
        writeStoredSlug(activeWorkspaceSlug);
      }

      set({
        workspaces,
        activeWorkspaceSlug,
        isInitialized: true,
        isLoading: false,
      });
    } catch {
      set({ isLoading: false, isInitialized: true });
    }
  },

  setActiveWorkspace: (slug) => {
    const workspace = get().workspaces.find((item) => item.slug === slug);
    if (!workspace) return;
    writeStoredSlug(slug);
    set({ activeWorkspaceSlug: slug });
  },

  createWorkspace: async (payload) => {
    const created = await api.post<Record<string, unknown>>('/api/v1/workspaces', payload);
    const workspace: Workspace = {
      id: String(created.id),
      slug: String(created.slug),
      name: String(created.name),
      color: String(created.color ?? '#5BA4C4'),
      role: created.role ? String(created.role) : 'owner',
      primaryDomain: created.primary_domain ? String(created.primary_domain) : undefined,
    };
    set((state) => ({
      workspaces: [...state.workspaces, workspace],
      activeWorkspaceSlug: workspace.slug,
    }));
    writeStoredSlug(workspace.slug);
    return workspace;
  },

  reset: () => {
    writeStoredSlug('');
    set({
      workspaces: [],
      activeWorkspaceSlug: '',
      isInitialized: false,
      isLoading: false,
    });
  },
}));

export function getActiveWorkspaceSlug(fallbackCompanySlug = ''): string {
  const { activeWorkspaceSlug } = useWorkspaceStore.getState();
  return activeWorkspaceSlug || fallbackCompanySlug;
}
