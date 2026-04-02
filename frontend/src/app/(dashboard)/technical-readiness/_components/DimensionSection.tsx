'use client';

import { DIMENSIONS } from './tech-readiness-data';
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from 'recharts';
import { X } from 'lucide-react';

interface DimensionSectionProps {
  selectedDimension: string | null;
  onSelectDimension: (name: string | null) => void;
}

function statusIcon(score: number): string {
  if (score >= 90) return '\u2705';
  if (score >= 70) return '\u26A0\uFE0F';
  return '\u274C';
}

export function DimensionSection({ selectedDimension, onSelectDimension }: DimensionSectionProps) {
  const radarData = DIMENSIONS.map((d) => ({
    dimension: d.name,
    score: d.score,
    fullMark: 100,
  }));

  return (
    <div className="grid gap-4" style={{ gridTemplateColumns: '2fr 3fr' }}>
      {/* Left: Radar Chart (40%) */}
      <div style={{ border: '1px solid var(--border)', background: 'var(--surface)', borderRadius: '6px', padding: '12px' }}>
        <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
          Dimension Scores
        </h3>
        <div style={{ width: '100%', height: 280 }}>
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart cx="50%" cy="50%" outerRadius="70%" data={radarData}>
              <PolarGrid stroke="var(--border)" />
              <PolarAngleAxis
                dataKey="dimension"
                tick={{ fontSize: 11, fill: 'var(--text-secondary)' }}
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
                fillOpacity={0.12}
                strokeWidth={2}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Right: Dimension Table (60%) */}
      <div style={{ border: '1px solid var(--border)', background: 'var(--surface)', borderRadius: '6px', padding: '12px' }}>
        <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
          Dimension Breakdown
        </h3>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              <th style={{ textAlign: 'left', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-tertiary)', padding: '6px 8px' }}>
                Dimension
              </th>
              <th style={{ textAlign: 'right', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-tertiary)', padding: '6px 8px' }}>
                Score
              </th>
              <th style={{ textAlign: 'right', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-tertiary)', padding: '6px 8px' }}>
                Weight
              </th>
              <th style={{ textAlign: 'right', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-tertiary)', padding: '6px 8px' }}>
                Findings
              </th>
              <th style={{ textAlign: 'center', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-tertiary)', padding: '6px 8px' }}>
                Status
              </th>
            </tr>
          </thead>
          <tbody>
            {DIMENSIONS.map((dim) => {
              const isSelected = selectedDimension === dim.name;
              return (
                <tr
                  key={dim.name}
                  onClick={() => onSelectDimension(isSelected ? null : dim.name)}
                  style={{
                    height: '40px',
                    borderBottom: '1px solid var(--border-subtle)',
                    cursor: 'pointer',
                    background: isSelected ? 'var(--accent-subtle)' : undefined,
                    transition: 'background 0.1s',
                  }}
                  onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.background = 'var(--accent-subtle)'; }}
                  onMouseLeave={(e) => { if (!isSelected) e.currentTarget.style.background = ''; }}
                >
                  <td style={{ fontSize: '13px', color: 'var(--text-primary)', padding: '6px 8px' }}>
                    <span className="flex items-center gap-1.5">
                      {dim.name}
                      {isSelected && (
                        <button
                          onClick={(e) => { e.stopPropagation(); onSelectDimension(null); }}
                          style={{
                            width: 16, height: 16, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                            borderRadius: 3, color: 'var(--text-tertiary)', cursor: 'pointer', background: 'none', border: 'none',
                          }}
                        >
                          <X size={12} strokeWidth={1.5} />
                        </button>
                      )}
                    </span>
                  </td>
                  <td style={{ textAlign: 'right', fontSize: '13px', fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)', padding: '6px 8px' }}>
                    {dim.score}
                  </td>
                  <td style={{ textAlign: 'right', fontSize: '13px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', padding: '6px 8px' }}>
                    {dim.weight}
                  </td>
                  <td style={{ textAlign: 'right', fontSize: '13px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', padding: '6px 8px' }}>
                    {dim.findings.toLocaleString()}
                  </td>
                  <td style={{ textAlign: 'center', fontSize: '13px', padding: '6px 8px' }}>
                    {statusIcon(dim.score)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '8px', paddingLeft: '8px' }}>
          Click a dimension to filter findings below
        </p>
      </div>
    </div>
  );
}
