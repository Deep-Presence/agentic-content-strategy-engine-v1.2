'use client';

import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils/cn';
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
  const gapPct = citationPct - companyPct;

  const pieData = [
    { name: 'Citation Advantage', value: citationPct, color: '#6a9bcc' },
    { name: 'Company Similarity', value: companyPct, color: '#c5d9ea' },
  ];

  // Remaining arc to fill the full donut
  const remainder = Math.max(0, 1 - citationPct);
  const companyRemainder = Math.max(0, 1 - companyPct);

  const citationDonut = [
    { name: 'Citation', value: citationPct, color: '#4a7ba8' },
    { name: 'Rest', value: remainder, color: '#edf2f8' },
  ];

  const companyDonut = [
    { name: 'Company', value: companyPct, color: '#9abfdb' },
    { name: 'Rest', value: companyRemainder, color: '#edf2f8' },
  ];

  return (
    <Card accent="ocean" className={cn('overflow-hidden', className)}>
      <CardContent className="p-0">
        {/* Hero section with gradient background */}
        <div className="bg-gradient-to-br from-ocean-50 via-cream-50 to-ocean-50 p-8">
          <div className="flex flex-col lg:flex-row items-center gap-8">
            {/* Left: Large SPA score + donut charts */}
            <div className="flex items-center gap-8">
              {/* Main SPA Score */}
              <div className="text-center">
                <p className="text-micro font-sans text-ocean-600 uppercase tracking-widest mb-1">
                  Semantic Proximity Analysis
                </p>
                <p className="font-serif text-[3.5rem] leading-none font-semibold text-ocean-700 tracking-tight">
                  {spa.t_statistic.toFixed(3)}
                </p>
                <p className="text-caption font-sans text-ocean-500 mt-1">t-statistic</p>
              </div>

              {/* Dual donut comparison */}
              <div className="flex items-end gap-4">
                {/* Citation donut */}
                <div className="text-center">
                  <div className="relative w-28 h-28">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={citationDonut}
                          cx="50%"
                          cy="50%"
                          innerRadius={34}
                          outerRadius={48}
                          startAngle={90}
                          endAngle={-270}
                          paddingAngle={0}
                          dataKey="value"
                          strokeWidth={0}
                        >
                          {citationDonut.map((entry) => (
                            <Cell key={entry.name} fill={entry.color} />
                          ))}
                        </Pie>
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <span className="font-sans text-heading-3 font-semibold text-ocean-600">
                        {(citationPct * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                  <p className="text-micro font-sans text-ocean-500 mt-1">Competitors</p>
                </div>

                {/* VS indicator */}
                <div className="flex flex-col items-center pb-8">
                  <span className="text-caption font-sans font-semibold text-cream-600">vs</span>
                </div>

                {/* Company donut */}
                <div className="text-center">
                  <div className="relative w-28 h-28">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={companyDonut}
                          cx="50%"
                          cy="50%"
                          innerRadius={34}
                          outerRadius={48}
                          startAngle={90}
                          endAngle={-270}
                          paddingAngle={0}
                          dataKey="value"
                          strokeWidth={0}
                        >
                          {companyDonut.map((entry) => (
                            <Cell key={entry.name} fill={entry.color} />
                          ))}
                        </Pie>
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <span className="font-sans text-heading-3 font-semibold text-ocean-400">
                        {(companyPct * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                  <p className="text-micro font-sans text-ocean-400 mt-1">Webflow</p>
                </div>
              </div>
            </div>

            {/* Right: Stats + insight */}
            <div className="flex-1 space-y-5 lg:pl-4 lg:border-l lg:border-ocean-200">
              {/* Key insight */}
              <p className="text-body-lg font-body text-cream-800 leading-relaxed">
                Webflow is cited in <span className="font-semibold text-ocean-500">{(companyPct * 100).toFixed(0)}%</span> of
                AI responses. Competitors average <span className="font-semibold text-ocean-700">{(citationPct * 100).toFixed(0)}%</span>.
              </p>

              {/* Stats grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <StatBox label="t-statistic" value={spa.t_statistic.toFixed(3)} highlight />
                <StatBox label="p-value" value={spa.p_value === 0 ? '0.0000' : spa.p_value.toFixed(4)} />
                <StatBox label="Queries Analyzed" value={totalQueries.toLocaleString()} />
                <StatBox label="Citations Crawled" value={totalCitations.toLocaleString()} />
              </div>

              {/* Gap callout */}
              <div className="flex items-center gap-3 bg-ocean-100/60 rounded-lg p-3 border border-ocean-200">
                <div className="shrink-0 w-10 h-10 rounded-full bg-ocean-500 flex items-center justify-center">
                  <span className="text-body-sm font-sans font-bold text-white">
                    {(gapPct * 100).toFixed(0)}%
                  </span>
                </div>
                <p className="text-body-sm font-sans text-ocean-700">
                  AI platforms cite competitors <span className="font-semibold">{Math.round((citationPct / companyPct - 1) * 100)}% more effectively</span> than Webflow.
                  Focus on the gap briefs below to close visibility gaps.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Executive summary */}
        {executiveSummary && (
          <div className="px-8 py-4 bg-cream-50 border-t border-ocean-100">
            <p className="text-body-sm font-body text-cream-700 leading-relaxed">
              {executiveSummary}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

interface StatBoxProps {
  label: string;
  value: string;
  highlight?: boolean;
}

function StatBox({ label, value, highlight }: StatBoxProps) {
  return (
    <div className={cn(
      'rounded-lg p-2.5 text-center',
      highlight ? 'bg-ocean-100 border border-ocean-200' : 'bg-white/60 border border-cream-300'
    )}>
      <p className="text-micro font-sans text-cream-600 uppercase tracking-wide">{label}</p>
      <p className={cn(
        'font-sans text-heading-4 font-semibold mt-0.5',
        highlight ? 'text-ocean-600' : 'text-cream-950'
      )}>
        {value}
      </p>
    </div>
  );
}
