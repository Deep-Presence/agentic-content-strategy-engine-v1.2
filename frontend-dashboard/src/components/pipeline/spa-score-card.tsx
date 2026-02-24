import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils/cn';
import { formatPercent } from '@/lib/utils/format';
import type { GapReport } from '@/types/gap-analysis';

interface SpaScoreCardProps {
  spa: GapReport['spa_score'];
  className?: string;
}

export function SpaScoreCard({ spa, className }: SpaScoreCardProps) {
  const citationPct = spa.citation_advantage;
  const companyPct = spa.company_advantage;

  return (
    <Card accent="ocean" className={className}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-caption font-sans font-semibold uppercase tracking-wide text-cream-700">
            SPA Score
          </span>
          <span className="font-serif text-heading-2 font-semibold text-cream-950">
            {spa.t_statistic.toFixed(4)}
          </span>
        </div>
        <div className="flex gap-1 h-2 rounded-full overflow-hidden mb-2">
          <div
            className="bg-ocean-400 rounded-l-full transition-all duration-500"
            style={{ width: `${citationPct * 100}%` }}
          />
          <div
            className="bg-sage-400 rounded-r-full transition-all duration-500"
            style={{ width: `${companyPct * 100}%` }}
          />
        </div>
        <div className="flex justify-between text-caption font-sans">
          <span className="text-ocean-500">
            Citation Advantage: {formatPercent(citationPct)}
          </span>
          <span className="text-sage-500">
            Company Advantage: {formatPercent(companyPct)}
          </span>
        </div>
        <div className="flex gap-4 mt-2 text-caption font-sans text-cream-600">
          <span>t-stat: {spa.t_statistic.toFixed(2)}</span>
          <span>p-value: {spa.p_value < 0.001 ? '< 0.001' : spa.p_value.toFixed(4)}</span>
        </div>
      </CardContent>
    </Card>
  );
}
