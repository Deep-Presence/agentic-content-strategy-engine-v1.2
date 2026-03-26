'use client';

import { Badge, Button, Card, ProgressBar } from '@/components/ui';
import type { CMSConnectionInfo } from '@/lib/api/types';

interface CMSConnectedStateProps {
  connection: CMSConnectionInfo;
  onSync: () => void;
  onDisconnect: () => void;
  isSyncing: boolean;
  isSyncActive: boolean;
  isDisconnecting: boolean;
  isWriter: boolean;
  syncProgress: { status: string; currentStep: string; progressPct: number } | null;
}

function formatRelativeTime(isoDate: string | null): string {
  if (!isoDate) return 'Never';
  const diff = Date.now() - new Date(isoDate).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export function CMSConnectedState({
  connection,
  onSync,
  onDisconnect,
  isSyncing,
  isSyncActive,
  isDisconnecting,
  isWriter,
  syncProgress,
}: CMSConnectedStateProps) {
  const syncBusy = isSyncing || isSyncActive;
  const handleDisconnect = () => {
    if (window.confirm('Disconnect CMS? Synced posts and publish history will be preserved.')) {
      onDisconnect();
    }
  };

  return (
    <Card className="p-4 max-w-[600px]">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Badge variant={syncBusy ? 'info' : 'success'}>
            {syncBusy ? 'Syncing...' : 'Connected'}
          </Badge>
          <span className="text-[13px] font-medium text-text-primary">{connection.site_name}</span>
        </div>
        <span className="text-[11px] text-text-tertiary">{connection.provider}</span>
      </div>

      {/* Info grid */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Site URL</p>
          <p className="text-[12px] text-text-primary truncate">{connection.site_url}</p>
        </div>
        <div>
          <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">CMS Version</p>
          <p className="text-[12px] text-text-primary">{connection.cms_version || '—'}</p>
        </div>
        <div>
          <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Authenticated As</p>
          <p className="text-[12px] text-text-primary">{connection.user_display_name || '—'}</p>
        </div>
        <div>
          <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Last Sync</p>
          <p className="text-[12px] text-text-primary">{formatRelativeTime(connection.last_sync_at)}</p>
        </div>
      </div>

      {/* Stats */}
      <p className="text-[11px] text-text-secondary mb-3">
        {connection.sync_post_count} posts synced
      </p>

      {/* Sync progress */}
      {syncProgress && syncProgress.status === 'connected' && (
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] text-accent">{syncProgress.currentStep || 'Syncing...'}</span>
            <span className="text-[10px] font-mono text-text-tertiary">{syncProgress.progressPct}%</span>
          </div>
          <ProgressBar value={syncProgress.progressPct} max={100} />
        </div>
      )}

      {/* Actions */}
      {isWriter && (
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={onSync} disabled={syncBusy}>
            {syncBusy ? 'Syncing...' : 'Sync Now'}
          </Button>
          <Button variant="destructive" size="sm" onClick={handleDisconnect} disabled={isDisconnecting || syncBusy}>
            {isDisconnecting ? 'Disconnecting...' : 'Disconnect'}
          </Button>
        </div>
      )}
    </Card>
  );
}
