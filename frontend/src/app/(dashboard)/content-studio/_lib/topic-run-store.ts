import type { ContentCard, BriefPipelineStatus } from '../_components/types';
import type { TopicRunSummaryAPI } from './types';

export interface TopicRunStore {
  byTopicRunId: Record<string, TopicRunSummaryAPI>;
  byAssignmentId: Record<string, string[]>;
  byBriefId: Record<string, string[]>;
}

export const EMPTY_TOPIC_RUN_STORE: TopicRunStore = {
  byTopicRunId: {},
  byAssignmentId: {},
  byBriefId: {},
};

const VALID_STATUSES = new Set<BriefPipelineStatus>([
  'suggested',
  'gap_analysis_pending',
  'gap_analysis',
  'gap_analysis_complete',
  'content_queued',
  'briefing',
  'brief_review',
  'pending_brief_approval',
  'approved',
  'outlining',
  'drafting',
  'linking',
  'enriching',
  'evaluating',
  'revising',
  'review',
  'pending_content_approval',
  'completed',
  'published',
  'rejected',
  'failed',
]);

function isNewerSnapshot(
  existing: TopicRunSummaryAPI | undefined,
  incoming: TopicRunSummaryAPI,
): boolean {
  if (!existing) return true;
  if (incoming.seq !== existing.seq) return incoming.seq > existing.seq;
  return (incoming.updated_at || '') >= (existing.updated_at || '');
}

function pushUnique(index: Record<string, string[]>, key: string, topicRunId: string): void {
  const existing = index[key] ?? [];
  if (!existing.includes(topicRunId)) {
    index[key] = [...existing, topicRunId];
  }
}

export function mergeTopicRunSnapshots(
  store: TopicRunStore,
  snapshots: TopicRunSummaryAPI[],
): TopicRunStore {
  let changed = false;
  const next: TopicRunStore = {
    byTopicRunId: { ...store.byTopicRunId },
    byAssignmentId: { ...store.byAssignmentId },
    byBriefId: { ...store.byBriefId },
  };

  for (const snapshot of snapshots) {
    if (!snapshot.topic_run_id) continue;
    const existing = next.byTopicRunId[snapshot.topic_run_id];
    if (!isNewerSnapshot(existing, snapshot)) continue;

    next.byTopicRunId[snapshot.topic_run_id] = snapshot;
    if (snapshot.topic_assignment_id) {
      pushUnique(next.byAssignmentId, snapshot.topic_assignment_id, snapshot.topic_run_id);
    }
    if (snapshot.brief_id) {
      pushUnique(next.byBriefId, snapshot.brief_id, snapshot.topic_run_id);
    }
    if (snapshot.display_id && snapshot.display_id !== snapshot.brief_id) {
      pushUnique(next.byBriefId, snapshot.display_id, snapshot.topic_run_id);
    }
    changed = true;
  }

  return changed ? next : store;
}

function compareRuns(a: TopicRunSummaryAPI, b: TopicRunSummaryAPI): number {
  const updatedAtComparison = (b.updated_at || '').localeCompare(a.updated_at || '');
  if (updatedAtComparison !== 0) return updatedAtComparison;
  if (a.seq !== b.seq) return b.seq - a.seq;
  return (b.topic_run_id || '').localeCompare(a.topic_run_id || '');
}

export function selectTopicRunForCard(
  card: ContentCard,
  store: TopicRunStore,
): TopicRunSummaryAPI | null {
  const candidateIds = new Set<string>();
  if (card.topicAssignmentId) {
    for (const topicRunId of store.byAssignmentId[card.topicAssignmentId] ?? []) {
      candidateIds.add(topicRunId);
    }
  }
  for (const briefKey of [card.id, card.displayId]) {
    if (!briefKey) continue;
    for (const topicRunId of store.byBriefId[briefKey] ?? []) {
      candidateIds.add(topicRunId);
    }
  }

  const candidates = Array.from(candidateIds)
    .map((topicRunId) => store.byTopicRunId[topicRunId])
    .filter((run): run is TopicRunSummaryAPI => Boolean(run))
    .filter((run) => !card.effectiveSlug || !run.effective_slug || run.effective_slug === card.effectiveSlug)
    .sort(compareRuns);

  return candidates[0] ?? null;
}

export function isBriefPipelineStatus(value: string): value is BriefPipelineStatus {
  return VALID_STATUSES.has(value as BriefPipelineStatus);
}

export function overlayTopicRunOnCard(
  card: ContentCard,
  topicRun: TopicRunSummaryAPI | null,
): ContentCard {
  if (!topicRun) return card;
  const topicStatus = topicRun.stage || topicRun.status;
  if (!isBriefPipelineStatus(topicStatus)) return card;
  if ((card.updatedAt || '') > (topicRun.updated_at || '') && card.status !== topicStatus) {
    return card;
  }

  return {
    ...card,
    displayId: card.displayId ?? topicRun.display_id ?? undefined,
    topicRunId: topicRun.topic_run_id || card.topicRunId,
    batchRunId: topicRun.batch_run_id || card.batchRunId,
    topicRunSeq: topicRun.seq || card.topicRunSeq,
    topicAssignmentId: card.topicAssignmentId ?? topicRun.topic_assignment_id ?? undefined,
    taskId: topicRun.pipeline_task_id ?? card.taskId,
    gaRunId: topicRun.ga_run_id ?? card.gaRunId,
    effectiveSlug: card.effectiveSlug ?? topicRun.effective_slug ?? undefined,
    status: topicStatus,
    updatedAt: topicRun.updated_at || card.updatedAt,
  };
}
