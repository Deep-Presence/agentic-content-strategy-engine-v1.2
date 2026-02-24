'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, ChevronDown, ChevronRight, ExternalLink, Dna, FileText } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils/cn';
import type { GapBrief, CitationExemplar, StructuralSignals } from '@/types/gap-analysis';

interface GapBriefDetailProps {
  brief: GapBrief;
  className?: string;
}

const CLASSIFICATION_BADGE = {
  significant_gap: { variant: 'error' as const, label: 'Significant Gap' },
  gap_to_close: { variant: 'warning' as const, label: 'Gap to Close' },
  roughly_equal: { variant: 'default' as const, label: 'Roughly Equal' },
  company_wins: { variant: 'green' as const, label: 'Company Wins' },
} as const;

export function GapBriefDetail({ brief, className }: GapBriefDetailProps) {
  const classification = CLASSIFICATION_BADGE[brief.gap_classification];

  return (
    <div className={cn('space-y-6', className)}>
      {/* Header */}
      <div>
        <Link
          href="/signal-analysis"
          className="inline-flex items-center gap-1 text-body-sm font-sans text-ocean-500 hover:text-ocean-600 mb-4 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to Analysis
        </Link>

        <h2 className="font-serif text-heading-1 font-semibold text-cream-950 mb-2">
          {brief.query_text}
        </h2>
        <div className="flex items-center gap-3">
          <Badge variant="blue">{brief.cluster} ({brief.cluster_id})</Badge>
          <Badge variant={classification.variant}>{classification.label}</Badge>
          <span className="text-body-sm font-sans text-cream-600">
            Gap Score: <span className="font-semibold text-cream-900">{brief.gap_score.toFixed(3)}</span>
          </span>
        </div>
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Content Brief */}
        <div className="lg:col-span-1 space-y-4">
          <Card accent="ocean">
            <CardContent className="p-5 space-y-4">
              <h3 className="font-serif text-heading-3 font-semibold text-cream-950">
                Content Brief
              </h3>

              <div className="space-y-3">
                <BriefField
                  label="Target Word Count"
                  value={`${brief.content_brief.target_word_count.min.toLocaleString()}–${brief.content_brief.target_word_count.max.toLocaleString()}`}
                />
                <BriefField
                  label="Reading Level"
                  value={`${brief.content_brief.target_reading_level.min.toFixed(1)}–${brief.content_brief.target_reading_level.max.toFixed(1)}`}
                />
                <BriefField
                  label="Recommended Headers"
                  value={brief.content_brief.recommended_header_count.toString()}
                />
                <BriefField
                  label="Header Hierarchy"
                  value={Object.entries(brief.content_brief.header_hierarchy)
                    .map(([k, v]) => `${k}: ${v}`)
                    .join(', ')}
                />
                <BriefField
                  label="Content Patterns"
                  value={brief.content_brief.content_patterns.join(', ')}
                />
                <BriefField label="Authority Type" value={brief.content_brief.dominant_authority} />
                <BriefField label="Content Type" value={brief.content_brief.dominant_content_type} />
                <BriefField
                  label="Exemplars Analyzed"
                  value={brief.content_brief.exemplars_analyzed.toString()}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-5 space-y-3">
              <h3 className="font-serif text-heading-4 font-semibold text-cream-950">
                Best Company Match
              </h3>
              <p className="text-body-sm font-sans text-cream-700">
                Unit: <span className="font-medium">{brief.best_company_unit.unit_id}</span>
              </p>
              <p className="text-body-sm font-sans text-cream-700">
                Similarity: <span className="font-semibold">{brief.best_company_unit.similarity.toFixed(3)}</span>
              </p>
              {brief.best_company_unit.snippet && (
                <p className="text-body-sm font-body text-cream-600 italic line-clamp-4">
                  &ldquo;{brief.best_company_unit.snippet}&rdquo;
                </p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Citation Exemplars */}
        <div className="lg:col-span-2 space-y-4">
          <h3 className="font-serif text-heading-3 font-semibold text-cream-950">
            Top Citation Exemplars
          </h3>
          {brief.top_exemplars.length === 0 ? (
            <Card>
              <CardContent className="p-8 text-center">
                <p className="text-body-sm text-cream-600">No citation exemplars available.</p>
              </CardContent>
            </Card>
          ) : (
            brief.top_exemplars.map((exemplar, index) => (
              <ExemplarCard key={index} exemplar={exemplar} rank={index + 1} />
            ))
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3 pt-4 border-t border-cream-400">
        <Link href={`/content-pipeline?create=true&query=${brief.query_id}&cluster=${brief.cluster_id}`}>
          <Button variant="primary">
            <FileText className="h-4 w-4" />
            Create Content Brief
          </Button>
        </Link>
        <Link href={`/embedding-lab?company=webflow&query=${brief.query_id}`}>
          <Button variant="secondary">
            <Dna className="h-4 w-4" />
            Open in Embedding Lab
          </Button>
        </Link>
      </div>
    </div>
  );
}

interface BriefFieldProps {
  label: string;
  value: string;
}

function BriefField({ label, value }: BriefFieldProps) {
  return (
    <div>
      <p className="text-micro font-sans text-cream-600 uppercase tracking-wide">{label}</p>
      <p className="text-body-sm font-sans text-cream-900 mt-0.5">{value}</p>
    </div>
  );
}

interface ExemplarCardProps {
  exemplar: CitationExemplar;
  rank: number;
}

function ExemplarCard({ exemplar, rank }: ExemplarCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="flex items-center gap-2">
            <span className="text-caption font-sans font-semibold text-ocean-500">
              #{rank}
            </span>
            <span className="text-body-sm font-sans font-medium text-cream-900">
              {exemplar.domain}
            </span>
            <Badge variant="default">{exemplar.authority_type}</Badge>
            <Badge variant="default">{exemplar.content_type}</Badge>
          </div>
          <span className="text-body-sm font-sans font-semibold text-cream-950 tabular-nums shrink-0">
            {exemplar.similarity.toFixed(3)}
          </span>
        </div>

        <p className="text-body-sm font-body text-cream-700 line-clamp-2 mb-2">
          &ldquo;{exemplar.snippet}&rdquo;
        </p>

        {exemplar.url && (
          <a
            href={exemplar.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-caption font-sans text-ocean-500 hover:text-ocean-600 transition-colors mb-2"
          >
            {exemplar.url.slice(0, 60)}...
            <ExternalLink className="h-3 w-3" />
          </a>
        )}

        {/* 45-Signal Card toggle */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-body-sm font-sans font-medium text-ocean-500 hover:text-ocean-600 transition-colors mt-1"
        >
          {expanded ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
          45-Signal Analysis
        </button>

        {expanded && <SignalGrid signals={exemplar.structural_signals} />}
      </CardContent>
    </Card>
  );
}

interface SignalGridProps {
  signals: StructuralSignals;
}

function SignalGrid({ signals }: SignalGridProps) {
  const categories = [
    {
      name: 'Text Composition',
      color: 'ocean',
      items: [
        { label: 'Word Count', value: signals.word_count },
        { label: 'Sentence Count', value: signals.sentence_count },
        { label: 'Paragraph Count', value: signals.paragraph_count },
        { label: 'Avg Para Length', value: signals.avg_paragraph_length?.toFixed(1) },
        { label: 'Reading Level', value: signals.reading_level?.toFixed(1) },
        { label: 'Self-Contained', value: signals.self_contained_ratio?.toFixed(2) },
      ],
    },
    {
      name: 'Structural Elements',
      color: 'sage',
      items: [
        { label: 'H1', value: signals.h1_count },
        { label: 'H2', value: signals.h2_count },
        { label: 'H3', value: signals.h3_count },
        { label: 'H4', value: signals.h4_count },
        { label: 'Lists', value: signals.list_count },
        { label: 'Ordered Lists', value: signals.ordered_list_count },
        { label: 'Tables', value: signals.table_count },
        { label: 'Code Blocks', value: signals.code_block_count },
      ],
    },
    {
      name: 'Content Patterns',
      color: 'terracotta',
      items: [
        { label: 'FAQ Section', value: signals.has_faq_section ? 'Yes' : 'No' },
        { label: 'Definition Opening', value: signals.has_definition_opening ? 'Yes' : 'No' },
        { label: 'Key Takeaways', value: signals.has_key_takeaways ? 'Yes' : 'No' },
        { label: 'Comparison Table', value: signals.has_comparison_table ? 'Yes' : 'No' },
        { label: 'Step-by-Step', value: signals.has_step_by_step ? 'Yes' : 'No' },
        { label: 'Research Refs', value: signals.has_research_refs ? 'Yes' : 'No' },
        { label: 'Expert Quotes', value: signals.has_expert_quotes ? 'Yes' : 'No' },
      ],
    },
    {
      name: 'Factual Density',
      color: 'cream',
      items: [
        { label: 'Data Points', value: signals.data_point_count },
        { label: 'Citation Density', value: signals.citation_density?.toFixed(3) },
        { label: 'Named Entities', value: signals.named_entity_density?.toFixed(3) },
      ],
    },
  ];

  const colorClasses = {
    ocean: 'bg-ocean-50 border-ocean-200 text-ocean-600',
    sage: 'bg-sage-50 border-sage-200 text-sage-600',
    terracotta: 'bg-terracotta-50 border-terracotta-200 text-terracotta-500',
    cream: 'bg-cream-200 border-cream-400 text-cream-700',
  } as const;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-3 pt-3 border-t border-cream-300">
      {categories.map((cat) => (
        <div key={cat.name}>
          <h5
            className={cn(
              'text-micro font-sans font-semibold uppercase tracking-wide mb-2',
              cat.color === 'ocean' && 'text-ocean-500',
              cat.color === 'sage' && 'text-sage-500',
              cat.color === 'terracotta' && 'text-terracotta-500',
              cat.color === 'cream' && 'text-cream-700'
            )}
          >
            {cat.name}
          </h5>
          <div className="space-y-1">
            {cat.items.map((item) => (
              <div
                key={item.label}
                className={cn(
                  'flex items-center justify-between px-2 py-1 rounded text-micro font-sans border',
                  colorClasses[cat.color as keyof typeof colorClasses]
                )}
              >
                <span>{item.label}</span>
                <span className="font-semibold">{item.value ?? '—'}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
