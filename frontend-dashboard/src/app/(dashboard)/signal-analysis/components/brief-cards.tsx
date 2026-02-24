'use client';

import { useState, useMemo } from 'react';
import {
  ChevronDown,
  ChevronUp,
  FileText,
  Globe,
  BookOpen,
  ListOrdered,
  Target,
  ExternalLink,
  Eye,
  EyeOff,
  ArrowRight,
  Sparkles,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils/cn';
import { CLUSTER_COLORS, CLUSTER_NAMES, getTopGapQueries, type QueryData } from '../data/sample-data';

interface BriefCardsProps {
  queries: QueryData[];
}

function getGapScoreColor(score: number): string {
  if (score >= 0.85) return 'bg-red-50 text-red-700 border-red-200';
  if (score >= 0.7) return 'bg-orange-50 text-orange-700 border-orange-200';
  if (score >= 0.5) return 'bg-amber-50 text-amber-700 border-amber-200';
  return 'bg-green-50 text-green-700 border-green-200';
}

function getClassificationVariant(classification: string): 'terracotta' | 'warning' | 'green' | 'default' {
  const lower = classification.toLowerCase();
  if (lower.includes('critical') || lower.includes('high')) return 'terracotta';
  if (lower.includes('medium') || lower.includes('moderate')) return 'warning';
  if (lower.includes('low') || lower.includes('minor')) return 'green';
  return 'default';
}

function PlatformIcon({ platform }: { platform: string }) {
  const colors: Record<string, string> = {
    chatgpt: '#10a37f',
    claude: '#d97757',
    perplexity: '#1a73e8',
    gemini: '#8e44ad',
  };

  return (
    <span
      className="inline-block h-2 w-2 rounded-full"
      style={{ backgroundColor: colors[platform] || '#999' }}
    />
  );
}

interface BriefCardItemProps {
  query: QueryData;
  isExpanded: boolean;
  onToggle: () => void;
  rank: number;
}

function BriefCardItem({ query, isExpanded, onToggle, rank }: BriefCardItemProps) {
  const clusterColor = CLUSTER_COLORS[query.cluster_id] || '#999';

  return (
    <div
      className={cn(
        'rounded-lg border border-stone-200 bg-white transition-all duration-200',
        isExpanded && 'ring-1 ring-stone-300 shadow-sm'
      )}
    >
      {/* Collapsed View — Always Visible */}
      <button
        onClick={onToggle}
        className="w-full text-left px-4 py-3.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6a9bcc] focus-visible:ring-offset-1 rounded-lg"
      >
        <div className="flex items-start gap-3">
          {/* Rank number */}
          <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-stone-100 text-[10px] font-semibold text-stone-500 font-sans">
            {rank}
          </span>

          {/* Main content */}
          <div className="flex-1 min-w-0">
            <p className="font-serif text-sm font-medium text-[#141413] leading-snug mb-2">
              {query.text}
            </p>

            <div className="flex flex-wrap items-center gap-1.5 mb-2.5">
              <Badge
                variant="default"
                className="text-[10px] px-1.5 py-0 text-white"
                style={{ backgroundColor: clusterColor }}
              >
                {query.cluster_name}
              </Badge>
              <Badge variant={getClassificationVariant(query.classification)} className="text-[10px] px-1.5 py-0">
                {query.classification}
              </Badge>
            </div>

            {/* Key stats row */}
            <div className="flex flex-wrap items-center gap-3 text-[11px] text-stone-500 font-sans">
              <span className="flex items-center gap-1">
                <FileText className="h-3 w-3" />
                {query.target_words.min.toLocaleString()}–{query.target_words.max.toLocaleString()} words
              </span>
              <span className="flex items-center gap-1">
                <BookOpen className="h-3 w-3" />
                Grade {query.reading_level.min}–{query.reading_level.max}
              </span>
              <span className="flex items-center gap-1">
                <ListOrdered className="h-3 w-3" />
                {query.headers} headers
              </span>
              <span className="flex items-center gap-1">
                <Globe className="h-3 w-3" />
                {query.top_domain}
              </span>
            </div>
          </div>

          {/* Gap score + expand icon */}
          <div className="flex items-start gap-2 shrink-0">
            <div
              className={cn(
                'rounded-md border px-2.5 py-1.5 text-center min-w-[72px]',
                getGapScoreColor(query.gap_score)
              )}
            >
              <p className="text-[10px] font-sans uppercase tracking-wider opacity-70 mb-0.5">Gap</p>
              <p className="text-base font-bold font-sans tabular-nums">
                {query.gap_score.toFixed(4)}
              </p>
            </div>
            <div className="mt-2 text-stone-400">
              {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </div>
          </div>
        </div>
      </button>

      {/* Expanded View */}
      {isExpanded && (
        <div className="border-t border-stone-100 px-4 py-4 ml-9 space-y-4">
          {/* Content Brief Specs */}
          <div>
            <h4 className="text-xs font-semibold text-stone-400 uppercase tracking-wider font-sans mb-2">
              Content Brief Specs
            </h4>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <div className="rounded-md bg-stone-50 p-2.5">
                <p className="text-[10px] text-stone-400 font-sans mb-0.5">Word Count</p>
                <p className="text-sm font-semibold text-[#141413] font-sans">
                  {query.target_words.min.toLocaleString()}–{query.target_words.max.toLocaleString()}
                </p>
              </div>
              <div className="rounded-md bg-stone-50 p-2.5">
                <p className="text-[10px] text-stone-400 font-sans mb-0.5">Reading Level</p>
                <p className="text-sm font-semibold text-[#141413] font-sans">
                  Grade {query.reading_level.min}–{query.reading_level.max}
                </p>
              </div>
              <div className="rounded-md bg-stone-50 p-2.5">
                <p className="text-[10px] text-stone-400 font-sans mb-0.5">Headers</p>
                <p className="text-sm font-semibold text-[#141413] font-sans">
                  {query.headers} sections
                </p>
              </div>
              <div className="rounded-md bg-stone-50 p-2.5">
                <p className="text-[10px] text-stone-400 font-sans mb-0.5">Patterns</p>
                <p className="text-sm font-semibold text-[#141413] font-sans">
                  {query.patterns.length} detected
                </p>
              </div>
            </div>
          </div>

          {/* Headers count */}
          {query.headers > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-stone-400 uppercase tracking-wider font-sans mb-2">
                Suggested Headers
              </h4>
              <p className="text-xs text-stone-600 font-sans">
                {query.headers} header sections recommended
              </p>
            </div>
          )}

          {/* Patterns */}
          {query.patterns.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-stone-400 uppercase tracking-wider font-sans mb-2">
                Content Patterns
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {query.patterns.map((pattern, i) => (
                  <Badge key={i} variant="blue" className="text-[10px]">
                    {pattern}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Exemplar & Similarity Info */}
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="rounded-md bg-stone-50 p-3">
              <h4 className="text-xs font-semibold text-stone-400 uppercase tracking-wider font-sans mb-2">
                Top Exemplar
              </h4>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-sm text-[#141413] font-sans">
                  <Globe className="h-3.5 w-3.5 text-stone-400" />
                  {query.top_domain}
                </span>
                <div className="text-right">
                  <p className="text-[10px] text-stone-400 font-sans">Similarity</p>
                  <p className="text-sm font-bold text-[#6a9bcc] font-sans tabular-nums">
                    {query.top_exemplar_sim.toFixed(4)}
                  </p>
                </div>
              </div>
            </div>

            <div className="rounded-md bg-stone-50 p-3">
              <h4 className="text-xs font-semibold text-stone-400 uppercase tracking-wider font-sans mb-2">
                Company Match
              </h4>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-sm text-[#141413] font-sans">
                  <Target className="h-3.5 w-3.5 text-stone-400" />
                  Best similarity
                </span>
                <div className="text-right">
                  <p className="text-[10px] text-stone-400 font-sans">Score</p>
                  <p className="text-sm font-bold text-[#d97757] font-sans tabular-nums">
                    {query.company_sim.toFixed(4)}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Platform citations */}
          <div>
            <h4 className="text-xs font-semibold text-stone-400 uppercase tracking-wider font-sans mb-2">
              Platform Citations
            </h4>
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              {Object.entries(query.platform_citations).map(([platform, count]) => (
                <div
                  key={platform}
                  className="flex items-center gap-2 rounded-md bg-stone-50 px-2.5 py-2"
                >
                  <PlatformIcon platform={platform} />
                  <span className="text-xs text-stone-500 font-sans capitalize">{platform}</span>
                  <span className="ml-auto text-sm font-semibold text-[#141413] font-sans tabular-nums">
                    {count}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2 pt-1">
            <Button variant="secondary" size="sm" className="text-xs">
              <Sparkles className="mr-1.5 h-3.5 w-3.5" />
              View in Embedding Lab
              <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function BriefCards({ queries }: BriefCardsProps) {
  const topQueries = useMemo(() => getTopGapQueries(queries, 25), [queries]);

  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => {
    const initial = new Set<string>();
    topQueries.slice(0, 10).forEach((q) => initial.add(q.id));
    return initial;
  });

  const [showAll, setShowAll] = useState(true);

  const toggleCard = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleAll = () => {
    if (showAll) {
      setExpandedIds(new Set());
      setShowAll(false);
    } else {
      setExpandedIds(new Set(topQueries.map((q) => q.id)));
      setShowAll(true);
    }
  };

  const allExpanded = expandedIds.size === topQueries.length;
  const noneExpanded = expandedIds.size === 0;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="font-serif text-lg">Top 25 Gap Briefs</CardTitle>
            <CardDescription className="font-sans text-sm text-stone-500">
              Content opportunities ranked by gap severity
            </CardDescription>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleAll}
            className="text-xs text-stone-500 hover:text-[#141413]"
          >
            {allExpanded || showAll ? (
              <>
                <EyeOff className="mr-1.5 h-3.5 w-3.5" />
                Collapse All
              </>
            ) : (
              <>
                <Eye className="mr-1.5 h-3.5 w-3.5" />
                Show All
              </>
            )}
          </Button>
        </div>

        {/* Summary stats */}
        <div className="flex flex-wrap gap-4 mt-2 text-xs font-sans text-stone-500">
          <span>
            <span className="font-semibold text-[#141413]">{topQueries.length}</span> briefs
          </span>
          <span>
            Avg gap:{' '}
            <span className="font-semibold text-[#d97757]">
              {(topQueries.reduce((s, q) => s + q.gap_score, 0) / topQueries.length).toFixed(4)}
            </span>
          </span>
          <span>
            Clusters:{' '}
            <span className="font-semibold text-[#141413]">
              {new Set(topQueries.map((q) => q.cluster_id)).size}
            </span>
          </span>
        </div>
      </CardHeader>

      <CardContent>
        <div className="space-y-2">
          {topQueries.map((query, index) => (
            <BriefCardItem
              key={query.id}
              query={query}
              rank={index + 1}
              isExpanded={expandedIds.has(query.id)}
              onToggle={() => toggleCard(query.id)}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
