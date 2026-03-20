'use client';

import { useState, useEffect } from 'react';
import { Button, Input, Skeleton, Toast } from '@/components/ui';
import { useAuthStore } from '@/stores/auth';
import { usePipelineDefaults, useUpdatePipelineDefaults } from '@/lib/hooks/useSettings';

const AVAILABLE_PLATFORMS = ['perplexity', 'openai', 'gemini', 'claude'];

export function PipelineDefaultsTab() {
  const slug = useAuthStore((s) => s.company?.slug);
  const userRole = useAuthStore((s) => s.user?.role);
  const { data: defaults, isLoading, refetch } = usePipelineDefaults(slug);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const { update, isUpdating, error } = useUpdatePipelineDefaults(slug);

  const [maxCrawlPages, setMaxCrawlPages] = useState('200');
  const [maxCrawlDepth, setMaxCrawlDepth] = useState('4');
  const [maxQueries, setMaxQueries] = useState('150');
  const [platforms, setPlatforms] = useState<string[]>([]);
  const [maxPersonas, setMaxPersonas] = useState('5');
  const [maxBriefs, setMaxBriefs] = useState('20');
  const [maxRevisionCycles, setMaxRevisionCycles] = useState('2');
  const [autoApproveResearch, setAutoApproveResearch] = useState(false);
  const [autoApproveContent, setAutoApproveContent] = useState(false);
  const [toast, setToast] = useState({ open: false, message: '' });

  useEffect(() => {
    if (defaults) {
      setMaxCrawlPages(String(defaults.max_crawl_pages ?? 200));
      setMaxCrawlDepth(String(defaults.max_crawl_depth ?? 4));
      setMaxQueries(String(defaults.max_queries ?? 150));
      setPlatforms(defaults.platforms ?? ['perplexity', 'openai']);
      setMaxPersonas(String(defaults.max_personas ?? 5));
      setMaxBriefs(String(defaults.max_briefs ?? 20));
      setMaxRevisionCycles(String(defaults.max_revision_cycles ?? 2));
      setAutoApproveResearch(defaults.auto_approve_research);
      setAutoApproveContent(defaults.auto_approve_content);
    }
  }, [defaults]);

  const isSuperuser = userRole === 'superuser';

  const togglePlatform = (p: string) => {
    setPlatforms((prev) => prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]);
  };

  const parseIntOrNull = (v: string): number | null => {
    const n = parseInt(v, 10);
    return Number.isNaN(n) ? null : n;
  };

  const handleSave = async () => {
    const ok = await update({
      max_crawl_pages: parseIntOrNull(maxCrawlPages),
      max_crawl_depth: parseIntOrNull(maxCrawlDepth),
      max_queries: parseIntOrNull(maxQueries),
      platforms,
      max_personas: parseIntOrNull(maxPersonas),
      max_briefs: parseIntOrNull(maxBriefs),
      max_revision_cycles: parseIntOrNull(maxRevisionCycles),
      auto_approve_research: autoApproveResearch,
      auto_approve_content: autoApproveContent,
    });
    if (ok) {
      setToast({ open: true, message: 'Pipeline defaults saved!' });
      refetch();
    }
  };

  if (isLoading) {
    return <div className="space-y-3"><Skeleton className="h-10 w-full rounded-md" /><Skeleton className="h-60 w-full rounded-md" /></div>;
  }

  return (
    <div className="space-y-6 max-w-lg">
      <div>
        <h3 className="text-[13px] font-semibold text-text-primary mb-3">Site Audit Defaults</h3>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary block mb-1">Max Crawl Pages</label>
            <Input type="number" value={maxCrawlPages} onChange={(e) => setMaxCrawlPages(e.target.value)} disabled={!isSuperuser} />
          </div>
          <div>
            <label className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary block mb-1">Max Crawl Depth</label>
            <Input type="number" value={maxCrawlDepth} onChange={(e) => setMaxCrawlDepth(e.target.value)} disabled={!isSuperuser} />
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-[13px] font-semibold text-text-primary mb-3">Gap Analysis Defaults</h3>
        <div className="space-y-3">
          <div>
            <label className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary block mb-1">Max Queries</label>
            <Input type="number" value={maxQueries} onChange={(e) => setMaxQueries(e.target.value)} disabled={!isSuperuser} />
          </div>
          <div>
            <label className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary block mb-1">Platforms</label>
            <div className="flex gap-2 flex-wrap">
              {AVAILABLE_PLATFORMS.map((p) => (
                <button
                  key={p}
                  onClick={() => isSuperuser && togglePlatform(p)}
                  className={`px-2 py-1 rounded-sm text-[11px] border transition-colors cursor-pointer ${
                    platforms.includes(p)
                      ? 'bg-accent-subtle text-accent border-accent'
                      : 'bg-surface text-text-secondary border-border hover:border-border-strong'
                  } ${!isSuperuser ? 'opacity-60 cursor-not-allowed' : ''}`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-[13px] font-semibold text-text-primary mb-3">Research Defaults</h3>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary block mb-1">Max Personas</label>
            <Input type="number" value={maxPersonas} onChange={(e) => setMaxPersonas(e.target.value)} disabled={!isSuperuser} />
          </div>
          <div className="flex items-center gap-2 self-end pb-1">
            <input type="checkbox" checked={autoApproveResearch} onChange={(e) => setAutoApproveResearch(e.target.checked)} disabled={!isSuperuser} className="w-3 h-3 accent-[var(--accent)]" />
            <span className="text-[11px] text-text-secondary">Auto-approve research</span>
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-[13px] font-semibold text-text-primary mb-3">Content Defaults</h3>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary block mb-1">Max Briefs</label>
            <Input type="number" value={maxBriefs} onChange={(e) => setMaxBriefs(e.target.value)} disabled={!isSuperuser} />
          </div>
          <div>
            <label className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary block mb-1">Max Revision Cycles</label>
            <Input type="number" value={maxRevisionCycles} onChange={(e) => setMaxRevisionCycles(e.target.value)} disabled={!isSuperuser} />
          </div>
          <div className="flex items-center gap-2">
            <input type="checkbox" checked={autoApproveContent} onChange={(e) => setAutoApproveContent(e.target.checked)} disabled={!isSuperuser} className="w-3 h-3 accent-[var(--accent)]" />
            <span className="text-[11px] text-text-secondary">Auto-approve content</span>
          </div>
        </div>
      </div>

      {isSuperuser && (
        <Button variant="primary" size="sm" onClick={handleSave} disabled={isUpdating}>
          {isUpdating ? 'Saving...' : 'Save Defaults'}
        </Button>
      )}

      {!isSuperuser && (
        <p className="text-[11px] text-text-tertiary">Only admins can edit pipeline defaults.</p>
      )}

      <Toast open={toast.open} onClose={() => setToast({ ...toast, open: false })} variant="success" message={toast.message} />
    </div>
  );
}
