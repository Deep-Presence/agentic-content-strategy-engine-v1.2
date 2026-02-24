'use client';

import { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { PLATFORM_TRENDS } from '../data/sample-data';

const PLATFORM_COLORS = {
  chatgpt: '#d97757',
  claude: '#6a9bcc',
  perplexity: '#788c5d',
  gemini: '#b0aea5',
} as const;

const PLATFORM_LABELS = {
  chatgpt: 'ChatGPT',
  claude: 'Claude',
  perplexity: 'Perplexity',
  gemini: 'Gemini',
} as const;

interface TrendDataPoint {
  run: string;
  chatgpt: number;
  claude: number;
  perplexity: number;
  gemini: number;
}

export default function PlatformTrendChart() {
  const data: TrendDataPoint[] = useMemo(
    () =>
      PLATFORM_TRENDS.map((entry) => ({
        run: entry.run,
        chatgpt: entry.chatgpt,
        claude: entry.claude,
        perplexity: entry.perplexity,
        gemini: entry.gemini,
      })),
    []
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="font-serif">Platform Citation Trend</CardTitle>
        <CardDescription className="font-sans">
          Citations found across consecutive analysis runs
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={360}>
          <LineChart
            data={data}
            margin={{ top: 8, right: 24, bottom: 8, left: 8 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#e8e6e1"
              vertical={false}
            />
            <XAxis
              dataKey="run"
              tick={{ fontSize: 12, fill: '#141413', opacity: 0.6 }}
              tickLine={false}
              axisLine={{ stroke: '#e8e6e1' }}
              dy={8}
            />
            <YAxis
              tick={{ fontSize: 11, fill: '#141413', opacity: 0.5 }}
              tickLine={false}
              axisLine={false}
              width={40}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#faf9f5',
                border: '1px solid #e8e6e1',
                borderRadius: '8px',
                fontSize: '12px',
                fontFamily: 'sans-serif',
                boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
              }}
              labelStyle={{
                fontWeight: 600,
                marginBottom: '4px',
                color: '#141413',
              }}
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              formatter={((value: any, name: any) => [
                `${value} citations`,
                PLATFORM_LABELS[name as keyof typeof PLATFORM_LABELS] ?? name,
              ]) as any}
            />
            <Legend
              verticalAlign="bottom"
              height={40}
              iconType="circle"
              iconSize={8}
              wrapperStyle={{ fontSize: '12px', fontFamily: 'sans-serif' }}
              formatter={(value: string) =>
                PLATFORM_LABELS[value as keyof typeof PLATFORM_LABELS] ?? value
              }
            />

            {/* ChatGPT line */}
            <Line
              type="monotone"
              dataKey="chatgpt"
              stroke={PLATFORM_COLORS.chatgpt}
              strokeWidth={2.5}
              dot={{
                r: 5,
                fill: PLATFORM_COLORS.chatgpt,
                stroke: '#faf9f5',
                strokeWidth: 2,
              }}
              activeDot={{
                r: 7,
                fill: PLATFORM_COLORS.chatgpt,
                stroke: '#faf9f5',
                strokeWidth: 2,
              }}
            />

            {/* Claude line */}
            <Line
              type="monotone"
              dataKey="claude"
              stroke={PLATFORM_COLORS.claude}
              strokeWidth={2.5}
              dot={{
                r: 5,
                fill: PLATFORM_COLORS.claude,
                stroke: '#faf9f5',
                strokeWidth: 2,
              }}
              activeDot={{
                r: 7,
                fill: PLATFORM_COLORS.claude,
                stroke: '#faf9f5',
                strokeWidth: 2,
              }}
            />

            {/* Perplexity line */}
            <Line
              type="monotone"
              dataKey="perplexity"
              stroke={PLATFORM_COLORS.perplexity}
              strokeWidth={2.5}
              dot={{
                r: 5,
                fill: PLATFORM_COLORS.perplexity,
                stroke: '#faf9f5',
                strokeWidth: 2,
              }}
              activeDot={{
                r: 7,
                fill: PLATFORM_COLORS.perplexity,
                stroke: '#faf9f5',
                strokeWidth: 2,
              }}
            />

            {/* Gemini line */}
            <Line
              type="monotone"
              dataKey="gemini"
              stroke={PLATFORM_COLORS.gemini}
              strokeWidth={2.5}
              dot={{
                r: 5,
                fill: PLATFORM_COLORS.gemini,
                stroke: '#faf9f5',
                strokeWidth: 2,
              }}
              activeDot={{
                r: 7,
                fill: PLATFORM_COLORS.gemini,
                stroke: '#faf9f5',
                strokeWidth: 2,
              }}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
