'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils/cn';
import type { ClusterSpec } from '@/types/gap-analysis';

interface ClusterCardProps {
  cluster: ClusterSpec;
  isSelected?: boolean;
  onClick?: () => void;
  className?: string;
}

const BAR_COLORS = {
  headers: 'bg-ocean-400',
  lists: 'bg-ocean-300',
  stats: 'bg-sage-400',
  citations: 'bg-terracotta-300',
} as const;

const BAR_LABELS = {
  headers: 'Headers',
  lists: 'Lists',
  stats: 'Stats',
  citations: 'Citations',
} as const;

export function ClusterCard({ cluster, isSelected = false, onClick, className }: ClusterCardProps) {
  const faqPct = Math.round(cluster.faq_rate * 100);
  const tablePct = Math.round(cluster.table_rate * 100);

  return (
    <Card
      hoverable
      accent={isSelected ? 'ocean' : 'none'}
      className={cn(
        'cursor-pointer transition-all',
        isSelected && 'ring-2 ring-ocean-400/30',
        className
      )}
      onClick={onClick}
    >
      <CardContent className="p-4">
        {/* Header */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <h4 className="font-serif text-heading-4 font-semibold text-cream-950 leading-tight">
            {cluster.cluster_name}
          </h4>
          <Badge variant="blue" className="shrink-0">{cluster.cluster_id}</Badge>
        </div>

        {/* Meta row */}
        <div className="flex items-center gap-3 text-caption font-sans text-cream-600 mb-3">
          <span>{cluster.query_count} queries</span>
          <span className="text-cream-400">|</span>
          <span>{cluster.citations_analyzed} citations</span>
          <span className="text-cream-400">|</span>
          <span>~{cluster.avg_word_count.toLocaleString()} words</span>
        </div>

        {/* Featured rates: FAQ + Table */}
        <div className="flex items-center gap-3 mb-3">
          <div className={cn(
            'flex items-center gap-1.5 px-2 py-1 rounded-md text-caption font-sans',
            faqPct > 30 ? 'bg-ocean-100 text-ocean-600' : 'bg-cream-200 text-cream-700'
          )}>
            <span className="font-semibold">{faqPct}%</span>
            <span>FAQ</span>
          </div>
          <div className={cn(
            'flex items-center gap-1.5 px-2 py-1 rounded-md text-caption font-sans',
            tablePct > 30 ? 'bg-ocean-100 text-ocean-600' : 'bg-cream-200 text-cream-700'
          )}>
            <span className="font-semibold">{tablePct}%</span>
            <span>Tables</span>
          </div>
          <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-cream-200 text-cream-700 text-caption font-sans">
            <span className="font-semibold">{Math.round(cluster.key_takeaways_rate * 100)}%</span>
            <span>Takeaways</span>
          </div>
        </div>

        {/* Structural rate bars */}
        <div className="space-y-1.5 mb-3">
          {(Object.keys(cluster.structural_rates) as Array<keyof typeof cluster.structural_rates>).map((key) => {
            const value = cluster.structural_rates[key];
            return (
              <RateBar
                key={key}
                label={BAR_LABELS[key]}
                value={value}
                colorClass={BAR_COLORS[key]}
              />
            );
          })}
        </div>

        {/* Footer badges */}
        <div className="flex flex-wrap gap-1 pt-2 border-t border-cream-300">
          <Badge variant="default">{cluster.dominant_content_type}</Badge>
          <Badge variant="default">{cluster.dominant_authority_type}</Badge>
        </div>
      </CardContent>
    </Card>
  );
}

interface RateBarProps {
  label: string;
  value: number;
  colorClass: string;
}

function RateBar({ label, value, colorClass }: RateBarProps) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2">
      <span className="text-micro font-sans text-cream-600 w-16 truncate">{label}</span>
      <div className="flex-1 h-2 bg-cream-200 rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all duration-500', colorClass)}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className="text-micro font-sans text-cream-700 w-9 text-right tabular-nums font-medium">
        {pct}%
      </span>
    </div>
  );
}
