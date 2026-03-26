'use client';

import { useEffect, useState } from 'react';
import { StatusDot, Button, Toast, Skeleton } from '@/components/ui';
import { Globe, Users, BarChart3 } from 'lucide-react';
import { useAuthStore } from '@/stores/auth';
import { useTaskStream } from '@/lib/hooks/useTaskStream';
import {
  useCMSConnection,
  useCMSConnect,
  useCMSDisconnect,
  useCMSSync,
  useCMSSyncedPosts,
} from '@/lib/hooks/useCMS';
import { CMSConnectForm } from './CMSConnectForm';
import { CMSConnectedState } from './CMSConnectedState';
import { CMSSyncedPostsTable } from './CMSSyncedPostsTable';
import type { CMSConnectPayload } from '@/lib/api/types';

// ── Static placeholder cards for CRM + Analytics ────────────────────────

interface PlaceholderItem {
  id: string;
  name: string;
  description: string;
}

const crmItems: PlaceholderItem[] = [
  { id: 'salesforce', name: 'Salesforce', description: 'Track AI-attributed leads and pipeline' },
  { id: 'hubspot', name: 'HubSpot', description: 'Connect deals and attribution data' },
];

const analyticsItems: PlaceholderItem[] = [
  { id: 'ga4', name: 'Google Analytics 4', description: 'Import traffic and conversion data' },
  { id: 'plausible', name: 'Plausible', description: 'Privacy-first analytics integration' },
];

function PlaceholderCard({ item }: { item: PlaceholderItem }) {
  return (
    <div className="bg-surface border border-border rounded-md p-4 h-auto min-h-[80px] opacity-60">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[14px] font-medium text-text-primary">{item.name}</span>
        <StatusDot color="neutral" />
      </div>
      <p className="text-[13px] text-text-secondary mb-3">{item.description}</p>
      <Button size="sm" variant="secondary" disabled>Coming Soon</Button>
    </div>
  );
}

// ── Main Component ──────────────────────────────────────────────────────

export function IntegrationsTab() {
  const userRole = useAuthStore((s) => s.user?.role);
  const isWriter = userRole === 'superuser' || userRole === 'member';

  // CMS hooks
  const { data: connection, isLoading: connLoading, refetch: refetchConnection } = useCMSConnection();
  const { connect, isConnecting, error: connectError } = useCMSConnect();
  const { disconnect, isDisconnecting } = useCMSDisconnect();
  const { triggerSync, isSyncing, syncRunId, onSyncComplete } = useCMSSync();
  const { data: posts, isLoading: postsLoading, refetch: refetchPosts } = useCMSSyncedPosts();

  // SSE for sync progress
  const syncStream = useTaskStream(syncRunId);

  // When sync completes, refresh connection + posts
  useEffect(() => {
    if (syncStream.status === 'completed') {
      refetchConnection();
      refetchPosts();
      onSyncComplete();
    }
  }, [syncStream.status, refetchConnection, refetchPosts, onSyncComplete]);

  const isConnected = connection?.is_active ?? false;

  // Toast state
  const [toast, setToast] = useState<{ open: boolean; message: string; variant: 'success' | 'error' | 'info' }>({ open: false, message: '', variant: 'success' });

  // Connect → auto-trigger sync (F5: handle connected:false)
  const handleConnect = async (data: CMSConnectPayload) => {
    const result = await connect(data);
    if (result?.connected) {
      triggerSync();
    } else if (result && !result.connected) {
      setToast({ open: true, message: result.error || 'Failed to connect — check credentials', variant: 'error' });
    }
  };

  const handleDisconnect = async () => {
    const success = await disconnect();
    if (success) {
      setToast({ open: true, message: 'CMS disconnected', variant: 'success' });
    }
  };

  // Sync progress for child component
  const syncProgress = syncRunId && syncStream.status === 'connected'
    ? { status: syncStream.status, currentStep: syncStream.currentStep ?? '', progressPct: syncStream.progressPct }
    : null;

  return (
    <div className="space-y-6">
      {/* CMS Section */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <span className="text-text-tertiary"><Globe size={16} strokeWidth={1.5} /></span>
          <h3 className="text-[16px] font-semibold text-text-primary">CMS</h3>
        </div>

        {connLoading ? (
          <Skeleton className="h-[120px] w-full max-w-[600px] rounded-sm" />
        ) : isConnected && connection ? (
          <div className="space-y-4">
            <CMSConnectedState
              connection={connection}
              onSync={triggerSync}
              onDisconnect={handleDisconnect}
              isSyncing={isSyncing}
              isSyncActive={!!syncRunId}
              isDisconnecting={isDisconnecting}
              isWriter={isWriter}
              syncProgress={syncProgress}
            />
            <CMSSyncedPostsTable posts={posts ?? []} isLoading={postsLoading} />
          </div>
        ) : isWriter ? (
          <CMSConnectForm
            onSubmit={handleConnect}
            isSubmitting={isConnecting}
            error={connectError?.detail ?? null}
          />
        ) : (
          <p className="text-[12px] text-text-tertiary">No CMS connected. Ask an admin to connect one.</p>
        )}
      </div>

      {/* CRM Section */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <span className="text-text-tertiary"><Users size={16} strokeWidth={1.5} /></span>
          <h3 className="text-[16px] font-semibold text-text-primary">CRM</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {crmItems.map((item) => <PlaceholderCard key={item.id} item={item} />)}
        </div>
      </div>

      {/* Analytics Section */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <span className="text-text-tertiary"><BarChart3 size={16} strokeWidth={1.5} /></span>
          <h3 className="text-[16px] font-semibold text-text-primary">Analytics</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {analyticsItems.map((item) => <PlaceholderCard key={item.id} item={item} />)}
        </div>
      </div>

      <Toast
        open={toast.open}
        onClose={() => setToast({ ...toast, open: false })}
        variant={toast.variant}
        message={toast.message}
      />
    </div>
  );
}
