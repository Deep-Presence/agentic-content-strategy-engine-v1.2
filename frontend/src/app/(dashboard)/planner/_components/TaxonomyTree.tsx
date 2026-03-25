'use client';

import { useState, useMemo } from 'react';
import { cn } from '@/lib/utils';
import { ChevronRight, Plus, Minus } from 'lucide-react';
import {
  type CategoryNode,
  type SubdomainNode,
  type SortDimension,
  categories,
  getCategoryStats,
  getAssignments,
  getSortScore,
} from './topic-data';

interface TaxonomyTreeProps {
  selectedSubdomainId: string | null;
  onSelectSubdomain: (sub: SubdomainNode, cat: CategoryNode) => void;
  sortDimension: SortDimension;
  onSortChange: (dim: SortDimension) => void;
}

const SOURCE_KEYS = ['source_a', 'source_b', 'source_c', 'source_d'] as const;
const SOURCE_LABELS = ['A', 'B', 'C', 'D'];

export function TaxonomyTree({
  selectedSubdomainId,
  onSelectSubdomain,
  sortDimension,
  onSortChange,
}: TaxonomyTreeProps) {
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    return new Set(categories.length > 0 ? [categories[0].id] : []);
  });

  const sortedCategories = useMemo(() => {
    return [...categories].sort((a, b) => {
      const aAvg = getCategoryStats(a).avgScore;
      const bAvg = getCategoryStats(b).avgScore;
      return bAvg - aAvg;
    });
  }, []);

  const sortedChildren = useMemo(() => {
    const map = new Map<string, SubdomainNode[]>();
    for (const cat of sortedCategories) {
      const sorted = [...cat.children].sort(
        (a, b) => getSortScore(b, sortDimension) - getSortScore(a, sortDimension)
      );
      map.set(cat.id, sorted);
    }
    return map;
  }, [sortedCategories, sortDimension]);

  const toggleCategory = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const expandAll = () => setExpanded(new Set(sortedCategories.map((c) => c.id)));
  const collapseAll = () => setExpanded(new Set());

  return (
    <div className="flex flex-col h-full">
      {/* Sort Controls */}
      <div className="sticky top-0 z-10 bg-bg border-b border-border px-3 py-2 flex items-center justify-between gap-2 shrink-0">
        <div className="flex items-center gap-1">
          {(['citation', 'feasibility', 'return'] as SortDimension[]).map((dim) => (
            <button
              key={dim}
              onClick={() => onSortChange(dim)}
              className={cn(
                'px-2 h-[24px] text-[10px] font-medium rounded-sm capitalize transition-colors cursor-pointer',
                sortDimension === dim
                  ? 'bg-accent-subtle text-accent'
                  : 'text-text-tertiary hover:text-text-secondary hover:bg-surface'
              )}
            >
              {dim}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-0.5">
          <button
            onClick={expandAll}
            className="p-1 text-text-tertiary hover:text-text-secondary rounded-sm cursor-pointer"
            title="Expand all"
          >
            <Plus size={12} strokeWidth={1.5} />
          </button>
          <button
            onClick={collapseAll}
            className="p-1 text-text-tertiary hover:text-text-secondary rounded-sm cursor-pointer"
            title="Collapse all"
          >
            <Minus size={12} strokeWidth={1.5} />
          </button>
        </div>
      </div>

      {/* Tree */}
      <div className="flex-1 overflow-y-auto">
        {sortedCategories.map((cat) => {
          const isOpen = expanded.has(cat.id);
          const stats = getCategoryStats(cat);
          const children = sortedChildren.get(cat.id) ?? cat.children;
          const hasSelectedChild = children.some((c) => c.id === selectedSubdomainId);

          return (
            <div key={cat.id}>
              {/* Category Node */}
              <button
                onClick={() => toggleCategory(cat.id)}
                className={cn(
                  'w-full flex items-center gap-2 px-3 py-[7px] text-left transition-colors cursor-pointer',
                  'border-l-2 border-transparent',
                  'hover:bg-surface',
                  hasSelectedChild && 'border-l-accent bg-surface'
                )}
              >
                <ChevronRight
                  size={12}
                  strokeWidth={1.5}
                  className={cn(
                    'text-text-tertiary transition-transform duration-150 shrink-0',
                    isOpen && 'rotate-90'
                  )}
                />
                <span className="text-[12px] font-semibold text-text-primary truncate flex-1">
                  {cat.name}
                </span>
                <span className="text-[10px] text-text-tertiary font-mono shrink-0">
                  {stats.count}
                </span>
                {/* Avg Score Bar */}
                <div className="w-[40px] h-[4px] bg-border rounded-full overflow-hidden shrink-0">
                  <div
                    className="h-full bg-accent rounded-full"
                    style={{ width: `${stats.avgScore * 100}%` }}
                  />
                </div>
              </button>

              {/* Subdomain Nodes */}
              {isOpen &&
                children.map((sub) => {
                  const isSelected = sub.id === selectedSubdomainId;
                  const assignments = getAssignments(sub.id);
                  const score = getSortScore(sub, sortDimension);

                  return (
                    <button
                      key={sub.id}
                      onClick={() => onSelectSubdomain(sub, cat)}
                      className={cn(
                        'w-full flex items-center gap-1.5 pl-[30px] pr-3 py-[5px] text-left transition-colors cursor-pointer',
                        'border-l-2 border-transparent',
                        'hover:bg-surface',
                        isSelected && 'bg-accent-subtle border-l-accent'
                      )}
                    >
                      <span
                        className={cn(
                          'text-[11.5px] font-medium truncate flex-1',
                          isSelected ? 'text-accent' : 'text-text-primary'
                        )}
                      >
                        {sub.name}
                      </span>

                      {/* Pipeline B badge */}
                      {assignments.length > 0 && (
                        <span className="text-[9px] font-medium px-1 py-[1px] rounded-sm bg-accent-subtle text-accent shrink-0">
                          B
                        </span>
                      )}

                      {/* Source badges */}
                      <div className="flex items-center gap-[2px] shrink-0">
                        {SOURCE_KEYS.map((key, i) => {
                          const has = sub.source_provenance[key];
                          return (
                            <span
                              key={key}
                              className={cn(
                                'w-[14px] h-[14px] flex items-center justify-center text-[8px] font-medium rounded-sm',
                                has
                                  ? 'bg-accent text-text-on-accent'
                                  : 'border border-border text-text-tertiary'
                              )}
                            >
                              {SOURCE_LABELS[i]}
                            </span>
                          );
                        })}
                      </div>

                      {/* Assignment count */}
                      {assignments.length > 0 && (
                        <span className="text-[10px] text-text-tertiary font-mono shrink-0">
                          {assignments.length}
                        </span>
                      )}

                      {/* Score bar */}
                      <div className="w-[40px] h-[4px] bg-border rounded-full overflow-hidden shrink-0">
                        <div
                          className="h-full bg-accent rounded-full"
                          style={{ width: `${score * 100}%` }}
                        />
                      </div>
                    </button>
                  );
                })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
