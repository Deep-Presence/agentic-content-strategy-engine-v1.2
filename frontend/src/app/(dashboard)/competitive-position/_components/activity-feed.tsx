'use client';

import { useState } from 'react';
import { FileText, AlertTriangle, TrendingUp, Trophy, ShieldAlert, Zap, ArrowRight, ChevronDown, List, Clock } from 'lucide-react';
import { BrandLogo } from './brand-logo';

type Priority = 'P1' | 'P2' | 'P3';

interface FeedEvent {
  id: string;
  time: string;
  timeSort: number;
  priority: Priority;
  type: string;
  icon: React.ReactNode;
  iconColor: string;
  domain?: string;
  title: string;
  detail: string;
  impact?: string;
  action?: { label: string };
}

const PRIORITY_STYLES: Record<Priority, { bg: string; color: string }> = {
  P1: { bg: 'rgba(229,72,77,0.1)', color: '#E5484D' },
  P2: { bg: 'rgba(217,119,6,0.1)', color: '#D97706' },
  P3: { bg: 'rgba(136,144,150,0.1)', color: '#889096' },
};

const EVENTS: FeedEvent[] = [
  { id: '1', time: '3h ago', timeSort: 1, priority: 'P1', type: 'Content', icon: <FileText size={11} />, iconColor: '#E5484D', domain: 'cursor.com', title: 'cursor.com published "AI Coding Guide 2026"', detail: '2,800 words with FAQ section, comparison tables, and updated benchmarks', impact: 'Threatens your "vibe coding meaning" citation on ChatGPT', action: { label: 'View in Content Planner' } },
  { id: '2', time: '1d ago', timeSort: 2, priority: 'P1', type: 'Citation Lost', icon: <ShieldAlert size={11} />, iconColor: '#E5484D', domain: 'cursor.com', title: 'Lost "vibe coding meaning" to cursor.com', detail: 'ChatGPT now cites cursor.com. They published newer, more comprehensive content.', action: { label: 'Recapture' } },
  { id: '3', time: '2d ago', timeSort: 3, priority: 'P2', type: 'SOV Change', icon: <TrendingUp size={11} />, iconColor: '#D97706', domain: 'emergent.sh', title: 'emergent.sh SOV grew +3.1 points this month', detail: 'Fastest-growing competitor. Gaining in the Mechanism cluster.', action: { label: 'View Competitor' } },
  { id: '4', time: '3d ago', timeSort: 4, priority: 'P3', type: 'Rank Change', icon: <Trophy size={11} />, iconColor: '#34B27B', title: 'You overtook Replit. Now ranked #2 overall.', detail: 'Gap to #1 (bolt.new) is 5.8 points and narrowing.' },
  { id: '5', time: '4d ago', timeSort: 5, priority: 'P2', type: 'Position Drop', icon: <AlertTriangle size={11} />, iconColor: '#D97706', title: '"no-code AI app security audit" dropped from #1 to #3', detail: 'Your position on Perplexity is weakening. 2 new competitor pages published.', action: { label: 'Defend' } },
  { id: '6', time: '5d ago', timeSort: 6, priority: 'P1', type: 'Citation Lost', icon: <ShieldAlert size={11} />, iconColor: '#E5484D', domain: 'snyk.io', title: 'Lost "AI code generation security risks" to snyk.io', detail: 'Claude now cites snyk.io. Their content has stronger structural signals.', action: { label: 'Recapture' } },
  { id: '7', time: '6d ago', timeSort: 7, priority: 'P3', type: 'Citation Gained', icon: <Zap size={11} />, iconColor: '#34B27B', title: 'Perplexity started citing your Enterprise guide', detail: 'New citation on "AI app builder for startups". Your SOV on Perplexity now 18.6% (#1).' },
  { id: '8', time: '1w ago', timeSort: 8, priority: 'P2', type: 'Content', icon: <FileText size={11} />, iconColor: '#D97706', domain: 'retool.com', title: 'retool.com expanded their comparison page', detail: 'Grew from 1,800 to 3,200 words. Now outranks you on Gemini for "enterprise AI app builder features".', action: { label: 'View in Content Planner' } },
];

export function ActivityFeed({ onEventClick }: { onEventClick: (event: FeedEvent) => void }) {
  const [viewMode, setViewMode] = useState<'timeline' | 'table'>('timeline');
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? EVENTS : EVENTS.slice(0, 5);

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>Competitive Activity</p>
          <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Recent competitor moves and citation changes</p>
        </div>
        <div style={{ display: 'flex', gap: 0, border: '1px solid var(--border)', borderRadius: 6, overflow: 'hidden' }}>
          <button onClick={() => setViewMode('timeline')} style={{ padding: '4px 10px', border: 'none', cursor: 'pointer', background: viewMode === 'timeline' ? 'var(--accent)' : 'transparent', color: viewMode === 'timeline' ? '#fff' : 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 3, fontSize: 10 }}>
            <Clock size={10} /> Timeline
          </button>
          <button onClick={() => setViewMode('table')} style={{ padding: '4px 10px', border: 'none', cursor: 'pointer', background: viewMode === 'table' ? 'var(--accent)' : 'transparent', color: viewMode === 'table' ? '#fff' : 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 3, fontSize: 10 }}>
            <List size={10} /> Table
          </button>
        </div>
      </div>

      {viewMode === 'timeline' ? (
        /* Timeline view */
        <div>
          {visible.map((event, i) => (
            <div key={event.id} onClick={() => onEventClick(event)} style={{ display: 'flex', gap: 10, padding: '10px 16px', borderBottom: i < visible.length - 1 ? '1px solid var(--border-subtle)' : 'none', cursor: 'pointer', transition: 'background 0.12s' }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')} onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 20 }}>
                <div style={{ width: 20, height: 20, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', color: event.iconColor, background: `color-mix(in srgb, ${event.iconColor} 12%, transparent)` }}>{event.icon}</div>
                {i < visible.length - 1 && <div style={{ width: 1, flex: 1, background: 'var(--border-subtle)', marginTop: 4 }} />}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                  <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>{event.time}</span>
                  <span style={{ fontSize: 8, fontWeight: 600, padding: '1px 4px', borderRadius: 3, background: PRIORITY_STYLES[event.priority].bg, color: PRIORITY_STYLES[event.priority].color }}>{event.priority}</span>
                  {event.domain && <BrandLogo domain={event.domain} size={12} />}
                </div>
                <p style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 2 }}>{event.title}</p>
                <p style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.4 }}>{event.detail}</p>
                {event.action && (
                  <button style={{ display: 'inline-flex', alignItems: 'center', gap: 3, height: 22, padding: '0 8px', borderRadius: 4, border: '1px solid var(--accent)', background: 'transparent', color: 'var(--accent)', fontSize: 10, fontWeight: 500, cursor: 'pointer', marginTop: 6 }}>
                    {event.action.label} <ArrowRight size={9} />
                  </button>
                )}
              </div>
            </div>
          ))}
          {!showAll && EVENTS.length > 5 && (
            <button onClick={() => setShowAll(true)} style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4, padding: '8px 0', border: 'none', borderTop: '1px solid var(--border)', background: 'var(--bg)', cursor: 'pointer', color: 'var(--text-secondary)', fontSize: 11 }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')} onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--bg)')}>
              Show {EVENTS.length - 5} more <ChevronDown size={12} />
            </button>
          )}
        </div>
      ) : (
        /* Table view */
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: '40px 56px 1fr 80px 56px 60px', padding: '0 16px', height: 28, alignItems: 'center', borderBottom: '1px solid var(--border)', background: 'var(--bg)' }}>
            <TH>Pri</TH><TH>Time</TH><TH>Event</TH><TH>Competitor</TH><TH>Type</TH><TH>{''}</TH>
          </div>
          {EVENTS.map((event, i) => (
            <div key={event.id} onClick={() => onEventClick(event)} style={{
              display: 'grid', gridTemplateColumns: '40px 56px 1fr 80px 56px 60px', padding: '0 16px', height: 38, alignItems: 'center',
              borderBottom: i < EVENTS.length - 1 ? '1px solid var(--border-subtle)' : 'none', cursor: 'pointer', transition: 'background 0.12s',
            }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')} onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}>
              <span style={{ fontSize: 8, fontWeight: 600, padding: '1px 4px', borderRadius: 3, background: PRIORITY_STYLES[event.priority].bg, color: PRIORITY_STYLES[event.priority].color, textAlign: 'center' }}>{event.priority}</span>
              <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>{event.time}</span>
              <span style={{ fontSize: 11, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{event.title}</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                {event.domain && <BrandLogo domain={event.domain} size={12} />}
                <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>{event.domain || 'You'}</span>
              </div>
              <span style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>{event.type}</span>
              {event.action ? (
                <span style={{ fontSize: 10, color: 'var(--accent)', fontWeight: 500, textAlign: 'right' }}>{event.action.label}</span>
              ) : <span />}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TH({ children }: { children: React.ReactNode }) {
  return <span style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)' }}>{children}</span>;
}
