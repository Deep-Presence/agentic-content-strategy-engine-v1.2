'use client';

import { CheckCircle, Circle, Loader2, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import { GAP_ANALYSIS_STEPS } from '@/types/gap-analysis';
import type { GapAnalysisStep } from '@/types/gap-analysis';

type StepStatus = 'waiting' | 'active' | 'completed' | 'failed';

interface StepState {
  key: GapAnalysisStep;
  status: StepStatus;
  startedAt?: number;
  completedAt?: number;
}

interface PipelineProgressProps {
  steps: StepState[];
  compact?: boolean;
  className?: string;
}

function formatElapsed(startedAt?: number, completedAt?: number): string {
  if (!startedAt) return '';
  const end = completedAt || Date.now();
  const seconds = Math.floor((end - startedAt) / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}m ${remainingSeconds}s`;
}

const STATUS_ICON = {
  waiting: Circle,
  active: Loader2,
  completed: CheckCircle,
  failed: XCircle,
} as const;

const STATUS_STYLES = {
  waiting: 'text-cream-500',
  active: 'text-ocean-400 animate-spin',
  completed: 'text-sage-400',
  failed: 'text-error',
} as const;

const LINE_STYLES = {
  waiting: 'border-cream-400 border-dashed',
  active: 'border-ocean-400',
  completed: 'border-sage-400',
  failed: 'border-error',
} as const;

export function PipelineProgress({ steps, compact = false, className }: PipelineProgressProps) {
  const stepMeta = GAP_ANALYSIS_STEPS;

  return (
    <div className={cn('relative', className)}>
      {steps.map((step, index) => {
        const meta = stepMeta.find((m) => m.key === step.key);
        const Icon = STATUS_ICON[step.status];
        const isLast = index === steps.length - 1;

        return (
          <div key={step.key} className="flex gap-3">
            <div className="flex flex-col items-center">
              <div className={cn('relative z-10', STATUS_STYLES[step.status])}>
                <Icon className={cn(compact ? 'h-4 w-4' : 'h-5 w-5')} />
              </div>
              {!isLast && (
                <div
                  className={cn(
                    'w-0 flex-1 border-l-2 my-1',
                    LINE_STYLES[step.status === 'completed' ? 'completed' : steps[index + 1]?.status === 'active' ? 'active' : 'waiting']
                  )}
                />
              )}
            </div>
            <div className={cn('pb-4', compact ? 'pb-2' : 'pb-4')}>
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    'font-sans font-medium',
                    compact ? 'text-body-sm' : 'text-body',
                    step.status === 'completed' ? 'text-cream-800' : step.status === 'active' ? 'text-cream-950' : 'text-cream-600'
                  )}
                >
                  S{index + 1}: {meta?.label ?? step.key}
                </span>
                {step.startedAt && (
                  <span className="text-caption font-sans text-cream-600">
                    {formatElapsed(step.startedAt, step.completedAt)}
                  </span>
                )}
              </div>
              {!compact && meta?.description && (
                <p className="text-body-sm text-cream-600 mt-0.5">{meta.description}</p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
