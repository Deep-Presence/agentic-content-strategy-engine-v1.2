import { Skeleton } from '@/components/ui/skeleton';

export default function EmbeddingLabLoading() {
  return (
    <div className="space-y-6">
      {/* Page header skeleton */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-96" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-9 w-36" />
          <Skeleton className="h-9 w-32" />
          <Skeleton className="h-9 w-24" />
        </div>
      </div>

      {/* Tab bar skeleton */}
      <div className="flex gap-1 border-b border-[var(--border-default)] pb-0">
        <Skeleton className="h-10 w-32" />
        <Skeleton className="h-10 w-24" />
        <Skeleton className="h-10 w-24" />
        <Skeleton className="h-10 w-28" />
        <Skeleton className="h-10 w-24" />
        <Skeleton className="h-10 w-40" />
      </div>

      {/* Main chart area skeleton */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="lg:col-span-3">
          <Skeleton className="h-[500px] w-full rounded-md" />
        </div>
        <div className="space-y-4">
          <Skeleton className="h-24 w-full rounded-md" />
          <Skeleton className="h-24 w-full rounded-md" />
          <Skeleton className="h-24 w-full rounded-md" />
          <Skeleton className="h-24 w-full rounded-md" />
        </div>
      </div>
    </div>
  );
}
