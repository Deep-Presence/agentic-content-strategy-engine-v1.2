'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils/cn';
import { formatPercent } from '@/lib/utils/format';
import type { ClusterSpec } from '@/types/gap-analysis';

interface ClusterCardProps {
  cluster: ClusterSpec;
  isSelected?: boolean;
  onClick?: () => void;
  className?: string;
}

export function ClusterCard({ cluster, isSelected = false, onClick, className }: ClusterCardProps) {
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
        <div className="flex items-start justify-between gap-2 mb-3">
          <h4 className="font-serif text-heading-4 font-semibold text-cream-950 leading-tight">
            {cluster.cluster_name}
          </h4>
          <Badge variant="blue" className="shrink-0">{cluster.cluster_id}</Badge>
        </div>

        <div className="flex items-center gap-3 text-caption font-sans text-cream-600 mb-3">
          <span>{cluster.query_count} queries</span>
          <span className="text-cream-400">|</span>
          <span>Avg {cluster.avg_word_count.toLocaleString()} words</span>
        </div>

        {/* Structural rates mini bars */}
        <div className="space-y-1.5 mb-3">
          <RateBar label="FAQ" value={cluster.faq_rate} />
          <RateBar label="Tables" value={cluster.table_rate} />
          <RateBar label="Takeaways" value={cluster.key_takeaways_rate} />
          <RateBar label="Headers" value={cluster.structural_rates.headers} />
        </div>

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
}

function RateBar({ label, value }: RateBarProps) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-micro font-sans text-cream-600 w-16 truncate">{label}</span>
      <div className="flex-1 h-1.5 bg-cream-300 rounded-full overflow-hidden">
        <div
          className="h-full bg-ocean-400 rounded-full transition-all duration-300"
          style={{ width: `${Math.min(value * 100, 100)}%` }}
        />
      </div>
      <span className="text-micro font-sans text-cream-700 w-8 text-right tabular-nums">
        {formatPercent(value)}
      </span>
    </div>
  );
}
