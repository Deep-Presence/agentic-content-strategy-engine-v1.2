'use client';

import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from 'recharts';
import { DIMENSIONS } from './tech-readiness-data';

interface DimensionBreakdownProps {
  activeDimension: string | null;
  onDimensionClick: (name: string | null) => void;
}

export function DimensionBreakdown({ activeDimension, onDimensionClick }: DimensionBreakdownProps) {
  const radarData = DIMENSIONS.map((d) => ({
    dimension: d.name,
    score: d.score,
    fullMark: 100,
  }));

  function scoreColor(score: number): string {
    if (score >= 90) return 'var(--success)';
    if (score >= 70) return 'var(--warning)';
    return 'var(--error)';
  }

  function statusIcon(status: string): string {
    if (status === 'pass') return '\u2705';
    if (status === 'warning') return '\u26A0\uFE0F';
    return '\u274C';
  }

  return (
    <div>
      <h2
        className="text-[16px] font-semibold mb-3"
        style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
      >
        Readiness by Dimension
      </h2>

      <div className="flex gap-4 flex-col lg:flex-row">
        {/* Radar Chart */}
        <div
          className="border border-[var(--border)] rounded-[var(--radius-md)] p-3 bg-[var(--surface)] flex items-center justify-center"
          style={{ minWidth: 280, flex: '0 0 45%' }}
        >
          <ResponsiveContainer width={280} height={280}>
            <RadarChart data={radarData} cx="50%" cy="50%">
              <PolarGrid stroke="var(--border)" />
              <PolarAngleAxis
                dataKey="dimension"
                tick={{
                  fill: 'var(--text-secondary)',
                  fontSize: 10,
                  fontFamily: 'var(--font-display)',
                }}
              />
              <PolarRadiusAxis
                angle={90}
                domain={[0, 100]}
                tick={{ fontSize: 9, fill: 'var(--text-tertiary)' }}
                axisLine={false}
              />
              <Radar
                name="Score"
                dataKey="score"
                stroke="var(--accent)"
                fill="var(--accent)"
                fillOpacity={0.2}
                strokeWidth={2}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Dimension Table */}
        <div
          className="border border-[var(--border)] rounded-[var(--radius-md)] bg-[var(--surface)] flex-1 overflow-hidden"
        >
          <table className="w-full">
            <thead>
              <tr className="border-b border-[var(--border)]">
                {['Dimension', 'Score', 'What This Means for Citations', 'Findings', ''].map((h) => (
                  <th
                    key={h}
                    className="text-left px-3 py-2"
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                      color: 'var(--text-tertiary)',
                      fontFamily: 'var(--font-display)',
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {DIMENSIONS.map((dim, i) => {
                const isActive = activeDimension === dim.name;
                return (
                  <tr
                    key={dim.name}
                    className="border-b border-[var(--border)] last:border-b-0 cursor-pointer hover:bg-[var(--accent-subtle)] transition-colors"
                    style={{
                      backgroundColor: isActive ? 'var(--accent-subtle)' : undefined,
                      animation: `fadeUp 200ms ease ${i * 30}ms both`,
                    }}
                    onClick={() => onDimensionClick(isActive ? null : dim.name)}
                  >
                    <td
                      className="px-3 py-1.5 text-[13px] font-medium"
                      style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
                    >
                      {dim.name}
                    </td>
                    <td className="px-3 py-1.5">
                      <span
                        className="text-[14px] font-medium"
                        style={{ fontFamily: 'var(--font-mono)', color: scoreColor(dim.score) }}
                      >
                        {dim.score}
                      </span>
                    </td>
                    <td
                      className="px-3 py-1.5 text-[12px]"
                      style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}
                    >
                      {dim.explanation}
                    </td>
                    <td className="px-3 py-1.5">
                      <span
                        className="text-[12px]"
                        style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}
                      >
                        {dim.findings}
                      </span>
                    </td>
                    <td className="px-3 py-1.5 text-center text-[14px]">
                      {statusIcon(dim.status)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
