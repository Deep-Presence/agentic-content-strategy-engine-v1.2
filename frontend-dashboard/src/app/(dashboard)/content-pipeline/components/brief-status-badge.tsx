import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils/cn';
import type { ContentBriefStatus } from '@/types/content';

interface BriefStatusBadgeProps {
  status: ContentBriefStatus;
  className?: string;
}

const STATUS_CONFIG = {
  suggested: { label: 'Suggested', variant: 'default' as const },
  approved: { label: 'Approved', variant: 'blue' as const },
  research: { label: 'Research', variant: 'blue' as const },
  drafting: { label: 'Drafting', variant: 'blue' as const },
  enriching: { label: 'Enriching', variant: 'blue' as const },
  formatting: { label: 'Formatting', variant: 'blue' as const },
  evaluating: { label: 'Evaluating', variant: 'terracotta' as const },
  review: { label: 'Review', variant: 'terracotta' as const },
  published: { label: 'Published', variant: 'green' as const },
  draft_saved: { label: 'Draft Saved', variant: 'default' as const },
  rejected: { label: 'Rejected', variant: 'error' as const },
} as const;

export function BriefStatusBadge({ status, className }: BriefStatusBadgeProps) {
  const config = STATUS_CONFIG[status];

  return (
    <Badge variant={config.variant} className={cn(className)}>
      {config.label}
    </Badge>
  );
}
