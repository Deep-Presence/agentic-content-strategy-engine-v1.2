'use client';

import { useState } from 'react';
import { Badge, Sparkline } from '@/components/ui';
import { ArrowUpDown } from 'lucide-react';
import type { Platform } from '@/types';

interface PublishedContent {
  id: string;
  title: string;
  publishDate: string;
  citations: number;
  citationTrend: number[];
  platforms: Platform[];
  cpsPlatforms: Record<Platform, { predicted: number; actual: number }>;
  aiReferrals: number;
  status: 'published' | 'draft';
}

const MOCK_PUBLISHED: PublishedContent[] = [
  {
    id: '1', title: 'How AI App Builders Handle Database Migrations', publishDate: '2026-03-01', citations: 14,
    citationTrend: [2, 4, 6, 8, 10, 12, 14], platforms: ['chatgpt', 'claude', 'perplexity'],
    cpsPlatforms: { chatgpt: { predicted: 0.72, actual: 0.68 }, claude: { predicted: 0.65, actual: 0.71 }, perplexity: { predicted: 0.80, actual: 0.75 }, google_ai_overview: { predicted: 0, actual: 0 }, gemini: { predicted: 0, actual: 0 } },
    aiReferrals: 1240, status: 'published',
  },
  {
    id: '2', title: 'Lovable vs Bolt.new: Full-Stack Comparison (2026)', publishDate: '2026-02-22', citations: 23,
    citationTrend: [5, 8, 12, 15, 18, 21, 23], platforms: ['chatgpt', 'gemini', 'perplexity', 'google_ai_overview'],
    cpsPlatforms: { chatgpt: { predicted: 0.81, actual: 0.85 }, claude: { predicted: 0, actual: 0 }, perplexity: { predicted: 0.78, actual: 0.82 }, google_ai_overview: { predicted: 0.70, actual: 0.79 }, gemini: { predicted: 0.75, actual: 0.80 } },
    aiReferrals: 3420, status: 'published',
  },
  {
    id: '3', title: 'Understanding Text-to-App: From Prompt to Production', publishDate: '2026-02-15', citations: 18,
    citationTrend: [3, 6, 9, 12, 14, 16, 18], platforms: ['claude', 'perplexity'],
    cpsPlatforms: { chatgpt: { predicted: 0, actual: 0 }, claude: { predicted: 0.65, actual: 0.71 }, perplexity: { predicted: 0.60, actual: 0.68 }, google_ai_overview: { predicted: 0, actual: 0 }, gemini: { predicted: 0, actual: 0 } },
    aiReferrals: 1890, status: 'published',
  },
  {
    id: '4', title: 'RBAC in AI-Generated Apps: A Validation Guide', publishDate: '2026-02-08', citations: 9,
    citationTrend: [1, 2, 4, 5, 6, 7, 9], platforms: ['chatgpt', 'claude'],
    cpsPlatforms: { chatgpt: { predicted: 0.58, actual: 0.52 }, claude: { predicted: 0.55, actual: 0.49 }, perplexity: { predicted: 0, actual: 0 }, google_ai_overview: { predicted: 0, actual: 0 }, gemini: { predicted: 0, actual: 0 } },
    aiReferrals: 560, status: 'published',
  },
  {
    id: '5', title: 'SOC 2 Compliance Checklist for AI Development Platforms', publishDate: '2026-01-28', citations: 31,
    citationTrend: [4, 10, 16, 20, 24, 28, 31], platforms: ['chatgpt', 'claude', 'perplexity', 'google_ai_overview', 'gemini'],
    cpsPlatforms: { chatgpt: { predicted: 0.88, actual: 0.91 }, claude: { predicted: 0.82, actual: 0.87 }, perplexity: { predicted: 0.85, actual: 0.89 }, google_ai_overview: { predicted: 0.79, actual: 0.83 }, gemini: { predicted: 0.75, actual: 0.80 } },
    aiReferrals: 4580, status: 'published',
  },
  {
    id: '6', title: 'Environment Variable Security in Prompt-to-App Tools', publishDate: '2026-01-15', citations: 12,
    citationTrend: [2, 3, 5, 7, 8, 10, 12], platforms: ['chatgpt', 'perplexity'],
    cpsPlatforms: { chatgpt: { predicted: 0.62, actual: 0.59 }, claude: { predicted: 0, actual: 0 }, perplexity: { predicted: 0.58, actual: 0.61 }, google_ai_overview: { predicted: 0, actual: 0 }, gemini: { predicted: 0, actual: 0 } },
    aiReferrals: 890, status: 'published',
  },
  {
    id: '7', title: 'Audit Logging Best Practices for No-Code Platforms', publishDate: '2026-01-05', citations: 7,
    citationTrend: [1, 1, 2, 3, 4, 5, 7], platforms: ['claude'],
    cpsPlatforms: { chatgpt: { predicted: 0, actual: 0 }, claude: { predicted: 0.45, actual: 0.41 }, perplexity: { predicted: 0, actual: 0 }, google_ai_overview: { predicted: 0, actual: 0 }, gemini: { predicted: 0, actual: 0 } },
    aiReferrals: 320, status: 'published',
  },
  {
    id: '8', title: 'AI Code Generation vs Low-Code: Decision Framework', publishDate: '2026-03-10', citations: 0,
    citationTrend: [0, 0, 0], platforms: [],
    cpsPlatforms: { chatgpt: { predicted: 0.76, actual: 0 }, claude: { predicted: 0.70, actual: 0 }, perplexity: { predicted: 0.72, actual: 0 }, google_ai_overview: { predicted: 0.65, actual: 0 }, gemini: { predicted: 0.68, actual: 0 } },
    aiReferrals: 0, status: 'draft',
  },
];

const PLATFORM_LABELS: Record<Platform, string> = {
  chatgpt: 'GPT', claude: 'Cl', perplexity: 'Px', google_ai_overview: 'AIO', gemini: 'Gem',
};

const PLATFORM_ORDER: Platform[] = ['chatgpt', 'claude', 'perplexity', 'google_ai_overview', 'gemini'];

type SortKey = 'title' | 'publishDate' | 'citations' | 'aiReferrals';

export function HistoryTab() {
  const [sortKey, setSortKey] = useState<SortKey>('publishDate');
  const [sortAsc, setSortAsc] = useState(false);

  const sorted = [...MOCK_PUBLISHED].sort((a, b) => {
    const mul = sortAsc ? 1 : -1;
    if (sortKey === 'title') return mul * a.title.localeCompare(b.title);
    if (sortKey === 'publishDate') return mul * (new Date(a.publishDate).getTime() - new Date(b.publishDate).getTime());
    return mul * ((a[sortKey] as number) - (b[sortKey] as number));
  });

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(false); }
  };

  const SortHeader = ({ label, sortKeyValue, className }: { label: string; sortKeyValue: SortKey; className?: string }) => (
    <th
      onClick={() => toggleSort(sortKeyValue)}
      className={`text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-left p-[6px_8px] border-b border-border cursor-pointer hover:text-text-primary select-none ${className || ''}`}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        <ArrowUpDown size={10} strokeWidth={1.5} className={sortKey === sortKeyValue ? 'text-accent' : 'opacity-40'} />
      </span>
    </th>
  );

  return (
    <div className="bg-surface border border-border rounded-md overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr>
            <SortHeader label="Title" sortKeyValue="title" />
            <SortHeader label="Published" sortKeyValue="publishDate" />
            <th className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-left p-[6px_8px] border-b border-border">
              Platforms
            </th>
            <SortHeader label="Citations" sortKeyValue="citations" />
            <th className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-left p-[6px_8px] border-b border-border">
              CPS (P/A per platform)
            </th>
            <SortHeader label="AI Referrals" sortKeyValue="aiReferrals" />
            <th className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-left p-[6px_8px] border-b border-border">
              Status
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map(item => (
            <tr key={item.id} className="hover:bg-bg transition-colors">
              <td className="text-[12px] p-[6px_8px] border-b border-border-subtle text-text-primary font-medium max-w-[260px]">
                <span className="line-clamp-1">{item.title}</span>
              </td>
              <td className="text-[12px] p-[6px_8px] border-b border-border-subtle text-text-secondary whitespace-nowrap">
                {new Date(item.publishDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              </td>
              <td className="p-[6px_8px] border-b border-border-subtle">
                <div className="flex flex-wrap gap-1">
                  {item.platforms.map(p => (
                    <Badge key={p} variant="neutral">{PLATFORM_LABELS[p]}</Badge>
                  ))}
                </div>
              </td>
              <td className="p-[6px_8px] border-b border-border-subtle">
                <div className="flex items-center gap-1.5">
                  <span className="text-[12px] font-medium text-text-primary">{item.citations}</span>
                  <Sparkline data={item.citationTrend} width={48} height={14} />
                </div>
              </td>
              <td className="p-[6px_8px] border-b border-border-subtle">
                <div className="flex items-center gap-1">
                  {PLATFORM_ORDER.map(p => {
                    const cps = item.cpsPlatforms[p];
                    if (!cps || (cps.predicted === 0 && cps.actual === 0)) return null;
                    return (
                      <div key={p} className="flex flex-col items-center" title={`${PLATFORM_LABELS[p]}: P=${cps.predicted.toFixed(2)} A=${cps.actual.toFixed(2)}`}>
                        <div className="flex items-end gap-px h-[18px]">
                          <div
                            className="w-[4px] bg-text-tertiary rounded-t-[1px]"
                            style={{ height: `${cps.predicted * 18}px` }}
                          />
                          <div
                            className={`w-[4px] rounded-t-[1px] ${cps.actual >= cps.predicted ? 'bg-success' : 'bg-warning'}`}
                            style={{ height: `${Math.max(cps.actual, 0.05) * 18}px` }}
                          />
                        </div>
                        <span className="text-[8px] text-text-tertiary mt-0.5">{PLATFORM_LABELS[p]}</span>
                      </div>
                    );
                  })}
                </div>
              </td>
              <td className="text-[12px] p-[6px_8px] border-b border-border-subtle text-text-secondary font-mono">
                {item.aiReferrals > 0 ? item.aiReferrals.toLocaleString() : '—'}
              </td>
              <td className="p-[6px_8px] border-b border-border-subtle">
                <Badge variant={item.status === 'published' ? 'success' : 'warning'}>
                  {item.status}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
