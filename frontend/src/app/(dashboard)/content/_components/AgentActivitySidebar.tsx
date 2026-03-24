'use client';

import { cn } from '@/lib/utils';
import { StatusDot } from '@/components/ui';
import { PanelRightClose, PanelRightOpen, Filter } from 'lucide-react';
import { useState } from 'react';
import { agentActivities } from './content-data';

type AgentType = 'writer' | 'interlink' | 'strategy' | 'eval';

const agentTypeColors: Record<AgentType, 'success' | 'warning' | 'error' | 'info' | 'neutral'> = {
  writer: 'info',
  interlink: 'success',
  strategy: 'warning',
  eval: 'neutral',
};

const agentTypeLabels: Record<AgentType, string> = {
  writer: 'Writer',
  interlink: 'Interlink',
  strategy: 'Strategy',
  eval: 'Eval',
};

interface AgentActivitySidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function AgentActivitySidebar({ collapsed, onToggle }: AgentActivitySidebarProps) {
  const [filterType, setFilterType] = useState<AgentType | 'all'>('all');

  const filteredActivities =
    filterType === 'all'
      ? agentActivities
      : agentActivities.filter((a) => a.type === filterType);

  if (collapsed) {
    return (
      <div className="flex flex-col items-center py-3 w-[40px] min-w-[40px] border-l border-border bg-surface">
        <button
          onClick={onToggle}
          className="p-1.5 rounded-sm text-text-tertiary hover:text-text-primary hover:bg-accent-subtle transition-colors cursor-pointer"
          title="Show agent activity"
        >
          <PanelRightOpen size={14} strokeWidth={1.5} />
        </button>
      </div>
    );
  }

  return (
    <div className="w-[280px] min-w-[280px] border-l border-border bg-surface flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border shrink-0">
        <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
          Agent Activity
        </span>
        <button
          onClick={onToggle}
          className="p-1 rounded-sm text-text-tertiary hover:text-text-primary hover:bg-accent-subtle transition-colors cursor-pointer"
        >
          <PanelRightClose size={14} strokeWidth={1.5} />
        </button>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-1 px-3 py-2 border-b border-border shrink-0">
        <Filter size={11} strokeWidth={1.5} className="text-text-tertiary mr-1" />
        {(['all', 'writer', 'interlink', 'strategy', 'eval'] as const).map((type) => (
          <button
            key={type}
            onClick={() => setFilterType(type)}
            className={cn(
              'text-[10px] px-1.5 py-0.5 rounded-sm transition-colors cursor-pointer',
              filterType === type
                ? 'bg-accent-subtle text-accent'
                : 'text-text-tertiary hover:text-text-secondary hover:bg-surface'
            )}
          >
            {type === 'all' ? 'All' : agentTypeLabels[type]}
          </button>
        ))}
      </div>

      {/* Activity Feed */}
      <div className="flex-1 overflow-y-auto">
        {filteredActivities.map((activity) => (
          <div
            key={activity.id}
            className="flex items-start gap-2 px-3 py-2 border-b border-border-subtle hover:bg-accent-subtle transition-colors"
          >
            <StatusDot
              color={agentTypeColors[activity.type]}
              className="mt-1.5 flex-shrink-0"
            />
            <div className="min-w-0 flex-1">
              <span className="text-[11px] font-medium text-text-primary block">
                {activity.agent}
              </span>
              <span className="text-[11px] text-text-secondary block leading-snug">
                {activity.action}
              </span>
            </div>
            <span className="text-[10px] text-text-tertiary flex-shrink-0 mt-0.5">
              {activity.time}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
