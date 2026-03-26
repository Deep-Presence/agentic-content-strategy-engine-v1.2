'use client';

import { useState, useMemo } from 'react';
import { RefreshCw } from 'lucide-react';
import { useCMSConnection, useCMSSyncedPosts } from '@/lib/hooks/useCMS';
import { ConnectionStatusBanner } from './_components/ConnectionStatusBanner';
import { SyncedPostsFilter } from './_components/SyncedPostsFilter';
import { SyncedPostsTable } from './_components/SyncedPostsTable';

export default function SyncedContentPage() {
  const { data: connection, isLoading: connLoading } = useCMSConnection();
  const [staleOnly, setStaleOnly] = useState(false);
  const { data: posts, isLoading: postsLoading } = useCMSSyncedPosts({
    staleOnly,
    limit: 200,
  });

  const postList = posts ?? [];
  const staleCount = useMemo(
    () => postList.filter((p) => p.is_stale).length,
    [postList],
  );

  return (
    <div className="max-w-[960px] mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <RefreshCw size={18} strokeWidth={1.5} className="text-accent" />
        <h1 className="font-display text-[20px] font-semibold tracking-[-0.02em] text-text-primary">
          Synced Content
        </h1>
      </div>

      {/* Connection status */}
      <ConnectionStatusBanner connection={connection ?? null} isLoading={connLoading} />

      {/* Filter bar */}
      {postList.length > 0 && (
        <SyncedPostsFilter
          staleOnly={staleOnly}
          onStaleOnlyChange={setStaleOnly}
          totalCount={postList.length}
          staleCount={staleCount}
        />
      )}

      {/* Table */}
      <SyncedPostsTable posts={postList} isLoading={postsLoading} />
    </div>
  );
}
