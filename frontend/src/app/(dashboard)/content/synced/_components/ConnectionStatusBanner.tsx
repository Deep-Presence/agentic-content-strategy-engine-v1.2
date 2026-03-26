'use client';

import Link from 'next/link';
import { Globe, Info } from 'lucide-react';
import { Card, Badge, Skeleton } from '@/components/ui';
import type { CMSConnectionInfo } from '@/lib/api/types';

interface ConnectionStatusBannerProps {
  connection: CMSConnectionInfo | null;
  isLoading: boolean;
}

function formatRelativeTime(iso: string | null): string {
  if (!iso) return 'Never';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function ConnectionStatusBanner({ connection, isLoading }: ConnectionStatusBannerProps) {
  if (isLoading) {
    return <Skeleton className="h-[52px] w-full rounded-sm" />;
  }

  if (!connection) {
    return (
      <Card className="p-3">
        <div className="flex items-center gap-2">
          <Info size={16} strokeWidth={1.5} className="text-text-tertiary shrink-0" />
          <p className="text-[13px] text-text-secondary">
            No CMS connected.{' '}
            <Link
              href="/settings?tab=integrations"
              className="text-accent hover:underline"
            >
              Connect in Settings
            </Link>{' '}
            to sync existing content.
          </p>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-3">
      <div className="flex items-center gap-3">
        <Globe size={16} strokeWidth={1.5} className="text-accent shrink-0" />
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="info">{connection.provider}</Badge>
          <span className="text-[13px] text-text-primary font-medium">
            {connection.site_name || connection.site_url}
          </span>
          <span className="text-[11px] text-text-tertiary">
            {connection.sync_post_count} posts synced
          </span>
          <span className="text-[11px] text-text-tertiary">
            Last sync: {formatRelativeTime(connection.last_sync_at)}
          </span>
        </div>
      </div>
    </Card>
  );
}
