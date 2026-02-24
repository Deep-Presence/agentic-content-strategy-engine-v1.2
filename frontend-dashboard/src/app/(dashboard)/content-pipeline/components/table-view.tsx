'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ArrowUpDown } from 'lucide-react';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { cn } from '@/lib/utils/cn';
import { relativeTime } from '@/lib/utils/format';
import { CONTENT_TYPE_LABELS } from '@/lib/utils/constants';
import { BriefStatusBadge } from './brief-status-badge';
import { ContentTypeBadge } from './content-type-badge';
import { CitabilityScoreBadge } from './citability-score-badge';
import type { ContentBriefItem } from '@/types/content';

interface TableViewProps {
  briefs: ContentBriefItem[];
  className?: string;
}

type SortKey = 'title' | 'status' | 'content_type' | 'cluster' | 'citability_score' | 'target_word_count' | 'updated_at';
type SortDir = 'asc' | 'desc';

export function TableView({ briefs, className }: TableViewProps) {
  const [sortKey, setSortKey] = useState<SortKey>('updated_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  }

  const sorted = [...briefs].sort((a, b) => {
    const dir = sortDir === 'asc' ? 1 : -1;
    switch (sortKey) {
      case 'title':
        return dir * a.title.localeCompare(b.title);
      case 'status':
        return dir * a.status.localeCompare(b.status);
      case 'content_type':
        return dir * (CONTENT_TYPE_LABELS[a.content_type] ?? '').localeCompare(CONTENT_TYPE_LABELS[b.content_type] ?? '');
      case 'cluster':
        return dir * a.cluster.localeCompare(b.cluster);
      case 'citability_score':
        return dir * ((a.citability_score ?? 0) - (b.citability_score ?? 0));
      case 'target_word_count':
        return dir * (a.target_word_count - b.target_word_count);
      case 'updated_at':
        return dir * a.updated_at.localeCompare(b.updated_at);
      default:
        return 0;
    }
  });

  function SortableHead({ label, sortField, width }: { label: string; sortField: SortKey; width?: string }) {
    const isActive = sortKey === sortField;
    return (
      <TableHead
        className={cn('cursor-pointer select-none', width && `w-[${width}]`)}
        style={width ? { width } : undefined}
        onClick={() => handleSort(sortField)}
      >
        <span className="flex items-center gap-1">
          {label}
          <ArrowUpDown className={cn('h-3 w-3', isActive ? 'text-sage-400' : 'text-cream-500')} />
        </span>
      </TableHead>
    );
  }

  return (
    <div className={cn('overflow-x-auto', className)}>
      <Table>
        <TableHeader>
          <TableRow>
            <SortableHead label="Title" sortField="title" />
            <SortableHead label="Status" sortField="status" width="120px" />
            <SortableHead label="Type" sortField="content_type" width="100px" />
            <SortableHead label="Cluster" sortField="cluster" width="140px" />
            <SortableHead label="Citability" sortField="citability_score" width="100px" />
            <SortableHead label="Words" sortField="target_word_count" width="80px" />
            <SortableHead label="Updated" sortField="updated_at" width="100px" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((brief) => (
            <TableRow key={brief.id} className="hover:bg-cream-100 cursor-pointer">
              <TableCell>
                <Link
                  href={`/content-pipeline/${brief.id}`}
                  className="text-body-sm font-body text-cream-950 hover:text-sage-400 transition-colors line-clamp-1"
                >
                  {brief.title}
                </Link>
              </TableCell>
              <TableCell>
                <BriefStatusBadge status={brief.status} />
              </TableCell>
              <TableCell>
                <ContentTypeBadge type={brief.content_type} />
              </TableCell>
              <TableCell>
                <span className="text-body-sm font-sans text-cream-700 truncate block max-w-[140px]">
                  {brief.cluster}
                </span>
              </TableCell>
              <TableCell>
                {brief.citability_score != null ? (
                  <CitabilityScoreBadge score={brief.citability_score} size="sm" />
                ) : (
                  <span className="text-caption font-sans text-cream-500">--</span>
                )}
              </TableCell>
              <TableCell>
                <span className="text-body-sm font-sans tabular-nums text-cream-800">
                  {brief.target_word_count.toLocaleString()}
                </span>
              </TableCell>
              <TableCell>
                <span className="text-caption font-sans text-cream-600">
                  {relativeTime(brief.updated_at)}
                </span>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
