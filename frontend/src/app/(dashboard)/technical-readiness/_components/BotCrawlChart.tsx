'use client';

import { BOT_CRAWL_DATA, BOT_COLORS, BOT_DOMAINS, CRAWL_SUMMARY, BOT_KEYS } from './tech-readiness-data';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

function BrandLogo({ domain, size = 12 }: { domain: string; size?: number }) {
  return (
    <img
      src={`https://www.google.com/s2/favicons?domain=${domain}&sz=${size * 2}`}
      alt={domain}
      width={size}
      height={size}
      style={{ borderRadius: 3 }}
      onError={(e) => {
        const target = e.target as HTMLImageElement;
        if (!target.dataset.fallback) {
          target.dataset.fallback = '1';
          target.src = `https://logo.clearbit.com/${domain}`;
        }
      }}
    />
  );
}

export function BotCrawlChart() {
  return (
    <div style={{ border: '1px solid var(--border)', background: 'var(--surface)', borderRadius: '6px', padding: '12px' }}>
      {/* Title + inline legend */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <div>
          <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '2px' }}>
            Bot Crawl Activity
          </h3>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            AI bot crawl requests per day over the last 28 days
          </p>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
          {BOT_KEYS.map((key) => (
            <span key={key} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ width: 16, height: 2, background: BOT_COLORS[key], display: 'inline-block', borderRadius: 1 }} />
              <BrandLogo domain={BOT_DOMAINS[key]} size={12} />
              <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{key}</span>
            </span>
          ))}
        </div>
      </div>

      <div style={{ width: '100%', height: 260 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={BOT_CRAWL_DATA}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }}
              axisLine={{ stroke: 'var(--border)' }}
              tickLine={false}
              interval={6}
            />
            <YAxis
              tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }}
              axisLine={false}
              tickLine={false}
              label={{
                value: 'Requests/day',
                angle: -90,
                position: 'insideLeft',
                style: { fontSize: 11, fill: 'var(--text-tertiary)' },
              }}
            />
            <Tooltip
              contentStyle={{
                background: 'var(--surface-raised)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                fontSize: 11,
              }}
              labelStyle={{ fontWeight: 500, marginBottom: 4 }}
            />
            {BOT_KEYS.map((key) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                name={key}
                stroke={BOT_COLORS[key]}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Summary rows */}
      <div style={{ borderTop: '1px solid var(--border)', marginTop: '8px', paddingTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center' }}>
          <span style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-tertiary)' }}>
            Total crawls (28d):
          </span>
          {BOT_KEYS.map((key) => (
            <span key={key} style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px' }}>
              <BrandLogo domain={BOT_DOMAINS[key]} size={12} />
              <span style={{ color: BOT_COLORS[key] }}>{key}</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)' }}>
                {CRAWL_SUMMARY.totals[key]}
              </span>
            </span>
          ))}
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center' }}>
          <span style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-tertiary)' }}>
            Last crawl:
          </span>
          {BOT_KEYS.map((key) => (
            <span key={key} style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px' }}>
              <BrandLogo domain={BOT_DOMAINS[key]} size={12} />
              <span style={{ color: BOT_COLORS[key] }}>{key}</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                {CRAWL_SUMMARY.lastCrawl[key]}
              </span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
