# Kanban ↔ Pipeline Sync — Integration Spec

> **Purpose**: Fix the broken link between the v1.3 content engine pipeline stages and the Content Studio Kanban board. This document is the authoritative spec for implementation.

---

## Problem summary

Kanban tiles don't move when the backend pipeline progresses. Seven distinct failure points cause this (see diagnosis section). The root causes are:

1. **Dual brief_id creation** — frontend `add_brief()` and backend pipeline each generate separate brief_ids
2. **Coarse state writes** — `pipeline_state.json` only gets written at 4 of ~12 needed granularity levels
3. **No worker-level SSE events** — the dispatcher never emits per-step progress events
4. **Refetch-only frontend** — the frontend ignores SSE event payloads and just re-polls stale data
5. **Single task_id tracking** — concurrent manual pipelines are invisible to the frontend
6. **auto_approve skips visible states** — manual mode flies through states faster than the poll interval
7. **Dead frontend mappings** — `STATUS_TO_STAGE` lists statuses the backend never writes

---

## Phase 1: Backend — Fine-grained state writes (fixes F2, F3)

### 1A. Define the canonical status enum

Create `core/models/pipeline_status.py`:

```python
from enum import Enum

class BriefPipelineStatus(str, Enum):
    """Canonical brief-level status values.
    
    Each value maps 1:1 to a Kanban column + tile badge.
    Written to pipeline_state.json and returned by GET /briefs.
    """
    # Triage column
    SUGGESTED = "suggested"          # Initial state, awaiting user/planner approval
    
    # Brief column
    BRIEFING = "briefing"            # Brief Builder running
    BRIEF_REVIEW = "brief_review"    # HITL-2 pending (autonomous only)
    APPROVED = "approved"            # Brief approved, queued for workers
    
    # Generating column
    OUTLINING = "outlining"
    DRAFTING = "drafting"
    LINKING = "linking"
    ENRICHING = "enriching"
    EVALUATING = "evaluating"
    REVISING = "revising"            # Eval failed, drafter re-running
    
    # Review column
    REVIEW = "review"                # HITL-3 pending
    
    # Approved column
    COMPLETED = "completed"          # HITL-3 approved, final.md written
    PUBLISHED = "published"          # Alias for completed (legacy compat)
    
    # Hidden
    REJECTED = "rejected"
    FAILED = "failed"                # Worker/pipeline error
```

### 1B. Add per-worker SSE events to the dispatcher

In `dispatch_workers_v13()`, pass `event_bus` and `task_id` through:

```python
async def dispatch_workers_v13(
    briefs, input_data, style_guide_md, company_context_md,
    max_concurrent=3, *, artifact_dir, site_pages=None,
    parent_span=None, storage=None, session_factory=None,
    piece_id_map=None,
    event_bus=None,      # NEW
    task_id=None,        # NEW
) -> Tuple[...]:
```

In `_run_worker_chain_v13()`, emit progress events AND write pipeline_state at each sub-step:

```python
# Before each worker step:
_write_pipeline_state(artifact_dir, [brief.brief_id], "outlining")
_emit(event_bus, task_id, "worker_progress", {
    "brief_id": brief.brief_id,
    "step": "outlining",
    "worker_num": worker_num,
})

# ... outliner runs ...

_write_pipeline_state(artifact_dir, [brief.brief_id], "drafting")
_emit(event_bus, task_id, "worker_progress", {
    "brief_id": brief.brief_id,
    "step": "drafting",
    "worker_num": worker_num,
})

# ... drafter runs ...
# (repeat for linking, enriching)
```

### 1C. Add state writes for Stage 2 and Stage 4

In `pipeline_v13.py`, add writes at Brief Builder start and evaluator transitions:

```python
# Stage 2 start (both modes):
_write_pipeline_state(artifact_dir, [bp.brief_id for bp in blueprints_to_build], "briefing")

# After HITL-2 fires (autonomous):
_write_pipeline_state(artifact_dir, [bp.brief_id], "brief_review")

# Stage 4 evaluator start:
_write_pipeline_state(artifact_dir, [bid], "evaluating")

# Stage 4 revision loop:
_write_pipeline_state(artifact_dir, [bid], "revising")
```

### 1D. Pass event_bus into dispatch_workers_v13

In `pipeline_v13.py` Stage 3, add the new params:

```python
formatted_contents, worker_failures = await dispatch_workers_v13(
    briefs=approved_blueprints,
    input_data=input_data,
    style_guide_md=style_guide_md,
    company_context_md=company_context_md,
    max_concurrent=input_data.max_concurrent_workers,
    artifact_dir=artifact_dir,
    site_pages=site_pages,
    parent_span=stage3_span,
    storage=storage,
    session_factory=session_factory,
    piece_id_map=piece_id_map,
    event_bus=event_bus,      # NEW
    task_id=task_id,          # NEW
)
```

---

## Phase 2: Fix the dual brief_id problem (fixes F1)

### The problem

When the user clicks "Add to Content Cycle":
1. Frontend POSTs to `/briefs` → `add_brief()` generates `brief-001`
2. Frontend POSTs to `/content-engine/start` → pipeline generates `brief-002` (or `brief-001` if lucky)

The IDs may collide or diverge depending on race conditions.

### The fix: return the brief_id from add_brief and pass it to the pipeline

**Option A (recommended): Pipeline reuses the pre-created brief_id**

1. `add_brief()` already returns a `ContentBriefListItem` with an `id`. The frontend should capture this.

2. Add a `brief_id_hint` field to the pipeline input:

```python
class ContentGenerationInputV13(ContentGenerationInput):
    # ... existing fields ...
    brief_id_hint: Optional[str] = None  # Pre-created brief_id to reuse
```

3. In the manual mode branch of `pipeline_v13.py`, use `brief_id_hint` if provided instead of generating `_manual_brief_id`:

```python
if input_data.brief_id_hint:
    _manual_brief_id = input_data.brief_id_hint
else:
    # existing sequential ID logic
    _next_idx = 1
    while f"brief-{_next_idx:03d}" in _existing_ids:
        _next_idx += 1
    _manual_brief_id = f"brief-{_next_idx:03d}"
```

4. Frontend sends the brief_id in the pipeline start request:

```typescript
// Step 1: Create brief
const brief = await apiPost<ContentBriefListItem>(CONTENT_DATA.briefs(slug), {
  title: query.text,
  cluster: query.cluster,
  // ...
});

// Step 2: Start pipeline with the same brief_id
const res = await apiPost<{ run_id: string }>(CONTENT_ENGINE.start, {
  // ... existing fields ...
  brief_id_hint: brief.id,  // NEW — ensures same ID
});
```

**Option B (simpler but less correct): Don't pre-create the brief**

Remove the `add_brief()` call entirely. Let the pipeline create the brief. The tile appears when the pipeline writes to `blueprints.json`. Downside: user doesn't see immediate feedback when clicking "Add to Content Cycle" — there's a delay until the pipeline's Brief Builder runs.

**Recommendation: Option A.** Immediate feedback is important UX.

---

## Phase 3: Frontend — SSE-driven state updates (fixes F4, F5, F6)

### 3A. Track multiple task IDs

Replace the single `pipelineTaskId` with a Map of active task IDs:

```typescript
// In a Zustand store or context:
interface ContentPipelineStore {
  activeTaskIds: Map<string, string>;  // taskId → briefId (or "batch" for autonomous)
  addTask: (taskId: string, briefId: string) => void;
  removeTask: (taskId: string) => void;
}
```

Each "Add to Content Cycle" click adds its `run_id` to the map. The `useTaskStream` hook needs to be instantiated per active task, or refactored into a single multiplexed SSE connection.

### 3B. Use SSE events to update tile state directly

Instead of just calling `refetch()` on SSE events, maintain a local state overlay:

```typescript
// briefStatusOverrides: Map<briefId, { status: string, substep?: string }>
// SSE handler:
function handleSSEEvent(event: SSEEvent) {
  if (event.type === 'worker_progress') {
    const { brief_id, step } = event.data;
    setBriefStatusOverride(brief_id, { status: step, substep: step });
  }
  if (event.type === 'stage_started') {
    // Trigger a refetch for column-level moves
    refetch();
  }
  if (event.type === 'pending_approval') {
    const { brief_id, stage } = event.data;
    setBriefStatusOverride(brief_id, { status: `${stage}_review` });
    refetch();  // Also refetch to get full data
  }
  if (event.type === 'pipeline_complete') {
    clearAllOverrides();
    refetch();
  }
}
```

The override map takes priority over the GET /briefs response for in-flight tiles. When the pipeline completes, overrides are cleared and the final state from the API takes over.

### 3C. Update the STATUS_TO_STAGE mapping

Replace the existing `STATUS_TO_STAGE` in `transforms.ts` with the canonical mapping:

```typescript
const STATUS_TO_STAGE: Record<string, ContentBrief['stage']> = {
  // Triage
  suggested: 'triage',
  
  // Brief
  briefing: 'brief',
  brief_review: 'brief',
  approved: 'brief',
  
  // Generating
  outlining: 'generating',
  drafting: 'generating',
  linking: 'generating',
  enriching: 'generating',
  evaluating: 'generating',
  revising: 'generating',
  in_progress: 'generating',  // legacy compat
  
  // Review
  review: 'review',
  pending_review: 'review',
  
  // Approved
  completed: 'approved',
  published: 'approved',
  
  // Hidden
  rejected: 'triage',  // or filter out entirely
  failed: 'triage',
};
```

### 3D. Add sub-step badge to ContentCard

The tile should show the current sub-step as a badge:

```typescript
function ContentCard({ brief, statusOverride }: { brief: ExtendedBrief; statusOverride?: { status: string; substep?: string } }) {
  const effectiveStatus = statusOverride?.status ?? brief.status;
  const substep = statusOverride?.substep;
  
  // Badge text mapping
  const badgeText: Record<string, string> = {
    suggested: 'Awaiting approval',
    briefing: 'Generating brief',
    brief_review: 'Approve brief',
    approved: 'Brief approved',
    outlining: 'Outlining',
    drafting: 'Drafting',
    linking: 'Linking',
    enriching: 'Enriching',
    evaluating: 'Evaluating',
    revising: 'Revising',
    review: 'Final review',
    completed: 'Published',
  };
  
  // Badge color: amber for HITL states, blue for machine states, green for done
  const isHitl = ['suggested', 'brief_review', 'review'].includes(effectiveStatus);
  const isDone = ['completed', 'published'].includes(effectiveStatus);
  
  return (
    <div className="...">
      {/* ... existing card content ... */}
      <span className={cn(
        'text-[10px] font-medium px-1.5 py-0.5 rounded',
        isHitl && 'bg-warning/10 text-warning',
        !isHitl && !isDone && 'bg-accent/10 text-accent',
        isDone && 'bg-success/10 text-success',
      )}>
        {badgeText[effectiveStatus] ?? effectiveStatus}
      </span>
    </div>
  );
}
```

### 3E. Rename column labels

Update `stageColumns` in `content-data.ts`:

```typescript
export const stageColumns: { id: StageId; label: string; color: ... }[] = [
  { id: 'triage', label: 'Triage', color: 'neutral' },
  { id: 'brief', label: 'Brief', color: 'info' },
  { id: 'generating', label: 'Generating', color: 'warning' },
  { id: 'review', label: 'Review', color: 'error' },
  { id: 'approved', label: 'Approved', color: 'success' },
];
```

---

## Phase 4: Include brief_id in all SSE events (fixes F5 partially)

Ensure every SSE event from the pipeline includes `brief_id` so the frontend can route it to the correct tile:

```python
# In pipeline_v13.py, for Stage 4 evaluator:
_emit(event_bus, task_id, "eval_progress", {
    "brief_id": brief_id,
    "cycle": cycle_num,
    "passed": passed,
})

# In HITL checkpoints:
_emit(event_bus, task_id, "pending_approval", {
    "stage": "brief",
    "brief_id": bp.brief_id,
})

# In Stage 5 final review:
_emit(event_bus, task_id, "pending_approval", {
    "stage": "review",
    "brief_id": brief_id,
    "cps_score": cps_results.get(brief_id, {}).get("score"),
})
```

---

## Phase 5: _infer_brief_status alignment (fixes F7)

Update `_infer_brief_status()` in `content_data_service.py` to handle the new statuses:

```python
def _infer_brief_status(brief_id, pieces, content_dir, pipeline_state=None):
    # Phase 0: pipeline_state.json (highest priority)
    if pipeline_state and brief_id in pipeline_state:
        return pipeline_state[brief_id]  # Now returns fine-grained statuses
    
    # Phase 1: pieces (post-pipeline authoritative)
    for piece in pieces:
        if piece.get("brief_id") == brief_id:
            status = piece.get("status", "")
            return {
                "approved": "completed",
                "edited": "completed",
                "rejected": "rejected",
                "pending": "review",
            }.get(status, "review")
    
    # Phase 2: File-based inference (fallback for stale/crashed pipelines)
    brief_dir = content_dir / "content" / brief_id
    if (brief_dir / "final.md").exists():
        return "completed"
    if (brief_dir / "eval_history.json").exists():
        try:
            eh = json.loads((brief_dir / "eval_history.json").read_text())
            if eh.get("final_passed", False):
                return "review"
        except (json.JSONDecodeError, KeyError, OSError):
            pass
        return "evaluating"
    if (brief_dir / "fact_checked.md").exists() or (brief_dir / "enriched.md").exists():
        return "enriching"
    if (brief_dir / "draft.md").exists():
        return "drafting"
    if (brief_dir / "outline.json").exists():
        return "outlining"
    
    # Default
    return "suggested"
```

---

## Implementation order

| Step | Files touched | Fixes | Effort |
|------|--------------|-------|--------|
| 1. Create BriefPipelineStatus enum | `core/models/pipeline_status.py` | Foundation | 15 min |
| 2. Add _write_pipeline_state calls at each sub-step | `pipeline_v13.py` (Stage 2, 4) | F2 | 30 min |
| 3. Pass event_bus into dispatcher + emit per-step | `dispatcher.py`, `pipeline_v13.py` | F3 | 45 min |
| 4. Fix dual brief_id: add brief_id_hint | `pipeline_v13.py`, `models/content_generation_v13.py` | F1 | 30 min |
| 5. Frontend: send brief_id_hint in POST | `CitationsTab.tsx`, `RecommendedActions.tsx`, `planner/page.tsx` | F1 | 20 min |
| 6. Update STATUS_TO_STAGE mapping | `transforms.ts` | F7 | 10 min |
| 7. Update _infer_brief_status file-based fallback | `content_data_service.py` | F7 | 20 min |
| 8. Frontend: SSE-driven state overlay | `content/page.tsx`, new hook | F4, F6 | 1-2 hr |
| 9. Frontend: multi-task tracking | `content/page.tsx`, store | F5 | 1 hr |
| 10. Add sub-step badge to ContentCard | `KanbanBoard.tsx` | Visual | 30 min |
| 11. Rename column labels | `content-data.ts` | Visual | 5 min |

**Total estimated effort: ~5-6 hours of implementation**

Steps 1-3 are backend-only and can be tested with the CLI pipeline. Steps 4-7 bridge the gap. Steps 8-11 are frontend-only and can be tested against the updated backend.

---

## SSE event catalog (complete)

After implementation, the backend will emit these events for a manual-mode pipeline run:

```
stage_started       {stage: 2, name: "Brief Builder"}
worker_progress     {brief_id: "brief-001", step: "briefing"}
pending_approval    {stage: "brief", brief_id: "brief-001"}     # if not auto_approve
approval_received   {stage: "brief", brief_id: "brief-001"}
stage_complete      {stage: 2}
stage_started       {stage: 3, name: "Content Workers"}
worker_progress     {brief_id: "brief-001", step: "outlining"}
worker_progress     {brief_id: "brief-001", step: "drafting"}
worker_progress     {brief_id: "brief-001", step: "linking"}
worker_progress     {brief_id: "brief-001", step: "enriching"}
stage_complete      {stage: 3}
stage_started       {stage: 4, name: "Evaluator"}
worker_progress     {brief_id: "brief-001", step: "evaluating"}
worker_progress     {brief_id: "brief-001", step: "revising", cycle: 1}  # if eval fails
stage_complete      {stage: 4}
stage_started       {stage: 5, name: "Final Review"}
pending_approval    {stage: "review", brief_id: "brief-001", cps_score: 0.74}
approval_received   {stage: "review", brief_id: "brief-001", decision: "approve"}
stage_complete      {stage: 5}
pipeline_complete   {total_briefs: 1, total_approved: 1}
```

For autonomous mode, the same events fire but with `stage_started {stage: 1}` prepended and multiple `brief_id` values in parallel during Stage 3.
