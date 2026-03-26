'use client';

import { Card, Badge, Button } from '@/components/ui';
import { RefreshCw, ExternalLink } from 'lucide-react';
import { isSafeUrl } from '@/lib/utils';
import type { StaleContentAction } from '@/lib/api/types';

interface StaleContentActionsProps {
  actions: StaleContentAction[];
  onQueueRefresh: (cmsSyncedPostId: string) => Promise<void>;
  queuingId: string | null;
  queuedIds: Set<string>;
}

export function StaleContentActions({
  actions,
  onQueueRefresh,
  queuingId,
  queuedIds,
}: StaleContentActionsProps) {
  if (actions.length === 0) return null;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <RefreshCw size={16} strokeWidth={1.5} className="text-text-tertiary" />
        <h3 className="text-[14px] font-semibold text-text-primary">Stale Content</h3>
        <Badge variant="warning">{actions.length}</Badge>
      </div>

      {/* Cards */}
      <div className="space-y-2">
        {actions.map((action) => {
          const isQueuing = queuingId === action.cms_synced_post_id;
          const isQueued = queuedIds.has(action.cms_synced_post_id) || action.queued_for_refresh;

          return (
            <Card key={action.cms_synced_post_id} className="p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-[14px] font-semibold text-text-primary truncate">
                    {action.title}
                  </p>
                  {isSafeUrl(action.url) ? (
                    <a
                      href={action.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[11px] text-accent hover:underline flex items-center gap-0.5 mt-0.5"
                    >
                      <span className="truncate max-w-[300px]">{action.url}</span>
                      <ExternalLink size={9} strokeWidth={1.5} className="shrink-0" />
                    </a>
                  ) : (
                    <span className="text-[11px] text-text-secondary truncate mt-0.5">{action.url}</span>
                  )}
                  <p className="text-[11px] text-text-tertiary mt-1">
                    Last updated {action.staleness_days} days ago. Refreshing improves LLM presence.
                  </p>
                </div>

                <div className="shrink-0">
                  {isQueued ? (
                    <Button size="sm" variant="ghost" disabled>
                      Queued
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={isQueuing}
                      onClick={() => onQueueRefresh(action.cms_synced_post_id)}
                    >
                      {isQueuing ? 'Queuing...' : 'Refresh Content'}
                    </Button>
                  )}
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
