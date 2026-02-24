'use client';

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';

interface VisibilityTrendPanelProps {
  data: Array<{ week: string; score: number }>;
}

const TOOLTIP_STYLE = {
  backgroundColor: '#ffffff',
  border: '1px solid var(--border-default)',
  borderRadius: 6,
  fontSize: 12,
  fontFamily: 'ui-sans-serif, sans-serif',
};

const TICK_STYLE = {
  fontSize: 10,
  fill: 'var(--text-tertiary)',
  fontFamily: 'ui-sans-serif, sans-serif',
};

export function VisibilityTrendPanel({ data }: VisibilityTrendPanelProps) {
  const latest = data[data.length - 1];
  const earliest = data[0];
  const change = latest.score - earliest.score;

  return (
    <Card className="animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>AI Visibility Score — 12 Week Trend</CardTitle>
            <CardDescription>Weekly aggregate across ChatGPT, Claude, Perplexity, Gemini</CardDescription>
          </div>
          <div className="text-right">
            <span className="font-sans text-heading-3 font-semibold text-terracotta-400">
              +{change} pts
            </span>
            <p className="text-micro font-sans text-cream-600">since {earliest.week}</p>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="gradTerracotta" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#d97757" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#d97757" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
            <XAxis dataKey="week" tick={TICK_STYLE} axisLine={false} tickLine={false} />
            <YAxis domain={[0, 100]} tick={TICK_STYLE} axisLine={false} tickLine={false} width={30} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <ReferenceLine
              y={70}
              stroke="var(--text-muted)"
              strokeDasharray="6 4"
              label={{
                value: 'Target: 70%',
                position: 'right',
                fill: 'var(--text-muted)',
                fontSize: 10,
                fontFamily: 'ui-sans-serif, sans-serif',
              }}
            />
            <Area
              type="monotone"
              dataKey="score"
              stroke="#d97757"
              fill="url(#gradTerracotta)"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 2, fill: '#fff', stroke: '#d97757' }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
