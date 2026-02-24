'use client';

import { useState, useMemo } from 'react';
import { SignalInspector } from '@/components/charts/signal-inspector';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Select } from '@/components/ui/select';
import { cn } from '@/lib/utils/cn';
import type { CitationExemplar, ClusterSpec } from '@/types/gap-analysis';

interface SignalInspectorPanelProps {
  exemplars: CitationExemplar[];
  clusters: ClusterSpec[];
  className?: string;
}

function SignalInspectorPanel({ exemplars, clusters, className }: SignalInspectorPanelProps) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [sortBy, setSortBy] = useState<'similarity' | 'word_count'>('similarity');
  const [filterCluster, setFilterCluster] = useState('');

  const sortedExemplars = useMemo(() => {
    const sorted = [...exemplars].sort((a, b) => {
      if (sortBy === 'similarity') return b.similarity - a.similarity;
      return b.structural_signals.word_count - a.structural_signals.word_count;
    });
    return sorted;
  }, [exemplars, sortBy]);

  const selected = sortedExemplars[selectedIndex];

  const clusterAverages = useMemo(() => {
    if (exemplars.length === 0) return undefined;
    const signals = exemplars.map((e) => e.structural_signals);
    const count = signals.length;
    return {
      word_count: signals.reduce((s, sig) => s + sig.word_count, 0) / count,
      sentence_count: signals.reduce((s, sig) => s + sig.sentence_count, 0) / count,
      paragraph_count: signals.reduce((s, sig) => s + sig.paragraph_count, 0) / count,
      avg_paragraph_length: signals.reduce((s, sig) => s + sig.avg_paragraph_length, 0) / count,
      reading_level: signals.reduce((s, sig) => s + sig.reading_level, 0) / count,
      self_contained_ratio: signals.reduce((s, sig) => s + sig.self_contained_ratio, 0) / count,
      h1_count: signals.reduce((s, sig) => s + sig.h1_count, 0) / count,
      h2_count: signals.reduce((s, sig) => s + sig.h2_count, 0) / count,
      h3_count: signals.reduce((s, sig) => s + sig.h3_count, 0) / count,
      h4_count: signals.reduce((s, sig) => s + sig.h4_count, 0) / count,
      list_count: signals.reduce((s, sig) => s + sig.list_count, 0) / count,
      ordered_list_count: signals.reduce((s, sig) => s + sig.ordered_list_count, 0) / count,
      table_count: signals.reduce((s, sig) => s + sig.table_count, 0) / count,
      code_block_count: signals.reduce((s, sig) => s + sig.code_block_count, 0) / count,
      data_point_count: signals.reduce((s, sig) => s + sig.data_point_count, 0) / count,
      citation_density: signals.reduce((s, sig) => s + sig.citation_density, 0) / count,
      named_entity_density: signals.reduce((s, sig) => s + sig.named_entity_density, 0) / count,
    };
  }, [exemplars]);

  return (
    <div className={cn('grid grid-cols-1 lg:grid-cols-3 gap-6', className)}>
      {/* Left: Exemplar list */}
      <div className="space-y-3">
        <div className="flex items-end gap-2">
          <Select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as 'similarity' | 'word_count')}
            label="Sort by"
          >
            <option value="similarity">Similarity</option>
            <option value="word_count">Word Count</option>
          </Select>
        </div>

        <div className="space-y-1.5 max-h-[600px] overflow-y-auto">
          {sortedExemplars.map((exemplar, i) => (
            <button
              key={i}
              onClick={() => setSelectedIndex(i)}
              className={cn(
                'w-full text-left p-3 rounded-md border transition-colors',
                selectedIndex === i
                  ? 'bg-ocean-50 border-ocean-200'
                  : 'bg-white border-[var(--border-default)] hover:bg-cream-100',
              )}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-body-sm font-sans font-medium text-cream-900 truncate">
                  {exemplar.domain}
                </span>
                <span className="text-caption font-sans tabular-nums text-ocean-400 shrink-0 ml-2">
                  {exemplar.similarity.toFixed(2)}
                </span>
              </div>
              <p className="text-caption text-cream-600 line-clamp-2">
                {exemplar.snippet}
              </p>
              <div className="flex items-center gap-1.5 mt-1.5">
                <Badge variant="default">
                  {exemplar.content_type.replace(/_/g, ' ')}
                </Badge>
                <Badge variant="blue">
                  {exemplar.authority_type.replace(/_/g, ' ')}
                </Badge>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Right: Signal breakdown */}
      <div className="lg:col-span-2">
        {selected ? (
          <div className="space-y-4">
            <Card accent="ocean">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>{selected.domain}</CardTitle>
                  <span className="text-heading-3 font-sans font-semibold tabular-nums text-ocean-400">
                    {selected.similarity.toFixed(2)}
                  </span>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-body-sm text-cream-700">{selected.snippet}</p>
                <div className="flex items-center gap-2 mt-2">
                  <Badge variant="default">{selected.content_type.replace(/_/g, ' ')}</Badge>
                  <Badge variant="blue">{selected.authority_type.replace(/_/g, ' ')}</Badge>
                  <span className="text-caption text-cream-600 font-sans ml-auto">
                    {selected.structural_signals.word_count.toLocaleString()} words
                  </span>
                </div>
              </CardContent>
            </Card>

            <div>
              <h4 className="text-heading-4 font-serif font-semibold text-cream-950 mb-3">
                45-Signal Breakdown
              </h4>
              <SignalInspector
                signals={selected.structural_signals}
                clusterAverages={clusterAverages}
              />
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-64 text-body text-cream-600">
            Select an exemplar to view its signal breakdown
          </div>
        )}
      </div>
    </div>
  );
}

export { SignalInspectorPanel };
export type { SignalInspectorPanelProps };
