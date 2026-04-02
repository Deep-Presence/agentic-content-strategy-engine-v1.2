'use client';

interface KPIItem {
  label: string;
  value: string;
  trend?: string;
  trendType?: 'positive' | 'negative' | 'neutral';
  sub: string;
}

const kpis: KPIItem[] = [
  { label: 'Gap to #1', value: '-5.8pp', trend: 'was -7.9pp 30d ago', trendType: 'positive', sub: 'vs bolt.new' },
  { label: 'Gap Trend', value: 'Closing', trend: '↑ +2.1pp/30d', trendType: 'positive', sub: '8-week direction' },
  { label: 'Avg Win Rate', value: '39%', trend: '↑ from 34%', trendType: 'positive', sub: 'vs top 5 competitors' },
  { label: 'At-Risk Citations', value: '4', trend: '+2 this period', trendType: 'negative', sub: 'queries drifting' },
  { label: 'Early Warnings', value: '2', sub: 'pre-drift signals' },
  { label: 'Recapture Opps', value: '3', sub: 'lost but recoverable' },
];

export function KPIStrip() {
  return (
    <div
      className="grid gap-px rounded-sm overflow-hidden"
      style={{ gridTemplateColumns: `repeat(6, 1fr)`, background: 'var(--border)' }}
    >
      {kpis.map((kpi) => (
        <div key={kpi.label} className="p-3" style={{ background: 'var(--bg)' }}>
          <p
            className="uppercase"
            style={{
              fontSize: '11px',
              fontWeight: 500,
              letterSpacing: '0.05em',
              color: 'var(--text-secondary)',
              lineHeight: 1.4,
            }}
          >
            {kpi.label}
          </p>
          <p
            className="mt-1"
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '28px',
              fontWeight: 600,
              letterSpacing: '-0.02em',
              color: 'var(--text-primary)',
              lineHeight: 1.15,
            }}
          >
            {kpi.value}
          </p>
          {kpi.trend && (
            <p
              style={{
                fontSize: '12px',
                fontFamily: 'var(--font-mono)',
                fontWeight: 500,
                marginTop: '2px',
                color: kpi.trendType === 'positive'
                  ? 'var(--success)'
                  : kpi.trendType === 'negative'
                  ? 'var(--error)'
                  : 'var(--text-tertiary)',
              }}
            >
              {kpi.trend}
            </p>
          )}
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
            {kpi.sub}
          </p>
        </div>
      ))}
    </div>
  );
}
