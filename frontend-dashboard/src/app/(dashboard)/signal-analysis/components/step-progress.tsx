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

interface StepProgressProps {
  steps: StepState[];
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

const STATUS_CONFIG = {
  waiting: {
    icon: Circle,
    iconClass: 'text-cream-500',
    labelClass: 'text-cream-600',
    descClass: 'text-cream-500',
    bgClass: 'bg-cream-200',
    borderClass: 'border-cream-200',
    label: 'Waiting',
  },
  active: {
    icon: Loader2,
    iconClass: 'text-ocean-400 animate-spin',
    labelClass: 'text-cream-950 font-semibold',
    descClass: 'text-cream-700',
    bgClass: 'bg-ocean-50',
    borderClass: 'border-ocean-200',
    label: 'In Progress',
  },
  completed: {
    icon: CheckCircle,
    iconClass: 'text-sage-400',
    labelClass: 'text-cream-800',
    descClass: 'text-cream-600',
    bgClass: 'bg-sage-50',
    borderClass: 'border-sage-200',
    label: 'Completed',
  },
  failed: {
    icon: XCircle,
    iconClass: 'text-error',
    labelClass: 'text-error',
    descClass: 'text-error/70',
    bgClass: 'bg-error/5',
    borderClass: 'border-error/20',
    label: 'Failed',
  },
} as const;

export function StepProgress({ steps, className }: StepProgressProps) {
  const stepMeta = GAP_ANALYSIS_STEPS;

  return (
    <div className={cn('space-y-0', className)}>
      {steps.map((step, index) => {
        const meta = stepMeta.find((m) => m.key === step.key);
        const config = STATUS_CONFIG[step.status];
        const Icon = config.icon;
        const isLast = index === steps.length - 1;
        const elapsed = formatElapsed(step.startedAt, step.completedAt);

        return (
          <div key={step.key} className="flex">
            {/* Vertical line + icon column */}
            <div className="flex flex-col items-center w-10 shrink-0">
              <div
                className={cn(
                  'flex items-center justify-center w-8 h-8 rounded-full border-2 z-10 transition-all duration-300',
                  config.bgClass,
                  config.borderClass
                )}
              >
                <Icon className={cn('h-4 w-4', config.iconClass)} />
              </div>
              {!isLast && (
                <div
                  className={cn(
                    'w-0.5 flex-1 transition-colors duration-300',
                    step.status === 'completed' ? 'bg-sage-400' : 'bg-cream-300'
                  )}
                />
              )}
            </div>

            {/* Step content */}
            <div className={cn('flex-1 pb-6 pl-3', isLast && 'pb-0')}>
              <div
                className={cn(
                  'rounded-md border p-3 transition-all duration-300',
                  step.status === 'active'
                    ? 'border-ocean-200 bg-ocean-50/50 shadow-sm'
                    : 'border-transparent bg-transparent'
                )}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-caption font-sans font-semibold text-ocean-500">
                      S{index + 1}
                    </span>
                    <span className={cn('text-body font-sans font-medium', config.labelClass)}>
                      {meta?.label ?? step.key}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {elapsed && (
                      <span className="text-caption font-sans text-cream-600">{elapsed}</span>
                    )}
                    <span
                      className={cn(
                        'text-micro font-sans px-1.5 py-0.5 rounded',
                        step.status === 'completed' && 'bg-sage-50 text-sage-500',
                        step.status === 'active' && 'bg-ocean-50 text-ocean-500',
                        step.status === 'failed' && 'bg-error/10 text-error',
                        step.status === 'waiting' && 'bg-cream-200 text-cream-600'
                      )}
                    >
                      {config.label}
                    </span>
                  </div>
                </div>
                {meta?.description && (
                  <p className={cn('text-body-sm mt-1', config.descClass)}>
                    {meta.description}
                  </p>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
