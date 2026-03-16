'use client';

import { Badge, StatusDot } from '@/components/ui';
import type { EnrichedTopic } from '@/data/topics';
import { FileText, Users, TrendingUp } from 'lucide-react';

interface TopicCardProps {
  topic: EnrichedTopic;
  selected?: boolean;
  onSelect?: (id: string) => void;
  onClick: (topic: EnrichedTopic) => void;
}

export function TopicCard({ topic, selected, onSelect, onClick }: TopicCardProps) {
  return (
    <div
      className={`bg-surface border rounded-md p-[14px] hover:border-border-strong cursor-pointer transition-[border-color] duration-150 ${
        selected ? 'border-accent bg-accent-subtle' : 'border-border'
      }`}
      onClick={() => onClick(topic)}
    >
      {/* Priority badge top-right */}
      <div className="flex justify-between items-start mb-2">
        <Badge variant={topic.priority === 'high' ? 'error' : topic.priority === 'medium' ? 'warning' : 'info'}>
          {topic.priority}
        </Badge>
      </div>

      {/* Title */}
      <h4 className="text-[14px] font-semibold text-text-primary leading-tight line-clamp-2 mb-2">
        {topic.title}
      </h4>

      {/* Coverage + Cluster */}
      <div className="flex items-center gap-2 mb-3">
        <Badge variant={topic.coverage === 'gap' ? 'error' : topic.coverage === 'partial' ? 'warning' : 'success'}>
          {topic.coverage}
        </Badge>
        <span className="text-[10px] text-text-tertiary">{topic.cluster}</span>
      </div>

      {/* Gap + Exemplar stats */}
      <div className="flex items-center gap-1.5 text-[12px] text-text-tertiary mb-1.5">
        <span className="font-medium text-text-secondary">Gap: {topic.gapScore.toFixed(3)}</span>
        <span>·</span>
        <span>{topic.exemplarCount} exemplar{topic.exemplarCount !== 1 ? 's' : ''}</span>
      </div>
      <div className="flex items-center gap-1.5 text-[11px] text-text-tertiary mb-3">
        <FileText size={11} strokeWidth={1.5} />
        <span>Avg exemplar: {topic.avgExemplarWords.toLocaleString()} words · {topic.avgExemplarHeaders} headers</span>
      </div>

      {/* Personas */}
      <div className="flex items-center gap-1 mb-3">
        <Users size={11} strokeWidth={1.5} className="text-text-tertiary" />
        {topic.personas.map(p => (
          <StatusDot key={p} color="info" />
        ))}
        <span className="text-[10px] text-text-tertiary ml-1">
          {topic.personas.length} of 3 personas matched
        </span>
      </div>

      {/* Estimated impact */}
      <div className="border-t border-border pt-2 space-y-1">
        <div className="flex items-center gap-1.5 text-[11px]">
          <TrendingUp size={11} strokeWidth={1.5} className="text-success" />
          <span className="text-text-tertiary">Est. citations:</span>
          <span className="text-text-secondary font-medium">{topic.estCitations}</span>
        </div>
        <div className="flex items-center gap-1.5 text-[11px]">
          <TrendingUp size={11} strokeWidth={1.5} className="text-accent" />
          <span className="text-text-tertiary">Est. AI referrals:</span>
          <span className="text-text-secondary font-medium">{topic.estReferrals}</span>
        </div>
      </div>

      {/* Bulk select checkbox */}
      {onSelect && (
        <div className="mt-2 pt-2 border-t border-border">
          <label
            className="flex items-center gap-1.5 text-[10px] text-text-secondary cursor-pointer"
            onClick={(e) => e.stopPropagation()}
          >
            <input
              type="checkbox"
              checked={selected}
              onChange={() => onSelect(topic.id)}
              className="w-3 h-3 accent-accent cursor-pointer"
            />
            Select
          </label>
        </div>
      )}
    </div>
  );
}
