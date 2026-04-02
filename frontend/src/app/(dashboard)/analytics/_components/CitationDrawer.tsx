'use client';

import { useEffect, useMemo } from 'react';
import { X, ExternalLink } from 'lucide-react';
import { AreaChart, Area, ResponsiveContainer } from 'recharts';
import { type CitationURL, QUERIES_SERVED, CITATION_EXAMPLES, COMPETING_URLS, PLATFORM_DOMAINS } from './data';
import { BrandLogo } from './BrandLogo';

const PLATFORM_NAMES = ['ChatGPT', 'Claude', 'Perplexity', 'Google AI', 'Gemini'] as const;
const PLATFORM_KEY_MAP: Record<string, keyof CitationURL['platforms']> = {
  ChatGPT: 'chatgpt',
  Claude: 'claude',
  Perplexity: 'perplexity',
  'Google AI': 'google_ai',
  Gemini: 'gemini',
};

function generateDrawerTimeline() {
  return Array.from({ length: 28 }, (_, i) => ({
    day: i + 1,
    citations: Math.floor(1 + Math.random() * 4 + i * 0.1),
  }));
}

export function CitationDrawer({
  url,
  onClose,
}: {
  url: CitationURL | null;
  onClose: () => void;
}) {
  const timelineData = useMemo(() => generateDrawerTimeline(), []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (url) window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [url, onClose]);

  if (!url) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40"
        style={{ background: 'rgba(0,0,0,0.15)' }}
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        className="fixed right-0 top-0 bottom-0 z-50 w-[50vw] overflow-y-auto"
        style={{
          background: 'var(--surface)',
          borderLeft: '1px solid var(--border)',
          boxShadow: 'var(--shadow-float)',
        }}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 w-[30px] h-[30px] flex items-center justify-center rounded-md transition-colors"
          style={{ color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--border-strong)'; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--border)'; }}
        >
          <X size={14} />
        </button>

        {/* Header */}
        <div className="px-6 pt-5 pb-4">
          <h2 className="text-[16px] font-semibold pr-10" style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}>
            {url.title}
          </h2>
          <a
            className="flex items-center gap-1 text-[12px] mt-1"
            style={{ color: 'var(--text-secondary)' }}
            href={`https://${url.url}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            {url.url} <ExternalLink size={10} />
          </a>
          <div className="flex items-center gap-3 mt-2 text-[11px]" style={{ color: 'var(--text-secondary)' }}>
            <span>First cited: {new Date(url.firstCited).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
            <span>|</span>
            <span>Total citations: {url.citations}</span>
          </div>
        </div>

        {/* A. Citation Timeline */}
        <DrawerSection title="Citation Timeline">
          <div style={{ height: 120 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={timelineData} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
                <Area
                  type="monotone"
                  dataKey="citations"
                  stroke="var(--accent)"
                  strokeWidth={1.5}
                  fill="var(--accent)"
                  fillOpacity={0.1}
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </DrawerSection>

        {/* B. Platform Breakdown */}
        <DrawerSection title="Platform Breakdown">
          <div className="grid grid-cols-5 gap-2">
            {PLATFORM_NAMES.map((p) => {
              const key = PLATFORM_KEY_MAP[p];
              const cited = url.platforms[key];
              const domain = PLATFORM_DOMAINS[p];
              // Approximate per-platform citations
              const count = cited ? Math.floor(url.citations / Object.values(url.platforms).filter(Boolean).length + Math.random() * 5) : 0;

              return (
                <div
                  key={p}
                  className="p-2 flex flex-col items-center gap-1"
                  style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}
                >
                  <BrandLogo domain={domain} size={16} />
                  <span className="text-[11px]" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
                    {p}
                  </span>
                  <span
                    className="text-[16px] font-semibold"
                    style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}
                  >
                    {count}
                  </span>
                  <span
                    className="text-[10px]"
                    style={{ color: cited ? 'var(--success)' : 'var(--error)' }}
                  >
                    {cited ? 'Cited \u2713' : 'Not cited \u2717'}
                  </span>
                </div>
              );
            })}
          </div>
        </DrawerSection>

        {/* C. Queries Served */}
        <DrawerSection title="Queries Served">
          <div className="flex flex-col gap-1">
            {QUERIES_SERVED.map((q, i) => (
              <div
                key={i}
                className="flex items-center gap-2 px-2 py-1.5"
                style={{ borderBottom: '1px solid var(--border)' }}
              >
                <span className="text-[12px] flex-1" style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
                  {q.query}
                </span>
                <BrandLogo domain={PLATFORM_DOMAINS[q.platform] || 'openai.com'} size={12} />
                <span
                  className="text-[11px] w-[24px] text-right"
                  style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}
                >
                  #{q.position}
                </span>
              </div>
            ))}
          </div>
        </DrawerSection>

        {/* D. Citation Context */}
        <DrawerSection title="Citation Context">
          <div className="flex flex-col gap-3">
            {CITATION_EXAMPLES.map((ex, i) => (
              <div key={i} className="flex gap-2">
                <BrandLogo domain={PLATFORM_DOMAINS[ex.platform] || 'openai.com'} size={14} className="mt-0.5 flex-shrink-0" />
                <div>
                  <span className="text-[11px] font-medium block mb-1" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
                    {ex.platform}
                  </span>
                  <p
                    className="text-[12px] leading-relaxed"
                    style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
                    dangerouslySetInnerHTML={{
                      __html: ex.text.replace(
                        /\*\*(.*?)\*\*/g,
                        '<span style="background:rgba(108,184,210,0.15);padding:1px 3px;border-radius:2px;font-weight:500">$1</span>'
                      ),
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </DrawerSection>

        {/* E. Competing URLs */}
        <DrawerSection title="Competing URLs">
          <div className="flex flex-col gap-1">
            {COMPETING_URLS.map((cu, i) => (
              <div
                key={i}
                className="flex items-center gap-2 px-2 py-1.5"
                style={{
                  borderBottom: '1px solid var(--border)',
                  background: cu.isOwn ? 'var(--accent-subtle)' : 'transparent',
                  borderRadius: cu.isOwn ? 'var(--radius-sm)' : 0,
                }}
              >
                <BrandLogo domain={cu.domain} size={14} />
                <span className="text-[12px] flex-1 truncate" style={{ color: 'var(--accent)', fontFamily: 'var(--font-display)' }}>
                  {cu.url}
                </span>
                {cu.isOwn && (
                  <span
                    className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full flex-shrink-0"
                    style={{ background: 'var(--accent)', color: 'var(--text-on-accent)' }}
                  >
                    YOUR PAGE
                  </span>
                )}
                <span className="text-[11px] flex-shrink-0" style={{ color: 'var(--text-secondary)' }}>
                  {cu.sharedQueries} shared
                </span>
                <span
                  className="text-[12px] flex-shrink-0 w-[36px] text-right"
                  style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}
                >
                  {cu.citations}
                </span>
              </div>
            ))}
          </div>
        </DrawerSection>

        <div className="h-6" />
      </div>
    </>
  );
}

function DrawerSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="px-6 pb-4">
      <div className="pt-3 mb-2" style={{ borderTop: '1px solid var(--border)' }}>
        <h4
          className="text-[14px] uppercase font-semibold"
          style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)', letterSpacing: '0.03em' }}
        >
          {title}
        </h4>
      </div>
      {children}
    </div>
  );
}
