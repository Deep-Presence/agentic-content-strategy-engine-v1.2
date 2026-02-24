import { cn } from '@/lib/utils/cn';

interface CitabilityScoreBadgeProps {
  score: number;
  threshold?: number;
  size?: 'sm' | 'md' | 'lg';
  showBar?: boolean;
}

function getScoreConfig(score: number) {
  if (score < 50) return { color: 'text-error', bg: 'bg-error/10', barColor: 'bg-error', label: 'Low' };
  if (score < 70) return { color: 'text-warning', bg: 'bg-warning/10', barColor: 'bg-warning', label: 'Below threshold' };
  if (score < 85) return { color: 'text-sage-400', bg: 'bg-sage-50', barColor: 'bg-sage-400', label: 'Good' };
  return { color: 'text-sage-500', bg: 'bg-sage-50', barColor: 'bg-sage-500', label: 'Excellent' };
}

const sizeClasses = {
  sm: 'text-caption',
  md: 'text-body-sm',
  lg: 'text-body font-semibold',
} as const;

export function CitabilityScoreBadge({ score, size = 'md', showBar = false }: CitabilityScoreBadgeProps) {
  const config = getScoreConfig(score);

  return (
    <div className="flex items-center gap-2">
      <span className={cn('font-sans tabular-nums', sizeClasses[size], config.color)}>
        {score}%
      </span>
      {showBar && (
        <div className="flex-1 h-1.5 bg-cream-300 rounded-full overflow-hidden min-w-[60px]">
          <div
            className={cn('h-full rounded-full transition-all duration-300', config.barColor)}
            style={{ width: `${Math.min(100, score)}%` }}
          />
        </div>
      )}
    </div>
  );
}
