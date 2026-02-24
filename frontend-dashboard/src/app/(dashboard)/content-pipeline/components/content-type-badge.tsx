import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils/cn';
import { CONTENT_TYPE_LABELS } from '@/lib/utils/constants';
import type { ContentType } from '@/types/content';

interface ContentTypeBadgeProps {
  type: ContentType;
  className?: string;
}

const TYPE_VARIANTS = {
  blog: 'blue' as const,
  guide: 'green' as const,
  case_study: 'terracotta' as const,
  product_page: 'default' as const,
} as const;

export function ContentTypeBadge({ type, className }: ContentTypeBadgeProps) {
  return (
    <Badge variant={TYPE_VARIANTS[type]} className={cn(className)}>
      {CONTENT_TYPE_LABELS[type]}
    </Badge>
  );
}
