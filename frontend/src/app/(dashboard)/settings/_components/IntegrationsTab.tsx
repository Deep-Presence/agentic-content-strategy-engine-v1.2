'use client';

import { useState, Suspense } from 'react';
import { StatusDot, Button, Badge, Toast, Skeleton } from '@/components/ui';
import { Globe, Users, BarChart3, ExternalLink, AlertCircle } from 'lucide-react';
import { useIntegrationsData } from '../_hooks/useIntegrationsData';
import { WordPressConnectModal } from './WordPressConnectModal';
import { GA4ConnectFlow } from './GA4ConnectFlow';
import type { IntegrationDef, IntegrationCategory, CMSConnectionInfoAPI, GA4ConnectionResponseAPI, GA4PropertyItemAPI, GA4SelectPropertyRequestAPI } from '../_lib/types';

// ── Static integration definitions ──────────────────────

const INTEGRATIONS: IntegrationDef[] = [
  { id: 'wordpress', name: 'WordPress', description: 'Publish content directly to your WordPress site', domain: 'wordpress.org', category: 'cms', available: true },
  { id: 'webflow', name: 'Webflow', description: 'Push content to Webflow CMS collections', domain: 'webflow.com', category: 'cms', available: false },
  { id: 'ghost', name: 'Ghost', description: 'Sync content with your Ghost publication', domain: 'ghost.org', category: 'cms', available: false },
  { id: 'salesforce', name: 'Salesforce', description: 'Track AI-attributed leads and pipeline', domain: 'salesforce.com', category: 'crm', available: false },
  { id: 'hubspot', name: 'HubSpot', description: 'Connect deals and attribution data', domain: 'hubspot.com', category: 'crm', available: false },
  { id: 'ga4', name: 'Google Analytics 4', description: 'Import traffic and conversion data', domain: 'analytics.google.com', category: 'analytics', available: true },
  { id: 'plausible', name: 'Plausible', description: 'Privacy-first analytics integration', domain: 'plausible.io', category: 'analytics', available: false },
];

const CATEGORIES: { key: IntegrationCategory; label: string; icon: React.ReactNode }[] = [
  { key: 'cms', label: 'CMS', icon: <Globe size={16} strokeWidth={1.5} /> },
  { key: 'crm', label: 'CRM', icon: <Users size={16} strokeWidth={1.5} /> },
  { key: 'analytics', label: 'Analytics', icon: <BarChart3 size={16} strokeWidth={1.5} /> },
];

// ── Main component ──────────────────────────────────────

function IntegrationsContent() {
  const {
    cmsConnection,
    ga4Connection,
    ga4Properties,
    isLoading,
    error,
    connectWordPress,
    disconnectWordPress,
    startGA4Connect,
    disconnectGA4Connection,
    loadGA4Properties,
    selectProperty,
    syncGA4,
    refetch,
  } = useIntegrationsData();

  const [wpModalOpen, setWpModalOpen] = useState(false);
  const [toast, setToast] = useState({ open: false, message: '', variant: 'success' as 'success' | 'error' });

  const handleDisconnectWordPress = async () => {
    try {
      await disconnectWordPress();
      setToast({ open: true, message: 'WordPress disconnected', variant: 'success' });
    } catch {
      setToast({ open: true, message: 'Failed to disconnect', variant: 'error' });
    }
  };

  const formatDate = (iso: string | null) => {
    if (!iso) return null;
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const renderIntegrationCard = (def: IntegrationDef) => {
    // WordPress — real integration
    if (def.id === 'wordpress') {
      return (
        <WordPressCard
          key={def.id}
          def={def}
          connection={cmsConnection}
          onConnect={() => setWpModalOpen(true)}
          onDisconnect={handleDisconnectWordPress}
          formatDate={formatDate}
        />
      );
    }

    // GA4 — real integration
    if (def.id === 'ga4') {
      return (
        <GA4Card
          key={def.id}
          def={def}
          connection={ga4Connection}
          properties={ga4Properties}
          onStartConnect={startGA4Connect}
          onDisconnect={disconnectGA4Connection}
          onLoadProperties={loadGA4Properties}
          onSelectProperty={selectProperty}
          onSync={syncGA4}
        />
      );
    }

    // Coming soon integrations
    return <ComingSoonCard key={def.id} def={def} />;
  };

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-surface border border-error/30 rounded-md px-4 py-2.5 flex items-center gap-2">
          <AlertCircle size={14} strokeWidth={1.5} className="text-error shrink-0" />
          <span className="text-[13px] text-error">{error}</span>
          <Button variant="ghost" size="sm" onClick={refetch} className="ml-auto">
            Retry
          </Button>
        </div>
      )}

      {CATEGORIES.map((cat) => {
        const items = INTEGRATIONS.filter((i) => i.category === cat.key);
        return (
          <div key={cat.key}>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-text-tertiary">{cat.icon}</span>
              <h3 className="text-[16px] font-semibold text-text-primary">{cat.label}</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {isLoading
                ? items.map((item) => <SkeletonCard key={item.id} />)
                : items.map((item) => renderIntegrationCard(item))
              }
            </div>
          </div>
        );
      })}

      <WordPressConnectModal
        open={wpModalOpen}
        onClose={() => setWpModalOpen(false)}
        onConnect={connectWordPress}
      />

      <Toast open={toast.open} onClose={() => setToast({ ...toast, open: false })} variant={toast.variant} message={toast.message} />
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────

function SkeletonCard() {
  return (
    <div className="bg-surface border border-border rounded-md p-4 min-h-[80px]">
      <div className="flex items-center justify-between mb-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-3 w-3 rounded-full" />
      </div>
      <Skeleton className="h-3 w-full mb-3" />
      <Skeleton className="h-7 w-20" />
    </div>
  );
}

function WordPressCard({
  def,
  connection,
  onConnect,
  onDisconnect,
  formatDate,
}: {
  def: IntegrationDef;
  connection: CMSConnectionInfoAPI | null;
  onConnect: () => void;
  onDisconnect: () => void;
  formatDate: (iso: string | null) => string | null;
}) {
  const isConnected = connection?.is_active ?? false;

  return (
    <div className="bg-surface border border-border rounded-md p-4 min-h-[80px] hover:border-border-strong transition-[border-color] duration-150">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[14px] font-medium text-text-primary">{def.name}</span>
        <StatusDot color={isConnected ? 'success' : 'neutral'} />
      </div>
      <p className="text-[13px] text-text-secondary mb-3">{def.description}</p>

      {isConnected && connection && (
        <div className="space-y-1 mb-3">
          <p className="text-[12px] text-text-primary font-medium">
            {connection.site_name}
          </p>
          <a
            href={connection.site_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[11px] text-accent hover:underline inline-flex items-center gap-1"
          >
            {connection.site_url}
            <ExternalLink size={10} strokeWidth={1.5} />
          </a>
          <p className="text-[11px] text-text-tertiary">
            {connection.sync_post_count} posts synced
            {connection.last_sync_at && ` \u00B7 Last sync: ${formatDate(connection.last_sync_at)}`}
          </p>
        </div>
      )}

      <Button
        size="sm"
        variant={isConnected ? 'destructive' : 'secondary'}
        onClick={isConnected ? onDisconnect : onConnect}
      >
        {isConnected ? 'Disconnect' : 'Connect'}
      </Button>
    </div>
  );
}

function GA4Card({
  def,
  connection,
  properties,
  onStartConnect,
  onDisconnect,
  onLoadProperties,
  onSelectProperty,
  onSync,
}: {
  def: IntegrationDef;
  connection: GA4ConnectionResponseAPI | null;
  properties: GA4PropertyItemAPI[];
  onStartConnect: () => Promise<void>;
  onDisconnect: (purgeData: boolean) => Promise<void>;
  onLoadProperties: () => Promise<void>;
  onSelectProperty: (body: GA4SelectPropertyRequestAPI) => Promise<void>;
  onSync: () => Promise<unknown>;
}) {
  const isConnected = connection?.is_active ?? false;

  return (
    <div className="bg-surface border border-border rounded-md p-4 min-h-[80px] hover:border-border-strong transition-[border-color] duration-150">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[14px] font-medium text-text-primary">{def.name}</span>
        <StatusDot color={isConnected ? 'success' : 'neutral'} />
      </div>
      <p className="text-[13px] text-text-secondary mb-3">{def.description}</p>

      <GA4ConnectFlow
        connection={connection}
        properties={properties}
        onStartConnect={onStartConnect}
        onDisconnect={onDisconnect}
        onLoadProperties={onLoadProperties}
        onSelectProperty={onSelectProperty}
        onSync={onSync}
      />
    </div>
  );
}

function ComingSoonCard({ def }: { def: IntegrationDef }) {
  return (
    <div className="bg-surface border border-border rounded-md p-4 min-h-[80px] opacity-60">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[14px] font-medium text-text-primary">{def.name}</span>
        <Badge variant="neutral">Coming Soon</Badge>
      </div>
      <p className="text-[13px] text-text-secondary mb-3">{def.description}</p>
      <Button size="sm" variant="secondary" disabled>
        Connect
      </Button>
    </div>
  );
}

// ── Export with Suspense wrapper (useSearchParams requires it) ─

export function IntegrationsTab() {
  return (
    <Suspense fallback={
      <div className="space-y-6">
        {CATEGORIES.map((cat) => (
          <div key={cat.key}>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-text-tertiary">{cat.icon}</span>
              <h3 className="text-[16px] font-semibold text-text-primary">{cat.label}</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              <SkeletonCard />
              <SkeletonCard />
            </div>
          </div>
        ))}
      </div>
    }>
      <IntegrationsContent />
    </Suspense>
  );
}
