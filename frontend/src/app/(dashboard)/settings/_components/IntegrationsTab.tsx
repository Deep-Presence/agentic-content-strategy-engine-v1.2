'use client';

import { useState } from 'react';
import { StatusDot, Button, Toast } from '@/components/ui';
import { Globe, Users, BarChart3 } from 'lucide-react';

interface IntegrationItem {
  id: string;
  name: string;
  description: string;
  connected: boolean;
  lastSynced?: string;
  category: 'cms' | 'crm' | 'analytics';
}

const initialIntegrations: IntegrationItem[] = [
  { id: 'wordpress', name: 'WordPress', description: 'Publish content directly to your WordPress site', connected: false, category: 'cms' },
  { id: 'webflow', name: 'Webflow', description: 'Push content to Webflow CMS collections', connected: false, category: 'cms' },
  { id: 'ghost', name: 'Ghost', description: 'Sync content with your Ghost publication', connected: false, category: 'cms' },
  { id: 'salesforce', name: 'Salesforce', description: 'Track AI-attributed leads and pipeline', connected: false, category: 'crm' },
  { id: 'hubspot', name: 'HubSpot', description: 'Connect deals and attribution data', connected: false, category: 'crm' },
  { id: 'ga4', name: 'Google Analytics 4', description: 'Import traffic and conversion data', connected: false, category: 'analytics' },
  { id: 'plausible', name: 'Plausible', description: 'Privacy-first analytics integration', connected: false, category: 'analytics' },
];

const categoryConfig: Record<string, { label: string; icon: React.ReactNode }> = {
  cms: { label: 'CMS', icon: <Globe size={16} strokeWidth={1.5} /> },
  crm: { label: 'CRM', icon: <Users size={16} strokeWidth={1.5} /> },
  analytics: { label: 'Analytics', icon: <BarChart3 size={16} strokeWidth={1.5} /> },
};

export function IntegrationsTab() {
  const [integrations, setIntegrations] = useState(initialIntegrations);
  const [toast, setToast] = useState({ open: false, message: '' });

  const toggleConnection = (id: string) => {
    setIntegrations(integrations.map((i) => {
      if (i.id !== id) return i;
      const newState = !i.connected;
      setToast({ open: true, message: newState ? `${i.name} connected` : `${i.name} disconnected` });
      return {
        ...i,
        connected: newState,
        lastSynced: newState ? 'Just now' : undefined,
      };
    }));
  };

  const categories = ['cms', 'crm', 'analytics'] as const;

  return (
    <div className="space-y-6">
      {categories.map((cat) => {
        const cfg = categoryConfig[cat];
        const items = integrations.filter((i) => i.category === cat);
        return (
          <div key={cat}>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-text-tertiary">{cfg.icon}</span>
              <h3 className="text-[16px] font-semibold text-text-primary">
                {cfg.label}
              </h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {items.map((item) => (
                <div
                  key={item.id}
                  className="bg-surface border border-border rounded-md p-4 h-auto min-h-[80px] hover:border-border-strong transition-[border-color] duration-150"
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[14px] font-medium text-text-primary">{item.name}</span>
                    <StatusDot color={item.connected ? 'success' : 'neutral'} />
                  </div>
                  <p className="text-[13px] text-text-secondary mb-3">{item.description}</p>
                  {item.connected && item.lastSynced && (
                    <p className="text-[11px] text-text-tertiary mb-2">Last synced: {item.lastSynced}</p>
                  )}
                  <Button
                    size="sm"
                    variant={item.connected ? 'destructive' : 'secondary'}
                    onClick={() => toggleConnection(item.id)}
                  >
                    {item.connected ? 'Disconnect' : 'Connect'}
                  </Button>
                </div>
              ))}
            </div>
          </div>
        );
      })}

      <Toast open={toast.open} onClose={() => setToast({ ...toast, open: false })} variant="success" message={toast.message} />
    </div>
  );
}
