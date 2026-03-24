'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { EmptyState } from '@/components/ui';
import { ActiveTasks } from './_components/home/ActiveTasks';
import { HITLReviews } from './_components/home/HITLReviews';
import { RecentActivity } from './_components/home/RecentActivity';

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

function formatDate(): string {
  return new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

const KPI_DATA = [
  { label: 'Published', value: '7', delta: '+2 this week', deltaType: 'positive' as const },
  { label: 'Cited Queries', value: '8', delta: '4 platforms', deltaType: 'neutral' as const },
  { label: 'Total Citations', value: '1,816', delta: '+142', deltaType: 'positive' as const },
  { label: 'SOV', value: '12.4%', delta: '+1.8pp', deltaType: 'positive' as const },
  { label: 'Pipeline Value', value: '$284K', delta: '3 briefs active', deltaType: 'neutral' as const },
  { label: 'AEO Score', value: '38.7', delta: '/100', deltaType: 'neutral' as const },
];

export default function HomePage() {
  const router = useRouter();
  const [hasData] = useState(true);

  if (!hasData) {
    return (
      <EmptyState
        title="Welcome to Deep Presence"
        description="Start by analyzing your brand to see how you're cited across AI platforms."
        action={{
          label: 'Begin Analysis →',
          onClick: () => router.push('/onboarding'),
        }}
      />
    );
  }

  return (
    <div className="max-w-[960px] mx-auto space-y-6">
      {/* Welcome header */}
      <div>
        <h1 className="font-display text-[24px] font-semibold tracking-[-0.02em] text-text-primary mb-0.5">
          {getGreeting()}, Shank
        </h1>
        <p className="text-[14px] text-text-secondary leading-[1.6]">
          {formatDate()}
        </p>
      </div>

      {/* Outcomes Strip — 6 KPIs */}
      <div
        className="grid gap-[1px] bg-border rounded-sm overflow-hidden"
        style={{ gridTemplateColumns: 'repeat(6, 1fr)' }}
      >
        {KPI_DATA.map((kpi) => (
          <div key={kpi.label} className="bg-bg px-3 py-3">
            <p className="text-[11px] font-medium uppercase tracking-[0.06em] text-text-tertiary leading-[1.4]">
              {kpi.label}
            </p>
            <div className="flex items-baseline gap-1.5 mt-1">
              <p className="font-display text-[28px] font-semibold tracking-[-0.02em] text-text-primary">
                {kpi.value}
              </p>
              {kpi.delta && (
                <p className={`text-[11px] font-medium ${
                  kpi.deltaType === 'positive' ? 'text-success' : 'text-text-tertiary'
                }`}>
                  {kpi.delta}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Two-column layout for tasks + reviews */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <ActiveTasks />
        <HITLReviews />
      </div>

      {/* Recent Activity */}
      <RecentActivity />
    </div>
  );
}
