import type { TopicRunEventAPI } from './types';

export type CardActivitySourceKind = 'topic_run' | 'unavailable';

export interface CardActivityItem {
  activityId: string;
  cardId: string;
  displayId: string;
  sourceKind: 'topic_run';
  sourceRunId: string;
  eventType: string;
  stage: string;
  status: string;
  seq: number;
  contentPieceId?: string | null;
  pipelineTaskId?: string | null;
  payload: Record<string, unknown>;
  createdAt: string;
}

export function adaptTopicRunEventsToCardActivity(
  events: TopicRunEventAPI[],
): CardActivityItem[] {
  return events.map((event) => ({
    activityId: event.topic_event_id,
    cardId: event.display_id || event.brief_id || event.topic_assignment_id,
    displayId: event.display_id || event.brief_id,
    sourceKind: 'topic_run',
    sourceRunId: event.topic_run_id,
    eventType: event.event_type,
    stage: event.stage,
    status: event.status,
    seq: event.seq,
    contentPieceId: event.content_piece_id,
    pipelineTaskId: event.pipeline_task_id,
    payload: event.payload_json || {},
    createdAt: event.created_at,
  }));
}

function humanizeActivityToken(value: string): string {
  return value.replace(/_/g, ' ');
}

export function formatCardActivityLabel(event: CardActivityItem): string {
  if (event.eventType === 'topic_run_created') return 'Run created';
  if (event.stage === 'completed') return 'Content produced';
  return humanizeActivityToken(event.stage);
}

export function formatCardActivityDetail(event: CardActivityItem): string | null {
  const payload = event.payload || {};
  const workerError = typeof payload.worker_error === 'string' ? payload.worker_error : null;
  if (workerError) return workerError;

  const note = typeof payload.note === 'string' ? payload.note : null;
  if (note) return note;

  if (event.eventType === 'topic_run_created') {
    const details: string[] = [];
    const buyerStage = typeof payload.buyer_stage === 'string' ? payload.buyer_stage.toUpperCase() : null;
    const intentType = typeof payload.intent_type === 'string' ? humanizeActivityToken(payload.intent_type) : null;
    const batchRunId = typeof payload.batch_run_id === 'string' ? payload.batch_run_id : null;
    if (buyerStage) details.push(buyerStage);
    if (intentType) details.push(intentType);
    if (batchRunId) details.push(`Batch ${batchRunId}`);
    if (details.length > 0) return details.join(' · ');
  }

  return null;
}
