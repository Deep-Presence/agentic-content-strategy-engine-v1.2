'use client';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { cn } from '@/lib/utils/cn';
import { Grid3X3 } from 'lucide-react';
import { CLUSTER_PATTERN_RATES, type ClusterPatternRates } from '../data/sample-data';

const PATTERN_KEYS = [
  { key: 'faq', label: 'FAQ' },
  { key: 'definition_opening', label: 'Definition' },
  { key: 'key_takeaways', label: 'Takeaways' },
  { key: 'comparison_table', label: 'Comparison' },
  { key: 'step_by_step', label: 'Step-by-Step' },
  { key: 'research_refs', label: 'Research' },
  { key: 'expert_quotes', label: 'Expert' },
] as const;

type PatternKey = (typeof PATTERN_KEYS)[number]['key'];

/**
 * Compute a background color that interpolates from white (0%) through
 * light ocean (#6a9bcc at ~25%) to deep terracotta (#d97757 at 50%+).
 */
function getCellColor(rate: number): string {
  const pct = Math.min(rate, 1);

  if (pct <= 0.01) {
    return '#faf9f5';
  }

  if (pct <= 0.25) {
    // white → light ocean
    const t = pct / 0.25;
    const r = Math.round(250 + (106 - 250) * t);
    const g = Math.round(249 + (155 - 249) * t);
    const b = Math.round(245 + (204 - 245) * t);
    return `rgb(${r}, ${g}, ${b})`;
  }

  // light ocean → deep terracotta
  const t = Math.min((pct - 0.25) / 0.25, 1);
  const r = Math.round(106 + (217 - 106) * t);
  const g = Math.round(155 + (119 - 155) * t);
  const b = Math.round(204 + (87 - 204) * t);
  return `rgb(${r}, ${g}, ${b})`;
}

/**
 * Choose contrasting text color based on background luminance.
 */
function getTextColor(rate: number): string {
  if (rate < 0.15) return '#141413';
  if (rate < 0.35) return '#141413cc';
  return '#ffffff';
}

export default function ContentPatternMatrix() {
  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <div className="flex items-center gap-2.5">
          <Grid3X3 className="h-5 w-5 text-[#d97757]" />
          <div>
            <CardTitle className="font-serif text-xl text-[#141413]">
              Content Pattern Adoption by Cluster
            </CardTitle>
            <CardDescription className="font-sans text-sm text-[#141413]/50 mt-0.5">
              What percentage of citations in each cluster use each pattern
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Color scale legend */}
        <div className="flex items-center gap-2 mb-4">
          <span className="text-[10px] font-sans text-[#141413]/50">0%</span>
          <div className="flex h-3 flex-1 max-w-[200px] rounded overflow-hidden">
            {Array.from({ length: 20 }, (_, i) => {
              const rate = i / 20;
              return (
                <div
                  key={i}
                  className="flex-1"
                  style={{ backgroundColor: getCellColor(rate * 0.6) }}
                />
              );
            })}
          </div>
          <span className="text-[10px] font-sans text-[#141413]/50">50%+</span>
        </div>

        {/* Heatmap table */}
        <div className="overflow-x-auto -mx-2">
          <div className="min-w-[600px] px-2">
            {/* Header row */}
            <div
              className="grid gap-[2px] mb-[2px]"
              style={{
                gridTemplateColumns: '160px repeat(7, 1fr)',
              }}
            >
              <div />
              {PATTERN_KEYS.map((p) => (
                <div
                  key={p.key}
                  className="text-center py-2 px-1"
                >
                  <span className="text-[11px] font-sans font-medium text-[#141413]/60 leading-tight">
                    {p.label}
                  </span>
                </div>
              ))}
            </div>

            {/* Data rows */}
            {CLUSTER_PATTERN_RATES.map((row) => (
              <div
                key={row.cluster_id}
                className="grid gap-[2px] mb-[2px]"
                style={{
                  gridTemplateColumns: '160px repeat(7, 1fr)',
                }}
              >
                {/* Row label */}
                <div className="flex items-center py-2 pr-2">
                  <span className="text-xs font-sans text-[#141413]/70 leading-tight">
                    <span className="font-medium">{row.cluster_id}</span>{' '}
                    <span className="text-[#141413]/50">{row.cluster_name}</span>
                  </span>
                </div>

                {/* Cells */}
                {PATTERN_KEYS.map((p) => {
                  const rate = row[p.key as keyof ClusterPatternRates] as number;
                  const pctStr = `${Math.round(rate * 100)}%`;

                  return (
                    <div
                      key={p.key}
                      className="flex items-center justify-center rounded-sm py-2.5 transition-colors duration-200"
                      style={{
                        backgroundColor: getCellColor(rate),
                      }}
                      title={`${row.cluster_name} - ${p.label}: ${pctStr}`}
                    >
                      <span
                        className="text-xs font-sans font-medium tabular-nums"
                        style={{ color: getTextColor(rate) }}
                      >
                        {pctStr}
                      </span>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>

        {/* Insight note */}
        <div className="mt-4 px-4 py-3 bg-[#6a9bcc]/[0.06] border border-[#6a9bcc]/15 rounded-lg">
          <p className="text-sm font-sans text-[#141413]/70 leading-relaxed">
            <span className="font-semibold text-[#6a9bcc]">Pattern insight: </span>
            FAQ sections are concentrated in Definition (C5) and Problem/Awareness (C6)
            clusters. Comparison tables dominate in Category Comparison (C3) and
            Decision Criteria (C4). Match your content patterns to the target cluster
            for maximum citation alignment.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
