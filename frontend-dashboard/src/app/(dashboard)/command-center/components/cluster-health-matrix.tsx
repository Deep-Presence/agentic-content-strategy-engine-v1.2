'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface ClusterItem {
  id: string;
  name: string;
  queries: number;
  citations: number;
  avg_word_count: number;
  faq_rate: number;
  table_rate: number;
  citations_rate: number;
}

interface ClusterHealthMatrixProps {
  clusters: ClusterItem[];
}

function RadialRing({ value, size = 40, color }: { value: number; size?: number; color: string }) {
  const r = (size - 8) / 2;
  const circumference = 2 * Math.PI * r;
  const offset = circumference * (1 - value);
  const center = size / 2;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle
        cx={center}
        cy={center}
        r={r}
        fill="none"
        stroke="#efeee8"
        strokeWidth="3"
      />
      <circle
        cx={center}
        cy={center}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth="3"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform={`rotate(-90 ${center} ${center})`}
        style={{ transition: 'stroke-dashoffset 0.8s ease-out' }}
      />
      <text
        x={center}
        y={center}
        textAnchor="middle"
        dominantBaseline="central"
        fontSize="9"
        fontFamily="ui-sans-serif, sans-serif"
        fontWeight="600"
        fill="var(--text-secondary)"
      >
        {Math.round(value * 100)}%
      </text>
    </svg>
  );
}

function rateColor(rate: number): string {
  if (rate >= 0.95) return '#788c5d';
  if (rate >= 0.80) return '#6a9bcc';
  return '#e8926d';
}

function ClusterCard({ cluster, index }: { cluster: ClusterItem; index: number }) {
  return (
    <Card
      hoverable
      className="animate-fade-in-up cursor-pointer"
      style={{ animationDelay: `${0.25 + index * 0.04}s` }}
    >
      <CardContent className="p-3">
        <div className="flex items-start justify-between mb-2">
          <div className="min-w-0">
            <Badge variant="default" className="mb-1">{cluster.id}</Badge>
            <p className="text-body-sm font-sans font-semibold text-cream-950 truncate">
              {cluster.name}
            </p>
          </div>
          <RadialRing value={cluster.citations_rate} color={rateColor(cluster.citations_rate)} />
        </div>

        <div className="flex items-center gap-3 mt-2">
          <div>
            <p className="text-micro font-sans text-cream-600">{cluster.citations} cit.</p>
          </div>
          <div>
            <p className="text-micro font-sans text-cream-600">FAQ {Math.round(cluster.faq_rate * 100)}%</p>
          </div>
          <div>
            <p className="text-micro font-sans text-cream-600">Tbl {Math.round(cluster.table_rate * 100)}%</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function ClusterHealthMatrix({ clusters }: ClusterHealthMatrixProps) {
  return (
    <div>
      <h3 className="font-serif text-heading-3 font-semibold text-cream-950 mb-3 animate-fade-in-up" style={{ animationDelay: '0.25s' }}>
        Cluster Health Matrix
      </h3>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-9 gap-3">
        {clusters.map((c, i) => (
          <ClusterCard key={c.id} cluster={c} index={i} />
        ))}
      </div>
    </div>
  );
}
