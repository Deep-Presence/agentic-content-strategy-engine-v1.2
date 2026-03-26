'use client';

import { Toggle } from '@/components/ui';

interface SyncedPostsFilterProps {
  staleOnly: boolean;
  onStaleOnlyChange: (val: boolean) => void;
  totalCount: number;
  staleCount: number;
}

export function SyncedPostsFilter({
  staleOnly,
  onStaleOnlyChange,
  totalCount,
  staleCount,
}: SyncedPostsFilterProps) {
  return (
    <div className="flex items-center justify-between">
      <p className="text-[12px] text-text-secondary">
        {totalCount} {totalCount === 1 ? 'post' : 'posts'} synced
        {staleCount > 0 && (
          <span className="text-text-tertiary">
            {' '}&middot; {staleCount} stale
          </span>
        )}
      </p>

      <label className="flex items-center gap-2 cursor-pointer">
        <span className="text-[12px] text-text-secondary">Show stale only</span>
        <Toggle checked={staleOnly} onChange={onStaleOnlyChange} />
      </label>
    </div>
  );
}
