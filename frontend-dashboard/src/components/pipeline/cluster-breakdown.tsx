import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils/cn';
import { formatPercent } from '@/lib/utils/format';
import type { ClusterSpec } from '@/types/gap-analysis';

interface ClusterBreakdownProps {
  clusters: ClusterSpec[];
  onClusterClick?: (clusterId: string) => void;
  selectedCluster?: string | null;
  className?: string;
}

export function ClusterBreakdown({ clusters, onClusterClick, selectedCluster, className }: ClusterBreakdownProps) {
  return (
    <div className={cn('grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4', className)}>
      {clusters.map((cluster) => {
        const isSelected = selectedCluster === cluster.cluster_id;
        return (
          <Card
            key={cluster.cluster_id}
            hoverable
            accent={isSelected ? 'ocean' : 'none'}
            className={cn(
              'cursor-pointer transition-all',
              isSelected && 'ring-2 ring-ocean-400/30'
            )}
            onClick={() => onClusterClick?.(cluster.cluster_id)}
          >
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-serif text-heading-4 font-semibold text-cream-950 truncate">
                  {cluster.cluster_name}
                </h4>
                <Badge variant="blue">{cluster.cluster_id}</Badge>
              </div>
              <div className="flex items-center gap-3 text-caption font-sans text-cream-600 mb-3">
                <span>{cluster.query_count} queries</span>
                <span>{cluster.citations_analyzed} citations</span>
              </div>
              <div className="space-y-1.5 mb-3">
                {Object.entries(cluster.structural_rates).map(([key, value]) => (
                  <div key={key} className="flex items-center gap-2">
                    <span className="text-micro font-sans text-cream-600 w-16 capitalize">{key}</span>
                    <div className="flex-1 h-1.5 bg-cream-300 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-ocean-400 rounded-full transition-all duration-300"
                        style={{ width: `${Math.min(value * 100, 100)}%` }}
                      />
                    </div>
                    <span className="text-micro font-sans text-cream-700 w-8 text-right">
                      {formatPercent(value)}
                    </span>
                  </div>
                ))}
              </div>
              <div className="flex flex-wrap gap-1">
                <Badge variant="default">{cluster.dominant_content_type}</Badge>
                <Badge variant="default">{cluster.dominant_authority_type}</Badge>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
