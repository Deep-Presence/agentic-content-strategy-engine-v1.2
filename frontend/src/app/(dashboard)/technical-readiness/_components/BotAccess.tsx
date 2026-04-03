'use client';

import { BOT_ACCESS, CRITICAL_FILES } from './tech-readiness-data';

function BrandLogo({ domain, size = 16 }: { domain: string; size?: number }) {
  return (
    <img
      src={`https://www.google.com/s2/favicons?domain=${domain}&sz=${size * 2}`}
      alt={domain}
      width={size}
      height={size}
      style={{ borderRadius: 4 }}
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

export function BotAccess() {
  return (
    <div>
      <h2
        className="text-[16px] font-semibold mb-3"
        style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
      >
        AI Bot Access
      </h2>

      {/* Bot Access Grid */}
      <div className="border border-[var(--border)] rounded-[var(--radius-md)] bg-[var(--surface)] overflow-hidden mb-3">
        {BOT_ACCESS.map((bot, i) => (
          <div
            key={bot.name}
            className="flex items-center justify-between px-3 py-2.5 border-b border-[var(--border)] last:border-b-0"
            style={{ animation: `fadeUp 200ms ease ${i * 40}ms both` }}
          >
            <div className="flex items-center gap-2.5">
              <BrandLogo domain={bot.domain} size={16} />
              <div>
                <div className="flex items-center gap-1.5">
                  <span
                    className="text-[13px] font-medium"
                    style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
                  >
                    {bot.name}
                  </span>
                  <span
                    className="text-[12px]"
                    style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}
                  >
                    ({bot.company})
                  </span>
                </div>
                <span
                  className="text-[11px]"
                  style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}
                >
                  Last crawl: {bot.lastCrawl}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5">
                <span
                  className="inline-block w-2 h-2 rounded-full"
                  style={{ backgroundColor: bot.status === 'allowed' ? 'var(--success)' : 'var(--error)' }}
                />
                <span
                  className="text-[12px] font-medium uppercase tracking-[0.03em]"
                  style={{
                    color: bot.status === 'allowed' ? 'var(--success)' : 'var(--error)',
                    fontFamily: 'var(--font-display)',
                  }}
                >
                  {bot.status}
                </span>
              </div>
              <span
                className="text-[11px]"
                style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}
              >
                robots.txt {bot.robotsTxt ? '\u2713' : '\u2717'}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Critical Files Status */}
      <div className="border border-[var(--border)] rounded-[var(--radius-md)] bg-[var(--surface)] overflow-hidden">
        {CRITICAL_FILES.map((file) => {
          const isLlms = file.name === 'llms.txt';
          return (
            <div
              key={file.name}
              className="flex items-center justify-between px-3 py-2.5 border-b border-[var(--border)] last:border-b-0"
              style={{
                backgroundColor: isLlms ? 'var(--error-subtle)' : undefined,
                borderLeft: isLlms ? '3px solid var(--error)' : undefined,
              }}
            >
              <div className="flex items-center gap-2.5">
                <span
                  className="text-[13px] font-medium"
                  style={{
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--text-primary)',
                  }}
                >
                  {file.name}
                </span>
                <span
                  className="text-[12px] font-medium"
                  style={{ color: file.present ? 'var(--success)' : 'var(--error)' }}
                >
                  {file.present ? '\u2705 Present' : '\u274C Missing'}
                </span>
              </div>
              <div className="flex items-center gap-2.5">
                <span
                  className="text-[12px]"
                  style={{
                    color: isLlms ? 'var(--error)' : 'var(--text-secondary)',
                    fontFamily: 'var(--font-display)',
                  }}
                >
                  {file.description}
                </span>
                {isLlms && (
                  <button
                    className="h-[28px] px-2.5 text-[11px] font-medium rounded-[var(--radius-sm)] border border-[var(--error)] hover:bg-[var(--error-subtle)] transition-colors"
                    style={{ color: 'var(--error)', fontFamily: 'var(--font-display)' }}
                    title="Coming soon — auto-generate llms.txt based on your content"
                  >
                    Generate llms.txt
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
