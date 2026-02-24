import { cn } from '@/lib/utils/cn';
import { Check, X } from 'lucide-react';

interface EvalDimension {
  label: string;
  score: number;
  threshold: number;
}

interface EvalScoresPanelProps {
  scores: EvalDimension[];
  className?: string;
}

const DEFAULT_DIMENSIONS: EvalDimension[] = [
  { label: 'Structural', score: 0, threshold: 0.8 },
  { label: 'Semantic Proximity', score: 0, threshold: 0.65 },
  { label: 'Style Alignment', score: 0, threshold: 0.7 },
  { label: 'Factual Grounding', score: 0, threshold: 0.7 },
];

export function EvalScoresPanel({ scores = DEFAULT_DIMENSIONS, className }: EvalScoresPanelProps) {
  return (
    <div className={cn('space-y-3', className)}>
      {scores.map((dim) => {
        const passed = dim.score >= dim.threshold;
        return (
          <div key={dim.label} className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-body-sm font-sans text-cream-800">{dim.label}</span>
              <div className="flex items-center gap-1.5">
                <span className={cn(
                  'text-body-sm font-sans tabular-nums font-medium',
                  passed ? 'text-sage-400' : 'text-error'
                )}>
                  {dim.score.toFixed(2)}
                </span>
                {passed ? (
                  <Check className="h-3.5 w-3.5 text-sage-400" />
                ) : (
                  <X className="h-3.5 w-3.5 text-error" />
                )}
              </div>
            </div>
            <div className="relative h-1.5 bg-cream-300 rounded-full overflow-hidden">
              <div
                className={cn(
                  'h-full rounded-full transition-all duration-300',
                  passed ? 'bg-sage-400' : 'bg-error'
                )}
                style={{ width: `${Math.min(100, dim.score * 100)}%` }}
              />
              <div
                className="absolute top-0 h-full w-px bg-cream-700"
                style={{ left: `${dim.threshold * 100}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
