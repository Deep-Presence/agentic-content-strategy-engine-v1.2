'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import { Button, Badge, Toast } from '@/components/ui';
import type { Query } from '@/types';

interface CitationDrillDownProps {
  query: Query | null;
  onClose: () => void;
  onAddToContentCycle?: (query: Query) => void;
  isSending?: boolean;
}

export function CitationDrillDown({ query, onClose, onAddToContentCycle, isSending }: CitationDrillDownProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [toastOpen, setToastOpen] = useState(false);
  const closeToast = useCallback(() => setToastOpen(false), []);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  // Close on click outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);

  const topExemplar = query?.citedExemplars[0];
  const companyStructure = query?.bestCompanyUnit
    ? {
        words: 800,
        headers: 6,
        lists: 3,
        citations: 2,
      }
    : null;

  const citedStructure = topExemplar?.structure;

  // Compute max for scaling bars
  const metrics = ['words', 'headers', 'lists', 'citations'] as const;

  return (
    <AnimatePresence mode="wait">
      {query && (
        <motion.div
          ref={panelRef}
          initial={{ x: 360 }}
          animate={{ x: 0 }}
          exit={{ x: 360 }}
          transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          className="fixed right-0 top-0 h-full w-[360px] bg-surface border-l border-border z-50 overflow-y-auto"
        >
          <div className="p-4 space-y-4">
            {/* Header */}
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-1">
                  Query Drill-Down
                </p>
                <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em] leading-[1.3]">
                  {query.text}
                </h3>
              </div>
              <button
                onClick={onClose}
                className="p-1 rounded-sm hover:bg-surface-raised text-text-tertiary hover:text-text-primary transition-colors cursor-pointer"
              >
                <X size={16} strokeWidth={1.5} />
              </button>
            </div>

            {/* Metadata */}
            <div className="flex flex-wrap gap-1.5">
              <Badge variant="info">{query.cluster}</Badge>
              <Badge
                variant={
                  query.classification === 'significant_gap'
                    ? 'error'
                    : query.classification === 'company_wins'
                      ? 'success'
                      : query.classification === 'gap_to_close'
                        ? 'warning'
                        : 'neutral'
                }
              >
                {query.classification.replace(/_/g, ' ')}
              </Badge>
              {query.companyCited && <Badge variant="success">Company Cited</Badge>}
            </div>

            {/* Gap Score */}
            <div className="bg-bg border border-border rounded-md p-3">
              <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-1">
                Gap Score
              </p>
              <p className="font-mono text-[20px] font-semibold text-text-primary">
                {query.gap.toFixed(4)}
              </p>
              <p className="text-[11px] text-text-secondary mt-0.5">
                Avg citation similarity: {query.avgCitationSimilarity.toFixed(4)}
              </p>
              <p className="text-[11px] text-text-secondary">
                Company similarity: {query.bestCompanyUnit.similarity.toFixed(4)}
              </p>
            </div>

            {/* Structural Comparison */}
            {citedStructure && (
              <div className="space-y-3">
                <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em]">
                  Structural Comparison
                </h3>
                <div className="flex items-center gap-3 text-[10px] text-text-tertiary mb-1">
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-sm bg-accent" /> Your Page
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-sm bg-text-tertiary/30" /> Cited Pages
                  </span>
                </div>
                {metrics.map((metric) => {
                  const yourVal = companyStructure?.[metric] ?? 0;
                  const citedVal = citedStructure[metric] ?? 0;
                  const max = Math.max(yourVal, citedVal, 1);
                  const yourPct = (yourVal / max) * 100;
                  const citedPct = (citedVal / max) * 100;

                  return (
                    <div key={metric} className="space-y-1">
                      <div className="flex justify-between">
                        <span className="text-[10px] uppercase tracking-[0.06em] text-text-tertiary">
                          {metric}
                        </span>
                        <span className="text-[10px] font-mono text-text-secondary">
                          {yourVal} vs {citedVal}
                        </span>
                      </div>
                      <div className="space-y-0.5">
                        <div
                          className="h-[6px] bg-accent rounded-sm transition-all"
                          style={{ width: `${yourPct}%` }}
                        />
                        <div
                          className="h-[6px] bg-text-tertiary/30 rounded-sm transition-all"
                          style={{ width: `${citedPct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Top Cited Exemplars */}
            {query.citedExemplars.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em]">
                  Cited Exemplars
                </h3>
                {query.citedExemplars.slice(0, 5).map((ex, i) => (
                  <div
                    key={i}
                    className="bg-bg border border-border rounded-md p-2.5 space-y-1"
                  >
                    <p className="text-[11px] font-mono text-accent truncate">
                      {ex.domain}
                    </p>
                    <p className="text-[10px] text-text-secondary truncate">
                      {ex.url}
                    </p>
                    <div className="flex gap-2 text-[10px] text-text-tertiary">
                      <span>sim: {ex.similarity.toFixed(4)}</span>
                      {ex.structure.words > 0 && (
                        <span>{ex.structure.words} words</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Best Company Match */}
            {query.bestCompanyUnit.url && (
              <div className="space-y-1">
                <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em]">
                  Best Company Match
                </h3>
                <div className="bg-bg border border-border rounded-md p-2.5">
                  <p className="text-[11px] font-mono text-accent truncate">
                    {query.bestCompanyUnit.url}
                  </p>
                  <p className="text-[10px] text-text-secondary mt-1">
                    Similarity: {query.bestCompanyUnit.similarity.toFixed(4)}
                  </p>
                  {query.bestCompanyUnit.snippet && (
                    <p className="text-[11px] text-text-secondary mt-1 line-clamp-3">
                      {query.bestCompanyUnit.snippet}
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Action Button */}
            <Button
              variant="primary"
              className="w-full mt-4"
              disabled={isSending}
              onClick={() => {
                if (query && onAddToContentCycle) {
                  onAddToContentCycle(query);
                }
              }}
            >
              {isSending ? 'Adding...' : 'Add to Content Cycle'}
            </Button>
          </div>

          <Toast
            open={toastOpen}
            onClose={closeToast}
            variant="success"
            message="Content pipeline started. Track progress in Content Studio."
          />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
