'use client';

import { useState, useMemo } from 'react';
import { FilterBar, Toast } from '@/components/ui';
import { LayoutGrid, List } from 'lucide-react';
import type { Query } from '@/types';
import type { EnrichedTopic } from '@/data/topics';
import type { EnrichedQuery } from '@/data/gap-report';
import { TopicCard } from './TopicCard';
import { TopicDetailPanel } from './TopicDetailPanel';

interface DiscoverTabProps {
  topics: EnrichedTopic[];
  queries: Query[];
  enrichedQueries: EnrichedQuery[];
}

type SortMode = 'impact' | 'gap' | 'alpha';

export function DiscoverTab({ topics, queries, enrichedQueries }: DiscoverTabProps) {
  const [selectedTopic, setSelectedTopic] = useState<EnrichedTopic | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkMode, setBulkMode] = useState(false);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [toastOpen, setToastOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [sortMode, setSortMode] = useState<SortMode>('impact');
  const [filters, setFilters] = useState({
    persona: 'all',
    coverage: 'all',
    priority: 'all',
    cluster: 'all',
  });

  const clusters = useMemo(() => Array.from(new Set(topics.map(t => t.cluster))).sort(), [topics]);
  const personas = useMemo(() => {
    const all = new Set<string>();
    topics.forEach(t => t.personas.forEach(p => all.add(p)));
    return Array.from(all).sort();
  }, [topics]);

  const filteredTopics = useMemo(() => {
    const result = topics.filter(t => {
      if (filters.coverage !== 'all' && t.coverage !== filters.coverage) return false;
      if (filters.priority !== 'all' && t.priority !== filters.priority) return false;
      if (filters.cluster !== 'all' && t.cluster !== filters.cluster) return false;
      if (filters.persona !== 'all' && !t.personas.includes(filters.persona)) return false;
      return true;
    });

    if (sortMode === 'gap') result.sort((a, b) => b.gapScore - a.gapScore);
    else if (sortMode === 'alpha') result.sort((a, b) => a.title.localeCompare(b.title));

    return result;
  }, [topics, filters, sortMode]);

  const selectedQuery = useMemo(() => {
    if (!selectedTopic) return null;
    return queries.find(q => q.id === selectedTopic.id) || null;
  }, [selectedTopic, queries]);

  const selectedEnrichedQuery = useMemo(() => {
    if (!selectedTopic) return null;
    return enrichedQueries.find(q => q.id === selectedTopic.id) || null;
  }, [selectedTopic, enrichedQueries]);

  const clusterPoints = useMemo(() => {
    if (!selectedTopic) return [];
    const sameCluster = topics.filter(t => t.cluster === selectedTopic.cluster);
    return sameCluster.map((t, i) => ({
      x: Math.cos((i / sameCluster.length) * Math.PI * 2) * (0.3 + (i % 3) * 0.2),
      y: Math.sin((i / sameCluster.length) * Math.PI * 2) * (0.3 + (i % 3) * 0.2),
      label: t.title.slice(0, 40),
      isCurrent: t.id === selectedTopic.id,
    }));
  }, [selectedTopic, topics]);

  const handleFilterChange = (key: string, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const handleToggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleAddToCycle = (topic: EnrichedTopic, cycle: 'current' | 'next') => {
    setToastMessage(`"${topic.title.slice(0, 50)}..." added to ${cycle} cycle`);
    setToastOpen(true);
    setSelectedTopic(null);
  };

  const handleDismiss = () => {
    setToastMessage('Topic dismissed');
    setToastOpen(true);
    setSelectedTopic(null);
  };

  const handleBulkAdd = () => {
    setToastMessage(`${selectedIds.size} topics added to cycle`);
    setToastOpen(true);
    setSelectedIds(new Set());
    setBulkMode(false);
  };

  const filterConfig = [
    {
      key: 'persona',
      label: 'Persona',
      options: [
        { value: 'all', label: 'All' },
        ...personas.map(p => ({ value: p, label: p })),
      ],
      value: filters.persona,
    },
    {
      key: 'coverage',
      label: 'Coverage',
      options: [
        { value: 'all', label: 'All' },
        { value: 'gap', label: 'Gap' },
        { value: 'partial', label: 'Partial' },
        { value: 'covered', label: 'Covered' },
      ],
      value: filters.coverage,
    },
    {
      key: 'priority',
      label: 'Priority',
      options: [
        { value: 'all', label: 'All' },
        { value: 'high', label: 'High' },
        { value: 'medium', label: 'Medium' },
        { value: 'low', label: 'Low' },
      ],
      value: filters.priority,
    },
    {
      key: 'cluster',
      label: 'Cluster',
      options: [
        { value: 'all', label: 'All' },
        ...clusters.map(c => ({ value: c, label: c })),
      ],
      value: filters.cluster,
    },
  ];

  return (
    <div>
      {/* Toolbar */}
      <div className="flex items-center justify-between mb-4 gap-3">
        <FilterBar filters={filterConfig} onChange={handleFilterChange} />
        <div className="flex items-center gap-2 flex-shrink-0">
          <select
            value={sortMode}
            onChange={e => setSortMode(e.target.value as SortMode)}
            className="h-[26px] px-2 text-[11px] border border-border rounded-sm bg-surface text-text-primary outline-none cursor-pointer hover:border-border-strong"
          >
            <option value="impact">Impact</option>
            <option value="gap">Gap Score</option>
            <option value="alpha">Alphabetical</option>
          </select>
          {bulkMode && selectedIds.size > 0 && (
            <button
              onClick={handleBulkAdd}
              className="h-[26px] px-3 text-[11px] font-medium bg-accent text-text-on-accent rounded-sm cursor-pointer"
            >
              Add {selectedIds.size} to Cycle
            </button>
          )}
          <button
            onClick={() => setBulkMode(!bulkMode)}
            className={`h-[26px] px-2 text-[11px] rounded-sm border cursor-pointer transition-colors ${
              bulkMode ? 'border-accent text-accent bg-accent-subtle' : 'border-border text-text-secondary hover:border-border-strong'
            }`}
          >
            {bulkMode ? 'Cancel' : 'Bulk Select'}
          </button>
          <div className="flex items-center border border-border rounded-sm overflow-hidden">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-1.5 cursor-pointer transition-colors ${
                viewMode === 'grid' ? 'bg-accent-subtle text-accent' : 'text-text-tertiary hover:text-text-primary'
              }`}
            >
              <LayoutGrid size={14} strokeWidth={1.5} />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-1.5 cursor-pointer transition-colors ${
                viewMode === 'list' ? 'bg-accent-subtle text-accent' : 'text-text-tertiary hover:text-text-primary'
              }`}
            >
              <List size={14} strokeWidth={1.5} />
            </button>
          </div>
        </div>
      </div>

      {/* Results count */}
      <div className="text-[11px] text-text-tertiary mb-3">
        {filteredTopics.length} topic{filteredTopics.length !== 1 ? 's' : ''}
      </div>

      {/* Grid / List */}
      {viewMode === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {filteredTopics.map(topic => (
            <TopicCard
              key={topic.id}
              topic={topic}
              selected={selectedIds.has(topic.id)}
              onSelect={bulkMode ? handleToggleSelect : undefined}
              onClick={(t) => setSelectedTopic(t)}
            />
          ))}
        </div>
      ) : (
        <div className="space-y-1">
          {filteredTopics.map(topic => (
            <TopicCard
              key={topic.id}
              topic={topic}
              selected={selectedIds.has(topic.id)}
              onSelect={bulkMode ? handleToggleSelect : undefined}
              onClick={(t) => setSelectedTopic(t)}
            />
          ))}
        </div>
      )}

      {/* Detail Panel */}
      {selectedTopic && (
        <TopicDetailPanel
          topic={selectedTopic}
          query={selectedQuery}
          enrichedQuery={selectedEnrichedQuery}
          clusterPoints={clusterPoints}
          onClose={() => setSelectedTopic(null)}
          onAddToCycle={handleAddToCycle}
          onDismiss={handleDismiss}
        />
      )}

      <Toast open={toastOpen} onClose={() => setToastOpen(false)} variant="success" message={toastMessage} />
    </div>
  );
}
