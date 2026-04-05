'use client';

import { useState } from 'react';
import { FileText, AlertTriangle, TrendingUp, Trophy, ShieldAlert, Zap, ArrowRight, ChevronDown } from 'lucide-react';
import { BrandLogo } from './brand-logo';

interface FeedEvent {
  id: string;
  time: string;
  icon: React.ReactNode;
  iconColor: string;
  domain?: string;
  title: string;
  detail: string;
  impact?: string;
  action?: { label: string; href?: string };
}

const FEED_EVENTS: FeedEvent[] = [
  {
    id: '1', time: '3h ago', icon: <FileText size={12} />, iconColor: 'var(--error)', domain: 'cursor.com',
    title: 'cursor.com published "AI Coding Guide 2026"',
    detail: '2,800 words with FAQ section, comparison tables, and updated benchmarks',
    impact: 'This threatens your "vibe coding meaning" citation on ChatGPT',
    action: { label: 'View in Content Planner' },
  },
  {
    id: '2', time: '1d ago', icon: <ShieldAlert size={12} />, iconColor: 'var(--error)', domain: 'cursor.com',
    title: 'Lost "vibe coding meaning" to cursor.com',
    detail: 'ChatGPT now cites cursor.com instead of you — they published newer, more comprehensive content',
    action: { label: 'Recapture' },
  },
  {
    id: '3', time: '2d ago', icon: <TrendingUp size={12} />, iconColor: 'var(--warning)', domain: 'emergent.sh',
    title: 'emergent.sh SOV grew +3.1 points this month',
    detail: 'Now the fastest-growing competitor in your space — gaining in the Mechanism cluster',
    action: { label: 'View Competitor' },
  },
  {
    id: '4', time: '3d ago', icon: <Trophy size={12} />, iconColor: 'var(--success)',
    title: 'You overtook Replit — now ranked #2 overall',
    detail: 'Gap to #1 (bolt.new) narrowing: 5.8 points. At current pace, you\'ll close it in ~6 weeks',
  },
  {
    id: '5', time: '4d ago', icon: <AlertTriangle size={12} />, iconColor: 'var(--warning)',
    title: '"no-code AI app security audit" dropped from #1 to #3',
    detail: 'Your position on Perplexity is weakening — 2 new competitor pages published this week',
    action: { label: 'Defend' },
  },
  {
    id: '6', time: '5d ago', icon: <ShieldAlert size={12} />, iconColor: 'var(--error)', domain: 'snyk.io',
    title: 'Lost "AI code generation security risks" to snyk.io',
    detail: 'Claude now cites snyk.io — their content has stronger structural signals (FAQ, headers, schema)',
    action: { label: 'Recapture' },
  },
  {
    id: '7', time: '6d ago', icon: <Zap size={12} />, iconColor: 'var(--success)', domain: 'perplexity.ai',
    title: 'Perplexity started citing your Enterprise guide',
    detail: 'New citation on "AI app builder for startups" — your SOV on Perplexity now 18.6% (#1)',
  },
  {
    id: '8', time: '1w ago', icon: <FileText size={12} />, iconColor: 'var(--warning)', domain: 'retool.com',
    title: 'retool.com expanded their comparison page',
    detail: 'Grew from 1,800 to 3,200 words — now outranks you on Gemini for "enterprise AI app builder features"',
    action: { label: 'View in Content Planner' },
  },
];

export function ActivityFeed() {
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? FEED_EVENTS : FEED_EVENTS.slice(0, 5);

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
      <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
        <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>Competitive Activity</p>
        <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Recent competitor moves and citation changes — newest first</p>
      </div>

      <div>
        {visible.map((event, i) => (
          <div key={event.id} style={{ display: 'flex', gap: 10, padding: '10px 14px', borderBottom: i < visible.length - 1 ? '1px solid var(--border-subtle)' : 'none', animation: `fadeUp 200ms ease ${i * 30}ms both` }}>
            {/* Timeline dot + line */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 20, flexShrink: 0 }}>
              <div style={{ width: 20, height: 20, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', color: event.iconColor, background: `color-mix(in srgb, ${event.iconColor} 12%, transparent)` }}>
                {event.icon}
              </div>
              {i < visible.length - 1 && <div style={{ width: 1, flex: 1, background: 'var(--border-subtle)', marginTop: 4 }} />}
            </div>

            {/* Content */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                <span style={{ fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', fontWeight: 500, flexShrink: 0 }}>{event.time}</span>
                {event.domain && <BrandLogo domain={event.domain} size={12} />}
                <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>{event.title}</span>
              </div>
              <p style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.4, marginBottom: event.impact || event.action ? 4 : 0 }}>{event.detail}</p>
              {event.impact && (
                <p style={{ fontSize: 11, color: event.iconColor, fontWeight: 500, marginBottom: event.action ? 4 : 0 }}>→ {event.impact}</p>
              )}
              {event.action && (
                <button style={{ display: 'inline-flex', alignItems: 'center', gap: 3, height: 22, padding: '0 8px', borderRadius: 4, border: '1px solid var(--accent)', background: 'transparent', color: 'var(--accent)', fontSize: 10, fontWeight: 500, cursor: 'pointer', fontFamily: 'var(--font-display)' }}>
                  {event.action.label} <ArrowRight size={9} strokeWidth={1.5} />
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {!showAll && FEED_EVENTS.length > 5 && (
        <button
          onClick={() => setShowAll(true)}
          style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4, padding: '8px 0', border: 'none', borderTop: '1px solid var(--border)', background: 'var(--bg)', cursor: 'pointer', color: 'var(--text-secondary)', fontSize: 11, fontWeight: 500, transition: 'background 0.15s' }}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--bg)')}
        >
          Show {FEED_EVENTS.length - 5} more <ChevronDown size={12} />
        </button>
      )}
    </div>
  );
}
