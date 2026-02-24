'use client';

import { ClusterBoxplot } from '@/components/charts/cluster-boxplot';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { cn } from '@/lib/utils/cn';
import type { ClusterComparison } from '@/components/charts/cluster-boxplot';

interface ClusterBoxplotChartProps {
  data: ClusterComparison[];
  className?: string;
}

function ClusterBoxplotChart({ data, className }: ClusterBoxplotChartProps) {
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Similarity Distribution by Cluster</CardTitle>
        <CardDescription>
          Compare company content similarity vs citation similarity across all clusters
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ClusterBoxplot data={data} height={380} />
      </CardContent>
    </Card>
  );
}

export { ClusterBoxplotChart };
export type { ClusterBoxplotChartProps };
