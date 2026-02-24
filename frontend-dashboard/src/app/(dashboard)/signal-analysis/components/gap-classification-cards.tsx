'use client';

import { useMemo } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils/cn';
import { AlertTriangle, TrendingDown, Equal, TrendingUp } from 'lucide-react';
import type { QueryData } from '../data/sample-data';

interface GapClassificationCardsProps {
  queries: QueryData[];
}

interface ClassificationConfig {
  key: string;
  label: string;
  description: string;
  bgClass: string;
  borderClass: string;
  numberClass: string;
  dotColor: string;
  iconColor: string;
  icon: React.ElementType;
}

const CLASSIFICATIONS: ClassificationConfig[] = [
  {
    key: 'significant_gap',
    label: 'Significant Gap',
    description: 'Queries where citations significantly outperform',
    bgClass: 'bg-red-50/80',
    borderClass: 'border-red-200/70',
    numberClass: 'text-red-700',
    dotColor: '#dc4a3a',
    iconColor: 'text-red-500',
    icon: AlertTriangle,
  },
  {
    key: 'gap_to_close',
    label: 'Gap to Close',
    description: 'Moderate gaps that need attention',
    bgClass: 'bg-amber-50/80',
    borderClass: 'border-amber-200/70',
    numberClass: 'text-amber-700',
    dotColor: '#e8913a',
    iconColor: 'text-amber-500',
    icon: TrendingDown,
  },
  {
    key: 'roughly_equal',
    label: 'Roughly Equal',
    description: 'Company content matches citations',
    bgClass: 'bg-stone-50/80',
    borderClass: 'border-stone-200/70',
    numberClass: 'text-stone-700',
    dotColor: '#8a8880',
    iconColor: 'text-stone-400',
    icon: Equal,
  },
  {
    key: 'company_wins',
    label: 'Company Wins',
    description: 'Company outperforms average citations',
    bgClass: 'bg-emerald-50/80',
    borderClass: 'border-emerald-200/70',
    numberClass: 'text-emerald-700',
    dotColor: '#788c5d',
    iconColor: 'text-emerald-500',
    icon: TrendingUp,
  },
];

export function GapClassificationCards({ queries }: GapClassificationCardsProps) {
  const counts = useMemo(() => {
    const map: Record<string, number> = {
      significant_gap: 0,
      gap_to_close: 0,
      roughly_equal: 0,
      company_wins: 0,
    };
    for (const q of queries) {
      const key = q.classification;
      if (key in map) {
        map[key]++;
      }
    }
    return map;
  }, [queries]);

  const total = queries.length;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {CLASSIFICATIONS.map((config) => {
        const count = counts[config.key] || 0;
        const percent = total > 0 ? ((count / total) * 100).toFixed(1) : '0.0';
        const Icon = config.icon;

        return (
          <Card
            key={config.key}
            className={cn(
              'relative overflow-hidden transition-all duration-200 hover:shadow-md',
              config.bgClass,
              config.borderClass
            )}
          >
            <CardContent className="pt-5 pb-4 px-5">
              {/* Top row: icon + dot */}
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span
                    className="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: config.dotColor }}
                  />
                  <span className="text-xs font-semibold uppercase tracking-wider text-stone-500">
                    {config.label}
                  </span>
                </div>
                <Icon className={cn('h-4 w-4', config.iconColor)} />
              </div>

              {/* Large count */}
              <p
                className={cn(
                  'text-[2.75rem] leading-none font-serif font-bold tracking-tight',
                  config.numberClass
                )}
              >
                {count}
              </p>

              {/* Percentage */}
              <p className={cn('text-lg font-semibold mt-1', config.numberClass)}>
                {percent}%
              </p>

              {/* Description */}
              <p className="text-xs text-stone-500 mt-2 leading-relaxed">
                {config.description}
              </p>

              {/* Subtle bottom bar showing proportion */}
              <div className="mt-3 h-1 rounded-full bg-white/60 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${percent}%`,
                    backgroundColor: config.dotColor,
                    opacity: 0.6,
                  }}
                />
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
