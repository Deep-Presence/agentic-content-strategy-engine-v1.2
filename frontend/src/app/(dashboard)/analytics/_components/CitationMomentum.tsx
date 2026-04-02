'use client';

import { useMemo, useState, useCallback } from 'react';
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceDot,
} from 'recharts';
import { X } from 'lucide-react';
import { generateMomentumData, PLATFORM_COLORS, PLATFORM_DOMAINS, CHART_EVENTS, generateDayBreakdown } from './data';
import { BrandLogo } from './BrandLogo';

const PLATFORMS = ['ChatGPT', 'Claude', 'Perplexity', 'Google AI', 'Gemini'] as const;

// ─── Custom Tooltip ─────────────────────────────────────────────────────────

function MomentumTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ dataKey: string; value: number; fill?: string; color?: string }>; label?: string }) {
  if (!active || !payload) return null;
  const total = payload.reduce((sum, p) => sum + (p.dataKey !== 'sov' && p.dataKey !== 'competitorSov' ? (p.value || 0) : 0), 0);
  const sov = payload.find((p) => p.dataKey === 'sov')?.value;

  return (
    <div
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        padding: '12px',
        borderRadius: '4px',
        maxWidth: '280px',
        fontFamily: 'var(--font-display)',
      }}
    >
      <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>{label}</div>
      <div style={{ fontSize: '20px', fontFamily: 'var(--font-mono)', fontWeight: 600, marginTop: '4px', color: 'var(--text-primary)' }}>
        {total} citations
      </div>
      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
        SOV: {sov?.toFixed(1)}%
      </div>
      <div style={{ borderTop: '1px solid var(--border)', marginTop: '8px', paddingTop: '8px' }}>
        {payload
          .filter((p) => p.dataKey !== 'sov' && p.dataKey !== 'competitorSov')
          .map((p) => (
            <div
              key={p.dataKey}
              style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', marginTop: '4px' }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-primary)' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '2px', background: p.fill || p.color }} />
                {p.dataKey}
              </span>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{p.value}</span>
            </div>
          ))}
      </div>
      <div style={{ borderTop: '1px solid var(--border)', marginTop: '8px', paddingTop: '8px', fontSize: '11px', color: 'var(--text-secondary)' }}>
        Click for detailed breakdown &rarr;
      </div>
    </div>
  );
}

// ─── Main Component ─────────────────────────────────────────────────────────

export function CitationMomentum() {
  const rawData = useMemo(() => generateMomentumData(), []);
  const [isHovered, setIsHovered] = useState(false);
  const [expandedDay, setExpandedDay] = useState<string | null>(null);
  // Event hover handled by legend strip below chart

  // Enhance data with competitor SOV ghost line
  const data = useMemo(() => {
    return rawData.map((d, i) => ({
      ...d,
      competitorSov: parseFloat((18.2 - i * 0.04 + (Math.random() * 0.5 - 0.25)).toFixed(1)),
    }));
  }, [rawData]);

  const handleBarClick = useCallback((entry: Record<string, unknown>) => {
    if (entry && entry.date) {
      setExpandedDay((prev) => (prev === entry.date ? null : (entry.date as string)));
    }
  }, []);

  // Generate day breakdown for expanded panel
  const dayBreakdownData = useMemo(() => {
    if (!expandedDay) return null;
    const dayData = data.find((d) => d.date === expandedDay);
    if (!dayData) return null;
    const prev = data.find((d) => d.date === `Mar ${parseInt(expandedDay.replace('Mar ', '')) - 1}`);
    const total = PLATFORMS.reduce((sum, p) => sum + (dayData[p] || 0), 0);
    const prevTotal = prev ? PLATFORMS.reduce((sum, p) => sum + ((prev[p] as number) || 0), 0) : total;
    return {
      date: expandedDay,
      total,
      delta: total - prevTotal,
      breakdown: generateDayBreakdown(expandedDay, dayData as unknown as Record<string, number>),
    };
  }, [expandedDay, data]);

  return (
    <div
      className="p-3"
      style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface)' }}
    >
      {/* Header + Legend */}
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-[15px] font-semibold" style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}>
            Citation Momentum
          </h3>
          <p className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
            Daily citation volume by platform + Share of Voice trend
          </p>
        </div>
        <div className="flex items-center gap-4">
          {PLATFORMS.map((p) => (
            <div key={p} className="flex items-center gap-1.5">
              <BrandLogo domain={PLATFORM_DOMAINS[p]} size={12} />
              <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ background: PLATFORM_COLORS[p] }} />
              <span className="text-[11px]" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
                {p}
              </span>
            </div>
          ))}
          <div className="flex items-center gap-1.5">
            <span className="w-6 h-[3px] rounded-full" style={{ background: 'var(--accent)' }} />
            <span className="text-[11px]" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>SOV %</span>
          </div>
          {isHovered && (
            <div className="flex items-center gap-1.5">
              <span className="w-6 h-[3px] rounded-full" style={{ background: 'var(--text-secondary)', opacity: 0.5 }} />
              <span className="text-[10px]" style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}>bolt.new</span>
            </div>
          )}
        </div>
      </div>

      {/* Chart */}
      <div
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart
            data={data}
            margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
            onClick={(state: Record<string, unknown>) => {
              const ap = (state as { activePayload?: Array<{ payload: Record<string, unknown> }> })?.activePayload;
              if (ap?.[0]?.payload) {
                handleBarClick(ap[0].payload);
              }
            }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}
              tickLine={false}
              axisLine={{ stroke: 'var(--border)' }}
              interval={3}
            />
            <YAxis
              yAxisId="left"
              tick={{ fontSize: 11, fill: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}
              tickLine={false}
              axisLine={false}
              width={36}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fontSize: 11, fill: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}
              tickLine={false}
              axisLine={false}
              width={40}
              tickFormatter={(v: number) => `${v}%`}
              domain={[0, 20]}
            />
            <Tooltip content={<MomentumTooltip />} />
            {PLATFORMS.map((p) => (
              <Bar key={p} yAxisId="left" dataKey={p} stackId="citations" fill={PLATFORM_COLORS[p]} radius={0} barSize={14} />
            ))}

            {/* Competitor ghost line */}
            <Line
              yAxisId="right"
              dataKey="competitorSov"
              stroke="var(--text-secondary)"
              strokeDasharray="4 4"
              strokeWidth={1.5}
              strokeOpacity={isHovered ? 0.35 : 0}
              dot={false}
              name="bolt.new SOV"
              style={{ transition: 'stroke-opacity 200ms' }}
            />

            {/* SOV line */}
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="sov"
              stroke="var(--accent)"
              strokeWidth={3}
              dot={{ fill: 'var(--accent)', r: 3, strokeWidth: 0 }}
              activeDot={{ r: 5, fill: 'var(--accent)', strokeWidth: 0 }}
            />

            {/* Event milestone markers */}
            {CHART_EVENTS.map((evt) => (
              <ReferenceDot
                key={evt.date}
                yAxisId="right"
                x={evt.date}
                y={evt.sov}
                r={6}
                fill={evt.color}
                stroke="var(--surface)"
                strokeWidth={2}
                label={{
                  value: evt.type === 'published' ? '▲' : evt.type === 'lost' ? '▼' : '●',
                  position: 'top',
                  fill: evt.color,
                  fontSize: 8,
                  offset: 8,
                }}
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Event Legend Strip */}
      <div
        className="flex items-center gap-4 overflow-x-auto mt-1 px-1"
        style={{ height: 28 }}
      >
        {CHART_EVENTS.map((evt) => (
          <div key={evt.date} className="flex items-center gap-1.5 flex-shrink-0">
            <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: evt.color }} />
            <span className="text-[10px]" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)', whiteSpace: 'nowrap' }}>
              {evt.date}: {evt.label}
            </span>
          </div>
        ))}
      </div>

      {/* Click-to-expand day breakdown panel */}
      {expandedDay && dayBreakdownData && (
        <div
          className="mt-2 p-3"
          style={{
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)',
            background: 'var(--surface)',
          }}
        >
          <div className="flex items-center justify-between mb-2">
            <div>
              <span className="text-[13px] font-semibold" style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
                {expandedDay}, 2026
              </span>
              <span className="text-[12px] ml-2" style={{ color: 'var(--text-secondary)' }}>
                — {dayBreakdownData.total} total citations
              </span>
              <span
                className="text-[12px] ml-1 font-medium"
                style={{ color: dayBreakdownData.delta >= 0 ? 'var(--success)' : 'var(--error)' }}
              >
                ({dayBreakdownData.delta >= 0 ? '+' : ''}{dayBreakdownData.delta} vs previous day)
              </span>
            </div>
            <button
              onClick={() => setExpandedDay(null)}
              className="w-[24px] h-[24px] flex items-center justify-center rounded-sm"
              style={{ color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
            >
              <X size={12} />
            </button>
          </div>
          <div className="flex flex-col gap-1">
            {dayBreakdownData.breakdown.map((row) => (
              <div key={row.platform} className="flex items-center gap-2" style={{ height: 30 }}>
                <BrandLogo domain={row.domain} size={14} />
                <span className="text-[12px] w-[72px]" style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
                  {row.platform}
                </span>
                <span className="text-[13px] w-[80px]" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                  {row.count} citations
                </span>
                <span
                  className="text-[11px] w-[36px]"
                  style={{
                    fontFamily: 'var(--font-mono)',
                    color: row.delta > 0 ? 'var(--success)' : row.delta < 0 ? 'var(--error)' : 'var(--text-tertiary)',
                  }}
                >
                  ({row.delta > 0 ? '+' : ''}{row.delta === 0 ? '—' : row.delta})
                </span>
                <span className="text-[12px] flex-1 truncate" style={{ color: 'var(--text-secondary)' }}>
                  {row.topEvent}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
