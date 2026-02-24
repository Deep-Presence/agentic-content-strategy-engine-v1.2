import { Skeleton } from '@/components/ui/skeleton';

export default function SignalAnalysisLoading() {
  return (
    <div className="space-y-8">
      {/* Page header skeleton */}
      <div className="flex items-start justify-between">
        <div>
          <Skeleton className="h-8 w-64 mb-2" />
          <Skeleton className="h-5 w-96" />
        </div>
        <Skeleton className="h-10 w-40" />
      </div>

      {/* SPA Score card skeleton */}
      <Skeleton className="h-48 w-full rounded-md" />

      {/* Cluster grid skeleton */}
      <div>
        <Skeleton className="h-7 w-48 mb-4" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 9 }).map((_, i) => (
            <Skeleton key={i} className="h-44 rounded-md" />
          ))}
        </div>
      </div>

      {/* Table skeleton */}
      <div>
        <Skeleton className="h-7 w-40 mb-4" />
        <Skeleton className="h-10 w-full rounded-md mb-2" />
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full mb-1 rounded" />
        ))}
      </div>
    </div>
  );
}
