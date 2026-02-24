'use client';

import { CheckCircle, AlertTriangle, XCircle } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils/cn';

type ItemStatus = 'approved' | 'draft' | 'none';

interface CompletenessItem {
  label: string;
  status: ItemStatus;
  weight: number;
  statusLabel?: string;
}

interface BrandOverviewCardsProps {
  companyContextStatus: ItemStatus;
  personaStatus: ItemStatus;
  styleGuideStatus: ItemStatus;
  hasKnowledgeDocs: boolean;
  companyContextDate?: string;
  personaDate?: string;
  styleGuideDate?: string;
  knowledgeDocsLabel?: string;
}

const STATUS_ICONS = {
  approved: CheckCircle,
  draft: AlertTriangle,
  none: XCircle,
} as const;

const DEFAULT_STATUS_LABELS = {
  approved: 'Generated & Approved',
  draft: 'Draft — Needs Approval',
  none: 'Not started',
} as const;

const STATUS_STYLES = {
  approved: 'text-sage-400',
  draft: 'text-warning',
  none: 'text-cream-500',
} as const;

export function BrandOverviewCards({
  companyContextStatus,
  personaStatus,
  styleGuideStatus,
  hasKnowledgeDocs,
  companyContextDate,
  personaDate,
  styleGuideDate,
  knowledgeDocsLabel,
}: BrandOverviewCardsProps) {
  const items: CompletenessItem[] = [
    {
      label: 'Company Context',
      status: companyContextStatus,
      weight: 25,
      statusLabel: companyContextStatus === 'approved' && companyContextDate
        ? `Generated & Approved — ${companyContextDate}`
        : undefined,
    },
    {
      label: 'ICP Persona',
      status: personaStatus,
      weight: 25,
      statusLabel: personaStatus === 'approved' && personaDate
        ? `Generated & Approved — ${personaDate}`
        : undefined,
    },
    {
      label: 'Style Guide',
      status: styleGuideStatus,
      weight: 25,
      statusLabel: styleGuideStatus === 'approved' && styleGuideDate
        ? `Generated & Approved — ${styleGuideDate}`
        : undefined,
    },
    {
      label: 'Brand Guidelines',
      status: hasKnowledgeDocs ? 'approved' : 'none',
      weight: 25,
      statusLabel: hasKnowledgeDocs ? undefined : (knowledgeDocsLabel ?? 'Not uploaded'),
    },
  ];

  const score = items.reduce((sum, item) => {
    if (item.status === 'approved') return sum + item.weight;
    if (item.status === 'draft') return sum + item.weight * 0.5;
    return sum;
  }, 0);

  const progressColor = score >= 80 ? 'sage' : score >= 50 ? 'terracotta' : 'warning';

  return (
    <div className="bg-white rounded-md border border-[var(--border-default)] p-5 shadow-[var(--shadow-sm)]">
      <h3 className="font-serif text-heading-3 font-semibold text-cream-950 mb-4">
        Knowledge Completeness
      </h3>
      <div className="flex items-center gap-4 mb-4">
        <Progress value={score} color={progressColor} className="flex-1" />
        <span className="font-sans text-heading-4 font-semibold text-cream-800 tabular-nums">
          {score}%
        </span>
      </div>
      <div className="space-y-2.5">
        {items.map((item) => {
          const Icon = STATUS_ICONS[item.status];
          const label = item.statusLabel ?? DEFAULT_STATUS_LABELS[item.status];
          return (
            <div key={item.label} className="flex items-center gap-2.5">
              <Icon className={cn('h-4 w-4 shrink-0', STATUS_STYLES[item.status])} />
              <span className="font-sans text-body-sm text-cream-800 flex-1">
                {item.label}
              </span>
              <span
                className={cn(
                  'font-sans text-caption',
                  STATUS_STYLES[item.status]
                )}
              >
                {label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
