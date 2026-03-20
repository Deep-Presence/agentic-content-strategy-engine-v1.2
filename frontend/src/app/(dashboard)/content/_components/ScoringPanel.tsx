'use client';

import { cn } from '@/lib/utils';
import { Button, Badge, ProgressBar } from '@/components/ui';
import type { Platform } from '@/types';
import type { ExtendedBrief } from './content-data';
import { platformLabels, platformColors } from './content-data';
import { useState, useEffect, useRef } from 'react';
import { ExternalLink, CheckSquare, Square } from 'lucide-react';

interface ScoringPanelProps {
  brief: ExtendedBrief;
  editorContent: string;
}

const platforms: Platform[] = ['chatgpt', 'claude', 'perplexity', 'google_ai_overview', 'gemini'];

interface StructuralMetrics {
  wordCount: number;
  headerCount: number;
  listCount: number;
  citationCount: number;
  readingLevel: string;
}

function computeStructural(html: string): StructuralMetrics {
  const text = html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
  const wordCount = text ? text.split(/\s+/).length : 0;
  const headerCount = (html.match(/<h[2-3][^>]*>/gi) || []).length;
  const listCount = (html.match(/<li[^>]*>/gi) || []).length;
  const citationCount = (html.match(/\[.+?\]/g) || []).length;
  const avgWordLength = text ? text.replace(/\s/g, '').length / Math.max(wordCount, 1) : 0;
  const readingLevel = avgWordLength > 5.5 ? 'Advanced' : avgWordLength > 4.5 ? 'Intermediate' : 'Basic';

  return { wordCount, headerCount, listCount, citationCount, readingLevel };
}

const interlinkSuggestions = [
  { url: '/blog/cap-table-management', anchorText: 'cap table management guide', applied: true },
  { url: '/blog/equity-compensation-101', anchorText: 'equity compensation basics', applied: false },
  { url: '/blog/409a-valuations', anchorText: '409A valuation process', applied: false },
  { url: '/blog/series-a-checklist', anchorText: 'Series A fundraising checklist', applied: true },
];

export function ScoringPanel({ brief, editorContent }: ScoringPanelProps) {
  const [metrics, setMetrics] = useState<StructuralMetrics>(() => computeStructural(editorContent));
  const [links, setLinks] = useState(interlinkSuggestions);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  // Debounced structural recalculation
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setMetrics(computeStructural(editorContent));
    }, 500);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [editorContent]);

  const scores = brief.cpsActual || brief.cpsPredict;
  const voiceCompliance = 72;

  return (
    <div className="w-full h-full overflow-y-auto p-4 space-y-5">
      {/* CPS Per Platform */}
      <section>
        <h3 className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-3">
          Citation Prediction Score
        </h3>
        <div className="space-y-2">
          {platforms.map((p) => {
            const score = scores[p] || 0;
            return (
              <div key={p}>
                <div className="flex justify-between items-center mb-0.5">
                  <span className="text-[11px] text-text-secondary">{platformLabels[p]}</span>
                  <span className="text-[11px] font-medium text-text-primary">{score}</span>
                </div>
                <div className="h-[6px] w-full bg-bg rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-[width] duration-500"
                    style={{
                      width: `${score}%`,
                      backgroundColor: platformColors[p],
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Structural Compliance */}
      <section>
        <h3 className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-3">
          Structural Compliance
        </h3>
        <div className="space-y-2">
          <StructuralRow
            label="Word Count"
            current={metrics.wordCount}
            target={brief.structuralTargets.words}
            unit="words"
          />
          <StructuralRow
            label="Headers"
            current={metrics.headerCount}
            target={brief.structuralTargets.headers}
            unit="headers"
          />
          <StructuralRow
            label="List Items"
            current={metrics.listCount}
            target={brief.structuralTargets.lists}
            unit="items"
          />
          <StructuralRow
            label="Citations"
            current={metrics.citationCount}
            target={brief.structuralTargets.citations}
            unit="citations"
          />
          <div className="flex justify-between items-center">
            <span className="text-[11px] text-text-secondary">Reading Level</span>
            <Badge variant="neutral">{metrics.readingLevel}</Badge>
          </div>
        </div>
      </section>

      {/* Voice Compliance */}
      <section>
        <h3 className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
          Voice Compliance
        </h3>
        <div className="flex items-center gap-2">
          <ProgressBar value={voiceCompliance} className="flex-1" />
          <span className="text-[11px] font-medium text-text-primary">{voiceCompliance}%</span>
        </div>
      </section>

      {/* Interlink Suggestions */}
      <section>
        <h3 className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
          Interlink Suggestions
        </h3>
        <div className="space-y-1.5">
          {links.map((link, i) => (
            <button
              key={i}
              onClick={() => {
                setLinks((prev) =>
                  prev.map((l, j) => (j === i ? { ...l, applied: !l.applied } : l))
                );
              }}
              className="flex items-start gap-2 w-full text-left p-1.5 rounded-sm hover:bg-accent-subtle transition-colors cursor-pointer"
            >
              {link.applied ? (
                <CheckSquare size={12} strokeWidth={1.5} className="text-accent mt-0.5 flex-shrink-0" />
              ) : (
                <Square size={12} strokeWidth={1.5} className="text-text-tertiary mt-0.5 flex-shrink-0" />
              )}
              <div className="min-w-0">
                <span className="text-[11px] text-accent block truncate">{link.anchorText}</span>
                <span className="text-[10px] text-text-tertiary block truncate">{link.url}</span>
              </div>
            </button>
          ))}
        </div>
      </section>

      {/* View in Embedding Space */}
      <Button variant="secondary" size="sm" className="w-full">
        <ExternalLink size={11} strokeWidth={1.5} className="mr-1.5" />
        View in Embedding Space
      </Button>
    </div>
  );
}

function StructuralRow({
  label,
  current,
  target,
  unit,
}: {
  label: string;
  current: number;
  target: number;
  unit: string;
}) {
  const ratio = Math.min(current / target, 1);
  const isOver = current > target * 1.2;
  const isMet = current >= target;

  return (
    <div>
      <div className="flex justify-between items-center mb-0.5">
        <span className="text-[11px] text-text-secondary">{label}</span>
        <span
          className={cn(
            'text-[11px] font-medium',
            isOver ? 'text-warning' : isMet ? 'text-success' : 'text-text-primary'
          )}
        >
          {current}/{target} {unit}
        </span>
      </div>
      <ProgressBar value={ratio * 100} />
    </div>
  );
}
