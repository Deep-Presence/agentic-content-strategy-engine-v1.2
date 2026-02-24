'use client';

import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils/cn';
import { formatPercent } from '@/lib/utils/format';
import type { GapReport } from '@/types/gap-analysis';

interface SpaScoreDisplayProps {
  spa: GapReport['spa_score'];
  totalQueries: number;
  totalCitations: number;
  executiveSummary?: string;
  className?: string;
}

export function SpaScoreDisplay({
  spa,
  totalQueries,
  totalCitations,
  executiveSummary,
  className,
}: SpaScoreDisplayProps) {
  const citationPct = spa.citation_advantage;
  const companyPct = spa.company_advantage;

  const pieData = [
    { name: 'Citation Advantage', value: citationPct, color: '#6a9bcc' },
    { name: 'Company Advantage', value: companyPct, color: '#788c5d' },
  ];

  return (
    <Card accent="ocean" className={cn('overflow-hidden', className)}>
      <CardContent className="p-6">
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Score + Chart */}
          <div className="flex items-center gap-6">
            <div className="relative w-36 h-36 shrink-0">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={42}
                    outerRadius={58}
                    paddingAngle={2}
                    dataKey="value"
                    strokeWidth={0}
                  >
                    {pieData.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-micro font-sans text-cream-600 uppercase tracking-wide">SPA</span>
                <span className="font-serif text-heading-2 font-semibold text-cream-950">
                  {spa.t_statistic.toFixed(2)}
                </span>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <div className="w-2.5 h-2.5 rounded-full bg-ocean-400" />
                  <span className="text-body-sm font-sans text-cream-700">Citation Advantage</span>
                </div>
                <span className="font-serif text-heading-3 font-semibold text-ocean-500">
                  {formatPercent(citationPct)}
                </span>
              </div>
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <div className="w-2.5 h-2.5 rounded-full bg-sage-400" />
                  <span className="text-body-sm font-sans text-cream-700">Company Advantage</span>
                </div>
                <span className="font-serif text-heading-3 font-semibold text-sage-500">
                  {formatPercent(companyPct)}
                </span>
              </div>
            </div>
          </div>

          {/* Stats + Summary */}
          <div className="flex-1 space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <StatBox label="t-statistic" value={spa.t_statistic.toFixed(2)} />
              <StatBox label="p-value" value={spa.p_value < 0.001 ? '< 0.001' : spa.p_value.toFixed(4)} />
              <StatBox label="Total Queries" value={totalQueries.toString()} />
              <StatBox label="Total Citations" value={totalCitations.toString()} />
            </div>
            {executiveSummary && (
              <div className="bg-ocean-50 rounded-md p-3 border border-ocean-200">
                <p className="text-body-sm font-body text-cream-800 leading-relaxed">
                  {executiveSummary}
                </p>
              </div>
            )}
            {citationPct > companyPct && (
              <p className="text-body-sm font-sans text-cream-700">
                AI platforms cite competitors{' '}
                <span className="font-semibold text-ocean-500">
                  {formatPercent(citationPct)}
                </span>{' '}
                more than your content. Focus on the gap briefs below to close visibility gaps.
              </p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

interface StatBoxProps {
  label: string;
  value: string;
}

function StatBox({ label, value }: StatBoxProps) {
  return (
    <div className="bg-cream-100 rounded-md p-2.5 text-center">
      <p className="text-micro font-sans text-cream-600 uppercase tracking-wide">{label}</p>
      <p className="font-sans text-heading-4 font-semibold text-cream-950 mt-0.5">{value}</p>
    </div>
  );
}
