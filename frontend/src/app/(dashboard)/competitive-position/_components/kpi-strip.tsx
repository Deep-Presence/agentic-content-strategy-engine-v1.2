'use client';

import { YOUR_DATA } from './data';

interface KPICardProps {
  label: string;
  value: string;
  sub: string;
  borderColor?: string;
  valueColor?: string;
  delay: number;
}

function KPICard({ label, value, sub, borderColor, valueColor, delay }: KPICardProps) {
  return (
    <div
      style={{
        border: '1px solid var(--border)',
        borderRadius: '6px',
        padding: '14px',
        borderLeft: borderColor ? `2px solid ${borderColor}` : '1px solid var(--border)',
        animation: `fadeUp 400ms ease ${delay}ms both`,
      }}
    >
      <p
        style={{
          fontSize: '10px',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: 'var(--text-secondary)',
          fontFamily: 'var(--font-display)',
        }}
      >
        {label}
      </p>
      <p
        style={{
          fontSize: '28px',
          fontWeight: 600,
          fontFamily: 'var(--font-mono)',
          color: valueColor || 'var(--text-primary)',
          marginTop: '4px',
          lineHeight: 1.1,
        }}
      >
        {value}
      </p>
      <p
        style={{
          fontSize: '13px',
          color: 'var(--text-secondary)',
          marginTop: '4px',
          fontFamily: 'var(--font-display)',
        }}
      >
        {sub}
      </p>
    </div>
  );
}

export function KPIStrip() {
  const d = YOUR_DATA;

  // Rank color: accent if top 3, amber 4-6, red 7+
  const rankBorder = d.rank <= 3 ? 'var(--accent)' : d.rank <= 6 ? 'var(--warning)' : 'var(--error)';

  // Win rate color
  const winColor = d.winRate > 50 ? 'var(--success)' : d.winRate >= 30 ? 'var(--warning)' : 'var(--error)';

  // At-risk color
  const atRiskColor = d.atRisk > 0 ? 'var(--error)' : 'var(--success)';
  const atRiskValue = d.atRisk > 0 ? String(d.atRisk) : '0';
  const atRiskSub = d.atRisk > 0 ? `${d.lost} lost this week` : 'All stable — no action needed';

  // Growth direction
  const growthColor =
    d.growthDirection === 'gaining' ? 'var(--success)' : d.growthDirection === 'losing' ? 'var(--error)' : 'var(--text-secondary)';
  const growthWord = d.growthDirection === 'gaining' ? 'Gaining' : d.growthDirection === 'losing' ? 'Losing' : 'Stable';
  const growthSub =
    d.growthDelta > 0 ? `+${d.growthDelta} points this month` : d.growthDelta < 0 ? `${d.growthDelta} points this month` : 'No change this month';

  return (
    <div className="grid grid-cols-4" style={{ gap: '12px' }}>
      <KPICard label="Your Rank" value={`#${d.rank}`} sub={`out of ${d.totalTracked} tracked`} borderColor={rankBorder} delay={0} />
      <KPICard label="Win Rate" value={`${d.winRate}%`} sub="vs top 5 rivals" valueColor={winColor} delay={40} />
      <KPICard label="At-Risk Citations" value={atRiskValue} sub={atRiskSub} valueColor={atRiskColor} delay={80} />
      <KPICard label="Growth Direction" value={growthWord} sub={growthSub} valueColor={growthColor} delay={120} />
    </div>
  );
}
