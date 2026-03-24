'use client';

import { Sidebar } from '@/components/ui/Sidebar';
import { TopBar } from '@/components/ui/TopBar';
import { SearchCommand } from '@/components/ui/SearchCommand';
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
