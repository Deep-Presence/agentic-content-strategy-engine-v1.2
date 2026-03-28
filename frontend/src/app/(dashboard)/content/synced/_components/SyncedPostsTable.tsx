'use client';

import { ExternalLink } from 'lucide-react';
import { Badge, Skeleton, EmptyState } from '@/components/ui';
import type { CMSSyncedPostSummary } from '@/lib/api/types';

interface SyncedPostsTableProps {
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
  if (months < 12) return `${months}mo ago`;
  const years = Math.floor(months / 12);
  return `${years}y ago`;
}

function getStatusBadge(post: CMSSyncedPostSummary) {
  if (post.queued_for_refresh) {
    return <Badge variant="info">Queued</Badge>;
  }
  if (post.is_stale) {
    return <Badge variant="warning">Stale &middot; {post.staleness_days}d</Badge>;
  }
  return <Badge variant="success">Fresh</Badge>;
}

function truncateUrl(url: string): string {
  try {
    const parsed = new URL(url);
    const path = parsed.pathname;
    return path.length > 40 ? path.slice(0, 37) + '...' : path;
  } catch {
    return url.length > 40 ? url.slice(0, 37) + '...' : url;
  }
}

export function SyncedPostsTable({ posts, isLoading }: SyncedPostsTableProps) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-[40px] w-full rounded-sm" />
        ))}
      </div>
    );
  }

  if (posts.length === 0) {
    return (
      <EmptyState
        title="No synced posts yet"
        description="Connect your CMS in Settings to import existing content."
      />
    );
  }

  return (
    <div className="border border-border rounded-sm overflow-hidden">
      {/* Header */}
      <div className="grid grid-cols-[1fr_120px_70px_80px_80px_90px_100px] gap-2 px-3 py-2 bg-surface border-b border-border">
        <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
          Title
        </span>
        <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
          URL
        </span>
        <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-right">
          Words
        </span>
        <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
          Published
        </span>
        <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
          Modified
        </span>
        <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
          Status
        </span>
        <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
          Categories
        </span>
      </div>

      {/* Rows */}
      {posts.map((post) => (
        <div
          key={post.id}
          className="grid grid-cols-[1fr_120px_70px_80px_80px_90px_100px] gap-2 px-3 py-1.5 border-b border-border-subtle last:border-b-0 hover:bg-accent-subtle/30 transition-colors"
        >
          <span
            className="text-[13px] font-medium text-text-primary truncate"
            title={post.title}
          >
            {post.title}
          </span>

          <a
            href={post.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[11px] text-accent truncate flex items-center gap-0.5 hover:underline"
            title={post.url}
          >
            <span className="truncate">{truncateUrl(post.url)}</span>
            <ExternalLink size={9} strokeWidth={1.5} className="shrink-0" />
          </a>

          <span className="text-[11px] text-text-secondary text-right font-mono">
            {post.word_count.toLocaleString()}
          </span>

          <span className="text-[11px] text-text-tertiary">
            {formatRelativeDate(post.published_at)}
          </span>

          <span className="text-[11px] text-text-tertiary">
            {formatRelativeDate(post.modified_at)}
          </span>

          <div className="flex items-center">
            {getStatusBadge(post)}
          </div>

          <span
            className="text-[11px] text-text-tertiary truncate"
            title={post.categories.join(', ')}
          >
            {post.categories.length > 0 ? post.categories.join(', ') : '—'}
          </span>
        </div>
      ))}
    </div>
  );
}
