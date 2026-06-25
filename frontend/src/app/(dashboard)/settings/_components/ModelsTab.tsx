'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, BarChart3, CheckCircle2, KeyRound, RefreshCw, Save, Trash2, Zap } from 'lucide-react';
import { Badge, Button, Input, Skeleton, Toast, Toggle } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { ApiError } from '@/lib/api-client';
import {
  deleteOpenRouterKey,
  fetchWorkspaceModelConfig,
  testAgentModelConfig,
  testOpenRouterKey,
  updateAgentModelConfig,
  upsertOpenRouterKey,
} from '@/lib/model-config';
import type {
  AgentCatalogItemAPI,
  AgentModelConfigAPI,
  CredentialStatusAPI,
  WorkspaceModelConfigAPI,
} from '@/lib/model-config';

interface AgentDraft {
  model: string;
  temperature: string;
  maxTokens: string;
  timeoutS: string;
  enabled: boolean;
}

interface AgentRow {
  catalog: AgentCatalogItemAPI;
  config: AgentModelConfigAPI | null;
  draft: AgentDraft;
}

type ToastState = {
  open: boolean;
  message: string;
  variant: 'success' | 'error' | 'info';
};

function toDraft(catalog: AgentCatalogItemAPI, config?: AgentModelConfigAPI): AgentDraft {
  return {
    model: config?.model || catalog.default_model,
    temperature: config?.temperature == null ? '' : String(config.temperature),
    maxTokens: config?.max_tokens == null ? '' : String(config.max_tokens),
    timeoutS: config?.timeout_s == null ? '' : String(config.timeout_s),
    enabled: config?.enabled ?? true,
  };
}

type OptionalNumberResult =
  | { ok: true; value: number | null }
  | { ok: false; message: string };

function parseOptionalNumber(value: string, label: string): OptionalNumberResult {
  const trimmed = value.trim();
  if (!trimmed) return { ok: true, value: null };
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) {
    return { ok: false, message: `${label} must be a number` };
  }
  return { ok: true, value: parsed };
}

function hasUnsavedChanges(row: AgentRow): boolean {
  const current = toDraft(row.catalog, row.config ?? undefined);
  return (
    current.model !== row.draft.model ||
    current.temperature !== row.draft.temperature ||
    current.maxTokens !== row.draft.maxTokens ||
    current.timeoutS !== row.draft.timeoutS ||
    current.enabled !== row.draft.enabled
  );
}

function formatDate(iso: string | null): string {
  if (!iso) return 'Never';
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatTokenCount(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return String(value);
}

function formatUsd(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: value < 1 ? 4 : 2,
    maximumFractionDigits: value < 1 ? 4 : 2,
  }).format(value);
}

function statusBadge(credential: CredentialStatusAPI) {
  if (!credential.configured) return <Badge variant="error">Missing key</Badge>;
  if (credential.status === 'active' || credential.status === 'valid') return <Badge variant="success">Active</Badge>;
  if (credential.status === 'invalid') return <Badge variant="error">Invalid</Badge>;
  return <Badge variant="warning">Untested</Badge>;
}

export function ModelsTab() {
  const { activeWorkspaceSlug, isInitialized, hasRole } = useAuth();
  const canManageModels = hasRole('superuser');

  const [configView, setConfigView] = useState<WorkspaceModelConfigAPI | null>(null);
  const [drafts, setDrafts] = useState<Record<string, AgentDraft>>({});
  const [keyInput, setKeyInput] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSavingKey, setIsSavingKey] = useState(false);
  const [isTestingKey, setIsTestingKey] = useState(false);
  const [deletingKey, setDeletingKey] = useState(false);
  const [savingAgentKey, setSavingAgentKey] = useState<string | null>(null);
  const [testingAgentKey, setTestingAgentKey] = useState<string | null>(null);
  const [toast, setToast] = useState<ToastState>({
    open: false,
    message: '',
    variant: 'info',
  });

  const abortRef = useRef<AbortController | null>(null);

  const loadConfig = useCallback(async (workspaceSlug: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setIsLoading(true);
    setError(null);

    try {
      const view = await fetchWorkspaceModelConfig(workspaceSlug, controller.signal);
      if (controller.signal.aborted) return;

      const byAgent = new Map(view.configs.map((item) => [item.agent_key, item]));
      const nextDrafts = Object.fromEntries(
        view.catalog.map((item) => [
          item.agent_key,
          toDraft(item, byAgent.get(item.agent_key)),
        ]),
      );

      setConfigView(view);
      setDrafts(nextDrafts);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      const msg = err instanceof ApiError ? err.detail : 'Failed to load model configuration';
      setError(msg);
    } finally {
      if (!controller.signal.aborted) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isInitialized) return;
    if (!activeWorkspaceSlug) {
      setConfigView(null);
      setIsLoading(false);
      setError('No active workspace selected');
      return;
    }

    loadConfig(activeWorkspaceSlug);
    return () => { abortRef.current?.abort(); };
  }, [activeWorkspaceSlug, isInitialized, loadConfig]);

  const rows = useMemo<AgentRow[]>(() => {
    if (!configView) return [];
    const byAgent = new Map(configView.configs.map((item) => [item.agent_key, item]));
    return configView.catalog.map((catalog) => ({
      catalog,
      config: byAgent.get(catalog.agent_key) ?? null,
      draft: drafts[catalog.agent_key] ?? toDraft(catalog, byAgent.get(catalog.agent_key)),
    }));
  }, [configView, drafts]);

  const groupedRows = useMemo(() => {
    const groups = new Map<string, AgentRow[]>();
    for (const row of rows) {
      const group = row.catalog.group || 'Other';
      groups.set(group, [...(groups.get(group) ?? []), row]);
    }
    return Array.from(groups.entries());
  }, [rows]);

  const missingRequiredCount = configView?.missing_required_agent_keys.length ?? 0;
  const usageSummary = configView?.usage_summary ?? [];
  const catalogNames = useMemo(() => {
    if (!configView) return new Map<string, string>();
    return new Map(configView.catalog.map((item) => [item.agent_key, item.display_name]));
  }, [configView]);
  const usageTotals = useMemo(() => {
    return usageSummary.reduce(
      (acc, row) => ({
        calls: acc.calls + row.call_count,
        tokens: acc.tokens + row.prompt_tokens + row.completion_tokens,
        cost: acc.cost + row.estimated_cost_usd,
      }),
      { calls: 0, tokens: 0, cost: 0 },
    );
  }, [usageSummary]);

  const updateDraft = useCallback((agentKey: string, patch: Partial<AgentDraft>) => {
    setDrafts((current) => ({
      ...current,
      [agentKey]: {
        ...current[agentKey],
        ...patch,
      },
    }));
  }, []);

  const refetch = useCallback(() => {
    if (activeWorkspaceSlug) loadConfig(activeWorkspaceSlug);
  }, [activeWorkspaceSlug, loadConfig]);

  const handleSaveKey = async () => {
    if (!activeWorkspaceSlug || !keyInput.trim()) return;
    setIsSavingKey(true);
    try {
      await upsertOpenRouterKey(activeWorkspaceSlug, { api_key: keyInput.trim() });
      setKeyInput('');
      setToast({ open: true, message: 'OpenRouter key saved', variant: 'success' });
      refetch();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to save OpenRouter key';
      setToast({ open: true, message: msg, variant: 'error' });
    } finally {
      setIsSavingKey(false);
    }
  };

  const handleDeleteKey = async () => {
    if (!activeWorkspaceSlug) return;
    setDeletingKey(true);
    try {
      await deleteOpenRouterKey(activeWorkspaceSlug);
      setToast({ open: true, message: 'OpenRouter key removed', variant: 'success' });
      refetch();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to remove OpenRouter key';
      setToast({ open: true, message: msg, variant: 'error' });
    } finally {
      setDeletingKey(false);
    }
  };

  const handleTestKey = async () => {
    if (!activeWorkspaceSlug) return;
    setIsTestingKey(true);
    try {
      const trimmedKey = keyInput.trim();
      const result = await testOpenRouterKey(activeWorkspaceSlug, {
        api_key: trimmedKey || null,
      });
      setToast({
        open: true,
        message: result.ok ? `OpenRouter connected with ${result.model}` : result.error || 'OpenRouter test failed',
        variant: result.ok ? 'success' : 'error',
      });
      refetch();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to test OpenRouter key';
      setToast({ open: true, message: msg, variant: 'error' });
    } finally {
      setIsTestingKey(false);
    }
  };

  const handleSaveAgent = async (row: AgentRow) => {
    if (!activeWorkspaceSlug) return;
    const model = row.draft.model.trim();
    if (!model) {
      setToast({ open: true, message: 'Model ID is required', variant: 'error' });
      return;
    }
    const temperature = parseOptionalNumber(row.draft.temperature, 'Temperature');
    const maxTokens = parseOptionalNumber(row.draft.maxTokens, 'Max tokens');
    const timeoutS = parseOptionalNumber(row.draft.timeoutS, 'Timeout');
    if (!temperature.ok) {
      setToast({ open: true, message: temperature.message, variant: 'error' });
      return;
    }
    if (!maxTokens.ok) {
      setToast({ open: true, message: maxTokens.message, variant: 'error' });
      return;
    }
    if (!timeoutS.ok) {
      setToast({ open: true, message: timeoutS.message, variant: 'error' });
      return;
    }

    setSavingAgentKey(row.catalog.agent_key);
    try {
      await updateAgentModelConfig(activeWorkspaceSlug, row.catalog.agent_key, {
        model,
        temperature: temperature.value,
        max_tokens: maxTokens.value,
        timeout_s: timeoutS.value,
        enabled: row.draft.enabled,
      });
      setToast({ open: true, message: `${row.catalog.display_name} saved`, variant: 'success' });
      refetch();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to save agent model config';
      setToast({ open: true, message: msg, variant: 'error' });
    } finally {
      setSavingAgentKey(null);
    }
  };

  const handleTestAgent = async (row: AgentRow) => {
    if (!activeWorkspaceSlug) return;
    setTestingAgentKey(row.catalog.agent_key);
    try {
      const result = await testAgentModelConfig(activeWorkspaceSlug, row.catalog.agent_key);
      setToast({
        open: true,
        message: result.ok ? `${row.catalog.display_name} connected with ${result.model}` : result.error || 'Agent test failed',
        variant: result.ok ? 'success' : 'error',
      });
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to test agent model config';
      setToast({ open: true, message: msg, variant: 'error' });
    } finally {
      setTestingAgentKey(null);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-[128px] rounded-md" />
        <Skeleton className="h-[360px] rounded-md" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="border border-border rounded-md bg-surface p-4">
        <div className="flex items-start gap-3">
          <AlertCircle size={16} strokeWidth={1.5} className="mt-[2px] text-error" />
          <div className="min-w-0">
            <h3 className="text-[14px] font-semibold text-text-primary">Models unavailable</h3>
            <p className="mt-1 text-[13px] text-text-secondary">{error}</p>
            <Button size="sm" variant="secondary" className="mt-3" onClick={refetch}>
              <RefreshCw size={12} strokeWidth={1.5} className="mr-1" />
              Retry
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (!configView) return null;

  return (
    <div className="space-y-5">
      <section className="border border-border rounded-md bg-surface p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <KeyRound size={16} strokeWidth={1.5} className="text-accent" />
              <h3 className="text-[16px] font-semibold text-text-primary">OpenRouter BYOK</h3>
            </div>
            <p className="mt-1 text-[13px] text-text-secondary">
              Workspace: <span className="font-mono text-[12px] text-text-primary">{configView.workspace_slug}</span>
            </p>
          </div>
          <div className="flex items-center gap-2">
            {statusBadge(configView.credential)}
            {missingRequiredCount > 0 && (
              <Badge variant="warning">{missingRequiredCount} required missing</Badge>
            )}
          </div>
        </div>

        <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_auto] lg:items-end">
          <div>
            <label className="mb-1 block text-[11px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
              API key
            </label>
            <Input
              type="password"
              value={keyInput}
              disabled={!canManageModels || isSavingKey}
              onChange={(event) => setKeyInput(event.target.value)}
              placeholder={configView.credential.configured ? configView.credential.masked_key : 'sk-or-v1-...'}
              className="w-full"
            />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              onClick={handleTestKey}
              disabled={!canManageModels || isTestingKey}
            >
              <Zap size={12} strokeWidth={1.5} className="mr-1" />
              {isTestingKey ? 'Testing' : 'Test'}
            </Button>
            <Button
              size="sm"
              onClick={handleSaveKey}
              disabled={!canManageModels || !keyInput.trim() || isSavingKey}
            >
              <Save size={12} strokeWidth={1.5} className="mr-1" />
              {isSavingKey ? 'Saving' : 'Save key'}
            </Button>
            {configView.credential.configured && (
              <Button
                size="sm"
                variant="destructive"
                onClick={handleDeleteKey}
                disabled={!canManageModels || deletingKey}
              >
                <Trash2 size={12} strokeWidth={1.5} className="mr-1" />
                {deletingKey ? 'Removing' : 'Remove'}
              </Button>
            )}
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-[12px] text-text-tertiary">
          <span>Status: <span className="text-text-secondary">{configView.credential.status || 'not_configured'}</span></span>
          <span>Last validated: <span className="text-text-secondary">{formatDate(configView.credential.last_validated_at)}</span></span>
          {configView.credential.last_validation_error && (
            <span className="text-error">{configView.credential.last_validation_error}</span>
          )}
        </div>
      </section>

      <section className="border border-border rounded-md bg-surface">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
          <div className="flex items-center gap-2">
            <BarChart3 size={16} strokeWidth={1.5} className="text-accent" />
            <h3 className="text-[16px] font-semibold text-text-primary">Usage Summary</h3>
          </div>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[12px] text-text-tertiary">
            <span>Calls: <span className="text-text-secondary">{usageTotals.calls}</span></span>
            <span>Tokens: <span className="text-text-secondary">{formatTokenCount(usageTotals.tokens)}</span></span>
            <span>Cost: <span className="text-text-secondary">{formatUsd(usageTotals.cost)}</span></span>
          </div>
        </div>
        {usageSummary.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-[12px]">
              <thead className="border-b border-border bg-bg text-[10px] uppercase tracking-[0.06em] text-text-tertiary">
                <tr>
                  <th className="px-4 py-2 font-medium">Agent</th>
                  <th className="px-3 py-2 font-medium">Calls</th>
                  <th className="px-3 py-2 font-medium">Tokens</th>
                  <th className="px-3 py-2 font-medium">Cost</th>
                  <th className="px-3 py-2 font-medium">Last used</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {usageSummary.map((row) => (
                  <tr key={row.agent_key}>
                    <td className="px-4 py-2">
                      <div className="font-medium text-text-primary">
                        {catalogNames.get(row.agent_key) ?? row.agent_key}
                      </div>
                      <div className="font-mono text-[11px] text-text-tertiary">
                        {row.agent_key}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-text-secondary">{row.call_count}</td>
                    <td className="px-3 py-2 text-text-secondary">
                      {formatTokenCount(row.prompt_tokens + row.completion_tokens)}
                    </td>
                    <td className="px-3 py-2 text-text-secondary">{formatUsd(row.estimated_cost_usd)}</td>
                    <td className="px-3 py-2 text-text-secondary">{formatDate(row.last_used_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="px-4 py-3 text-[13px] text-text-secondary">
            No BYOK usage recorded yet.
          </div>
        )}
      </section>

      <section className="border border-border rounded-md bg-surface">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
          <div>
            <h3 className="text-[16px] font-semibold text-text-primary">Agent Model Settings</h3>
            <p className="mt-1 text-[13px] text-text-secondary">
              {rows.length} workspace-scoped agents using OpenRouter model IDs.
            </p>
          </div>
          <Button size="sm" variant="secondary" onClick={refetch}>
            <RefreshCw size={12} strokeWidth={1.5} className="mr-1" />
            Refresh
          </Button>
        </div>

        <div className="divide-y divide-border">
          {groupedRows.map(([group, groupRows]) => (
            <div key={group}>
              <div className="bg-bg px-4 py-2 text-[11px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
                {group}
              </div>
              <div className="divide-y divide-border-subtle">
                {groupRows.map((row) => {
                  const unsaved = hasUnsavedChanges(row);
                  const isMissing = configView.missing_required_agent_keys.includes(row.catalog.agent_key);
                  return (
                    <div key={row.catalog.agent_key} className="px-4 py-3">
                      <div className="grid gap-3 xl:grid-cols-[minmax(220px,1.1fr)_minmax(280px,1.4fr)_92px_92px_92px_72px_auto] xl:items-end">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <h4 className="truncate text-[14px] font-semibold text-text-primary">
                              {row.catalog.display_name}
                            </h4>
                            {row.catalog.required && <Badge variant="info">Required</Badge>}
                            {isMissing && <Badge variant="error">Missing</Badge>}
                            {row.config?.uses_default && <Badge variant="neutral">Default</Badge>}
                            {unsaved && <Badge variant="warning">Unsaved</Badge>}
                          </div>
                          <p className="mt-1 font-mono text-[11px] text-text-tertiary">
                            {row.catalog.agent_key}
                          </p>
                          {row.catalog.description && (
                            <p className="mt-1 text-[12px] text-text-secondary">
                              {row.catalog.description}
                            </p>
                          )}
                        </div>

                        <div>
                          <label className="mb-1 block text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
                            Model ID
                          </label>
                          <Input
                            value={row.draft.model}
                            disabled={!canManageModels}
                            onChange={(event) => updateDraft(row.catalog.agent_key, { model: event.target.value })}
                            className="w-full font-mono"
                          />
                        </div>

                        <div>
                          <label className="mb-1 block text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
                            Temp
                          </label>
                          <Input
                            value={row.draft.temperature}
                            disabled={!canManageModels}
                            inputMode="decimal"
                            onChange={(event) => updateDraft(row.catalog.agent_key, { temperature: event.target.value })}
                          />
                        </div>

                        <div>
                          <label className="mb-1 block text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
                            Max tok
                          </label>
                          <Input
                            value={row.draft.maxTokens}
                            disabled={!canManageModels}
                            inputMode="numeric"
                            onChange={(event) => updateDraft(row.catalog.agent_key, { maxTokens: event.target.value })}
                          />
                        </div>

                        <div>
                          <label className="mb-1 block text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
                            Timeout
                          </label>
                          <Input
                            value={row.draft.timeoutS}
                            disabled={!canManageModels}
                            inputMode="decimal"
                            onChange={(event) => updateDraft(row.catalog.agent_key, { timeoutS: event.target.value })}
                          />
                        </div>

                        <div>
                          <label className="mb-1 block text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
                            Enabled
                          </label>
                          <Toggle
                            checked={row.draft.enabled}
                            onChange={(checked) => updateDraft(row.catalog.agent_key, { enabled: checked })}
                            className={!canManageModels ? 'pointer-events-none opacity-50' : undefined}
                          />
                        </div>

                        <div className="flex items-center gap-2">
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => handleTestAgent(row)}
                            disabled={!canManageModels || testingAgentKey === row.catalog.agent_key}
                          >
                            <Zap size={12} strokeWidth={1.5} className="mr-1" />
                            {testingAgentKey === row.catalog.agent_key ? 'Testing' : 'Test'}
                          </Button>
                          <Button
                            size="sm"
                            onClick={() => handleSaveAgent(row)}
                            disabled={!canManageModels || !unsaved || savingAgentKey === row.catalog.agent_key}
                          >
                            <CheckCircle2 size={12} strokeWidth={1.5} className="mr-1" />
                            {savingAgentKey === row.catalog.agent_key ? 'Saving' : 'Save'}
                          </Button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </section>

      <Toast
        open={toast.open}
        onClose={() => setToast((current) => ({ ...current, open: false }))}
        variant={toast.variant}
        message={toast.message}
      />
    </div>
  );
}
