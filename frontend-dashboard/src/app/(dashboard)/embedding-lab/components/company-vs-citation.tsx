'use client';

import { CompanyVsCitation as CompanyVsCitationChart } from '@/components/charts/company-vs-citation';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { cn } from '@/lib/utils/cn';
import type { ComparisonDataPoint } from '@/components/charts/company-vs-citation';

interface CompanyVsCitationPanelProps {
  data: ComparisonDataPoint[];
  className?: string;
}

function CompanyVsCitationPanel({ data, className }: CompanyVsCitationPanelProps) {
  const avgGap =
    data.reduce((s, d) => s + (d.citationSimilarity - d.companySimilarity), 0) / data.length;
  const biggestGapCluster = data.reduce((max, d) =>
    d.citationSimilarity - d.companySimilarity > max.citationSimilarity - max.companySimilarity
      ? d
      : max,
  );

  return (
    <div className={cn('space-y-6', className)}>
      {/* Summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-caption font-sans text-cream-600 uppercase tracking-wide">
              Avg Citation Advantage
            </div>
            <div className="text-heading-2 font-sans font-semibold tabular-nums text-terracotta-400 mt-1">
              {avgGap > 0 ? '+' : ''}{avgGap.toFixed(3)}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-caption font-sans text-cream-600 uppercase tracking-wide">
              Biggest Gap
            </div>
            <div className="text-heading-3 font-sans font-semibold text-cream-950 mt-1">
              {biggestGapCluster.cluster}
            </div>
            <div className="text-caption font-sans text-terracotta-400 tabular-nums">
              +{(biggestGapCluster.citationSimilarity - biggestGapCluster.companySimilarity).toFixed(3)}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-caption font-sans text-cream-600 uppercase tracking-wide">
              Clusters Analyzed
            </div>
            <div className="text-heading-2 font-sans font-semibold tabular-nums text-cream-950 mt-1">
              {data.length}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Citation vs Company Similarity Gap</CardTitle>
          <CardDescription>
            Positive values indicate citations outperform company content. Negative values indicate company content advantage.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <CompanyVsCitationChart data={data} height={380} />
        </CardContent>
      </Card>
    </div>
  );
}

export { CompanyVsCitationPanel };
export type { CompanyVsCitationPanelProps };
