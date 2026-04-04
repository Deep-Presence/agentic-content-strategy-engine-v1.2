'use client';

import { useState, useCallback } from 'react';
import { Modal, Button, Input } from '@/components/ui';
import { AlertCircle } from 'lucide-react';
import type { CMSConnectRequestAPI } from '../_lib/types';

interface WordPressConnectModalProps {
  open: boolean;
  onClose: () => void;
  onConnect: (body: CMSConnectRequestAPI) => Promise<{ success: boolean; error?: string }>;
}

export function WordPressConnectModal({ open, onClose, onConnect }: WordPressConnectModalProps) {
  const [siteUrl, setSiteUrl] = useState('');
  const [username, setUsername] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(async () => {
    if (!siteUrl || !apiKey) {
      setError('Site URL and Application Password are required');
      return;
    }

    setIsConnecting(true);
    setError(null);

    const result = await onConnect({
      provider: 'wordpress',
      site_url: siteUrl,
      username,
      api_key: apiKey,
    });

    setIsConnecting(false);

    if (result.success) {
      // Reset form and close
      setSiteUrl('');
      setUsername('');
      setApiKey('');
      onClose();
    } else {
      setError(result.error || 'Connection failed');
    }
  }, [siteUrl, username, apiKey, onConnect, onClose]);

  const handleClose = useCallback(() => {
    if (isConnecting) return;
    setError(null);
    onClose();
  }, [isConnecting, onClose]);

  return (
    <Modal open={open} onClose={handleClose} title="Connect WordPress">
      <div className="space-y-4">
        <div>
          <label className="text-[13px] font-medium text-text-secondary block mb-1.5">
            Site URL
          </label>
          <Input
            type="url"
            placeholder="https://your-site.com"
            value={siteUrl}
            onChange={(e) => setSiteUrl(e.target.value)}
            disabled={isConnecting}
            className="text-[14px] h-[34px]"
          />
        </div>

        <div>
          <label className="text-[13px] font-medium text-text-secondary block mb-1.5">
            Username
          </label>
          <Input
            type="text"
            placeholder="admin"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled={isConnecting}
            className="text-[14px] h-[34px]"
          />
          <p className="text-[11px] text-text-tertiary mt-1">
            WordPress username with edit permissions
          </p>
        </div>

        <div>
          <label className="text-[13px] font-medium text-text-secondary block mb-1.5">
            Application Password
          </label>
          <Input
            type="password"
            placeholder="xxxx xxxx xxxx xxxx xxxx xxxx"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            disabled={isConnecting}
            className="text-[14px] h-[34px]"
          />
          <p className="text-[11px] text-text-tertiary mt-1">
            Generate one in WordPress &rarr; Users &rarr; Profile &rarr; Application Passwords
          </p>
        </div>

        {error && (
          <div className="flex items-start gap-2 bg-error/5 border border-error/20 rounded-md px-3 py-2">
            <AlertCircle size={14} strokeWidth={1.5} className="text-error shrink-0 mt-0.5" />
            <span className="text-[13px] text-error">{error}</span>
          </div>
        )}

        <div className="flex items-center gap-2 pt-1">
          <Button onClick={handleSubmit} disabled={isConnecting || !siteUrl || !apiKey}>
            {isConnecting ? 'Connecting...' : 'Connect'}
          </Button>
          <Button variant="ghost" onClick={handleClose} disabled={isConnecting}>
            Cancel
          </Button>
        </div>
      </div>
    </Modal>
  );
}
