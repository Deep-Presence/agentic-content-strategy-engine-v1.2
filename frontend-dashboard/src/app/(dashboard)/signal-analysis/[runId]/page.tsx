'use client';

import { useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { AlertCircle, RotateCw, XCircle } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import { usePipelineStore } from '@/stores/pipeline-store';
import { useEventStream } from '@/lib/hooks/use-event-stream';
import { gapAnalysis } from '@/lib/api/gap-analysis';
import { tasks } from '@/lib/api/tasks';
import { relativeTime } from '@/lib/utils/format';
import { STATUS_COLORS } from '@/lib/utils/constants';
import { StepProgress } from '../components/step-progress';
import type { GapAnalysisStep } from '@/types/gap-analysis';
import type { TaskStatus } from '@/types/common';

export default function RunDetailPage() {
  const params = useParams<{ runId: string }>();
  const router = useRouter();
  const { toast } = useToast();
  const runId = params.runId;

  const {
    activeRunStatus,
    steps,
    setActiveRun,
    updateStep,
    reset,
  } = usePipelineStore();

  // Fetch initial status
  useEffect(() => {
    let cancelled = false;

    async function fetchStatus() {
      try {
        const status = await gapAnalysis.getStatus(runId);
        if (!cancelled) {
          setActiveRun(runId, status.status as TaskStatus);
        }
      } catch {
        if (!cancelled) {
          toast('Failed to fetch run status', 'error');
        }
      }
    }

    fetchStatus();
    return () => { cancelled = true; };
  }, [runId, setActiveRun, toast]);

  // SSE event handler
  const handleEvent = useCallback(
    (event: string, data: Record<string, unknown>) => {
      const stepEvents: GapAnalysisStep[] = [
        's1_embed_assets', 's2_generate_queries', 's3_search_platforms',
        's4_enrich_citations', 's5_embed_content', 's6_analyze',
        's7_visualize', 's8_generate_report',
      ];

      if (stepEvents.includes(event as GapAnalysisStep)) {
        // Current step starts; mark previous step as completed
        const stepIndex = stepEvents.indexOf(event as GapAnalysisStep);
        if (stepIndex > 0) {
          updateStep(stepEvents[stepIndex - 1], 'completed');
        }
        updateStep(event as GapAnalysisStep, 'active');
      } else if (event === 'completed') {
        // Mark last active step as completed
        const lastStep = stepEvents[stepEvents.length - 1];
        updateStep(lastStep, 'completed');
        setActiveRun(runId, 'completed');
        toast('Analysis completed successfully!', 'success');
        // Navigate to results after a short delay
        setTimeout(() => router.push('/signal-analysis'), 1500);
      } else if (event === 'failed') {
        setActiveRun(runId, 'failed');
        toast(
          (data?.error as string) || 'Pipeline failed. Check logs for details.',
          'error'
        );
      } else if (event === 'cancelled') {
        setActiveRun(runId, 'cancelled');
        toast('Pipeline was cancelled.', 'warning');
      }
    },
    [runId, updateStep, setActiveRun, toast, router]
  );

  const isRunning = activeRunStatus === 'running' || activeRunStatus === 'pending';

  const { connected, error: sseError } = useEventStream(
    isRunning ? runId : null,
    { onEvent: handleEvent }
  );

  async function handleCancel() {
    try {
      await tasks.cancel(runId);
      toast('Pipeline cancellation requested.', 'info');
    } catch {
      toast('Failed to cancel pipeline.', 'error');
    }
  }

  function handleRetry() {
    reset();
    router.push('/signal-analysis/run');
  }

  if (!activeRunStatus) {
    return (
      <div>
        <PageHeader title="Deep Signal Analysis" description="Loading run details..." />
        <div className="mt-6 space-y-4">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-96 w-full rounded-md" />
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Deep Signal Analysis"
        description={`Run ${runId.slice(0, 8)}...`}
        actions={
          activeRunStatus === 'running' ? (
            <Button variant="danger" onClick={handleCancel}>
              <XCircle className="h-4 w-4" />
              Cancel Run
            </Button>
          ) : activeRunStatus === 'failed' ? (
            <Button variant="secondary" onClick={handleRetry}>
              <RotateCw className="h-4 w-4" />
              Retry
            </Button>
          ) : undefined
        }
      />

      <div className="mt-6 space-y-4">
        {/* Status bar */}
        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Badge className={STATUS_COLORS[activeRunStatus] || STATUS_COLORS.pending}>
                {activeRunStatus}
              </Badge>
              {connected && (
                <span className="flex items-center gap-1.5 text-caption font-sans text-sage-500">
                  <span className="w-1.5 h-1.5 rounded-full bg-sage-400 animate-pulse" />
                  Connected
                </span>
              )}
            </div>
            {sseError && (
              <span className="text-caption font-sans text-warning">{sseError}</span>
            )}
          </CardContent>
        </Card>

        {/* Failed state */}
        {activeRunStatus === 'failed' && (
          <Card accent="sage">
            <CardContent className="p-6 text-center">
              <AlertCircle className="h-10 w-10 text-error mx-auto mb-3" />
              <h3 className="font-serif text-heading-3 font-semibold text-cream-950 mb-2">
                Pipeline Failed
              </h3>
              <p className="text-body-sm text-cream-600 mb-4">
                The analysis encountered an error. You can retry with the same or different parameters.
              </p>
              <Button onClick={handleRetry}>
                <RotateCw className="h-4 w-4" />
                Run New Analysis
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Completed state */}
        {activeRunStatus === 'completed' && (
          <Card accent="sage">
            <CardContent className="p-6 text-center">
              <h3 className="font-serif text-heading-3 font-semibold text-cream-950 mb-2">
                Analysis Complete
              </h3>
              <p className="text-body-sm text-cream-600 mb-4">
                Redirecting to results...
              </p>
              <Button onClick={() => router.push('/signal-analysis')}>
                View Results
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Step progress */}
        <Card>
          <CardContent className="p-5">
            <h3 className="font-serif text-heading-3 font-semibold text-cream-950 mb-4">
              8-Step Pipeline Progress
            </h3>
            <StepProgress steps={steps} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
