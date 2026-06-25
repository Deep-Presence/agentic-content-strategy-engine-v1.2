'use client';

import { useState } from 'react';
import type { DayData, ViewType } from './mock-data';
import { PLATFORMS, CITATION_URLS } from './mock-data';
import { SlideDrawer } from './SlideDrawer';

interface InsightCardsProps {
  data: DayData[];
  activeView: ViewType;
  onViewChange: (view: ViewType) => void;
}

function BrandLogo({ domain, size = 14 }: { domain: string; size?: number }) {
  return (
    <img
      src={`https://www.google.com/s2/favicons?domain=${domain}&sz=${size * 2}`}
      alt={domain}
      width={size}
      height={size}
      style={{ borderRadius: 3, flexShrink: 0 }}
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

function CardShell({
  children,
  active,
  accentColor,
  onClick,
}: {
  children: React.ReactNode;
  active?: boolean;
  accentColor?: string;
  onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      style={{
        padding: 14,
        background: active ? 'var(--accent-subtle)' : 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
        borderTopWidth: active ? 2 : 1,
        borderTopColor: active ? (accentColor || 'var(--accent)') : 'var(--border)',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all 150ms',
      }}
      onMouseEnter={(e) => {
        if (!active) e.currentTarget.style.borderColor = 'var(--border-strong)';
      }}
      onMouseLeave={(e) => {
        if (!active) e.currentTarget.style.borderColor = 'var(--border)';
      }}
    >
      {children}
    </div>
  );
}

function OverlineLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: 10,
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
        color: 'var(--text-secondary)',
        fontFamily: 'var(--font-display)',
        marginBottom: 8,
      }}
    >
      {children}
    </div>
  );
}

function StatBlock({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--bg)' }}>
      <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)', marginBottom: 2 }}>
        {label}
      </div>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 18, fontWeight: 600, color: color || 'var(--text-primary)' }}>
        {value}
      </div>
    </div>
  );
}

// ─── Card 1: Content Velocity ─────────────────────────────────────────
function ContentVelocity({ onDrillDown }: { onDrillDown: () => void }) {
  return (
    <CardShell onClick={onDrillDown}>
      <OverlineLabel>Content Velocity</OverlineLabel>
      <div style={{ marginBottom: 8 }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 28, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1 }}>
          3.2/week
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'var(--font-display)', marginTop: 6 }}>
          2 published, 1 in review
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
          <path d="M5 2L8 6H2L5 2Z" fill="var(--success)" />
        </svg>
        <span style={{ fontSize: 11, color: 'var(--success)', fontFamily: 'var(--font-display)' }}>
          +0.4/week vs last month
        </span>
      </div>
    </CardShell>
  );
}

// ─── Card 2: Platform Breakdown ─────────────────────────────────────────
function PlatformBreakdown({ data, onDrillDown }: { data: DayData[]; onDrillDown: () => void }) {
  const totals = PLATFORMS.map(p => ({
    ...p,
    total: data.reduce((sum, d) => sum + (d[p.key] as number), 0),
  }));
  const grandTotal = totals.reduce((sum, p) => sum + p.total, 0);
  const maxTotal = Math.max(...totals.map(p => p.total));

  return (
    <CardShell onClick={onDrillDown}>
      <OverlineLabel>Platform Breakdown</OverlineLabel>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {totals.map(p => {
          const pct = ((p.total / grandTotal) * 100).toFixed(1);
          const barWidth = (p.total / maxTotal) * 100;
          return (
            <div key={p.key} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <BrandLogo domain={p.domain} size={14} />
              <span className="truncate" style={{ fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'var(--font-display)', maxWidth: 70, width: 70, flexShrink: 0 }}>
                {p.name}
              </span>
              <div style={{ flex: 1, height: 6, borderRadius: 9999, background: 'var(--border)', minWidth: 0 }}>
                <div style={{ height: '100%', borderRadius: 9999, width: `${barWidth}%`, background: p.color, transition: 'width 300ms' }} />
              </div>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-primary)', fontWeight: 500, flexShrink: 0, width: 50, textAlign: 'right' }}>
                {pct}%
              </span>
            </div>
          );
        })}
      </div>
    </CardShell>
  );
}

// ─── Card 3: Top Cited Content ──────────────────────────────────────────
function TopCitedContent({ onDrillDown }: { onDrillDown: () => void }) {
  const top3 = CITATION_URLS.slice(0, 3);
  return (
    <CardShell onClick={onDrillDown}>
      <OverlineLabel>Top Cited Content</OverlineLabel>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {top3.map((url, idx) => (
          <div key={url.url} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-tertiary)', width: 16, flexShrink: 0 }}>
              #{idx + 1}
            </span>
            <span className="truncate" style={{ flex: 1, fontSize: 12, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
              {url.title}
            </span>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 600, color: 'var(--success)', flexShrink: 0 }}>
              {url.citations}
            </span>
          </div>
        ))}
      </div>
    </CardShell>
  );
}

// ─── Card 4: Citation Sentiment ─────────────────────────────────────────
function CitationSentiment({ data, onDrillDown }: { data: DayData[]; onDrillDown: () => void }) {
  const latest = data[data.length - 1];
  const segments = [
    { label: 'Positive', pct: latest.positive, color: 'var(--success)' },
    { label: 'Neutral', pct: latest.neutral, color: 'var(--text-tertiary)' },
    { label: 'Negative', pct: latest.negative, color: 'var(--error)' },
  ];

  return (
    <CardShell onClick={onDrillDown}>
      <OverlineLabel>Citation Sentiment</OverlineLabel>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 8 }}>
        {segments.map(s => (
          <div key={s.label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'var(--font-display)', width: 52, flexShrink: 0 }}>
              {s.label}
            </span>
            <div style={{ flex: 1, height: 5, borderRadius: 9999, background: 'var(--border)' }}>
              <div style={{ height: '100%', borderRadius: 9999, width: `${s.pct}%`, minWidth: 20, background: s.color }} />
            </div>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-primary)', fontWeight: 500, flexShrink: 0, width: 32, textAlign: 'right' }}>
              {s.pct}%
            </span>
          </div>
        ))}
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}>
        Overwhelmingly positive. Negative around pricing.
      </div>
    </CardShell>
  );
}

// ─── Drill-down drawer content ──────────────────────────────────────────
function ContentVelocityDetail() {
  const recentContent = [
    { title: 'AI App Builder Comparison Guide', status: 'Published', date: 'Mar 25', citations: 12 },
    { title: 'Lovable vs Cursor: Honest Review', status: 'Published', date: 'Mar 21', citations: 8 },
    { title: 'Enterprise Deployment Best Practices', status: 'In Review', date: 'Mar 27', citations: 0 },
    { title: 'Security in AI-Generated Apps', status: 'Published', date: 'Mar 18', citations: 6 },
    { title: 'Non-Technical Founder\'s Guide', status: 'Draft', date: 'Mar 28', citations: 0 },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, paddingTop: 16 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
        <StatBlock label="Weekly Rate" value="3.2" color="var(--accent)" />
        <StatBlock label="Published" value="2" color="var(--success)" />
        <StatBlock label="In Review" value="1" />
      </div>
      <div>
        <OverlineLabel>Recent Content</OverlineLabel>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {recentContent.map(item => (
            <div key={item.title} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span style={{ fontSize: 12, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>{item.title}</span>
                <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}>{item.date}</span>
              </div>
              <span
                style={{
                  fontSize: 10, fontWeight: 600, fontFamily: 'var(--font-display)',
                  padding: '2px 6px', borderRadius: 9999,
                  background: item.status === 'Published' ? 'var(--success-subtle)' : item.status === 'In Review' ? 'var(--warning-subtle)' : 'var(--accent-subtle)',
                  color: item.status === 'Published' ? 'var(--success)' : item.status === 'In Review' ? 'var(--warning)' : 'var(--accent)',
                }}
              >
                {item.status}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function PlatformDetail({ data }: { data: DayData[] }) {
  const totals = PLATFORMS.map(p => ({
    ...p,
    total: data.reduce((sum, d) => sum + (d[p.key] as number), 0),
  }));
  const grandTotal = totals.reduce((sum, p) => sum + p.total, 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingTop: 16 }}>
      {totals.map(p => (
        <div key={p.key} style={{ padding: '10px 12px', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--bg)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <BrandLogo domain={p.domain} size={16} />
            <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>{p.name}</span>
            <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 600, color: p.color }}>
              {((p.total / grandTotal) * 100).toFixed(1)}%
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
              {p.total} citations total
            </span>
            <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}>
              avg {Math.round(p.total / data.length)}/day
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

function TopContentDetail() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingTop: 16 }}>
      {CITATION_URLS.map((url, idx) => (
        <div key={url.url} style={{ padding: '10px 12px', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--bg)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-tertiary)' }}>#{idx + 1}</span>
            <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>{url.title}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600, color: 'var(--success)' }}>{url.citations} citations</span>
            <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}>CPS {url.cps.toFixed(3)}</span>
            <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}>v{url.velocity.toFixed(1)}</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 2, marginLeft: 'auto' }}>
              {url.platforms.map(pk => (
                <BrandLogo key={pk} domain={PLATFORMS.find(p => p.key === pk)?.domain || ''} size={12} />
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function SentimentDetail({ data }: { data: DayData[] }) {
  const latest = data[data.length - 1];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, paddingTop: 16 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
        <StatBlock label="Positive" value={`${latest.positive}%`} color="var(--success)" />
        <StatBlock label="Neutral" value={`${latest.neutral}%`} />
        <StatBlock label="Negative" value={`${latest.negative}%`} color="var(--error)" />
      </div>
      <div>
        <OverlineLabel>Sentiment Trend (last 7 days)</OverlineLabel>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {data.slice(-7).map(d => (
            <div key={d.dateShort} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>{d.dateShort}</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--success)' }}>{d.positive}%</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-tertiary)' }}>{d.neutral}%</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--error)' }}>{d.negative}%</span>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div style={{ padding: '10px 12px', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--bg)' }}>
        <OverlineLabel>Key Insights</OverlineLabel>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div style={{ fontSize: 12, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
            <span style={{ color: 'var(--success)' }}>&#10003;</span> Strong positive sentiment driven by product quality and ease of use
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
            <span style={{ color: 'var(--warning)' }}>&#10007;</span> Negative sentiment concentrated around pricing and enterprise features
          </div>
        </div>
      </div>
    </div>
  );
}

type DrawerType = 'velocity' | 'platforms' | 'content' | 'sentiment' | null;

export function InsightCards({ data, activeView, onViewChange }: InsightCardsProps) {
  const [openDrawer, setOpenDrawer] = useState<DrawerType>(null);

  const drawerConfig: Record<Exclude<DrawerType, null>, { title: string; subtitle: string }> = {
    velocity: { title: 'Content Velocity', subtitle: 'Content production rate and publishing cadence' },
    platforms: { title: 'Platform Breakdown', subtitle: 'Citation distribution across AI platforms' },
    content: { title: 'Top Cited Content', subtitle: 'All URLs ranked by citation count' },
    sentiment: { title: 'Citation Sentiment', subtitle: 'Sentiment analysis of AI-generated responses' },
  };

  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <ContentVelocity onDrillDown={() => setOpenDrawer('velocity')} />
        <PlatformBreakdown data={data} onDrillDown={() => setOpenDrawer('platforms')} />
        <TopCitedContent onDrillDown={() => setOpenDrawer('content')} />
        <CitationSentiment data={data} onDrillDown={() => setOpenDrawer('sentiment')} />
      </div>

      <SlideDrawer
        open={openDrawer !== null}
        onClose={() => setOpenDrawer(null)}
        title={openDrawer ? drawerConfig[openDrawer].title : ''}
        subtitle={openDrawer ? drawerConfig[openDrawer].subtitle : ''}
      >
        {openDrawer === 'velocity' && <ContentVelocityDetail />}
        {openDrawer === 'platforms' && <PlatformDetail data={data} />}
        {openDrawer === 'content' && <TopContentDetail />}
        {openDrawer === 'sentiment' && <SentimentDetail data={data} />}
      </SlideDrawer>
    </>
  );
}
