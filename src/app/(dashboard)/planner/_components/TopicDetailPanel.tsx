'use client';

import { Badge, Button } from '@/components/ui';
import type { Query } from '@/types';
import type { EnrichedTopic } from '@/data/topics';
import type { EnrichedQuery } from '@/data/gap-report';
import { motion, AnimatePresence } from 'framer-motion';
import { X, ExternalLink, Plus, CalendarPlus, EyeOff, Compass } from 'lucide-react';
import dynamic from 'next/dynamic';
import Link from 'next/link';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

const PLATFORM_LABELS: Record<string, string> = {
  chatgpt: 'ChatGPT', claude: 'Claude', perplexity: 'Perplexity',
  google_ai_overview: 'AIO', gemini: 'Gemini',
};

interface TopicDetailPanelProps {
  topic: EnrichedTopic;
  query: Query | null;
  enrichedQuery: EnrichedQuery | null;
  clusterPoints: { x: number; y: number; label: string; isCurrent: boolean }[];
  onClose: () => void;
  onAddToCycle: (topic: EnrichedTopic, cycle: 'current' | 'next') => void;
  onDismiss: () => void;
}

export function TopicDetailPanel({
  topic, query, enrichedQuery, clusterPoints, onClose, onAddToCycle, onDismiss,
}: TopicDetailPanelProps) {
  if (!query) return null;

  const currentPoints = clusterPoints.filter(p => p.isCurrent);
  const neighborPoints = clusterPoints.filter(p => !p.isCurrent);
  const brief = enrichedQuery?.contentBrief;
  const companySig = enrichedQuery?.companyStructural;

  // Compute opportunity bullets
  const competitorDomains = query.citedExemplars
    .map(e => e.domain)
    .filter((v, i, a) => a.indexOf(v) === i)
    .slice(0, 3);
  const avgExemplarWords = query.citedExemplars.length > 0
    ? Math.round(query.citedExemplars.reduce((s, e) => s + e.structure.words, 0) / query.citedExemplars.length)
    : 0;
  const avgExemplarHeaders = query.citedExemplars.length > 0
    ? Math.round(query.citedExemplars.reduce((s, e) => s + e.structure.headers, 0) / query.citedExemplars.length)
    : 0;
  const avgExemplarLists = query.citedExemplars.length > 0
    ? Math.round(query.citedExemplars.reduce((s, e) => s + e.structure.lists, 0) / query.citedExemplars.length)
    : 0;

  // Determine content patterns for structural targets
  const patterns: string[] = [];
  if (brief) {
    if (brief.hasFaq > 0.3) patterns.push('FAQ section');
    if (brief.hasTables > 0.3) patterns.push('Comparison table');
    if (brief.hasStepByStep > 0.3) patterns.push('Step-by-step');
    if (brief.hasKeyTakeaways > 0.3) patterns.push('Key takeaways');
  }

  return (
    <AnimatePresence>
      <motion.div
        key={topic.id}
        initial={{ x: 380 }}
        animate={{ x: 0 }}
        exit={{ x: 380 }}
        transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
        className="fixed right-0 top-0 bottom-0 w-[380px] bg-surface border-l border-border z-40 overflow-y-auto"
      >
        <div className="p-4">
          {/* Header */}
          <div className="flex items-start justify-between mb-3">
            <h3 className="text-[14px] font-semibold text-text-primary leading-tight flex-1 mr-2">
              {topic.title}
            </h3>
            <button onClick={onClose} className="p-1 text-text-tertiary hover:text-text-primary cursor-pointer">
              <X size={16} strokeWidth={1.5} />
            </button>
          </div>

          {/* Section 1: Query Info */}
          <div className="mb-4">
            <div className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
              Query Info
            </div>
            <div className="flex flex-wrap items-center gap-1.5 mb-2">
              <Badge variant={topic.priority === 'high' ? 'error' : topic.priority === 'medium' ? 'warning' : 'info'}>
                {topic.priority} priority
              </Badge>
              <Badge variant={topic.coverage === 'gap' ? 'error' : topic.coverage === 'partial' ? 'warning' : 'success'}>
                {topic.coverage}
              </Badge>
              <Badge variant="neutral">{topic.cluster}</Badge>
            </div>
            <div className="bg-bg border border-border rounded-md p-3 mb-2">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-text-tertiary">Gap Score</span>
                <span className="text-[16px] font-semibold text-text-primary">{topic.gapScore.toFixed(4)}</span>
              </div>
              <div className="flex items-center gap-4">
                <div>
                  <span className="text-[10px] text-text-tertiary">Cited Avg</span>
                  <span className="text-[12px] text-text-primary ml-1">{query.avgCitationSimilarity.toFixed(4)}</span>
                </div>
                <div>
                  <span className="text-[10px] text-text-tertiary">Company</span>
                  <span className="text-[12px] text-text-primary ml-1">{query.bestCompanyUnit.similarity.toFixed(4)}</span>
                </div>
              </div>
            </div>
            {/* Platform presence */}
            {query.platforms.length > 0 && (
              <div className="flex items-center gap-1.5 mb-1">
                <span className="text-[10px] text-text-tertiary">Cited on:</span>
                {query.platforms.map(p => (
                  <Badge key={p} variant="info">{PLATFORM_LABELS[p] || p}</Badge>
                ))}
              </div>
            )}
            {!query.companyCited && (
              <div className="text-[11px] text-error mt-1">Company not cited on any platform</div>
            )}
          </div>

          {/* Section 2: Why This Matters */}
          <div className="mb-4">
            <div className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
              Why This Matters
            </div>
            <div className="bg-bg border border-border rounded-md p-3">
              <ul className="space-y-1.5">
                {competitorDomains.length > 0 && (
                  <li className="text-[12px] text-text-secondary leading-[1.55]">
                    <span className="font-medium text-text-primary">{competitorDomains.length} competitor{competitorDomains.length !== 1 ? 's' : ''} cited</span>
                    {' '}({competitorDomains.join(', ')}), you&apos;re not
                  </li>
                )}
                <li className="text-[12px] text-text-secondary leading-[1.55]">
                  Avg cited content: <span className="font-medium text-text-primary">{avgExemplarWords.toLocaleString()} words</span>,{' '}
                  {avgExemplarHeaders} headers, {avgExemplarLists} lists —
                  your closest page: <span className="font-medium text-text-primary">{companySig?.wordCount.toLocaleString() ?? '?'} words</span>
                </li>
                <li className="text-[12px] text-text-secondary leading-[1.55]">
                  Gap of <span className="font-medium text-text-primary">{topic.gapScore.toFixed(3)}</span> puts this in the top {
                    topic.priority === 'high' ? '10%' : topic.priority === 'medium' ? '30%' : '50%'
                  } of opportunities
                </li>
              </ul>
            </div>
          </div>

          {/* Section 3: Exemplar Analysis Table */}
          {query.citedExemplars.length > 0 && (
            <div className="mb-4">
              <div className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
                Exemplar Analysis
              </div>
              <div className="bg-bg border border-border rounded-md overflow-hidden">
                <table className="w-full border-collapse">
                  <thead>
                    <tr>
                      <th className="text-[9px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-left p-[4px_8px] border-b border-border">URL</th>
                      <th className="text-[9px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-right p-[4px_8px] border-b border-border">Words</th>
                      <th className="text-[9px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-right p-[4px_8px] border-b border-border">H</th>
                      <th className="text-[9px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-right p-[4px_8px] border-b border-border">L</th>
                      <th className="text-[9px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-right p-[4px_8px] border-b border-border">Sim</th>
                    </tr>
                  </thead>
                  <tbody>
                    {query.citedExemplars.slice(0, 5).map((ex, i) => (
                      <tr key={i} className="hover:bg-surface transition-colors">
                        <td className="text-[11px] p-[4px_8px] border-b border-border-subtle text-accent max-w-[140px]">
                          <a
                            href={ex.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:underline inline-flex items-center gap-0.5 truncate"
                            title={ex.url}
                          >
                            {ex.domain}
                            <ExternalLink size={9} strokeWidth={1.5} className="flex-shrink-0" />
                          </a>
                        </td>
                        <td className="text-[11px] p-[4px_8px] border-b border-border-subtle text-text-secondary text-right font-mono">
                          {ex.structure.words.toLocaleString()}
                        </td>
                        <td className="text-[11px] p-[4px_8px] border-b border-border-subtle text-text-secondary text-right font-mono">
                          {ex.structure.headers}
                        </td>
                        <td className="text-[11px] p-[4px_8px] border-b border-border-subtle text-text-secondary text-right font-mono">
                          {ex.structure.lists}
                        </td>
                        <td className="text-[11px] p-[4px_8px] border-b border-border-subtle text-text-primary text-right font-mono font-medium">
                          {ex.similarity.toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Section 4: Structural Targets */}
          {brief && (
            <div className="mb-4">
              <div className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
                Structural Targets
              </div>
              <div className="bg-bg border border-border rounded-md p-3 space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <div className="text-[10px] text-text-tertiary">Word Count</div>
                    <div className="text-[12px] font-medium text-text-primary">
                      {brief.targetWordCount[0].toLocaleString()}–{brief.targetWordCount[1].toLocaleString()}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-text-tertiary">Headers</div>
                    <div className="text-[12px] font-medium text-text-primary">
                      {brief.recommendedHeaders[0]}–{brief.recommendedHeaders[1]}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-text-tertiary">Reading Level</div>
                    <div className="text-[12px] font-medium text-text-primary">
                      {brief.targetReadingLevel[0].toFixed(1)}–{brief.targetReadingLevel[1].toFixed(1)}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-text-tertiary">Content Type</div>
                    <div className="text-[12px] font-medium text-text-primary capitalize">
                      {brief.dominantContentType.replace(/_/g, ' ')}
                    </div>
                  </div>
                </div>
                {patterns.length > 0 && (
                  <div>
                    <div className="text-[10px] text-text-tertiary mb-1">Required Elements</div>
                    <div className="flex flex-wrap gap-1">
                      {patterns.map(p => <Badge key={p} variant="neutral">{p}</Badge>)}
                    </div>
                  </div>
                )}
                {Object.keys(brief.headerHierarchy).length > 0 && (
                  <div>
                    <div className="text-[10px] text-text-tertiary mb-1">Header Hierarchy</div>
                    <div className="flex items-center gap-2 text-[11px] text-text-secondary">
                      {Object.entries(brief.headerHierarchy).map(([k, v]) => (
                        <span key={k} className="font-mono">{k}: {v}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Best Company Match */}
          <div className="mb-4">
            <div className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
              Best Company Match
            </div>
            <div className="bg-bg border border-border rounded-md p-3">
              <p className="text-[12px] text-text-secondary leading-[1.55] mb-2 line-clamp-3">
                &ldquo;{query.bestCompanyUnit.snippet}&rdquo;
              </p>
              {query.bestCompanyUnit.url && (
                <a
                  href={query.bestCompanyUnit.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[11px] text-accent hover:underline inline-flex items-center gap-1"
                >
                  {query.bestCompanyUnit.url.replace(/^https?:\/\//, '').slice(0, 45)}
                  <ExternalLink size={10} strokeWidth={1.5} />
                </a>
              )}
            </div>
          </div>

          {/* Mini Cluster Scatter */}
          <div className="mb-4">
            <div className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
              Cluster Neighborhood
            </div>
            <div className="bg-bg border border-border rounded-md overflow-hidden">
              <Plot
                data={[
                  {
                    x: neighborPoints.map(p => p.x),
                    y: neighborPoints.map(p => p.y),
                    text: neighborPoints.map(p => p.label),
                    mode: 'markers' as const,
                    type: 'scatter' as const,
                    marker: { color: 'var(--text-tertiary)', size: 5, opacity: 0.4 },
                    hoverinfo: 'text' as const,
                    name: 'Neighbors',
                  },
                  {
                    x: currentPoints.map(p => p.x),
                    y: currentPoints.map(p => p.y),
                    text: currentPoints.map(p => p.label),
                    mode: 'markers' as const,
                    type: 'scatter' as const,
                    marker: { color: 'var(--accent)', size: 10, symbol: 'diamond' },
                    hoverinfo: 'text' as const,
                    name: 'Current',
                  },
                ]}
                layout={{
                  width: 340,
                  height: 200,
                  margin: { t: 10, r: 10, b: 30, l: 30 },
                  paper_bgcolor: 'transparent',
                  plot_bgcolor: 'transparent',
                  showlegend: false,
                  xaxis: { showgrid: false, zeroline: false, showticklabels: false },
                  yaxis: { showgrid: false, zeroline: false, showticklabels: false },
                }}
                config={{ displayModeBar: false, staticPlot: true }}
              />
            </div>
          </div>

          {/* Section 5: Actions */}
          <div className="space-y-2">
            <Button
              variant="primary"
              className="w-full"
              onClick={() => onAddToCycle(topic, 'current')}
            >
              <Plus size={14} strokeWidth={1.5} className="mr-1.5" />
              Add to Current Cycle
            </Button>
            <Button
              variant="secondary"
              className="w-full"
              onClick={() => onAddToCycle(topic, 'next')}
            >
              <CalendarPlus size={14} strokeWidth={1.5} className="mr-1.5" />
              Add to Next Cycle
            </Button>
            <div className="flex gap-2">
              <Button
                variant="ghost"
                className="flex-1"
                onClick={onDismiss}
              >
                <EyeOff size={14} strokeWidth={1.5} className="mr-1.5" />
                Dismiss
              </Button>
              <Link href="/analytics/lab" className="flex-1">
                <Button variant="ghost" className="w-full">
                  <Compass size={14} strokeWidth={1.5} className="mr-1.5" />
                  View in Lab
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
