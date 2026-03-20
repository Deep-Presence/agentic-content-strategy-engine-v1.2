'use client';

import { useState } from 'react';
import { Button, Toast, Badge } from '@/components/ui';
import { Eye, EyeOff, Trash2, Zap } from 'lucide-react';

interface ModelRow {
  id: string;
  agentType: string;
  provider: string;
  model: string;
  apiKeySet: boolean;
  apiKeyMasked: string;
  tokensUsed: number;
  tokenLimit: number;
}

const modelOptions: Record<string, string[]> = {
  'Anthropic': ['claude-opus-4-6', 'claude-sonnet-4-6', 'claude-haiku-4-5'],
  'OpenAI': ['gpt-4o', 'gpt-4o-mini', 'o3'],
  'Google': ['gemini-2.5-pro', 'gemini-2.5-flash'],
};

const providerNames = Object.keys(modelOptions);

const initialModels: ModelRow[] = [
  { id: '1', agentType: 'Research Agent', provider: 'Anthropic', model: 'claude-sonnet-4-6', apiKeySet: true, apiKeyMasked: 'sk-...a7x9', tokensUsed: 1240000, tokenLimit: 5000000 },
  { id: '2', agentType: 'Writing Agent', provider: 'Anthropic', model: 'claude-opus-4-6', apiKeySet: true, apiKeyMasked: 'sk-...b3m2', tokensUsed: 890000, tokenLimit: 5000000 },
  { id: '3', agentType: 'Strategy Agent', provider: 'Anthropic', model: 'claude-sonnet-4-6', apiKeySet: false, apiKeyMasked: '', tokensUsed: 0, tokenLimit: 5000000 },
  { id: '4', agentType: 'Image Generation', provider: 'OpenAI', model: 'gpt-4o', apiKeySet: false, apiKeyMasked: '', tokensUsed: 0, tokenLimit: 2000000 },
];

function formatTokens(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(0)}K`;
  return String(n);
}

export function ModelsTab() {
  const [models, setModels] = useState<ModelRow[]>(initialModels);
  const [showKey, setShowKey] = useState<string | null>(null);
  const [toast, setToast] = useState({ open: false, message: '' });

  const handleProviderChange = (id: string, provider: string) => {
    setModels(models.map((m) => {
      if (m.id !== id) return m;
      const newModels = modelOptions[provider] || [];
      return { ...m, provider, model: newModels[0] || '' };
    }));
  };

  const handleModelChange = (id: string, model: string) => {
    setModels(models.map((m) => (m.id === id ? { ...m, model } : m)));
  };

  const handleRemoveKey = (id: string) => {
    setModels(models.map((m) => (m.id === id ? { ...m, apiKeySet: false, apiKeyMasked: '' } : m)));
    setToast({ open: true, message: 'API key removed' });
  };

  const handleAddKey = (id: string) => {
    const mask = `sk-...${Math.random().toString(36).substring(2, 6)}`;
    setModels(models.map((m) => (m.id === id ? { ...m, apiKeySet: true, apiKeyMasked: mask } : m)));
    setToast({ open: true, message: 'API key added' });
  };

  const handleTestConnection = (id: string) => {
    const model = models.find((m) => m.id === id);
    if (model?.apiKeySet) {
      setToast({ open: true, message: `Connection to ${model.model} successful` });
    } else {
      setToast({ open: true, message: 'Add an API key first' });
    }
  };

  return (
    <div className="space-y-5">
      <div className="bg-surface border border-border rounded-md p-4">
        <h3 className="text-[16px] font-semibold text-text-primary mb-4">
          Agent Models & API Keys
        </h3>
        <div className="space-y-3">
          {models.map((m) => (
            <div key={m.id} className="border border-border rounded-md p-3 hover:border-border-strong transition-[border-color] duration-150">
              <div className="flex items-start justify-between gap-4 flex-wrap">
                {/* Agent name and model */}
                <div className="flex-1 min-w-[200px]">
                  <div className="text-[14px] font-medium text-text-primary mb-1">{m.agentType}</div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <select
                      value={m.provider}
                      onChange={(e) => handleProviderChange(m.id, e.target.value)}
                      className="h-[30px] px-2 rounded-sm border border-border bg-surface text-[13px] text-text-primary outline-none cursor-pointer hover:border-border-strong transition-colors"
                    >
                      {providerNames.map((p) => (
                        <option key={p} value={p}>{p}</option>
                      ))}
                    </select>
                    <select
                      value={m.model}
                      onChange={(e) => handleModelChange(m.id, e.target.value)}
                      className="h-[30px] px-2 rounded-sm border border-border bg-surface text-[13px] text-text-primary outline-none cursor-pointer hover:border-border-strong transition-colors"
                    >
                      {(modelOptions[m.provider] || []).map((mod) => (
                        <option key={mod} value={mod}>{mod}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* API key */}
                <div className="flex-shrink-0">
                  {m.apiKeySet ? (
                    <div className="flex items-center gap-2">
                      <code className="font-mono text-[13px] text-text-secondary bg-surface border border-border rounded-sm px-2 py-0.5">
                        {showKey === m.id ? 'sk-ant-api03-xxxxxxxxxxxx' : m.apiKeyMasked}
                      </code>
                      <button
                        onClick={() => setShowKey(showKey === m.id ? null : m.id)}
                        className="p-1 text-text-tertiary hover:text-text-primary cursor-pointer"
                      >
                        {showKey === m.id ? <EyeOff size={14} strokeWidth={1.5} /> : <Eye size={14} strokeWidth={1.5} />}
                      </button>
                      <button
                        onClick={() => handleRemoveKey(m.id)}
                        className="p-1 text-text-tertiary hover:text-error cursor-pointer"
                      >
                        <Trash2 size={14} strokeWidth={1.5} />
                      </button>
                    </div>
                  ) : (
                    <Button size="sm" variant="secondary" onClick={() => handleAddKey(m.id)}>
                      Add Key
                    </Button>
                  )}
                </div>

                {/* Test connection */}
                <Button size="sm" variant="ghost" onClick={() => handleTestConnection(m.id)}>
                  <Zap size={12} strokeWidth={1.5} className="mr-1" />
                  Test
                </Button>
              </div>

              {/* Usage stats */}
              <div className="flex items-center gap-3 mt-2">
                <span className="text-[12px] text-text-tertiary">Tokens this month:</span>
                <span className="text-[12px] text-text-primary font-medium">
                  {formatTokens(m.tokensUsed)} / {formatTokens(m.tokenLimit)}
                </span>
                {m.tokensUsed > 0 && (
                  <div className="flex-1 max-w-[120px] h-[4px] bg-border rounded-full overflow-hidden">
                    <div
                      className="h-full bg-accent rounded-full"
                      style={{ width: `${Math.min(100, (m.tokensUsed / m.tokenLimit) * 100)}%` }}
                    />
                  </div>
                )}
                {!m.apiKeySet && (
                  <Badge variant="neutral">No key set</Badge>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <Toast open={toast.open} onClose={() => setToast({ ...toast, open: false })} variant="info" message={toast.message} />
    </div>
  );
}
