'use client';

import { BOT_ACCESS, SITE_FILES } from './tech-readiness-data';

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

export function BotAccessCard() {
  return (
    <div style={{ border: '1px solid var(--border)', background: 'var(--surface)', borderRadius: '6px', padding: '12px' }}>
      <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
        AI Bot Access
      </h3>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {BOT_ACCESS.map((bot) => (
          <div key={bot.name} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            height: '32px', padding: '0 4px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <BrandLogo domain={bot.domain} size={16} />
              <span style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)' }}>{bot.name}</span>
              <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>({bot.company})</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{
                width: 6, height: 6, borderRadius: '50%',
                background: bot.status === 'allowed' ? 'var(--success)' : 'var(--error)',
              }} />
              <span style={{
                fontSize: '11px', textTransform: 'uppercase', fontWeight: 600,
                color: bot.status === 'allowed' ? 'var(--success)' : 'var(--error)',
              }}>
                {bot.status === 'allowed' ? 'ALLOWED' : 'BLOCKED'}
              </span>
              <span style={{ fontSize: '10px', color: bot.robotsTxt ? 'var(--success)' : 'var(--error)' }}>
                robots.txt {bot.robotsTxt ? '\u2713' : '\u2717'}
              </span>
            </div>
          </div>
        ))}
      </div>

      <div style={{ borderTop: '1px solid var(--border)', marginTop: '8px', paddingTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0 4px' }}>
          <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>robots.txt</span>
          <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--success)' }}>
            {SITE_FILES.robotsTxt ? '\u2705 Present' : '\u274C Missing'}
          </span>
        </div>
        <div style={{
          display: 'flex', justifyContent: 'space-between', padding: '4px',
          background: 'rgba(229, 72, 77, 0.06)', borderRadius: '4px',
        }}>
          <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>llms.txt</span>
          <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--error)' }}>
            {SITE_FILES.llmsTxt ? '\u2705 Present' : '\u274C Missing'}
          </span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0 4px' }}>
          <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Sitemap</span>
          <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--success)' }}>
            {SITE_FILES.sitemap.found ? `\u2705 Found (${SITE_FILES.sitemap.urls} URLs)` : '\u274C Missing'}
          </span>
        </div>
      </div>
    </div>
  );
}
