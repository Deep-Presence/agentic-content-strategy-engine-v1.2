'use client';

import { useState, useMemo } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import { REVENUE_PROXY, WEEKLY_REFERRALS } from './data';

// Mini bar chart component for Card 1
function MiniBarChart({ data }: { data: number[] }) {
  const max = Math.max(...data);
  return (
    <div className="flex items-end gap-[3px]" style={{ height: 40 }}>
      {data.map((v, i) => (
        <div
          key={i}
          className="flex-1 rounded-sm"
          style={{
            height: `${(v / max) * 100}%`,
            background: 'var(--accent)',
            opacity: 0.4 + (i / data.length) * 0.6,
            minWidth: 4,
          }}
        />
      ))}
    </div>
  );
}

// Comparison bars for Card 2
function ComparisonBars({ yours, industry }: { yours: number; industry: number }) {
  const max = Math.max(yours, industry);
  return (
    <div className="flex flex-col gap-1.5" style={{ marginTop: 4 }}>
      <div className="flex items-center gap-2">
        <span className="text-[10px] w-[28px]" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>You</span>
        <div className="flex-1 h-[6px] rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
          <div className="h-full rounded-full" style={{ width: `${(yours / max) * 100}%`, background: 'var(--accent)' }} />
        </div>
        <span className="text-[10px]" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{yours}%</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-[10px] w-[28px]" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>Avg</span>
        <div className="flex-1 h-[6px] rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
          <div className="h-full rounded-full" style={{ width: `${(industry / max) * 100}%`, background: 'var(--text-tertiary)' }} />
        </div>
        <span className="text-[10px]" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{industry}%</span>
      </div>
    </div>
  );
}

// Mini donut for Card 3
function MiniDonut({ value, total }: { value: number; total: number }) {
  const pct = (value / total) * 100;
  const data = [
    { name: 'filled', value: pct },
    { name: 'empty', value: 100 - pct },
  ];

  return (
    <div style={{ width: 32, height: 32 }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            cx="50%"
            cy="50%"
            innerRadius={10}
            outerRadius={16}
            startAngle={90}
            endAngle={-270}
            strokeWidth={0}
          >
            <Cell fill="var(--accent)" />
            <Cell fill="var(--border)" />
          </Pie>
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

export function RevenueProxy() {
  const [toastVisible, setToastVisible] = useState(false);

  const showToast = () => {
    setToastVisible(true);
    setTimeout(() => setToastVisible(false), 2500);
  };

  return (
    <div
      className="p-3"
      style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface)' }}
    >
      <div className="mb-3">
        <h3 className="text-[15px] font-semibold" style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}>
          AI Referral Potential
        </h3>
        <p className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
          Leading indicators — actual attribution requires CRM integration
        </p>
      </div>

      {/* 3 metric cards with visuals */}
      <div className="grid grid-cols-3 gap-3">
        {/* Card 1: Est. AI Referrals with mini bar chart */}
        <div className="p-3 flex flex-col gap-1" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}>
          <span
            className="text-[11px] uppercase font-medium"
            style={{ letterSpacing: '0.05em', color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}
          >
            {REVENUE_PROXY[0].label}
          </span>
          <div className="flex items-end justify-between gap-2">
            <span className="text-[20px] font-semibold" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
              {REVENUE_PROXY[0].value}
            </span>
            <MiniBarChart data={WEEKLY_REFERRALS} />
          </div>
          <span className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>{REVENUE_PROXY[0].sub}</span>
          <span className="text-[11px] font-medium" style={{ color: 'var(--success)' }}>{REVENUE_PROXY[0].trend}</span>
        </div>

        {/* Card 2: Citation-to-Visit Rate with comparison bars */}
        <div className="p-3 flex flex-col gap-1" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}>
          <span
            className="text-[11px] uppercase font-medium"
            style={{ letterSpacing: '0.05em', color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}
          >
            {REVENUE_PROXY[1].label}
          </span>
          <span className="text-[20px] font-semibold" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
            {REVENUE_PROXY[1].value}
          </span>
          <ComparisonBars yours={8.4} industry={6.2} />
          <span className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>{REVENUE_PROXY[1].sub}</span>
        </div>

        {/* Card 3: High-Intent Queries with mini donut */}
        <div className="p-3 flex flex-col gap-1" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}>
          <span
            className="text-[11px] uppercase font-medium"
            style={{ letterSpacing: '0.05em', color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}
          >
            {REVENUE_PROXY[2].label}
          </span>
          <div className="flex items-center gap-3">
            <span className="text-[20px] font-semibold" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
              {REVENUE_PROXY[2].value}
            </span>
            <MiniDonut value={14} total={47} />
          </div>
          <span className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>{REVENUE_PROXY[2].sub}</span>
          <span className="text-[11px] font-medium" style={{ color: 'var(--success)' }}>{REVENUE_PROXY[2].trend}</span>
        </div>
      </div>

      {/* CRM Note */}
      <div
        className="mt-3 p-3 text-[12px] leading-relaxed relative"
        style={{
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-md)',
          background: 'var(--surface)',
          color: 'var(--text-secondary)',
          fontFamily: 'var(--font-display)',
        }}
      >
        These are estimates based on industry benchmarks. Connect Google Analytics or your CRM to see actual attribution data.{' '}
        <button
          onClick={showToast}
          className="inline underline"
          style={{ color: 'var(--accent)' }}
        >
          Set up attribution &rarr;
        </button>

        {toastVisible && (
          <div
            className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 rounded-md text-[12px] font-medium whitespace-nowrap"
            style={{
              background: 'rgba(17,24,28,0.92)',
              color: '#EDEDED',
              backdropFilter: 'blur(8px)',
              boxShadow: 'var(--shadow-float)',
            }}
          >
            Attribution setup coming soon
          </div>
        )}
      </div>
    </div>
  );
}
