'use client';

import { EmptyState } from '@/components/ui';
import { TrendingUp } from 'lucide-react';

export default function AttributionPage() {
  return (
    <div className="flex flex-col items-center justify-center py-20">
      <EmptyState
        title="Attribution Dashboard"
        description="Connect your analytics platform to track how AI citations drive revenue. This feature is coming soon."
        icon={<TrendingUp size={32} strokeWidth={1.5} className="text-text-tertiary" />}
      />
      <div className="mt-6 grid grid-cols-3 gap-4 max-w-xl w-full">
        <div className="bg-surface border border-border rounded-md p-4 text-center">
          <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Citation Impressions</p>
          <p className="font-display text-[20px] font-semibold text-text-tertiary mt-1">--</p>
        </div>
        <div className="bg-surface border border-border rounded-md p-4 text-center">
          <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">AI Click-Throughs</p>
          <p className="font-display text-[20px] font-semibold text-text-tertiary mt-1">--</p>
        </div>
        <div className="bg-surface border border-border rounded-md p-4 text-center">
          <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Revenue Attributed</p>
          <p className="font-display text-[20px] font-semibold text-text-tertiary mt-1">--</p>
        </div>
      </div>
    </div>
  );
}
