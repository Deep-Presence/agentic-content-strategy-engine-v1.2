'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, CheckCircle2, KeyRound, RefreshCw, Save, Zap } from 'lucide-react';
import { Badge, Button, Input, Skeleton, Toast, Toggle } from '@/components/ui';
import { ApiError } from '@/lib/api-client';
import {
  fetchWorkspaceModelConfig,
  preflightModelConfig,
  testOpenRouterKey,
  updateAgentModelConfig,
  upsertOpenRouterKey,
} from '@/lib/model-config';
import type {
  AgentCatalogItemAPI,
  AgentModelConfigAPI,
  ModelConfigPreflightResponseAPI,
  WorkspaceModelConfigAPI,
} from '@/lib/model-config';

const ONBOARDING_PIPELINES = new Set([
  'research_kb',
  'research_ap',
  'research_vsg',
  'gap',
  'topic_discovery',
]);

const GROUP_ORDER = [
  'Shared',
  'Knowledge Base',
  'Audience Persona',
  'Voice Style Guide',
  'Gap Analysis',
  'Topic Discovery',
];

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

interface ScreenModelConfigProps {
  workspaceSlug: string;
  canManageModels: boolean;
  onContinue: () => void;
}

function toDraft(catalog: AgentCatalogItemAPI, config?: AgentModelConfigAPI): AgentDraft {
  return {
    model: config?.model || catalog.default_model,
    temperature: config?.temperature == null ? '' : String(config.temperature),
    maxTokens: config?.max_tokens == null ? '' : String(config.max_tokens),
    timeoutS: config?.timeout_s == null ? '' : String(config.timeout_s),
    enabled: config?.enabled ?? true,
  };
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

function parseOptionalNumber(value: string, label: string): { ok: true; value: number | null } | { ok: false; message: string } {
  const trimmed = value.trim();
  if (!trimmed) return { ok: true, value: null };
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) return { ok: false, message: `${label} must be a number` };
  return { ok: true, value: parsed };
}

function credentialIsActive(view: WorkspaceModelConfigAPI | null): boolean {
  const credential = view?.credential;
  if (!credential?.configured) return false;
  return credential.status === 'active' || credential.status === 'valid';
}

function onboardingAgentKeys(view: WorkspaceModelConfigAPI): string[] {
  return view.catalog
    .filter((agent) => {
      if (!agent.required) return false;
      if (agent.agent_key === 'shared.embeddings.default') return true;
      return ONBOARDING_PIPELINES.has(agent.pipeline);
    })
    .map((agent) => agent.agent_key);
}

function statusBadge(view: WorkspaceModelConfigAPI | null) {
  const credential = view?.credential;
  if (!credential?.configured) return <Badge variant="error">Missing key</Badge>;
  if (credential.status === 'active' || credential.status === 'valid') return <Badge variant="success">Active</Badge>;
  if (credential.status === 'invalid') return <Badge variant="error">Invalid</Badge>;
  return <Badge variant="warning">Untested</Badge>;
}

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    return typeof err.detail === 'string' ? err.detail : fallback;
  }
  return fallback;
}

export function ScreenModelConfig({ workspaceSlug, canManageModels, onContinue }: ScreenModelConfigProps) {
  const [configView, setConfigView] = useState<WorkspaceModelConfigAPI | null>(null);
  const [drafts, setDrafts] = useState<Record<string, AgentDraft>>({});
  const [keyInput, setKeyInput] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSavingKey, setIsSavingKey] = useState(false);
  const [isTestingKey, setIsTestingKey] = useState(false);
  const [savingAgentKey, setSavingAgentKey] = useState<string | null>(null);
  const [isPreflighting, setIsPreflighting] = useState(false);
  const [preflight, setPreflight] = useState<ModelConfigPreflightResponseAPI | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<ToastState>({ open: false, message: '', variant: 'info' });
  const abortRef = useRef<AbortController | null>(null);

  const applyConfig = useCallback((view: WorkspaceModelConfigAPI) => {
    const byAgent = new Map(view.configs.map((item) => [item.agent_key, item]));
    setConfigView(view);
    setDrafts(Object.fromEntries(
      view.catalog.map((item) => [
        item.agent_key,
        toDraft(item, byAgent.get(item.agent_key)),
      ]),
    ));
  }, []);

  const runPreflight = useCallback(async (view: WorkspaceModelConfigAPI) => {
    const agentKeys = onboardingAgentKeys(view);
    if (agentKeys.length === 0) return;
    setIsPreflighting(true);
    try {
      const result = await preflightModelConfig(workspaceSlug, agentKeys);
      setPreflight(result);
    } catch (err) {
      setPreflight(null);
      setToast({
        open: true,
        message: errorMessage(err, 'Model preflight failed'),
        variant: 'error',
      });
    } finally {
      setIsPreflighting(false);
    }
  }, [workspaceSlug]);

  const loadConfig = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setIsLoading(true);
    setError(null);
    try {
      const view = await fetchWorkspaceModelConfig(workspaceSlug, controller.signal);
      if (controller.signal.aborted) return;
      applyConfig(view);
      await runPreflight(view);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      setError(errorMessage(err, 'Failed to load model configuration'));
    } finally {
      if (!controller.signal.aborted) setIsLoading(false);
    }
  }, [applyConfig, runPreflight, workspaceSlug]);

  useEffect(() => {
    if (!workspaceSlug) return;
    loadConfig();
    return () => abortRef.current?.abort();
  }, [loadConfig, workspaceSlug]);

  const rows = useMemo<AgentRow[]>(() => {
    if (!configView) return [];
    const byAgent = new Map(configView.configs.map((item) => [item.agent_key, item]));
    return configView.catalog
      .filter((agent) => (
        agent.agent_key === 'shared.embeddings.default' ||
        ONBOARDING_PIPELINES.has(agent.pipeline)
      ))
      .map((catalog) => ({
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
    return Array.from(groups.entries()).sort((a, b) => {
      const aIndex = GROUP_ORDER.indexOf(a[0]);
      const bIndex = GROUP_ORDER.indexOf(b[0]);
      return (aIndex === -1 ? 99 : aIndex) - (bIndex === -1 ? 99 : bIndex);
    });
  }, [rows]);

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
    void loadConfig();
  }, [loadConfig]);

  const handleSaveKey = async () => {
    if (!keyInput.trim()) return;
    setIsSavingKey(true);
    try {
      await upsertOpenRouterKey(workspaceSlug, { api_key: keyInput.trim() });
      setKeyInput('');
      setToast({ open: true, message: 'OpenRouter key saved', variant: 'success' });
      await loadConfig();
    } catch (err) {
      setToast({ open: true, message: errorMessage(err, 'Failed to save OpenRouter key'), variant: 'error' });
    } finally {
      setIsSavingKey(false);
    }
  };

  const handleTestKey = async () => {
    setIsTestingKey(true);
    try {
      const result = await testOpenRouterKey(workspaceSlug, { api_key: keyInput.trim() || null });
      setToast({
        open: true,
        message: result.ok ? `OpenRouter connected with ${result.model}` : result.error || 'OpenRouter test failed',
        variant: result.ok ? 'success' : 'error',
      });
      await loadConfig();
    } catch (err) {
      setToast({ open: true, message: errorMessage(err, 'Failed to test OpenRouter key'), variant: 'error' });
    } finally {
      setIsTestingKey(false);
    }
  };

  const handleSaveAgent = async (row: AgentRow) => {
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
      await updateAgentModelConfig(workspaceSlug, row.catalog.agent_key, {
        model,
        temperature: temperature.value,
        max_tokens: maxTokens.value,
        timeout_s: timeoutS.value,
        enabled: row.draft.enabled,
      });
      setToast({ open: true, message: `${row.catalog.display_name} saved`, variant: 'success' });
      await loadConfig();
    } catch (err) {
      setToast({ open: true, message: errorMessage(err, 'Failed to save model config'), variant: 'error' });
    } finally {
      setSavingAgentKey(null);
    }
  };

  const canContinue = credentialIsActive(configView) && preflight?.ok === true;
  const preflightProblems = [
    ...(preflight?.missing_agent_keys ?? []),
    ...(preflight?.disabled_agent_keys ?? []),
  ];

  if (isLoading) {
    return (
      <div className="mx-auto w-full max-w-[760px] space-y-4">
        <Skeleton className="h-[132px] rounded-md" />
        <Skeleton className="h-[420px] rounded-md" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto w-full max-w-[560px] border border-border rounded-md bg-surface p-4">
        <div className="flex items-start gap-3">
          <AlertCircle size={16} strokeWidth={1.5} className="mt-[2px] text-error" />
          <div className="min-w-0">
            <h1 className="text-[16px] font-semibold text-text-primary">Models unavailable</h1>
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

  return (
    <div className="mx-auto w-full max-w-[860px]">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-[24px] font-semibold tracking-[-0.02em] text-text-primary mb-2">
            Connect your models
          </h1>
          <p className="max-w-[560px] text-[14px] text-text-secondary leading-[1.6]">
            Add your OpenRouter key and review the model defaults used for onboarding.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {statusBadge(configView)}
          {preflight?.ok && <Badge variant="success">Preflight ready</Badge>}
          {isPreflighting && <Badge variant="info">Checking</Badge>}
        </div>
      </div>

      <section className="mb-4 border border-border rounded-md bg-surface p-4">
        <div className="flex items-center gap-2">
          <KeyRound size={16} strokeWidth={1.5} className="text-accent" />
          <h2 className="text-[16px] font-semibold text-text-primary">OpenRouter BYOK</h2>
        </div>
        <p className="mt-1 text-[13px] text-text-secondary">
          Workspace: <span className="font-mono text-[12px] text-text-primary">{workspaceSlug}</span>
        </p>
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
              placeholder={configView?.credential.configured ? configView.credential.masked_key : 'sk-or-v1-...'}
              className="h-[36px] w-full text-[13px]"
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
          </div>
        </div>
        {configView?.credential.last_validation_error && (
          <p className="mt-3 text-[13px] text-error">{configView.credential.last_validation_error}</p>
        )}
      </section>

      <section className="border border-border rounded-md bg-surface">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
          <div>
            <h2 className="text-[16px] font-semibold text-text-primary">Onboarding Model Settings</h2>
            <p className="mt-1 text-[13px] text-text-secondary">
              {rows.length} agents across the onboarding pipeline.
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
                  const isMissing = configView?.missing_required_agent_keys.includes(row.catalog.agent_key);
                  return (
                    <div key={row.catalog.agent_key} className="px-4 py-3">
                      <div className="grid gap-3 xl:grid-cols-[minmax(190px,1fr)_minmax(260px,1.35fr)_84px_84px_84px_68px_auto] xl:items-end">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="truncate text-[14px] font-semibold text-text-primary">
                              {row.catalog.display_name}
                            </h3>
                            {row.catalog.required && <Badge variant="info">Required</Badge>}
                            {isMissing && <Badge variant="error">Missing</Badge>}
                            {row.config?.uses_default && <Badge variant="neutral">Default</Badge>}
                            {unsaved && <Badge variant="warning">Unsaved</Badge>}
                          </div>
                          <p className="mt-1 font-mono text-[11px] text-text-tertiary">
                            {row.catalog.agent_key}
                          </p>
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
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </section>

      {!canContinue && (
        <div className="mt-4 flex items-start gap-2 rounded-sm border border-warning bg-warning-subtle px-3 py-2 text-[13px] text-warning">
          <AlertCircle size={14} strokeWidth={1.5} className="mt-[2px] flex-shrink-0" />
          <span>
            {credentialIsActive(configView)
              ? preflightProblems.length > 0
                ? `Resolve ${preflightProblems.length} model configuration issue${preflightProblems.length === 1 ? '' : 's'} before continuing.`
                : 'Model preflight must pass before continuing.'
              : 'An active OpenRouter key is required before continuing.'}
          </span>
        </div>
      )}

      <div className="mt-5 flex justify-end">
        <Button
          variant="primary"
          className="h-[36px] px-5 text-[14px]"
          disabled={!canContinue}
          onClick={onContinue}
        >
          Continue
        </Button>
      </div>

      <Toast
        open={toast.open}
        onClose={() => setToast((current) => ({ ...current, open: false }))}
        variant={toast.variant}
        message={toast.message}
      />
    </div>
  );
}
