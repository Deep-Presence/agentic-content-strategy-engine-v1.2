'use client';

import { Card, Skeleton } from '@/components/ui';

function SkeletonCard() {
  return (
    <Card className="!p-5">
      <div className="flex items-start gap-3">
        <Skeleton variant="rectangular" width={36} height={36} className="shrink-0" />
        <div className="flex-1 space-y-2">
          <Skeleton width="60%" height={14} />
          <Skeleton width="90%" height={10} />
          <Skeleton width="40%" height={10} />
        </div>
      </div>
    </Card>
  );
}

export function HubSkeleton() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton width={200} height={20} />
          <Skeleton width={140} height={12} />
        </div>
        <Skeleton variant="rectangular" width={120} height={30} />
      </div>

      {/* Activity bar */}
      <Card className="!p-4">
        <div className="flex items-center gap-4">
          <Skeleton variant="circular" width={8} height={8} />
          <Skeleton width={200} height={12} />
          <div className="ml-auto flex gap-6">
            <Skeleton width={60} height={12} />
            <Skeleton width={60} height={12} />
            <Skeleton width={60} height={12} />
          </div>
        </div>
      </Card>

      {/* Card grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 9 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    </div>
  );
}

export function DetailSkeleton() {
  return (
    <div className="space-y-6">
      {/* Breadcrumb + title */}
      <div className="space-y-3">
        <Skeleton width={200} height={12} />
        <Skeleton width={300} height={20} />
      </div>

      {/* Two-column layout */}
      <div className="flex gap-6">
        {/* Main content */}
        <div className="flex-1 space-y-4">
          <Card className="!p-6 space-y-4">
            <Skeleton width="80%" height={16} />
            <Skeleton width="100%" height={12} />
            <Skeleton width="95%" height={12} />
            <Skeleton width="60%" height={12} />
            <Skeleton width="100%" height={12} />
            <Skeleton width="85%" height={12} />
            <Skeleton width="70%" height={16} className="mt-6" />
            <Skeleton width="100%" height={12} />
            <Skeleton width="90%" height={12} />
            <Skeleton width="45%" height={12} />
          </Card>
        </div>

        {/* Sidebar */}
        <div className="w-[240px] shrink-0 space-y-4">
          <Card className="!p-4 space-y-3">
            <Skeleton width={100} height={12} />
            <Skeleton width="100%" height={10} />
            <Skeleton width="80%" height={10} />
            <Skeleton width="60%" height={10} />
          </Card>
          <Card className="!p-4 space-y-3">
            <Skeleton width={120} height={12} />
            <Skeleton width="100%" height={10} />
          </Card>
        </div>
      </div>
    </div>
  );
}

export function PersonaListSkeleton() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Skeleton width={200} height={20} />
        <div className="flex gap-2">
          <Skeleton variant="rectangular" width={100} height={30} />
          <Skeleton variant="rectangular" width={100} height={30} />
        </div>
      </div>

      {/* Table rows */}
      <Card className="!p-0 overflow-hidden">
        {/* Header row */}
        <div className="flex items-center gap-4 px-4 py-3 border-b border-[var(--border)]">
          <Skeleton width={150} height={10} />
          <Skeleton width={80} height={10} className="ml-auto" />
          <Skeleton width={80} height={10} />
          <Skeleton width={60} height={10} />
        </div>
        {/* Data rows */}
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 px-4 py-3 border-b border-[var(--border)] last:border-b-0">
            <div className="flex items-center gap-3">
              <Skeleton variant="circular" width={32} height={32} />
              <div className="space-y-1">
                <Skeleton width={120} height={12} />
                <Skeleton width={80} height={10} />
              </div>
            </div>
            <Skeleton width={80} height={10} className="ml-auto" />
            <Skeleton width={80} height={10} />
            <Skeleton width={40} height={10} />
          </div>
        ))}
      </Card>
    </div>
  );
}
