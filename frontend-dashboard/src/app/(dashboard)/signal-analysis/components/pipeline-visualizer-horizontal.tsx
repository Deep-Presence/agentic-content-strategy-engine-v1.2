'use client';

import { Check } from 'lucide-react';
import { cn } from '@/lib/utils/cn';

interface PipelineStep {
  key: string;
  label: string;
  description: string;
  status: 'completed' | 'active' | 'waiting';
  duration?: string;
}

interface PipelineVisualizerHorizontalProps {
  steps: PipelineStep[];
}

export function PipelineVisualizerHorizontal({ steps }: PipelineVisualizerHorizontalProps) {
  return (
    <div className="w-full overflow-x-auto">
      <div className="flex items-start min-w-[720px] px-2 py-4">
        {steps.map((step, index) => {
          const isLast = index === steps.length - 1;
          const nextStep = !isLast ? steps[index + 1] : null;

          // Determine line style based on current and next step status
          const lineCompleted =
            step.status === 'completed' &&
            nextStep?.status === 'completed';
          const lineActive =
            step.status === 'completed' &&
            nextStep?.status === 'active';

          return (
            <div
              key={step.key}
              className="flex items-start flex-1 min-w-0"
            >
              {/* Step circle + label column */}
              <div className="flex flex-col items-center min-w-[80px]">
                {/* Circle */}
                <div
                  className={cn(
                    'relative flex items-center justify-center w-10 h-10 rounded-full border-2 text-sm font-sans font-semibold transition-all',
                    step.status === 'completed' &&
                      'bg-[#788c5d] border-[#788c5d] text-white',
                    step.status === 'active' &&
                      'bg-[#6a9bcc] border-[#6a9bcc] text-white animate-pulse',
                    step.status === 'waiting' &&
                      'bg-[#faf9f5] border-gray-300 text-gray-400'
                  )}
                  title={step.description}
                >
                  {step.status === 'completed' ? (
                    <Check className="w-5 h-5" strokeWidth={2.5} />
                  ) : (
                    <span>{index + 1}</span>
                  )}
                </div>

                {/* Label */}
                <span
                  className={cn(
                    'mt-2 text-xs font-sans text-center leading-tight max-w-[90px]',
                    step.status === 'completed' && 'text-[#141413] font-medium',
                    step.status === 'active' && 'text-[#6a9bcc] font-semibold',
                    step.status === 'waiting' && 'text-gray-400'
                  )}
                >
                  {step.label}
                </span>

                {/* Description */}
                <span
                  className={cn(
                    'mt-0.5 text-[10px] font-sans text-center leading-tight max-w-[100px]',
                    step.status === 'waiting' ? 'text-gray-300' : 'text-gray-500'
                  )}
                >
                  {step.description}
                </span>

                {/* Duration */}
                {step.duration && step.status === 'completed' && (
                  <span className="mt-1 text-[10px] font-sans font-medium text-[#788c5d]">
                    {step.duration}
                  </span>
                )}
              </div>

              {/* Connecting line */}
              {!isLast && (
                <div className="flex-1 flex items-center pt-[18px] px-1 min-w-[16px]">
                  <div
                    className={cn(
                      'w-full h-0.5',
                      lineCompleted || lineActive
                        ? 'bg-[#788c5d]'
                        : 'border-t-2 border-dashed border-gray-300 h-0'
                    )}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
