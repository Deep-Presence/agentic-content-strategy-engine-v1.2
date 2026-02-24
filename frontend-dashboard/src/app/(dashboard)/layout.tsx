'use client';

import { useEffect } from 'react';
import { SidebarNav } from '@/components/layout/sidebar-nav';
import { TopBar } from '@/components/layout/top-bar';
import { useAppStore } from '@/stores/app-store';
import { artifacts } from '@/lib/api/artifacts';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { setCompanies, setCurrentCompany, currentCompany } = useAppStore();

  useEffect(() => {
    artifacts
      .listCompanies()
      .then((res) => {
        setCompanies(res.companies);
        if (!currentCompany && res.companies.length > 0) {
          setCurrentCompany(res.companies[0]);
        }
      })
      .catch(() => {
        // Backend not available, use fallback
        setCompanies(['webflow', 'ramp', 'carta']);
        if (!currentCompany) {
          setCurrentCompany('webflow');
        }
      });
  }, [setCompanies, setCurrentCompany, currentCompany]);

  return (
    <div className="flex h-screen overflow-hidden">
      <SidebarNav />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto bg-[var(--bg-primary)]">
          <div className="max-w-7xl mx-auto px-6 py-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
