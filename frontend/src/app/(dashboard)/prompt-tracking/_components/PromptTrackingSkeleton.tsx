'use client';

import { cn } from '@/lib/utils';

function Shimmer({ className }: { className?: string }) {
  return (
    <div
      className={cn('rounded bg-surface-raised animate-pulse', className)}
    />
  );
}

/** Skeleton for the main prompt table — 8 rows. */
export function PromptTableSkeleton() {
  return (
    <div className="flex flex-col gap-0">
      {/* Filter bar skeleton */}
      <div className="flex items-center gap-3 mb-4">
        <Shimmer className="h-[34px] w-[200px]" />
        <Shimmer className="h-[34px] w-[140px]" />
        <Shimmer className="h-[34px] w-[100px]" />
      </div>
      {/* Sub-nav bar skeleton */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex gap-2">
          <Shimmer className="h-[30px] w-[70px]" />
          <Shimmer className="h-[30px] w-[70px]" />
        </div>
        <div className="flex gap-2">
          <Shimmer className="h-[30px] w-[180px]" />
          <Shimmer className="h-[30px] w-[100px]" />
        </div>
      </div>
      {/* Table header */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 140px 80px 60px 60px 100px 100px',
          gap: 8,
          padding: '8px 12px',
          borderBottom: '1px solid var(--border)',
        }}
      >
        {Array.from({ length: 7 }).map((_, i) => (
          <Shimmer key={i} className="h-[12px]" />
        ))}
      </div>
      {/* Table rows */}
      {Array.from({ length: 8 }).map((_, row) => (
        <div
          key={row}
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 140px 80px 60px 60px 100px 100px',
            gap: 8,
            padding: '10px 12px',
            borderBottom: '1px solid var(--border-subtle)',
          }}
        >
          <Shimmer className="h-[14px] w-[80%]" />
          <Shimmer className="h-[22px] w-[100px] rounded-full" />
          <Shimmer className="h-[18px] w-[60px]" />
          <Shimmer className="h-[14px] w-[30px]" />
          <Shimmer className="h-[14px] w-[56px]" />
          <Shimmer className="h-[14px] w-[60px]" />
          <Shimmer className="h-[14px] w-[60px]" />
        </div>
      ))}
    </div>
  );
}

/** Skeleton for the prompt detail drawer sections. */
export function PromptDrawerSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      {/* Competitor section */}
      <div style={{ padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
        <Shimmer className="h-[12px] w-[200px] mb-3" />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div className="flex flex-col gap-2">
            <Shimmer className="h-[36px] w-[60px]" />
            {Array.from({ length: 5 }).map((_, i) => (
              <Shimmer key={i} className="h-[20px]" />
            ))}
          </div>
          <div className="flex flex-col gap-3">
            <Shimmer className="h-[12px] w-[160px]" />
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex flex-col gap-1">
                <Shimmer className="h-[14px] w-[120px]" />
                <Shimmer className="h-[4px]" />
              </div>
            ))}
          </div>
        </div>
      </div>
      {/* Fanouts section */}
      <div style={{ padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
        <Shimmer className="h-[12px] w-[140px] mb-3" />
        {Array.from({ length: 4 }).map((_, i) => (
          <Shimmer key={i} className="h-[18px] mb-2" />
        ))}
      </div>
      {/* Answer history section */}
      <div style={{ padding: '12px 0' }}>
        <Shimmer className="h-[12px] w-[160px] mb-3" />
        {Array.from({ length: 6 }).map((_, i) => (
          <Shimmer key={i} className="h-[22px] mb-2" />
        ))}
      </div>
    </div>
  );
}
