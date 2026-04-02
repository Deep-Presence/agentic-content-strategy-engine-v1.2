'use client';

import { useState, useMemo } from 'react';
import { useThemeColors } from './use-theme-colors';
import type { SignalCorrelationRow, PlatformSignalRow } from './embedding-lab-data';
import { SIGNAL_CORRELATIONS, PLATFORM_SIGNALS, CLUSTERS } from './embedding-lab-data';

const PLATFORM_LABELS: Record<string, string> = {
  chatgpt: 'ChatGPT', claude: 'Claude', gemini: 'Gemini', perplexity: 'Perplexity', google_ai_overview: 'Google AI',
};

const CATEGORY_COLORS: Record<string, string> = {
  structure: '#6CB8D2',
  authority: '#3ECF8E',
  content: '#FFB224',
  technical: '#8B5CF6',
  engagement: '#EC4899',
};

// ─── Component ──────────────────────────────────────────────────────────────

export function CorrelationAnalysis({
  correlations = SIGNAL_CORRELATIONS,
  platformSignals = PLATFORM_SIGNALS,
}: {
  correlations?: SignalCorrelationRow[];
  platformSignals?: PlatformSignalRow[];
}) {
  const colors = useThemeColors();
  const [selectedCluster, setSelectedCluster] = useState<string>('all');

  const sortedCorrelations = useMemo(
    () => [...correlations].sort((a, b) => b.correlation - a.correlation),
    [correlations],
  );

  const maxAbsCorr = useMemo(
    () => Math.max(...correlations.map(c => Math.abs(c.correlation))),
    [correlations],
  );

  return (
    <div className="space-y-3">
      {/* Cluster pills */}
      <div className="flex items-center gap-1 flex-wrap">
        <button
          onClick={() => setSelectedCluster('all')}
          className={`px-2.5 h-[24px] text-[10px] font-medium rounded-full border transition-colors cursor-pointer ${
            selectedCluster === 'all' ? 'border-accent bg-accent-subtle text-accent' : 'border-border text-text-tertiary hover:text-text-secondary'
          }`}
        >All</button>
        {CLUSTERS.map(c => (
          <button
            key={c.id}
            onClick={() => setSelectedCluster(c.id)}
            className={`px-2.5 h-[24px] text-[10px] font-medium rounded-full border transition-colors cursor-pointer ${
              selectedCluster === c.id ? 'border-accent bg-accent-subtle text-accent' : 'border-border text-text-tertiary hover:text-text-secondary'
            }`}
          >{c.name}</button>
        ))}
      </div>

      {/* Diverging bar chart */}
      <div className="bg-surface border border-border rounded-md p-3">
        <h4 className="text-[9px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-3">
          Signal Correlation with Citation Similarity
        </h4>
        <div className="space-y-[2px]">
          {sortedCorrelations.map((row) => {
            const isPos = row.correlation >= 0;
            const barPct = (Math.abs(row.correlation) / maxAbsCorr) * 100;
            const catColor = CATEGORY_COLORS[row.category] || colors.textTertiary;

            return (
              <div key={row.signal} className="flex items-center gap-1.5 h-[20px] group">
                <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: catColor }} title={row.category} />
                <span className="text-[10px] text-text-tertiary w-[160px] truncate shrink-0 group-hover:text-text-secondary transition-colors">
                  {row.signal}
                </span>
                <div className="flex-1 flex items-center h-[12px]">
                  <div className="flex-1 flex justify-end">
                    {!isPos && (
                      <div className="h-[10px] rounded-l-sm" style={{
                        width: `${barPct}%`,
                        background: `linear-gradient(to left, ${colors.error}CC, ${colors.error}55)`,
                      }} />
                    )}
                  </div>
                  <div className="w-px h-[16px] shrink-0" style={{ backgroundColor: colors.borderStrong }} />
                  <div className="flex-1">
                    {isPos && (
                      <div className="h-[10px] rounded-r-sm" style={{
                        width: `${barPct}%`,
                        background: `linear-gradient(to right, ${colors.success}55, ${colors.success}CC)`,
                      }} />
                    )}
                  </div>
                </div>
                <span className={`text-[9px] font-mono w-[38px] text-right shrink-0 ${isPos ? 'text-success' : 'text-error'}`}>
                  {row.correlation > 0 ? '+' : ''}{row.correlation.toFixed(2)}
                </span>
                <span className="text-[8px] font-mono text-text-tertiary w-[36px] text-right shrink-0 opacity-60">
                  p={row.pValue < 0.001 ? '<.001' : row.pValue.toFixed(3)}
                </span>
              </div>
            );
          })}
        </div>

        {/* Category legend */}
        <div className="flex items-center gap-3 mt-3 pt-2 border-t border-border">
          {Object.entries(CATEGORY_COLORS).map(([cat, color]) => (
            <div key={cat} className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
              <span className="text-[9px] text-text-tertiary capitalize">{cat}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Platform Signal Divergence */}
      <div>
        <h4 className="text-[9px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">Platform Signal Divergence</h4>
        <div className="grid grid-cols-4 gap-2">
          {platformSignals.map(ps => (
            <div key={ps.platform} className="bg-surface border border-border rounded-md p-3">
              <div className="text-[12px] font-medium text-text-primary mb-2">{PLATFORM_LABELS[ps.platform] || ps.platform}</div>
              <div className="space-y-1.5">
                {ps.topSignals.map((sig, i) => (
                  <div key={sig.signal} className="flex items-center gap-1.5">
                    <span className="text-[9px] font-mono text-text-tertiary w-2.5 shrink-0">{i + 1}</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-[10px] text-text-tertiary truncate">{sig.signal}</div>
                      <div className="w-full h-[3px] bg-bg rounded-full mt-0.5">
                        <div className="h-full rounded-full" style={{ width: `${sig.importance * 100}%`, backgroundColor: colors.accent }} />
                      </div>
                    </div>
                    <span className="text-[9px] font-mono text-text-tertiary shrink-0">{sig.importance.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
