'use client';

import { useState } from 'react';
import { CitationTreemap } from '@/components/charts/citation-treemap';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import type { DomainCitation } from '../data/webflow-sample';

interface CitationTreemapChartProps {
  data: DomainCitation[];
  className?: string;
}

function CitationTreemapChart({ data, className }: CitationTreemapChartProps) {
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);

  const selectedInfo = selectedDomain ? data.find((d) => d.domain === selectedDomain) : null;

  return (
    <div className={cn('space-y-4', className)}>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Citation Domain Distribution</CardTitle>
            {selectedDomain && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedDomain(null)}
              >
                <X className="h-3.5 w-3.5 mr-1" />
                Clear filter
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <CitationTreemap
            data={data}
            onDomainClick={(domain) => setSelectedDomain(domain === selectedDomain ? null : domain)}
            width={700}
            height={380}
          />
        </CardContent>
      </Card>

      {selectedInfo && (
        <Card accent="ocean">
          <CardHeader>
            <CardTitle>{selectedInfo.domain}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-caption font-sans text-cream-600 uppercase tracking-wide">Citations</div>
                <div className="text-heading-3 font-sans font-semibold text-cream-950 tabular-nums">{selectedInfo.count}</div>
              </div>
              <div>
                <div className="text-caption font-sans text-cream-600 uppercase tracking-wide">Avg Similarity</div>
                <div className="text-heading-3 font-sans font-semibold text-ocean-400 tabular-nums">
                  {selectedInfo.avgSimilarity.toFixed(2)}
                </div>
              </div>
              <div>
                <div className="text-caption font-sans text-cream-600 uppercase tracking-wide">Authority Type</div>
                <Badge variant="blue" className="mt-1">
                  {selectedInfo.authorityType.replace(/_/g, ' ')}
                </Badge>
              </div>
              <div>
                <div className="text-caption font-sans text-cream-600 uppercase tracking-wide">Share</div>
                <div className="text-heading-3 font-sans font-semibold text-cream-950 tabular-nums">
                  {((selectedInfo.count / data.reduce((s, d) => s + d.count, 0)) * 100).toFixed(1)}%
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Domain list */}
      <Card>
        <CardHeader>
          <CardTitle>All Domains</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="divide-y divide-[var(--border-subtle)]">
            {data.map((item) => (
              <button
                key={item.domain}
                onClick={() => setSelectedDomain(item.domain === selectedDomain ? null : item.domain)}
                className={cn(
                  'w-full flex items-center justify-between px-4 py-2.5 text-left transition-colors hover:bg-cream-100',
                  selectedDomain === item.domain && 'bg-ocean-50',
                )}
              >
                <div className="flex items-center gap-2">
                  <span className="text-body-sm font-sans font-medium text-cream-900">
                    {item.domain}
                  </span>
                  <Badge variant="default">{item.authorityType.replace(/_/g, ' ')}</Badge>
                </div>
                <div className="flex items-center gap-4 text-body-sm font-sans tabular-nums">
                  <span className="text-cream-700">{item.count} citations</span>
                  <span className="text-ocean-400">{item.avgSimilarity.toFixed(2)}</span>
                </div>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export { CitationTreemapChart };
export type { CitationTreemapChartProps };
