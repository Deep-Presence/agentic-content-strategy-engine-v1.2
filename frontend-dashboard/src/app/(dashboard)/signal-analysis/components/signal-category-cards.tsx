'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils/cn';
import { BarChart3, Layers, FileText, Database } from 'lucide-react';
import {
  SIGNAL_AVERAGES,
  type SignalAverageRow,
} from '../data/sample-data';

interface CategoryConfig {
  category: string;
  icon: React.ReactNode;
  bgClass: string;
  borderClass: string;
  accentColor: string;
  insight: string;
  isPercentage?: boolean;
  showTrafficLight?: boolean;
}

const CATEGORIES: CategoryConfig[] = [
  {
    category: 'Text Composition',
    icon: <BarChart3 className="h-5 w-5 text-[#d97757]" />,
    bgClass: 'bg-[#d97757]/5',
    borderClass: 'border-l-4 border-l-[#d97757]',
    accentColor: '#d97757',
    insight:
      'Citations average 1,735 words. Your content averages 1,100 words. Gap: -635 words.',
  },
  {
    category: 'Structural Elements',
    icon: <Layers className="h-5 w-5 text-[#6a9bcc]" />,
    bgClass: 'bg-[#6a9bcc]/5',
    borderClass: 'border-l-4 border-l-[#6a9bcc]',
    accentColor: '#6a9bcc',
    insight: 'Citations use 1.8x more lists than your content.',
  },
  {
    category: 'Content Patterns',
    icon: <FileText className="h-5 w-5 text-[#788c5d]" />,
    bgClass: 'bg-[#788c5d]/5',
    borderClass: 'border-l-4 border-l-[#788c5d]',
    accentColor: '#788c5d',
    insight:
      '28% of citations have FAQ sections. Only 5% of your content does.',
    isPercentage: true,
    showTrafficLight: true,
  },
  {
    category: 'Factual Density',
    icon: <Database className="h-5 w-5 text-[#141413]" />,
    bgClass: 'bg-[#e8e5de]/40',
    borderClass: 'border-l-4 border-l-[#c4c0b8]',
    accentColor: '#a09a8e',
    insight: 'Include 80% more data points and statistics.',
  },
];

function TrafficLight({ citationAvg, companyAvg }: { citationAvg: number; companyAvg: number }) {
  const ratio = citationAvg > 0 ? companyAvg / citationAvg : 1;
  let color: string;
  let label: string;

  if (ratio >= 0.8) {
    color = 'bg-emerald-500';
    label = 'On track';
  } else if (ratio >= 0.4) {
    color = 'bg-amber-400';
    label = 'Needs work';
  } else {
    color = 'bg-red-500';
    label = 'Gap';
  }

  return (
    <span
      className={cn('inline-block h-2.5 w-2.5 rounded-full flex-shrink-0', color)}
      title={label}
    />
  );
}

function HorizontalComparisonBar({
  signal,
  accentColor,
  isPercentage,
  showTrafficLight,
}: {
  signal: SignalAverageRow;
  accentColor: string;
  isPercentage?: boolean;
  showTrafficLight?: boolean;
}) {
  const maxVal = Math.max(signal.citation_avg, signal.company_avg, 0.01);

  const citationWidth = (signal.citation_avg / maxVal) * 100;
  const companyWidth = (signal.company_avg / maxVal) * 100;

  const formatVal = (v: number) => {
    if (isPercentage) return `${(v * 100).toFixed(0)}%`;
    if (signal.unit === '%') return `${(v * 100).toFixed(0)}%`;
    if (v >= 1000) return v.toLocaleString('en-US', { maximumFractionDigits: 0 });
    if (v < 1 && v > 0) return v.toFixed(2);
    return v.toLocaleString('en-US', { maximumFractionDigits: 1 });
  };

  return (
    <div className="py-2.5 border-b border-[#e8e5de]/60 last:border-b-0">
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          {showTrafficLight && (
            <TrafficLight
              citationAvg={signal.citation_avg}
              companyAvg={signal.company_avg}
            />
          )}
          <span className="text-sm font-sans text-[#141413]/80">{signal.signal}</span>
        </div>
        <span className="text-xs font-sans text-[#141413]/50">{signal.unit}</span>
      </div>
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-sans text-[#141413]/50 w-16 text-right flex-shrink-0">
            Citations
          </span>
          <div className="flex-1 h-3.5 bg-[#e8e5de]/40 rounded-sm overflow-hidden">
            <div
              className="h-full rounded-sm transition-all duration-500"
              style={{
                width: `${citationWidth}%`,
                backgroundColor: accentColor,
                opacity: 0.8,
              }}
            />
          </div>
          <span className="text-xs font-sans font-medium text-[#141413]/70 w-14 text-right flex-shrink-0">
            {formatVal(signal.citation_avg)}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-sans text-[#141413]/50 w-16 text-right flex-shrink-0">
            Yours
          </span>
          <div className="flex-1 h-3.5 bg-[#e8e5de]/40 rounded-sm overflow-hidden">
            <div
              className="h-full rounded-sm transition-all duration-500"
              style={{
                width: `${companyWidth}%`,
                backgroundColor: accentColor,
                opacity: 0.4,
              }}
            />
          </div>
          <span className="text-xs font-sans font-medium text-[#141413]/70 w-14 text-right flex-shrink-0">
            {formatVal(signal.company_avg)}
          </span>
        </div>
      </div>
    </div>
  );
}

export default function SignalCategoryCards() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {CATEGORIES.map((config) => {
        const signals = SIGNAL_AVERAGES.filter(
          (s) => s.category === config.category
        );

        return (
          <Card
            key={config.category}
            className={cn('overflow-hidden', config.bgClass, config.borderClass)}
          >
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2.5">
                {config.icon}
                <CardTitle className="font-serif text-lg text-[#141413]">
                  {config.category}
                </CardTitle>
              </div>
              <p className="text-xs font-sans text-[#141413]/50 mt-0.5">
                {signals.length} signals tracked
              </p>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="space-y-0">
                {signals.map((signal) => (
                  <HorizontalComparisonBar
                    key={signal.signal}
                    signal={signal}
                    accentColor={config.accentColor}
                    isPercentage={config.isPercentage}
                    showTrafficLight={config.showTrafficLight}
                  />
                ))}
              </div>
              <div className="mt-4 px-3 py-2.5 bg-[#141413]/[0.03] rounded-md">
                <p className="text-xs font-sans text-[#141413]/60 leading-relaxed">
                  <span className="font-medium text-[#141413]/80">Key insight: </span>
                  {config.insight}
                </p>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
