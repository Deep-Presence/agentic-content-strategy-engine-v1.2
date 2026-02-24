'use client';

import { Search } from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import { useContentStore } from '@/stores/content-store';
import type { ContentBriefStatus, ContentType } from '@/types/content';

interface FilterBarProps {
  clusters?: string[];
  cycles?: string[];
  className?: string;
}

const STATUS_OPTIONS: Array<{ value: ContentBriefStatus | 'all'; label: string }> = [
  { value: 'all', label: 'All Statuses' },
  { value: 'suggested', label: 'Suggested' },
  { value: 'approved', label: 'Approved' },
  { value: 'research', label: 'Research' },
  { value: 'drafting', label: 'Drafting' },
  { value: 'evaluating', label: 'Evaluating' },
  { value: 'review', label: 'Review' },
  { value: 'published', label: 'Published' },
  { value: 'draft_saved', label: 'Draft Saved' },
];

const TYPE_OPTIONS: Array<{ value: ContentType | 'all'; label: string }> = [
  { value: 'all', label: 'All Types' },
  { value: 'blog', label: 'Blog Post' },
  { value: 'guide', label: 'Guide' },
  { value: 'case_study', label: 'Case Study' },
  { value: 'product_page', label: 'Product Page' },
];

export function FilterBar({ clusters = [], cycles = [], className }: FilterBarProps) {
  const { statusFilter, typeFilter, clusterFilter, cycleFilter, searchQuery, setFilter } = useContentStore();

  return (
    <div className={cn('flex items-center gap-3 flex-wrap', className)}>
      <select
        value={statusFilter}
        onChange={(e) => setFilter('statusFilter', e.target.value)}
        className="px-3 py-1.5 text-body-sm font-sans bg-white border border-[var(--border-default)] rounded-md text-cream-800 focus:border-sage-400 focus:ring-2 focus:ring-sage-400/20 outline-none"
      >
        {STATUS_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>

      <select
        value={typeFilter}
        onChange={(e) => setFilter('typeFilter', e.target.value)}
        className="px-3 py-1.5 text-body-sm font-sans bg-white border border-[var(--border-default)] rounded-md text-cream-800 focus:border-sage-400 focus:ring-2 focus:ring-sage-400/20 outline-none"
      >
        {TYPE_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>

      {clusters.length > 0 && (
        <select
          value={clusterFilter}
          onChange={(e) => setFilter('clusterFilter', e.target.value)}
          className="px-3 py-1.5 text-body-sm font-sans bg-white border border-[var(--border-default)] rounded-md text-cream-800 focus:border-sage-400 focus:ring-2 focus:ring-sage-400/20 outline-none"
        >
          <option value="all">All Clusters</option>
          {clusters.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      )}

      {cycles.length > 0 && (
        <select
          value={cycleFilter}
          onChange={(e) => setFilter('cycleFilter', e.target.value)}
          className="px-3 py-1.5 text-body-sm font-sans bg-white border border-[var(--border-default)] rounded-md text-cream-800 focus:border-sage-400 focus:ring-2 focus:ring-sage-400/20 outline-none"
        >
          <option value="all">All Cycles</option>
          {cycles.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      )}

      <div className="relative flex-1 min-w-[200px] max-w-xs">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-cream-500" />
        <input
          type="text"
          placeholder="Search briefs..."
          value={searchQuery}
          onChange={(e) => setFilter('searchQuery', e.target.value)}
          className="w-full pl-9 pr-3 py-1.5 text-body-sm font-sans bg-white border border-[var(--border-default)] rounded-md text-cream-800 placeholder:text-cream-500 focus:border-sage-400 focus:ring-2 focus:ring-sage-400/20 outline-none"
        />
      </div>
    </div>
  );
}
