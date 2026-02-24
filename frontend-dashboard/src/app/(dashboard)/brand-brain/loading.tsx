import { Skeleton } from '@/components/ui/skeleton';

export default function BrandBrainLoading() {
  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <Skeleton className="h-8 w-48 mb-2" />
          <Skeleton className="h-5 w-80" />
        </div>
        <Skeleton className="h-9 w-32" />
      </div>

      {/* Knowledge Completeness */}
      <div className="bg-white rounded-md border border-[var(--border-default)] p-5">
        <Skeleton className="h-6 w-56 mb-4" />
        <div className="flex items-center gap-4 mb-4">
          <Skeleton className="h-2 flex-1 rounded-full" />
          <Skeleton className="h-5 w-10" />
        </div>
        <div className="space-y-2.5">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="flex items-center gap-2.5">
              <Skeleton className="h-4 w-4 rounded-full" />
              <Skeleton className="h-4 flex-1" />
              <Skeleton className="h-4 w-32" />
            </div>
          ))}
        </div>
      </div>

      {/* Quick Actions */}
      <div>
        <Skeleton className="h-6 w-32 mb-4" />
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-20 rounded-md" />
          ))}
        </div>
      </div>

      {/* Projects */}
      <div>
        <Skeleton className="h-6 w-28 mb-4" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2].map((i) => (
            <Skeleton key={i} className="h-48 rounded-md" />
          ))}
        </div>
      </div>

      {/* Recent Research Runs */}
      <div>
        <Skeleton className="h-6 w-48 mb-4" />
        <Skeleton className="h-40 rounded-md" />
      </div>
    </div>
  );
}
