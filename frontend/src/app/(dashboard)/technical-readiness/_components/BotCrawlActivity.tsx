'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import {
  BOT_CRAWL_DATA,
  BOT_COLORS,
  BOT_DOMAINS,
  BOT_KEYS,
  CRAWL_SUMMARY,
} from './tech-readiness-data';

function BrandLogo({ domain, size = 12 }: { domain: string; size?: number }) {
  return (
    <img
      src={`https://www.google.com/s2/favicons?domain=${domain}&sz=${size * 2}`}
      alt={domain}
      width={size}
      height={size}
      style={{ borderRadius: 2 }}
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

function lastCrawlColor(time: string): string {
  const hours = parseInt(time);
  if (isNaN(hours)) return 'var(--text-secondary)';
  if (hours < 6) return 'var(--success)';
  if (hours <= 24) return 'var(--warning)';
  return 'var(--error)';
}

export function BotCrawlActivity() {
  return (
    <div>
      <div className="mb-3">
        <h2
          className="text-[16px] font-semibold"
          style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
        >
          Bot Crawl Activity
        </h2>
        <p className="text-[12px]" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
          AI bot crawl requests per day over the last 28 days
        </p>
      </div>

      {/* Summary Stats */}
      <div className="border border-[var(--border)] rounded-[var(--radius-md)] p-3 bg-[var(--surface)] mb-3">
        <div className="flex flex-wrap gap-x-4 gap-y-1 mb-2">
          <span
            className="text-[10px] uppercase tracking-[0.05em] font-semibold"
            style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}
          >
            Total Crawls (28d):
          </span>
          {BOT_KEYS.map((bot) => (
            <span key={bot} className="flex items-center gap-1">
              <BrandLogo domain={BOT_DOMAINS[bot]} size={12} />
              <span className="text-[11px]" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
                {bot}
              </span>
              <span className="text-[11px] font-medium" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                {CRAWL_SUMMARY.totals[bot]}
              </span>
            </span>
          ))}
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          <span
            className="text-[10px] uppercase tracking-[0.05em] font-semibold"
            style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}
          >
            Last Crawl:
          </span>
          {BOT_KEYS.map((bot) => (
            <span key={bot} className="flex items-center gap-1">
              <BrandLogo domain={BOT_DOMAINS[bot]} size={12} />
              <span className="text-[11px]" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
                {bot}
              </span>
              <span
                className="text-[11px] font-medium"
                style={{ fontFamily: 'var(--font-mono)', color: lastCrawlColor(CRAWL_SUMMARY.lastCrawl[bot]) }}
              >
                {CRAWL_SUMMARY.lastCrawl[bot]}
              </span>
            </span>
          ))}
        </div>
      </div>

      {/* Chart */}
      <div className="border border-[var(--border)] rounded-[var(--radius-md)] p-3 bg-[var(--surface)]">
        {/* Legend */}
        <div className="flex flex-wrap gap-3 mb-3">
          {BOT_KEYS.map((bot) => (
            <div key={bot} className="flex items-center gap-1.5">
              <BrandLogo domain={BOT_DOMAINS[bot]} size={12} />
              <span className="text-[11px]" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
                {bot}
              </span>
              <span
                className="inline-block w-3 h-[2px] rounded-full"
                style={{ backgroundColor: BOT_COLORS[bot] }}
              />
            </div>
          ))}
        </div>

        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={BOT_CRAWL_DATA}>
            <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}
              interval={6}
            />
            <YAxis
              tick={{ fontSize: 10, fill: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}
              width={40}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'var(--surface)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-md)',
                fontSize: 11,
                fontFamily: 'var(--font-display)',
              }}
              labelStyle={{ color: 'var(--text-primary)', fontWeight: 600 }}
            />
            {BOT_KEYS.map((bot) => (
              <Line
                key={bot}
                type="monotone"
                dataKey={bot}
                stroke={BOT_COLORS[bot]}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3, strokeWidth: 0 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
