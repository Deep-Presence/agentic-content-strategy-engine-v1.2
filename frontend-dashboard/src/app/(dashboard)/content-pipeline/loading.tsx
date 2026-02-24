import { Skeleton } from '@/components/ui/skeleton';

export default function ContentPipelineLoading() {
  return (
    <div className="space-y-6">
      {/* Header skeleton */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-72" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-9 w-28" />
          <Skeleton className="h-9 w-40" />
        </div>
      </div>

      {/* View switcher skeleton */}
      <div className="flex gap-2 border-b border-[var(--border-default)] pb-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-8 w-20" />
        ))}
      </div>

      {/* Filter bar skeleton */}
      <div className="flex gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-8 w-32" />
        ))}
      </div>

      {/* Board columns skeleton */}
      <div className="flex gap-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="w-[300px] shrink-0 space-y-3">
            <Skeleton className="h-6 w-24" />
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-32 w-full" />
            {i < 3 && <Skeleton className="h-32 w-full" />}
          </div>
        ))}
      </div>
    </div>
  );
}
