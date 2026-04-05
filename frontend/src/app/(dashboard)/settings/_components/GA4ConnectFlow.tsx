'use client';

import { useState } from 'react';
import { Button, Badge, Toast } from '@/components/ui';
import { RefreshCw, Unplug, ChevronDown } from 'lucide-react';
import type { GA4ConnectionResponseAPI, GA4PropertyItemAPI, GA4SelectPropertyRequestAPI } from '../_lib/types';

interface GA4ConnectFlowProps {
  connection: GA4ConnectionResponseAPI | null;
  properties: GA4PropertyItemAPI[];
  onStartConnect: () => Promise<void>;
  onDisconnect: (purgeData: boolean) => Promise<void>;
  onLoadProperties: () => Promise<void>;
  onSelectProperty: (body: GA4SelectPropertyRequestAPI) => Promise<void>;
  onSync: () => Promise<unknown>;
}

export function GA4ConnectFlow({
  connection,
  properties,
  onStartConnect,
  onDisconnect,
  onLoadProperties,
  onSelectProperty,
  onSync,
}: GA4ConnectFlowProps) {
  const [isConnecting, setIsConnecting] = useState(false);
  const [isDisconnecting, setIsDisconnecting] = useState(false);
  const [showDisconnectConfirm, setShowDisconnectConfirm] = useState(false);
  const [purgeData, setPurgeData] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [selectedPropertyId, setSelectedPropertyId] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [toast, setToast] = useState({ open: false, message: '', variant: 'success' as 'success' | 'error' });

  // ── State: Disconnected ──────────────────────────────────

  if (!connection || !connection.is_active) {
    return (
      <div>
        <Button
          variant="secondary"
          size="sm"
          onClick={async () => {
            setIsConnecting(true);
            await onStartConnect();
            // If we get here, the redirect didn't happen (error case)
            setIsConnecting(false);
          }}
          disabled={isConnecting}
        >
          {isConnecting ? 'Redirecting...' : 'Connect with Google'}
        </Button>
      </div>
    );
  }

  // ── State: Connected, no property selected ───────────────

  if (!connection.ga4_property_id) {
    const handleSelectProperty = async () => {
      const prop = properties.find((p) => p.property_id === selectedPropertyId);
      if (!prop) return;
      setIsSaving(true);
      try {
        await onSelectProperty({
          property_id: prop.property_id,
          property_name: prop.display_name,
          account_id: prop.account_id,
        });
        setToast({ open: true, message: 'Property selected', variant: 'success' });
      } catch {
        setToast({ open: true, message: 'Failed to select property', variant: 'error' });
      } finally {
        setIsSaving(false);
      }
    };

    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2 mb-2">
          <Badge variant="success">Connected</Badge>
          <span className="text-[11px] text-text-tertiary">Select a GA4 property to start syncing data</span>
        </div>

        {properties.length === 0 ? (
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={onLoadProperties}>
              Load Properties
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={async () => {
                setIsDisconnecting(true);
                try {
                  await onDisconnect(false);
                  setToast({ open: true, message: 'Disconnected', variant: 'success' });
                } catch {
                  setToast({ open: true, message: 'Failed to disconnect', variant: 'error' });
                } finally {
                  setIsDisconnecting(false);
                }
              }}
              disabled={isDisconnecting}
            >
              <Unplug size={13} strokeWidth={1.5} className="mr-1.5" />
              {isDisconnecting ? 'Disconnecting...' : 'Disconnect'}
            </Button>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="flex items-end gap-2">
              <div className="relative flex-1">
                <select
                  value={selectedPropertyId}
                  onChange={(e) => setSelectedPropertyId(e.target.value)}
                  className="w-full h-[34px] px-3 pr-8 rounded-sm border border-border bg-surface text-[13px] text-text-primary outline-none cursor-pointer hover:border-border-strong transition-colors appearance-none"
                >
                  <option value="">Select a property...</option>
                  {properties.map((p) => (
                    <option key={p.property_id} value={p.property_id}>
                      {p.display_name} ({p.account_display_name})
                    </option>
                  ))}
                </select>
                <ChevronDown size={14} strokeWidth={1.5} className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-text-tertiary" />
              </div>
              <Button size="sm" onClick={handleSelectProperty} disabled={!selectedPropertyId || isSaving}>
                {isSaving ? 'Saving...' : 'Save'}
              </Button>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={async () => {
                setIsDisconnecting(true);
                try {
                  await onDisconnect(false);
                  setToast({ open: true, message: 'Disconnected', variant: 'success' });
                } catch {
                  setToast({ open: true, message: 'Failed to disconnect', variant: 'error' });
                } finally {
                  setIsDisconnecting(false);
                }
              }}
              disabled={isDisconnecting}
            >
              <Unplug size={13} strokeWidth={1.5} className="mr-1.5" />
              {isDisconnecting ? 'Disconnecting...' : 'Disconnect'}
            </Button>
          </div>
        )}

        <Toast open={toast.open} onClose={() => setToast({ ...toast, open: false })} variant={toast.variant} message={toast.message} />
      </div>
    );
  }

  // ── State: Fully connected ───────────────────────────────

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      await onSync();
      setToast({ open: true, message: 'Sync started', variant: 'success' });
    } catch {
      setToast({ open: true, message: 'Sync failed', variant: 'error' });
    } finally {
      setIsSyncing(false);
    }
  };

  const handleDisconnect = async () => {
    setIsDisconnecting(true);
    try {
      await onDisconnect(purgeData);
      setToast({ open: true, message: 'Disconnected', variant: 'success' });
      setShowDisconnectConfirm(false);
    } catch {
      setToast({ open: true, message: 'Failed to disconnect', variant: 'error' });
    } finally {
      setIsDisconnecting(false);
    }
  };

  const formatDate = (iso: string | null) => {
    if (!iso) return 'Never';
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const syncStatusVariant = (status: string): 'success' | 'warning' | 'error' | 'neutral' => {
    if (status === 'success') return 'success';
    if (status === 'in_progress' || status === 'pending') return 'warning';
    if (status === 'failed' || status === 'auth_revoked') return 'error';
    return 'neutral';
  };

  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <div className="flex items-center gap-2">
          <Badge variant="success">Connected</Badge>
          {connection.last_sync_status && (
            <Badge variant={syncStatusVariant(connection.last_sync_status)}>
              Sync: {connection.last_sync_status}
            </Badge>
          )}
        </div>
        <p className="text-[13px] text-text-primary font-medium">
          {connection.ga4_property_name}
        </p>
        <p className="text-[11px] text-text-tertiary">
          Last synced: {formatDate(connection.last_sync_at)}
        </p>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <Button variant="secondary" size="sm" onClick={handleSync} disabled={isSyncing}>
          <RefreshCw size={13} strokeWidth={1.5} className={`mr-1.5 ${isSyncing ? 'animate-spin' : ''}`} />
          {isSyncing ? 'Syncing...' : 'Sync Now'}
        </Button>

        {!showDisconnectConfirm ? (
          <Button variant="ghost" size="sm" onClick={() => setShowDisconnectConfirm(true)}>
            <Unplug size={13} strokeWidth={1.5} className="mr-1.5" />
            Disconnect
          </Button>
        ) : (
          <div className="flex items-center gap-2 bg-surface border border-border rounded-md px-3 py-2">
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="checkbox"
                checked={purgeData}
                onChange={(e) => setPurgeData(e.target.checked)}
                className="accent-accent"
              />
              <span className="text-[12px] text-text-secondary">Also delete synced data</span>
            </label>
            <Button variant="destructive" size="sm" onClick={handleDisconnect} disabled={isDisconnecting}>
              {isDisconnecting ? 'Disconnecting...' : 'Confirm'}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setShowDisconnectConfirm(false)}>
              Cancel
            </Button>
          </div>
        )}
      </div>

      <Toast open={toast.open} onClose={() => setToast({ ...toast, open: false })} variant={toast.variant} message={toast.message} />
    </div>
  );
}
