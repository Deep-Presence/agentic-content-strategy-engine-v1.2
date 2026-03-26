'use client';

import { StatusDot, Skeleton, EmptyState } from '@/components/ui';
import { ExternalLink } from 'lucide-react';
import { isSafeUrl } from '@/lib/utils';
import type { CMSSyncedPostSummary } from '@/lib/api/types';

interface CMSSyncedPostsTableProps {
  posts: CMSSyncedPostSummary[];
  isLoading: boolean;
}

function formatRelativeDate(isoDate: string | null): string {
  if (!isoDate) return '—';
  const diff = Date.now() - new Date(isoDate).getTime();
  const days = Math.floor(diff / 86_400_000);
  if (days < 1) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  return `${months}mo ago`;
}

function safePathname(url: string): string {
  try { return new URL(url).pathname; }
  catch { return url.length > 40 ? url.slice(0, 40) + '...' : url; }
}

export function CMSSyncedPostsTable({ posts, isLoading }: CMSSyncedPostsTableProps) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-[36px] w-full rounded-sm" />
        ))}
      </div>
    );
  }

  if (posts.length === 0) {
    return <EmptyState title="No posts synced yet" description="Click 'Sync Now' to import existing CMS content." />;
  }

  return (
    <div className="border border-border rounded-sm overflow-hidden">
      {/* Header */}
      <div className="grid grid-cols-[1fr_1fr_80px_100px_60px] gap-2 px-3 py-2 bg-surface-raised border-b border-border">
        <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Title</span>
        <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">URL</span>
        <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-right">Words</span>
        <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Modified</span>
        <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-center">Stale</span>
      </div>

      {/* Rows */}
      {posts.map((post) => (
        <div
          key={post.id}
          className="grid grid-cols-[1fr_1fr_80px_100px_60px] gap-2 px-3 py-1.5 border-b border-border-subtle last:border-b-0 hover:bg-surface-raised/50 transition-colors"
        >
          <span className="text-[12px] text-text-primary truncate" title={post.title}>
            {post.title}
          </span>
          {isSafeUrl(post.url) ? (
            <a
              href={post.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[11px] text-accent truncate flex items-center gap-0.5 hover:underline"
              title={post.url}
            >
              {safePathname(post.url)}
              <ExternalLink size={9} strokeWidth={1.5} className="shrink-0" />
            </a>
          ) : (
            <span className="text-[11px] text-text-secondary truncate" title={post.url}>
              {safePathname(post.url)}
            </span>
          )}
          <span className="text-[11px] text-text-secondary text-right font-mono">
            {post.word_count.toLocaleString()}
          </span>
          <span className="text-[11px] text-text-tertiary">
            {formatRelativeDate(post.modified_at)}
          </span>
          <div className="flex justify-center items-center">
            <StatusDot color={post.is_stale ? 'error' : 'success'} />
          </div>
        </div>
      ))}
    </div>
  );
}
