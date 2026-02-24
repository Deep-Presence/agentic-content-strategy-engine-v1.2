'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Plus, X, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { useToast } from '@/components/ui/toast';
import { gapAnalysis } from '@/lib/api/gap-analysis';
import { GAP_ANALYSIS_STEPS } from '@/types/gap-analysis';

export function PipelineTriggerForm() {
  const router = useRouter();
  const { toast } = useToast();

  const [companyName, setCompanyName] = useState('');
  const [domain, setDomain] = useState('');
  const [seedUrls, setSeedUrls] = useState<string[]>(['']);
  const [skipSteps, setSkipSteps] = useState<number[]>([]);
  const [submitting, setSubmitting] = useState(false);

  function addSeedUrl() {
    setSeedUrls((prev) => [...prev, '']);
  }

  function removeSeedUrl(index: number) {
    setSeedUrls((prev) => prev.filter((_, i) => i !== index));
  }

  function updateSeedUrl(index: number, value: string) {
    setSeedUrls((prev) => prev.map((url, i) => (i === index ? value : url)));
  }

  function toggleSkipStep(stepIndex: number) {
    setSkipSteps((prev) =>
      prev.includes(stepIndex)
        ? prev.filter((s) => s !== stepIndex)
        : [...prev, stepIndex]
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!companyName.trim() || !domain.trim()) return;

    setSubmitting(true);
    try {
      const result = await gapAnalysis.start({
        input_data: {
          company_name: companyName.trim(),
          domain: domain.trim(),
          seed_urls: seedUrls.filter((u) => u.trim()),
        },
        skip_steps: skipSteps.length > 0 ? skipSteps : undefined,
      });
      toast('Pipeline started successfully', 'success');
      router.push(`/signal-analysis/${result.run_id}`);
    } catch (err) {
      if (err instanceof Error && err.message.includes('409')) {
        toast('Pipeline already running for this company. Check existing runs.', 'warning');
      } else {
        toast(err instanceof Error ? err.message : 'Failed to start pipeline', 'error');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <Card>
        <CardContent className="p-5 space-y-4">
          <Input
            label="Company Name"
            placeholder="e.g., Webflow"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            required
          />

          <Input
            label="Domain"
            placeholder="e.g., webflow.com"
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            required
          />

          <div className="space-y-2">
            <label className="block text-body-sm font-sans font-medium text-cream-800">
              Seed URLs
            </label>
            {seedUrls.map((url, index) => (
              <div key={index} className="flex gap-2">
                <Input
                  placeholder="https://example.com/page"
                  value={url}
                  onChange={(e) => updateSeedUrl(index, e.target.value)}
                  className="flex-1"
                />
                {seedUrls.length > 1 && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => removeSeedUrl(index)}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>
            ))}
            <Button type="button" variant="ghost" size="sm" onClick={addSeedUrl}>
              <Plus className="h-3.5 w-3.5" />
              Add URL
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-5">
          <label className="block text-body-sm font-sans font-medium text-cream-800 mb-3">
            Skip Steps (for re-running partial analyses)
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {GAP_ANALYSIS_STEPS.map((step, index) => (
              <label
                key={step.key}
                className="flex items-center gap-2 px-3 py-2 rounded-md hover:bg-cream-100 transition-colors cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={skipSteps.includes(index + 1)}
                  onChange={() => toggleSkipStep(index + 1)}
                  className="h-4 w-4 rounded border-cream-400 text-ocean-400 focus:ring-ocean-400/20"
                />
                <span className="text-body-sm font-sans text-cream-800">
                  S{index + 1}: {step.label}
                </span>
              </label>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center gap-3">
        <Button type="submit" disabled={submitting || !companyName.trim() || !domain.trim()}>
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Starting...
            </>
          ) : (
            'Start Analysis'
          )}
        </Button>
        <Button type="button" variant="ghost" onClick={() => router.back()}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
