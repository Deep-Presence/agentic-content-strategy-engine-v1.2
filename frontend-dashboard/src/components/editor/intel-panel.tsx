'use client';

import Link from 'next/link';
import { ExternalLink, RotateCcw } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils/cn';
import { EvalScoresPanel } from '@/app/(dashboard)/content-pipeline/components/eval-scores-panel';

interface TargetSignals {
  word_count_range?: [number, number];
  reading_level_range?: [number, number];
  header_count_range?: [number, number];
  h2_count?: number;
  h3_count?: number;
  content_patterns?: string[];
  authority_type?: string;
  content_type?: string;
}

interface CurrentMetrics {
  word_count?: number;
  header_count?: number;
  reading_level?: number;
}

interface EvalScore {
  label: string;
  score: number;
  threshold: number;
}

interface RevisionCycle {
  cycle: number;
  scores: EvalScore[];
  passed: boolean;
}

interface CitationExemplar {
  domain: string;
  similarity: number;
  snippet?: string;
}

interface IntelPanelProps {
  targetSignals?: TargetSignals;
  currentMetrics?: CurrentMetrics;
  gapScore?: number;
  gapClassification?: string;
  evalScores?: EvalScore[];
  revisionHistory?: RevisionCycle[];
  exemplars?: CitationExemplar[];
  briefId?: string;
  onRegenerate?: () => void;
  className?: string;
}

function MetricRow({ label, current, target, inRange }: { label: string; current?: number; target?: string; inRange?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-body-sm font-sans text-cream-700">{label}</span>
      <div className="flex items-center gap-2">
        {current != null && (
          <span className={cn(
            'text-body-sm font-sans tabular-nums font-medium',
            inRange === true ? 'text-sage-400' : inRange === false ? 'text-error' : 'text-cream-800'
          )}>
            {typeof current === 'number' && current % 1 !== 0 ? current.toFixed(1) : current}
          </span>
        )}
        {target && (
          <span className="text-caption font-sans text-cream-500">({target})</span>
        )}
      </div>
    </div>
  );
}

export function IntelPanel({
  targetSignals,
  currentMetrics,
  gapScore,
  gapClassification,
  evalScores,
  revisionHistory,
  exemplars,
  briefId,
  onRegenerate,
  className,
}: IntelPanelProps) {
  const wordCountInRange = targetSignals?.word_count_range && currentMetrics?.word_count != null
    ? currentMetrics.word_count >= targetSignals.word_count_range[0] &&
      currentMetrics.word_count <= targetSignals.word_count_range[1]
    : undefined;

  return (
    <div className={cn('space-y-4 overflow-y-auto', className)}>
      {/* Target Signals */}
      {targetSignals && (
        <Card>
          <CardHeader>
            <CardTitle className="text-heading-4">Target Signals</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {targetSignals.word_count_range && (
              <MetricRow
                label="Word Count"
                current={currentMetrics?.word_count}
                target={`${targetSignals.word_count_range[0]}-${targetSignals.word_count_range[1]}`}
                inRange={wordCountInRange}
              />
            )}
            {targetSignals.reading_level_range && (
              <MetricRow
                label="Reading Level"
                current={currentMetrics?.reading_level}
                target={`${targetSignals.reading_level_range[0]}-${targetSignals.reading_level_range[1]}`}
              />
            )}
            {targetSignals.header_count_range && (
              <MetricRow
                label="Headers"
                current={currentMetrics?.header_count}
                target={`${targetSignals.header_count_range[0]}-${targetSignals.header_count_range[1]}`}
              />
            )}
            {(targetSignals.h2_count != null || targetSignals.h3_count != null) && (
              <div className="flex items-center justify-between">
                <span className="text-body-sm font-sans text-cream-700">Hierarchy</span>
                <span className="text-body-sm font-sans text-cream-800">
                  H2: {targetSignals.h2_count ?? '—'}, H3: {targetSignals.h3_count ?? '—'}
                </span>
              </div>
            )}
            {targetSignals.content_patterns && targetSignals.content_patterns.length > 0 && (
              <div className="space-y-1">
                <span className="text-body-sm font-sans text-cream-700">Patterns</span>
                <div className="flex flex-wrap gap-1">
                  {targetSignals.content_patterns.map((p) => (
                    <Badge key={p} variant="green">{p}</Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Gap Score */}
      {gapScore != null && (
        <Card>
          <CardHeader>
            <CardTitle className="text-heading-4">Gap Score</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <div className="flex items-center gap-3">
              <span className="text-heading-2 font-serif font-semibold text-terracotta-400 tabular-nums">
                {gapScore.toFixed(3)}
              </span>
              {gapClassification && (
                <Badge variant="terracotta">{gapClassification}</Badge>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Eval Scores */}
      {evalScores && evalScores.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-heading-4">Evaluator Scores</CardTitle>
          </CardHeader>
          <CardContent>
            <EvalScoresPanel scores={evalScores} />
          </CardContent>
        </Card>
      )}

      {/* Revision History */}
      {revisionHistory && revisionHistory.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-heading-4">Revision History</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {revisionHistory.map((cycle) => (
              <div key={cycle.cycle} className="space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-body-sm font-sans font-medium text-cream-800">
                    Cycle {cycle.cycle}
                  </span>
                  <Badge variant={cycle.passed ? 'green' : 'error'}>
                    {cycle.passed ? 'Passed' : 'Failed'}
                  </Badge>
                </div>
                <div className="text-caption font-sans text-cream-600">
                  {cycle.scores.map((s) => `${s.label}: ${s.score.toFixed(2)}`).join(' | ')}
                </div>
                {cycle.cycle < revisionHistory.length && <Separator />}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Top Citation Exemplars */}
      {exemplars && exemplars.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-heading-4">Top Citation Exemplars</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {exemplars.slice(0, 3).map((ex, idx) => (
              <div key={idx} className="space-y-0.5">
                <div className="flex items-center justify-between">
                  <span className="text-body-sm font-sans font-medium text-cream-800">
                    {idx + 1}. {ex.domain}
                  </span>
                  <span className="text-caption font-sans tabular-nums text-ocean-400">
                    {ex.similarity.toFixed(2)}
                  </span>
                </div>
                {ex.snippet && (
                  <p className="text-caption font-body text-cream-600 line-clamp-2">
                    {ex.snippet}
                  </p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Actions */}
      <Card>
        <CardContent className="space-y-2">
          <Link
            href="/embedding-lab"
            className="flex items-center gap-2 px-3 py-2 text-body-sm font-sans text-ocean-400 hover:bg-ocean-50 rounded-md transition-colors"
          >
            <ExternalLink className="h-4 w-4" />
            Open in Embedding Lab
          </Link>
          {briefId && (
            <Link
              href={`/signal-analysis/briefs/${briefId}`}
              className="flex items-center gap-2 px-3 py-2 text-body-sm font-sans text-ocean-400 hover:bg-ocean-50 rounded-md transition-colors"
            >
              <ExternalLink className="h-4 w-4" />
              View Gap Brief
            </Link>
          )}
          {onRegenerate && (
            <Button variant="secondary" size="sm" onClick={onRegenerate} className="w-full">
              <RotateCcw className="h-4 w-4" />
              Regenerate
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
