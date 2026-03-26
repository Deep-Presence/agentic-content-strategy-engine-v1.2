'use client';

import { useState } from 'react';
import { Card, Button, Input } from '@/components/ui';

interface CMSConnectFormProps {
  onSubmit: (data: { provider: string; site_url: string; username: string; api_key: string }) => void;
  isSubmitting: boolean;
  error: string | null;
}

export function CMSConnectForm({ onSubmit, isSubmitting, error }: CMSConnectFormProps) {
  const [provider, setProvider] = useState('wordpress');
  const [siteUrl, setSiteUrl] = useState('');
  const [username, setUsername] = useState('');
  const [apiKey, setApiKey] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!siteUrl.trim() || !username.trim() || !apiKey.trim()) return;
    onSubmit({ provider, site_url: siteUrl.trim(), username: username.trim(), api_key: apiKey });
  };

  return (
    <Card className="max-w-[480px] p-4">
      <form onSubmit={handleSubmit} className="space-y-3">
        {/* Provider */}
        <div>
          <label className="block text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-1">
            CMS Provider
          </label>
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            className="w-full h-[30px] px-2 text-[12px] bg-surface border border-border rounded-sm text-text-primary focus:outline-none focus:border-accent"
          >
            <option value="wordpress">WordPress</option>
            <option value="webflow" disabled>Webflow (Coming Soon)</option>
            <option value="ghost" disabled>Ghost (Coming Soon)</option>
          </select>
        </div>

        {/* Site URL */}
        <div>
          <label className="block text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-1">
            Site URL
          </label>
          <Input
            type="url"
            placeholder="https://yourblog.com"
            value={siteUrl}
            onChange={(e) => setSiteUrl(e.target.value)}
            disabled={isSubmitting}
          />
        </div>

        {/* Username */}
        <div>
          <label className="block text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-1">
            Username
          </label>
          <Input
            type="text"
            placeholder="WordPress username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled={isSubmitting}
          />
        </div>

        {/* Application Password */}
        <div>
          <label className="block text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-1">
            Application Password
          </label>
          <Input
            type="password"
            placeholder="xxxx xxxx xxxx xxxx xxxx xxxx"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            disabled={isSubmitting}
          />
          <p className="text-[10px] text-text-tertiary mt-1">
            Generate in WordPress → Users → Application Passwords
          </p>
        </div>

        {/* Error */}
        {error && (
          <p className="text-[11px] text-error">{error}</p>
        )}

        {/* Submit */}
        <Button type="submit" variant="primary" disabled={isSubmitting || !siteUrl.trim() || !username.trim() || !apiKey.trim()}>
          {isSubmitting ? 'Connecting...' : 'Connect'}
        </Button>
      </form>
    </Card>
  );
}
