'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Modal, Button, Input } from '@/components/ui';
import { AlertCircle, ChevronLeft, ChevronRight } from 'lucide-react';
import type {
  CMSConnectRequestAPI,
  WebflowCollectionConfigInputAPI,
  WebflowCollectionFieldsAPI,
  WebflowCollectionSummaryAPI,
  WebflowConfigureRequestAPI,
  WebflowFieldMappingAPI,
  WebflowSiteSummaryAPI,
  WebflowSelectSiteRequestAPI,
} from '../_lib/types';

type Step = 'credentials' | 'site' | 'collections' | 'mapping';
type AuthMode = 'oauth' | 'token';

const MAPPING_FIELDS: Array<{ key: keyof WebflowFieldMappingAPI; label: string; required?: boolean }> = [
  { key: 'title_field', label: 'Title' },
  { key: 'slug_field', label: 'Slug' },
  { key: 'body_field', label: 'Body', required: true },
  { key: 'excerpt_field', label: 'Excerpt' },
  { key: 'seo_title_field', label: 'SEO Title' },
  { key: 'seo_description_field', label: 'SEO Description' },
  { key: 'category_field', label: 'Category' },
  { key: 'tags_field', label: 'Tags' },
  { key: 'featured_image_field', label: 'Featured Image' },
];

interface WebflowConnectModalProps {
  open: boolean;
  onClose: () => void;
  oauthPendingSite?: boolean;
  onConnect: (body: CMSConnectRequestAPI) => Promise<{ success: boolean; error?: string }>;
  onStartOAuth: () => Promise<void>;
  onLoadSites: () => Promise<WebflowSiteSummaryAPI[]>;
  onSelectSite: (body: WebflowSelectSiteRequestAPI) => Promise<{ success: boolean; error?: string }>;
  onLoadCollections: () => Promise<WebflowCollectionSummaryAPI[]>;
  onLoadCollectionFields: (collectionId: string) => Promise<WebflowCollectionFieldsAPI>;
  onConfigure: (body: WebflowConfigureRequestAPI) => Promise<{ success: boolean; error?: string }>;
}

interface SelectedCollection {
  summary: WebflowCollectionSummaryAPI;
  enabled: boolean;
  isDefault: boolean;
  mapping: WebflowFieldMappingAPI;
  fields: WebflowCollectionFieldsAPI['fields'];
}

export function WebflowConnectModal({
  open,
  onClose,
  oauthPendingSite = false,
  onConnect,
  onStartOAuth,
  onLoadSites,
  onSelectSite,
  onLoadCollections,
  onLoadCollectionFields,
  onConfigure,
}: WebflowConnectModalProps) {
  const [step, setStep] = useState<Step>('credentials');
  const [authMode, setAuthMode] = useState<AuthMode>('oauth');
  const [siteUrl, setSiteUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [siteId, setSiteId] = useState('');
  const [sites, setSites] = useState<WebflowSiteSummaryAPI[]>([]);
  const [selectedSiteId, setSelectedSiteId] = useState('');
  const [selected, setSelected] = useState<Record<string, SelectedCollection>>({});
  const [activeMappingId, setActiveMappingId] = useState('');
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const enabledCollections = useMemo(
    () => Object.values(selected).filter((item) => item.enabled),
    [selected],
  );

  const resetState = useCallback(() => {
    setStep('credentials');
    setAuthMode('oauth');
    setSiteUrl('');
    setApiKey('');
    setSiteId('');
    setSites([]);
    setSelectedSiteId('');
    setSelected({});
    setActiveMappingId('');
    setError(null);
  }, []);

  const loadCollectionsStep = useCallback(async (resolvedSiteId: string) => {
    const collections = await onLoadCollections();
    if (collections.length === 0) {
      setError('No CMS collections found on this Webflow site');
      return false;
    }

    const nextSelected: Record<string, SelectedCollection> = {};
    for (let index = 0; index < collections.length; index += 1) {
      const summary = collections[index];
      const fieldsResponse = await onLoadCollectionFields(summary.collection_id);
      nextSelected[summary.collection_id] = {
        summary,
        enabled: index === 0,
        isDefault: index === 0,
        mapping: fieldsResponse.suggested_mapping,
        fields: fieldsResponse.fields,
      };
    }

    setSiteId(resolvedSiteId);
    setSelected(nextSelected);
    setActiveMappingId(collections[0]?.collection_id ?? '');
    setStep('collections');
    return true;
  }, [onLoadCollectionFields, onLoadCollections]);

  useEffect(() => {
    if (!open) return;
    if (!oauthPendingSite) return;

    let cancelled = false;
    setStep('site');
    setAuthMode('oauth');
    setIsBusy(true);
    setError(null);

    onLoadSites()
      .then((loaded) => {
        if (cancelled) return;
        setSites(loaded);
        setSelectedSiteId(loaded[0]?.site_id ?? '');
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load Webflow sites');
      })
      .finally(() => {
        if (!cancelled) setIsBusy(false);
      });

    return () => { cancelled = true; };
  }, [open, oauthPendingSite, onLoadSites]);

  const handleClose = useCallback(() => {
    if (isBusy) return;
    resetState();
    onClose();
  }, [isBusy, onClose, resetState]);

  useEffect(() => {
    if (!open) resetState();
  }, [open, resetState]);

  const handleOAuthStart = useCallback(async () => {
    setIsBusy(true);
    setError(null);
    try {
      await onStartOAuth();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start Webflow OAuth');
      setIsBusy(false);
    }
  }, [onStartOAuth]);

  const handleCredentialsNext = useCallback(async () => {
    if (!siteUrl || !apiKey) {
      setError('Site URL and Site API Token are required');
      return;
    }

    setIsBusy(true);
    setError(null);

    const connectResult = await onConnect({
      provider: 'webflow',
      site_url: siteUrl,
      username: '',
      api_key: apiKey,
    });

    if (!connectResult.success) {
      setIsBusy(false);
      setError(connectResult.error || 'Connection failed');
      return;
    }

    try {
      await loadCollectionsStep(siteId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load Webflow collections');
    } finally {
      setIsBusy(false);
    }
  }, [apiKey, loadCollectionsStep, onConnect, siteId, siteUrl]);

  const handleSiteNext = useCallback(async () => {
    if (!selectedSiteId) {
      setError('Select a Webflow site');
      return;
    }

    const site = sites.find((item) => item.site_id === selectedSiteId);
    setIsBusy(true);
    setError(null);

    const selectResult = await onSelectSite({
      site_id: selectedSiteId,
      site_url: site?.preview_url ?? '',
    });

    if (!selectResult.success) {
      setIsBusy(false);
      setError(selectResult.error || 'Failed to select Webflow site');
      return;
    }

    try {
      await loadCollectionsStep(selectedSiteId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load Webflow collections');
    } finally {
      setIsBusy(false);
    }
  }, [loadCollectionsStep, onSelectSite, selectedSiteId, sites]);

  const handleCollectionsNext = useCallback(() => {
    if (enabledCollections.length === 0) {
      setError('Select at least one collection to sync and publish');
      return;
    }
    if (!enabledCollections.some((item) => item.isDefault)) {
      setError('Choose a default publish collection');
      return;
    }
    setError(null);
    setActiveMappingId(enabledCollections[0]?.summary.collection_id ?? '');
    setStep('mapping');
  }, [enabledCollections]);

  const handleSave = useCallback(async () => {
    for (const item of enabledCollections) {
      if (!item.mapping.body_field) {
        setError(`Body field is required for ${item.summary.display_name}`);
        setActiveMappingId(item.summary.collection_id);
        return;
      }
    }

    setIsBusy(true);
    setError(null);

    const collections: WebflowCollectionConfigInputAPI[] = enabledCollections.map((item) => ({
      collection_id: item.summary.collection_id,
      collection_slug: item.summary.collection_slug,
      display_name: item.summary.display_name,
      enabled: true,
      is_default_publish_target: item.isDefault,
      field_mapping: item.mapping,
    }));

    const defaultCollection = enabledCollections.find((item) => item.isDefault);

    const result = await onConfigure({
      site_id: siteId,
      collections,
      publish_mode: 'live_direct',
      default_collection_id: defaultCollection?.summary.collection_id ?? '',
      trigger_sync: true,
    });

    setIsBusy(false);

    if (result.success) {
      handleClose();
      return;
    }

    setError(result.error || 'Failed to save Webflow configuration');
  }, [enabledCollections, handleClose, onConfigure, siteId]);

  const updateMapping = useCallback((
    collectionId: string,
    key: keyof WebflowFieldMappingAPI,
    value: string,
  ) => {
    setSelected((prev) => {
      const current = prev[collectionId];
      if (!current) return prev;
      return {
        ...prev,
        [collectionId]: {
          ...current,
          mapping: { ...current.mapping, [key]: value },
        },
      };
    });
  }, []);

  const toggleCollection = useCallback((collectionId: string, enabled: boolean) => {
    setSelected((prev) => {
      const current = prev[collectionId];
      if (!current) return prev;
      const next = {
        ...prev,
        [collectionId]: {
          ...current,
          enabled,
          isDefault: enabled ? current.isDefault : false,
        },
      };
      const enabledItems = Object.values(next).filter((item) => item.enabled);
      if (enabled && !enabledItems.some((item) => item.isDefault)) {
        next[collectionId] = { ...next[collectionId], isDefault: true };
      }
      if (enabledItems.length === 1) {
        const onlyId = enabledItems[0].summary.collection_id;
        Object.keys(next).forEach((id) => {
          next[id] = { ...next[id], isDefault: id === onlyId };
        });
      }
      return next;
    });
  }, []);

  const setDefaultCollection = useCallback((collectionId: string) => {
    setSelected((prev) => {
      const next = { ...prev };
      Object.keys(next).forEach((id) => {
        next[id] = {
          ...next[id],
          isDefault: id === collectionId && next[id].enabled,
        };
      });
      return next;
    });
  }, []);

  const activeCollection = activeMappingId ? selected[activeMappingId] : undefined;

  const stepTitle = step === 'credentials'
    ? 'Connect Webflow'
    : step === 'site'
      ? 'Select Site'
      : step === 'collections'
        ? 'Select Collections'
        : 'Map Fields';

  const showSiteStep = authMode === 'oauth' || oauthPendingSite;

  return (
    <Modal open={open} onClose={handleClose} title={stepTitle} className="min-w-[520px] max-w-[640px]">
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-[11px] text-text-tertiary flex-wrap">
          {!oauthPendingSite && (
            <>
              <span className={step === 'credentials' ? 'text-accent font-medium' : ''}>1. Connect</span>
              <ChevronRight size={12} />
            </>
          )}
          {showSiteStep && (
            <>
              <span className={step === 'site' ? 'text-accent font-medium' : ''}>
                {oauthPendingSite ? '1. Site' : '2. Site'}
              </span>
              <ChevronRight size={12} />
            </>
          )}
          <span className={step === 'collections' ? 'text-accent font-medium' : ''}>
            {showSiteStep ? (oauthPendingSite ? '2. Collections' : '3. Collections') : '2. Collections'}
          </span>
          <ChevronRight size={12} />
          <span className={step === 'mapping' ? 'text-accent font-medium' : ''}>
            {showSiteStep ? (oauthPendingSite ? '3. Field Map' : '4. Field Map') : '3. Field Map'}
          </span>
        </div>

        {step === 'credentials' && (
          <>
            <div className="flex gap-2">
              <Button
                type="button"
                variant={authMode === 'oauth' ? 'secondary' : 'ghost'}
                size="sm"
                onClick={() => setAuthMode('oauth')}
                disabled={isBusy}
              >
                Connect with Webflow
              </Button>
              <Button
                type="button"
                variant={authMode === 'token' ? 'secondary' : 'ghost'}
                size="sm"
                onClick={() => setAuthMode('token')}
                disabled={isBusy}
              >
                Site API Token
              </Button>
            </div>

            {authMode === 'oauth' ? (
              <div className="space-y-3">
                <p className="text-[13px] text-text-secondary">
                  Authorize Deep Presence in Webflow, then pick your site and CMS collections.
                </p>
                <Button onClick={handleOAuthStart} disabled={isBusy}>
                  {isBusy ? 'Redirecting...' : 'Continue to Webflow'}
                </Button>
              </div>
            ) : (
              <>
            <div>
              <label className="text-[13px] font-medium text-text-secondary block mb-1.5">
                Site URL
              </label>
              <Input
                type="url"
                placeholder="https://www.yoursite.com"
                value={siteUrl}
                onChange={(e) => setSiteUrl(e.target.value)}
                disabled={isBusy}
                className="text-[14px] h-[34px]"
              />
            </div>
            <div>
              <label className="text-[13px] font-medium text-text-secondary block mb-1.5">
                Site API Token
              </label>
              <Input
                type="password"
                placeholder="Webflow Site API Token"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                disabled={isBusy}
                className="text-[14px] h-[34px]"
              />
              <p className="text-[11px] text-text-tertiary mt-1">
                Create in Webflow &rarr; Site settings &rarr; Apps &amp; integrations &rarr; API access
              </p>
            </div>
            <div>
              <label className="text-[13px] font-medium text-text-secondary block mb-1.5">
                Site ID (optional)
              </label>
              <Input
                type="text"
                placeholder="Only needed if you have multiple sites on the token"
                value={siteId}
                onChange={(e) => setSiteId(e.target.value)}
                disabled={isBusy}
                className="text-[14px] h-[34px]"
              />
            </div>
              </>
            )}
          </>
        )}

        {step === 'site' && (
          <div className="space-y-2 max-h-[320px] overflow-y-auto pr-1">
            {sites.map((site) => (
              <label
                key={site.site_id}
                className="flex items-start gap-3 border border-border rounded-md p-3 cursor-pointer hover:border-border-strong"
              >
                <input
                  type="radio"
                  name="webflow-site"
                  checked={selectedSiteId === site.site_id}
                  onChange={() => setSelectedSiteId(site.site_id)}
                  className="mt-0.5 accent-[var(--accent)]"
                />
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-medium text-text-primary">
                    {site.display_name}
                  </div>
                  {site.preview_url && (
                    <div className="text-[11px] text-text-tertiary truncate">
                      {site.preview_url}
                    </div>
                  )}
                </div>
              </label>
            ))}
            {sites.length === 0 && !isBusy && (
              <p className="text-[13px] text-text-secondary">No Webflow sites found for this account.</p>
            )}
          </div>
        )}

        {step === 'collections' && (
          <div className="space-y-2 max-h-[320px] overflow-y-auto pr-1">
            {Object.values(selected).map((item) => (
              <label
                key={item.summary.collection_id}
                className="flex items-start gap-3 border border-border rounded-md p-3 cursor-pointer hover:border-border-strong"
              >
                <input
                  type="checkbox"
                  checked={item.enabled}
                  onChange={(e) => toggleCollection(item.summary.collection_id, e.target.checked)}
                  className="mt-0.5 accent-[var(--accent)]"
                />
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-medium text-text-primary">
                    {item.summary.display_name}
                  </div>
                  <div className="text-[11px] text-text-tertiary font-mono">
                    {item.summary.collection_slug}
                  </div>
                  {item.enabled && (
                    <label className="flex items-center gap-2 mt-2 text-[11px] text-text-secondary">
                      <input
                        type="radio"
                        name="webflow-default-collection"
                        checked={item.isDefault}
                        onChange={() => setDefaultCollection(item.summary.collection_id)}
                        className="accent-[var(--accent)]"
                      />
                      Default publish target
                    </label>
                  )}
                </div>
              </label>
            ))}
          </div>
        )}

        {step === 'mapping' && (
          <div className="space-y-3">
            {enabledCollections.length > 1 && (
              <div>
                <label className="text-[13px] font-medium text-text-secondary block mb-1.5">
                  Collection
                </label>
                <select
                  value={activeMappingId}
                  onChange={(e) => setActiveMappingId(e.target.value)}
                  className="w-full h-[34px] px-3 rounded-sm border border-border bg-surface text-[13px] text-text-primary outline-none"
                >
                  {enabledCollections.map((item) => (
                    <option key={item.summary.collection_id} value={item.summary.collection_id}>
                      {item.summary.display_name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {activeCollection && (
              <div className="space-y-2 max-h-[280px] overflow-y-auto pr-1">
                {MAPPING_FIELDS.map((field) => (
                  <div key={field.key}>
                    <label className="text-[12px] font-medium text-text-secondary block mb-1">
                      {field.label}
                      {field.required ? ' *' : ''}
                    </label>
                    <select
                      value={activeCollection.mapping[field.key]}
                      onChange={(e) => updateMapping(activeMappingId, field.key, e.target.value)}
                      className="w-full h-[32px] px-3 rounded-sm border border-border bg-surface text-[12px] text-text-primary outline-none"
                    >
                      <option value="">— Not mapped —</option>
                      {activeCollection.fields.map((schemaField) => (
                        <option key={schemaField.slug} value={schemaField.slug}>
                          {schemaField.display_name || schemaField.slug} ({schemaField.field_type})
                        </option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {error && (
          <div className="flex items-start gap-2 bg-error/5 border border-error/20 rounded-md px-3 py-2">
            <AlertCircle size={14} strokeWidth={1.5} className="text-error shrink-0 mt-0.5" />
            <span className="text-[13px] text-error">{error}</span>
          </div>
        )}

        <div className="flex items-center gap-2 pt-1">
          {step !== 'credentials' && !(oauthPendingSite && step === 'site') && (
            <Button
              variant="ghost"
              onClick={() => {
                if (step === 'mapping') setStep('collections');
                else if (step === 'collections') setStep(showSiteStep ? 'site' : 'credentials');
                else if (step === 'site') setStep('credentials');
              }}
              disabled={isBusy}
            >
              <ChevronLeft size={14} className="mr-1" />
              Back
            </Button>
          )}
          <div className="flex-1" />
          {step === 'credentials' && authMode === 'token' && (
            <Button onClick={handleCredentialsNext} disabled={isBusy || !siteUrl || !apiKey}>
              {isBusy ? 'Connecting...' : 'Next'}
            </Button>
          )}
          {step === 'site' && (
            <Button onClick={handleSiteNext} disabled={isBusy || !selectedSiteId}>
              {isBusy ? 'Loading collections...' : 'Next'}
            </Button>
          )}
          {step === 'collections' && (
            <Button onClick={handleCollectionsNext} disabled={isBusy || enabledCollections.length === 0}>
              Next
            </Button>
          )}
          {step === 'mapping' && (
            <Button onClick={handleSave} disabled={isBusy}>
              {isBusy ? 'Saving & syncing...' : 'Save & Sync'}
            </Button>
          )}
          <Button variant="ghost" onClick={handleClose} disabled={isBusy}>
            Cancel
          </Button>
        </div>
      </div>
    </Modal>
  );
}
