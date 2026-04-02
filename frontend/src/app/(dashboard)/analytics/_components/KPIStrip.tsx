'use client';

import { KPI_DATA } from './data';

export function KPIStrip() {
  return (
    <div
      className="grid grid-cols-6"
      style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}
    >
      {KPI_DATA.map((kpi, i) => (
        <div
          key={kpi.label}
          className="p-3 flex flex-col gap-1"
          style={{
            borderLeft: i > 0 ? '1px solid var(--border)' : 'none',
            background: 'var(--surface)',
          }}
        >
          <span
            className="text-[11px] font-medium uppercase"
            style={{ letterSpacing: '0.05em', color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}
          >
            {kpi.label}
          </span>
          <span
            className="text-[28px] font-semibold leading-none"
            style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}
          >
            {kpi.value}
          </span>
          <div className="flex items-center gap-2">
            <span
              className="text-[12px] font-medium"
              style={{
                color: kpi.trendType === 'positive' ? 'var(--success)' : kpi.trendType === 'negative' ? 'var(--error)' : 'var(--text-tertiary)',
              }}
            >
              {kpi.trend}
            </span>
          </div>
          <span className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
            {kpi.sub}
          </span>
        </div>
      ))}
    </div>
  );
}
