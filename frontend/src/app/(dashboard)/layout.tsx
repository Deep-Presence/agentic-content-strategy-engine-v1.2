'use client';

import { Sidebar } from '@/components/ui/Sidebar';
import { TopBar } from '@/components/ui/TopBar';
import { SearchCommand } from '@/components/ui/SearchCommand';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { useThemeStore } from '@/stores/theme';
import { useState, useEffect } from 'react';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { mode } = useThemeStore();
  const [searchOpen, setSearchOpen] = useState(false);

  useEffect(() => {
    if (mode === 'dark') {
      document.documentElement.setAttribute('data-theme', 'dark');
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
  }, [mode]);

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

  return (
    <AuthGuard>
      <div className="flex h-screen bg-bg overflow-hidden">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <TopBar onSearchClick={() => setSearchOpen(true)} />
          <main className="flex-1 overflow-y-auto p-4">
            {children}
          </main>
        </div>
        <SearchCommand
          open={searchOpen}
          onClose={() => setSearchOpen(false)}
          results={[
            { id: '1', label: 'Home', description: 'Dashboard overview', href: '/' },
            { id: '2', label: 'Citation Intelligence', description: 'AI citation tracking', href: '/analytics' },
            { id: '3', label: 'Competitive Position', description: 'Competitor analysis', href: '/competitive-position' },
            { id: '4', label: 'Prompt Tracking', description: 'Prompt monitoring', href: '/prompt-tracking' },
            { id: '5', label: 'Content Performance', description: 'Content metrics', href: '/content-performance' },
            { id: '6', label: 'Technical Readiness', description: 'Technical SEO audit', href: '/technical-readiness' },
            { id: '7', label: 'Embedding Lab', description: 'Deep embedding analysis', href: '/embedding-lab' },
            { id: '8', label: 'Content Planner', description: 'Topic planning', href: '/planner' },
            { id: '9', label: 'Content Studio', description: 'Content pipeline', href: '/content' },
            { id: '10', label: 'Brand Brain', description: 'Knowledge base & voice', href: '/artifacts' },
            { id: '11', label: 'Documents', description: 'Document library', href: '/documents' },
            { id: '12', label: 'Settings', description: 'Configuration', href: '/settings' },
          ]}
        />
      </div>
    </AuthGuard>
  );
}
