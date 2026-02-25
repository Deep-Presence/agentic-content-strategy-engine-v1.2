'use client';

import { useState } from 'react';
import { FlaskConical, Plus, X, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useToast } from '@/components/ui/toast';
import { research } from '@/lib/api/research';
import { useBrandStore } from '@/stores/brand-store';
import { ApiError } from '@/lib/api/client';
import { cn } from '@/lib/utils/cn';

type ResearchMode = 'full' | 'company' | 'persona' | 'style_guide';

interface ResearchTriggerProps {
  mode: ResearchMode;
  companySlug: string;
  companyName?: string;
  domain?: string;
  onStarted?: (runId: string) => void;
  className?: string;
}

const MODE_LABELS: Record<ResearchMode, string> = {
  full: 'Run Full Research',
  company: 'Generate Company Context',
  persona: 'Generate Personas',
  style_guide: 'Generate Style Guide',
};

const MODE_STAGES: Record<ResearchMode, ('company' | 'persona' | 'style_guide')[]> = {
  full: ['company', 'persona', 'style_guide'],
  company: ['company'],
  persona: ['persona'],
  style_guide: ['style_guide'],
};

export function ResearchTrigger({
  mode,
  companySlug,
  companyName: initialName,
  domain: initialDomain,
  onStarted,
  className,
}: ResearchTriggerProps) {
  const [expanded, setExpanded] = useState(false);
  const [companyName, setCompanyName] = useState(initialName ?? '');
  const [domain, setDomain] = useState(initialDomain ?? '');
  const [seedUrls, setSeedUrls] = useState<string[]>(['']);
  const [maxPersonas, setMaxPersonas] = useState(3);
  const [autoApprove, setAutoApprove] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const { toast } = useToast();
  const setResearchRun = useBrandStore((s) => s.setResearchRun);

  const addSeedUrl = () => setSeedUrls((prev) => [...prev, '']);
  const removeSeedUrl = (index: number) =>
    setSeedUrls((prev) => prev.filter((_, i) => i !== index));
  const updateSeedUrl = (index: number, value: string) =>
    setSeedUrls((prev) => prev.map((url, i) => (i === index ? value : url)));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!companyName.trim() || !domain.trim()) return;

    setSubmitting(true);
    try {
      const result = await research.start({
        company_name: companyName.trim(),
        domain: domain.trim(),
        seed_urls: seedUrls.filter((u) => u.trim()),
        stages: MODE_STAGES[mode],
        max_personas: maxPersonas,
        auto_approve: autoApprove,
      });

      setResearchRun(result.run_id, 'running', MODE_STAGES[mode][0] === 'company' ? 'company' : MODE_STAGES[mode][0] === 'persona' ? 'persona' : 'style_guide');
      toast('Research pipeline started', 'success');
      setExpanded(false);
      onStarted?.(result.run_id);
    } catch (err) {
      if (err instanceof ApiError && err.code === 'task_conflict') {
        toast('A research pipeline is already running for this company', 'warning');
      } else {
        toast('Failed to start research pipeline', 'error');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={cn('', className)}>
      {!expanded ? (
        <Button onClick={() => setExpanded(true)} size="sm">
          <FlaskConical className="h-4 w-4 mr-2" />
          {MODE_LABELS[mode]}
        </Button>
      ) : (
        <div className="bg-white rounded-md border border-[var(--border-default)] shadow-[var(--shadow-sm)]">
          <div className="flex items-center justify-between p-4 border-b border-[var(--border-subtle)]">
            <div className="flex items-center gap-2">
              <FlaskConical className="h-4 w-4 text-terracotta-400" />
              <h4 className="font-sans text-heading-4 font-semibold text-cream-950">
                {MODE_LABELS[mode]}
              </h4>
            </div>
            <button
              onClick={() => setExpanded(false)}
              className="p-1 hover:bg-cream-200 rounded transition-colors"
            >
              <X className="h-4 w-4 text-cream-600" />
            </button>
          </div>
          <form onSubmit={handleSubmit} className="p-4 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <Input
                label="Company Name"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="e.g., Webflow"
                required
              />
              <Input
                label="Domain"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                placeholder="e.g., webflow.com"
                required
              />
            </div>

            <div>
              <label className="block text-body-sm font-sans font-medium text-cream-800 mb-1.5">
                Seed URLs (optional)
              </label>
              <div className="space-y-2">
                {seedUrls.map((url, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <input
                      value={url}
                      onChange={(e) => updateSeedUrl(i, e.target.value)}
                      placeholder="https://..."
                      className="flex-1 px-3 py-1.5 bg-white border border-[var(--border-default)] rounded-md font-sans text-body-sm text-cream-900 placeholder:text-cream-600 focus:outline-none focus:ring-2 focus:ring-terracotta-400/20 focus:border-terracotta-400"
                    />
                    {seedUrls.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeSeedUrl(i)}
                        className="p-1 hover:bg-cream-200 rounded transition-colors"
                      >
                        <X className="h-3.5 w-3.5 text-cream-600" />
                      </button>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  onClick={addSeedUrl}
                  className="flex items-center gap-1 text-caption font-sans text-terracotta-400 hover:text-terracotta-500 transition-colors"
                >
                  <Plus className="h-3 w-3" />
                  Add URL
                </button>
              </div>
            </div>

            <div className="flex items-center gap-6">
              {mode === 'full' || mode === 'persona' ? (
                <div className="flex items-center gap-2">
                  <label className="text-body-sm font-sans font-medium text-cream-800">
                    Max Personas:
                  </label>
                  <input
                    type="number"
                    min={1}
                    max={10}
                    value={maxPersonas}
                    onChange={(e) => setMaxPersonas(parseInt(e.target.value) || 3)}
                    className="w-16 px-2 py-1 bg-white border border-[var(--border-default)] rounded-md font-sans text-body-sm text-cream-900 text-center focus:outline-none focus:ring-2 focus:ring-terracotta-400/20 focus:border-terracotta-400"
                  />
                </div>
              ) : null}
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoApprove}
                  onChange={(e) => setAutoApprove(e.target.checked)}
                  className="h-4 w-4 rounded border-cream-400 text-terracotta-400 focus:ring-terracotta-400/20"
                />
                <span className="text-body-sm font-sans text-cream-800">
                  Auto-approve drafts
                </span>
              </label>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-[var(--border-subtle)]">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setExpanded(false)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={!companyName.trim() || !domain.trim() || submitting}
              >
                {submitting ? 'Starting...' : 'Start Pipeline'}
              </Button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
