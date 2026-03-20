'use client';

import { Sidebar } from '@/components/ui/Sidebar';
import { TopBar } from '@/components/ui/TopBar';
import { SearchCommand } from '@/components/ui/SearchCommand';
import { SWRProvider } from '@/lib/api/SWRProvider';
import { useThemeStore } from '@/stores/theme';
import { useAuthStore } from '@/stores/auth';
import { useWorkspaceStore } from '@/stores/workspace';
import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { mode, hydrate: hydrateTheme } = useThemeStore();
  const { company, hydrateFromStorage, fetchMe } = useAuthStore();
  const { setCompany, setProject } = useWorkspaceStore();
  const [searchOpen, setSearchOpen] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);
  const router = useRouter();
  const checkedRef = useRef(false);

  // Auth guard: validate token on mount
  useEffect(() => {
    if (checkedRef.current) return;
    checkedRef.current = true;

    const checkAuth = async () => {
      hydrateFromStorage();
      const storedToken = localStorage.getItem('dp_token');
      if (!storedToken) {
        router.replace('/login');
        return;
      }
      const valid = await fetchMe();
      if (!valid) {
        router.replace('/login');
        return;
      }
      setAuthChecked(true);
    };

    checkAuth();
  }, [hydrateFromStorage, fetchMe, router]);

  // Sync workspace store with auth company
  useEffect(() => {
    if (company) {
      setCompany(company.name);
      setProject(company.domain);
    }
  }, [company, setCompany, setProject]);

  // Hydrate theme from localStorage on mount
  useEffect(() => { hydrateTheme(); }, [hydrateTheme]);

  // Theme sync
  useEffect(() => {
    if (mode === 'dark') {
      document.documentElement.setAttribute('data-theme', 'dark');
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
  }, [mode]);

  // Cmd+K shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setSearchOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // Show loading state while checking auth
  if (!authChecked) {
    return (
      <div className="flex h-screen bg-bg items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          <span className="text-[13px] text-text-secondary">Loading...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-bg overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar onSearchClick={() => setSearchOpen(true)} />
        <main className="flex-1 overflow-y-auto p-4">
          <SWRProvider>
            {children}
          </SWRProvider>
        </main>
      </div>
      <SearchCommand
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        results={[
          { id: '1', label: 'Home', description: 'Dashboard overview', href: '/' },
          { id: '2', label: 'Analytics', description: 'Measurement dashboard', href: '/analytics' },
          { id: '3', label: 'Content Studio', description: 'Content pipeline', href: '/content' },
          { id: '4', label: 'Content Planner', description: 'Topic planning', href: '/planner' },
          { id: '5', label: 'Brand Artifacts', description: 'KB, personas, voice', href: '/artifacts' },
          { id: '6', label: 'Attribution', description: 'Revenue attribution', href: '/attribution' },
          { id: '7', label: 'Settings', description: 'Configuration', href: '/settings' },
        ]}
      />
    </div>
  );
}
