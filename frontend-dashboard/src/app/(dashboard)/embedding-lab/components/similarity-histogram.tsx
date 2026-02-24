'use client';

import { SimilarityHistogram as SimilarityHistogramChart } from '@/components/charts/similarity-histogram';
import { ClusterBoxplot } from '@/components/charts/cluster-boxplot';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { cn } from '@/lib/utils/cn';
import type { HistogramBin } from '@/components/charts/similarity-histogram';
import type { ClusterComparison } from '@/components/charts/cluster-boxplot';

interface SimilarityHistogramPanelProps {
  histogramData: HistogramBin[];
  comparisonData: ClusterComparison[];
  className?: string;
}

function SimilarityHistogramPanel({
  histogramData,
  comparisonData,
  className,
}: SimilarityHistogramPanelProps) {
  const totalCitations = histogramData.reduce((s, b) => s + b.count, 0);
  const median = (() => {
    let cumulative = 0;
    const half = totalCitations / 2;
    for (const bin of histogramData) {
      cumulative += bin.count;
      if (cumulative >= half) return bin.range;
    }
    return histogramData[histogramData.length - 1]?.range || '—';
  })();

  return (
    <div className={cn('grid grid-cols-1 lg:grid-cols-2 gap-6', className)}>
      <Card>
        <CardHeader>
          <CardTitle>Similarity Score Distribution</CardTitle>
          <CardDescription>
            Distribution of citation similarity scores across {totalCitations} citations.
            Median range: {median}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SimilarityHistogramChart data={histogramData} height={320} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Company vs Citation by Cluster</CardTitle>
          <CardDescription>
            Comparison of average similarity scores between company content and citation content per cluster
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ClusterBoxplot data={comparisonData} height={320} />
        </CardContent>
      </Card>
    </div>
  );
}

export { SimilarityHistogramPanel };
export type { SimilarityHistogramPanelProps };
