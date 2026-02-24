'use client';

import { useState } from 'react';
import { Zap, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/toast';
import { useAppStore } from '@/stores/app-store';
import { content } from '@/lib/api/content';
import { ApiError } from '@/lib/api/client';
import { cn } from '@/lib/utils/cn';

interface PipelineTriggerBarProps {
  open: boolean;
  onClose: () => void;
  className?: string;
}

export function PipelineTriggerBar({ open, onClose, className }: PipelineTriggerBarProps) {
  const { currentCompany } = useAppStore();
  const { toast } = useToast();
  const [maxBriefs, setMaxBriefs] = useState(10);
  const [maxWorkers, setMaxWorkers] = useState(3);
  const [autoApprove, setAutoApprove] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit() {
    if (!currentCompany) {
      toast('No company selected', 'warning');
      return;
    }

    setLoading(true);
    try {
      await content.start({
        company_name: currentCompany,
        domain: `${currentCompany}.com`,
        gap_slug: currentCompany,
        max_briefs: maxBriefs,
        max_concurrent_workers: maxWorkers,
        auto_approve: autoApprove,
      });
      toast('Content generation started', 'success');
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.code === 'task_conflict') {
        toast('Pipeline already running for this company', 'warning');
      } else {
        toast('Failed to start content generation', 'error');
      }
    } finally {
      setLoading(false);
    }
  }

  if (!open) return null;

  return (
    <div className={cn(
      'fixed inset-y-0 right-0 w-[400px] bg-white shadow-xl border-l border-[var(--border-default)] z-40',
      'animate-in slide-in-from-right',
      className
    )}>
      <div className="flex flex-col h-full">
        <div className="flex items-center justify-between p-5 border-b border-[var(--border-default)]">
          <div className="flex items-center gap-2">
            <Zap className="h-5 w-5 text-sage-400" />
            <h2 className="font-serif text-heading-3 text-cream-950">Generate from Gaps</h2>
          </div>
          <button onClick={onClose} className="p-1 rounded hover:bg-cream-200 text-cream-600">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          <div className="space-y-1.5">
            <label className="text-body-sm font-sans font-medium text-cream-800">Company</label>
            <div className="px-3 py-2 text-body font-sans bg-cream-100 border border-[var(--border-default)] rounded-md text-cream-800">
              {currentCompany || 'No company selected'}
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-body-sm font-sans font-medium text-cream-800">Max Briefs</label>
            <input
              type="number"
              value={maxBriefs}
              onChange={(e) => setMaxBriefs(Number(e.target.value))}
              min={1}
              max={50}
              className="w-full px-3 py-2 text-body font-sans bg-white border border-[var(--border-default)] rounded-md text-cream-800 focus:border-sage-400 focus:ring-2 focus:ring-sage-400/20 outline-none tabular-nums"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-body-sm font-sans font-medium text-cream-800">Max Workers</label>
            <input
              type="number"
              value={maxWorkers}
              onChange={(e) => setMaxWorkers(Number(e.target.value))}
              min={1}
              max={10}
              className="w-full px-3 py-2 text-body font-sans bg-white border border-[var(--border-default)] rounded-md text-cream-800 focus:border-sage-400 focus:ring-2 focus:ring-sage-400/20 outline-none tabular-nums"
            />
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="auto-approve"
              checked={autoApprove}
              onChange={(e) => setAutoApprove(e.target.checked)}
              className="h-4 w-4 rounded border-cream-400 text-sage-400 focus:ring-sage-400/20"
            />
            <label htmlFor="auto-approve" className="text-body-sm font-sans text-cream-800">
              Auto-approve generated content
            </label>
          </div>
        </div>

        <div className="p-5 border-t border-[var(--border-default)] flex items-center gap-3">
          <Button variant="secondary" onClick={onClose} className="flex-1">
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={loading || !currentCompany}
            className="flex-1 bg-sage-400 hover:bg-sage-500"
          >
            {loading ? 'Starting...' : 'Generate Content'}
          </Button>
        </div>
      </div>
    </div>
  );
}
