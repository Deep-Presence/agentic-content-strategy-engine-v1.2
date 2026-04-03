'use client';

import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ZAxis, Cell, ReferenceLine, Label,
} from 'recharts';
import type { CPSScatterDatum } from './data';

interface CPSScatterChartProps {
  data: CPSScatterDatum[];
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: CPSScatterDatum }> }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{
      background: 'var(--surface)', border: '1px solid var(--border)',
      borderRadius: 4, padding: '8px 12px', boxShadow: 'var(--shadow-float)',
    }}>
      <p style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)' }}>{d.title}</p>
      <div style={{ display: 'flex', gap: 16, marginTop: 4 }}>
        <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
          Predicted: <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 500 }}>{d.predicted.toFixed(2)}</span>
        </span>
        <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
          Actual: <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 500 }}>{d.actual.toFixed(2)}</span>
        </span>
      </div>
      <p style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>
        {d.citations} citations
      </p>
    </div>
  );
}

export function CPSScatterChart({ data }: CPSScatterChartProps) {
  // Find top 3-4 most deviant dots
  const withDeviation = data.map((d) => ({
    ...d,
    deviation: Math.abs(d.actual - d.predicted),
    overperformer: d.actual > d.predicted,
  }));
  const topDeviators = [...withDeviation].sort((a, b) => b.deviation - a.deviation).slice(0, 4);
  const topDeviatorTitles = new Set(topDeviators.map((d) => d.title));

  return (
    <div style={{ border: '1px solid var(--border)', background: 'var(--surface)', borderRadius: 4, padding: 12 }}>
      <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>
        CPS: Predicted vs Actual
      </h3>
      <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
        Dots sized by citation count — green overperformers, red underperformers
      </p>
      <div style={{ height: 280, marginTop: 12, position: 'relative' }}>
        {/* Annotations */}
        <div style={{
          position: 'absolute', top: 16, left: 48, fontSize: 10,
          color: 'var(--text-secondary)', fontStyle: 'italic', zIndex: 1,
        }}>
          Overperformer
        </div>
        <div style={{
          position: 'absolute', bottom: 48, right: 16, fontSize: 10,
          color: 'var(--text-secondary)', fontStyle: 'italic', zIndex: 1,
        }}>
          Underperformer
        </div>

        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 16, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis
              dataKey="predicted"
              type="number"
              name="Predicted CPS"
              domain={[0.3, 0.9]}
              tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }}
              tickLine={false}
              axisLine={{ stroke: 'var(--border)' }}
            >
              <Label value="Predicted CPS" position="bottom" offset={-2} style={{ fontSize: 11, fill: 'var(--text-tertiary)' }} />
            </XAxis>
            <YAxis
              dataKey="actual"
              type="number"
              name="Actual CPS"
              domain={[0.3, 0.9]}
              tick={{ fontSize: 11, fill: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}
              tickLine={false}
              axisLine={{ stroke: 'var(--border)' }}
            >
              <Label value="Actual CPS" angle={-90} position="insideLeft" offset={10} style={{ fontSize: 11, fill: 'var(--text-tertiary)' }} />
            </YAxis>
            <ZAxis dataKey="citations" range={[64, 400]} />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine
              segment={[{ x: 0.3, y: 0.3 }, { x: 0.9, y: 0.9 }]}
              stroke="var(--text-secondary)"
              strokeOpacity={0.3}
              strokeDasharray="4 4"
            />
            <Scatter data={withDeviation} fillOpacity={0.85}>
              {withDeviation.map((entry, idx) => (
                <Cell
                  key={idx}
                  fill={entry.overperformer ? '#34B27B' : '#E5484D'}
                  stroke={entry.overperformer ? '#34B27B' : '#E5484D'}
                  strokeWidth={1}
                />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>

        {/* Labels for top deviators — positioned via approximate pixel mapping */}
        {withDeviation.filter((d) => topDeviatorTitles.has(d.title)).map((d, i) => {
          // Map data coords to approximate pixel positions (chart area ~80% of container width)
          const chartLeft = 48;
          const chartWidth = 100; // percent-based, approximate
          const xPct = ((d.predicted - 0.3) / 0.6) * chartWidth;
          const yPct = ((0.9 - d.actual) / 0.6) * chartWidth;
          const labelText = d.title.length > 15 ? d.title.slice(0, 15) + '\u2026' : d.title;
          const offsets = [
            { dx: 12, dy: -12 },
            { dx: -80, dy: -14 },
            { dx: 12, dy: 12 },
            { dx: -80, dy: 12 },
          ];
          const off = offsets[i % offsets.length];
          return (
            <div
              key={d.title}
              style={{
                position: 'absolute',
                left: `calc(${chartLeft}px + ${xPct}% * 0.82 + ${off.dx}px)`,
                top: `calc(${16}px + ${yPct}% * 0.82 + ${off.dy}px)`,
                fontSize: 10,
                color: 'var(--text-secondary)',
                whiteSpace: 'nowrap',
                pointerEvents: 'none',
                zIndex: 2,
              }}
            >
              {labelText}
            </div>
          );
        })}
      </div>
    </div>
  );
}
