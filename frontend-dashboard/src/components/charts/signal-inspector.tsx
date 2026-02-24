'use client';

import { Check, X, ArrowUp, ArrowDown, Minus } from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import type { StructuralSignals } from '@/types/gap-analysis';

interface SignalInspectorProps {
  signals: StructuralSignals;
  clusterAverages?: Partial<StructuralSignals>;
  compact?: boolean;
  className?: string;
}

interface NumericSignalProps {
  label: string;
  value: number;
  average?: number;
  format?: 'number' | 'decimal' | 'level';
}

function formatValue(value: number, format: string): string {
  if (format === 'decimal') return value.toFixed(2);
  if (format === 'level') return value.toFixed(1);
  return value.toLocaleString();
}

function ComparisonIndicator({ value, average }: { value: number; average?: number }) {
  if (average == null) return null;
  const diff = value - average;
  const threshold = average * 0.1;

  if (Math.abs(diff) < threshold) {
    return <Minus className="h-3 w-3 text-cream-500" />;
  }
  if (diff > 0) {
    return <ArrowUp className="h-3 w-3 text-sage-400" />;
  }
  return <ArrowDown className="h-3 w-3 text-error" />;
}

function NumericSignal({ label, value, average, format = 'number' }: NumericSignalProps) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-body-sm text-cream-700 font-sans">{label}</span>
      <div className="flex items-center gap-1.5">
        <span className="text-body-sm font-sans font-medium text-cream-950 tabular-nums">
          {formatValue(value, format)}
        </span>
        <ComparisonIndicator value={value} average={average} />
      </div>
    </div>
  );
}

function BooleanSignal({
  label,
  value,
  average,
}: {
  label: string;
  value: boolean;
  average?: boolean;
}) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-body-sm text-cream-700 font-sans">{label}</span>
      <div className="flex items-center gap-1.5">
        {value ? (
          <Check className="h-4 w-4 text-sage-400" />
        ) : (
          <X className="h-4 w-4 text-error" />
        )}
        {average != null && value !== average && (
          <span className="text-micro text-cream-500 font-sans">
            (avg: {average ? 'yes' : 'no'})
          </span>
        )}
      </div>
    </div>
  );
}

function SignalInspector({ signals, clusterAverages, compact, className }: SignalInspectorProps) {
  const avg = clusterAverages;

  return (
    <div className={cn('space-y-4', compact && 'space-y-3', className)}>
      {/* Category A: Text Composition */}
      <div className="rounded-md border border-terracotta-200 bg-terracotta-50 p-3">
        <h4 className="text-caption font-sans font-semibold text-terracotta-500 uppercase tracking-wide mb-2">
          Text Composition
        </h4>
        <div className="space-y-0.5">
          <NumericSignal label="Word Count" value={signals.word_count} average={avg?.word_count} />
          <NumericSignal label="Sentence Count" value={signals.sentence_count} average={avg?.sentence_count} />
          <NumericSignal label="Paragraphs" value={signals.paragraph_count} average={avg?.paragraph_count} />
          <NumericSignal label="Avg Paragraph Length" value={signals.avg_paragraph_length} average={avg?.avg_paragraph_length} />
          <NumericSignal label="Reading Level" value={signals.reading_level} average={avg?.reading_level} format="level" />
          <NumericSignal label="Self-Contained Ratio" value={signals.self_contained_ratio} average={avg?.self_contained_ratio} format="decimal" />
        </div>
      </div>

      {/* Category B: Structural Elements */}
      <div className="rounded-md border border-ocean-200 bg-ocean-50 p-3">
        <h4 className="text-caption font-sans font-semibold text-ocean-500 uppercase tracking-wide mb-2">
          Structural Elements
        </h4>
        <div className="space-y-0.5">
          <NumericSignal label="H1" value={signals.h1_count} average={avg?.h1_count} />
          <NumericSignal label="H2" value={signals.h2_count} average={avg?.h2_count} />
          <NumericSignal label="H3" value={signals.h3_count} average={avg?.h3_count} />
          <NumericSignal label="H4" value={signals.h4_count} average={avg?.h4_count} />
          <NumericSignal label="Lists" value={signals.list_count} average={avg?.list_count} />
          <NumericSignal label="Ordered Lists" value={signals.ordered_list_count} average={avg?.ordered_list_count} />
          <NumericSignal label="Tables" value={signals.table_count} average={avg?.table_count} />
          <NumericSignal label="Code Blocks" value={signals.code_block_count} average={avg?.code_block_count} />
        </div>
      </div>

      {/* Category C: Content Patterns */}
      <div className="rounded-md border border-sage-200 bg-sage-50 p-3">
        <h4 className="text-caption font-sans font-semibold text-sage-500 uppercase tracking-wide mb-2">
          Content Patterns
        </h4>
        <div className="space-y-0.5">
          <BooleanSignal label="FAQ Section" value={signals.has_faq_section} average={avg?.has_faq_section} />
          <BooleanSignal label="Definition Opening" value={signals.has_definition_opening} average={avg?.has_definition_opening} />
          <BooleanSignal label="Key Takeaways" value={signals.has_key_takeaways} average={avg?.has_key_takeaways} />
          <BooleanSignal label="Comparison Table" value={signals.has_comparison_table} average={avg?.has_comparison_table} />
          <BooleanSignal label="Step-by-Step" value={signals.has_step_by_step} average={avg?.has_step_by_step} />
          <BooleanSignal label="Research Refs" value={signals.has_research_refs} average={avg?.has_research_refs} />
          <BooleanSignal label="Expert Quotes" value={signals.has_expert_quotes} average={avg?.has_expert_quotes} />
        </div>
      </div>

      {/* Category D: Factual Density */}
      <div className="rounded-md border border-cream-400 bg-cream-200 p-3">
        <h4 className="text-caption font-sans font-semibold text-cream-800 uppercase tracking-wide mb-2">
          Factual Density
        </h4>
        <div className="space-y-0.5">
          <NumericSignal label="Data Points" value={signals.data_point_count} average={avg?.data_point_count} />
          <NumericSignal label="Citation Density" value={signals.citation_density} average={avg?.citation_density} format="decimal" />
          <NumericSignal label="Named Entity Density" value={signals.named_entity_density} average={avg?.named_entity_density} format="decimal" />
        </div>
      </div>
    </div>
  );
}

export { SignalInspector };
export type { SignalInspectorProps };
