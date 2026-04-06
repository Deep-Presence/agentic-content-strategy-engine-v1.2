'use client';

import { Check, X, ArrowRight } from 'lucide-react';
import { COMPETITORS, COMPETITOR_DETAILS, CLUSTER_DETAILS, CLUSTER_RANKINGS, ENGINE_DOMAINS } from './data';
import { BrandLogo } from './brand-logo';
import { SlideDrawer } from './slide-drawer';

function barColor(r: number) { return r > 50 ? 'var(--success)' : r >= 30 ? 'var(--warning)' : 'var(--error)'; }
function Section({ label, color, children }: { label: string; color: string; children: React.ReactNode }) {
  return <div style={{ marginBottom: 14 }}><p style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color, marginBottom: 6 }}>{label}</p>{children}</div>;
}

// ─── Competitor Drawer ──────────────────────────────────────────────────────

export function CompetitorDrawer({ domain, onClose }: { domain: string | null; onClose: () => void }) {
  const detail = domain ? COMPETITOR_DETAILS[domain] : null;
  const comp = domain ? COMPETITORS.find((c) => c.domain === domain) : null;

  return (
    <SlideDrawer isOpen={!!domain} onClose={onClose} title={comp ? `${comp.name} — Head to Head` : ''} subtitle={detail ? `Your win rate against ${comp?.domain}` : undefined}>
      {detail && comp && (
        <div style={{ paddingTop: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <BrandLogo domain={comp.domain} size={28} />
            <div>
              <p style={{ fontSize: 24, fontWeight: 600, fontFamily: 'var(--font-mono)', color: barColor(detail.winRate) }}>{detail.winRate}%</p>
              <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{comp.domain} wins {100 - detail.winRate}% of {detail.totalShared} shared queries</p>
            </div>
          </div>
          <Section label={`Queries You Win (${detail.queriesYouWin.length})`} color="var(--success)">
            {detail.queriesYouWin.map((q) => (
              <div key={q.query} style={{ display: 'flex', gap: 6, padding: '5px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                <Check size={12} strokeWidth={2.5} style={{ color: 'var(--success)', marginTop: 2 }} />
                <div>
                  <p style={{ fontSize: 12, color: 'var(--text-primary)' }}>&ldquo;{q.query}&rdquo;</p>
                  <div style={{ display: 'flex', gap: 4, marginTop: 2 }}>{q.platforms.map((p) => <span key={p} style={{ fontSize: 10, color: 'var(--text-tertiary)', display: 'inline-flex', alignItems: 'center', gap: 2 }}><BrandLogo domain={ENGINE_DOMAINS[p] || ''} size={9} />{p}</span>)}</div>
                </div>
              </div>
            ))}
          </Section>
          <Section label={`Queries You Lose (${detail.queriesYouLose.length})`} color="var(--error)">
            {detail.queriesYouLose.map((q) => (
              <div key={q.query} style={{ display: 'flex', gap: 6, padding: '5px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                <X size={12} strokeWidth={2.5} style={{ color: 'var(--error)', marginTop: 2 }} />
                <div>
                  <p style={{ fontSize: 12, color: 'var(--text-primary)' }}>&ldquo;{q.query}&rdquo;</p>
                  <p style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 1 }}>cited on {q.count} engines</p>
                </div>
              </div>
            ))}
          </Section>
          <Section label={`Why ${comp.name} Wins`} color="var(--text-secondary)">
            <ul style={{ margin: 0, paddingLeft: 14 }}>{detail.whyTheyWin.map((r, i) => <li key={i} style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{r}</li>)}</ul>
          </Section>
          <Section label="How to Close the Gap" color="var(--accent)">
            <ol style={{ margin: 0, paddingLeft: 14 }}>{detail.howToClose.map((s, i) => <li key={i} style={{ fontSize: 11, color: 'var(--text-primary)', lineHeight: 1.6 }}>{s.action} <span style={{ color: 'var(--success)', fontSize: 10 }}>({s.impact})</span></li>)}</ol>
          </Section>
          <button style={{ display: 'inline-flex', alignItems: 'center', gap: 4, height: 28, padding: '0 10px', borderRadius: 4, border: 'none', background: 'var(--accent)', color: 'var(--text-on-accent)', fontSize: 11, fontWeight: 500, cursor: 'pointer', marginTop: 4 }}>
            Create tasks in Content Planner <ArrowRight size={11} />
          </button>
        </div>
      )}
    </SlideDrawer>
  );
}

// ─── Cluster Drawer ─────────────────────────────────────────────────────────

export function ClusterDrawer({ cluster, onClose }: { cluster: string | null; onClose: () => void }) {
  const detail = cluster ? CLUSTER_DETAILS[cluster] : null;
  const ranking = cluster ? CLUSTER_RANKINGS.find((c) => c.cluster === cluster) : null;

  return (
    <SlideDrawer isOpen={!!cluster} onClose={onClose} title={ranking?.cluster || ''} subtitle={detail ? `${detail.totalCitations} citations · ${detail.totalDomains} domains` : ranking ? `Coverage: ${ranking.coverage}` : undefined}>
      {detail ? (
        <div style={{ paddingTop: 14 }}>
          {detail.queries.map((q) => (
            <div key={q.query} style={{ padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <p style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)' }}>&ldquo;{q.query}&rdquo;</p>
              {q.topCited.map((tc, j) => <span key={j} style={{ fontSize: 10, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 3, marginTop: 2 }}>#{j + 1} <BrandLogo domain={tc.domain} size={9} /> {tc.domain} ({tc.platforms.join(', ')})</span>)}
              {!q.yourContent && <button style={{ fontSize: 10, color: 'var(--accent)', background: 'none', border: 'none', cursor: 'pointer', marginTop: 4, display: 'flex', alignItems: 'center', gap: 2 }}>Create content <ArrowRight size={9} /></button>}
            </div>
          ))}
          <div style={{ padding: '10px 12px', background: 'var(--accent-subtle)', borderRadius: 6, marginTop: 12 }}>
            <p style={{ fontSize: 10, fontWeight: 600, color: 'var(--accent)', marginBottom: 4 }}>Strategy</p>
            <p style={{ fontSize: 11, color: 'var(--text-primary)', lineHeight: 1.6 }}>{detail.strategy}</p>
          </div>
        </div>
      ) : ranking ? (
        <div style={{ paddingTop: 14 }}>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>Coverage: {ranking.coverage}. {ranking.yourRank ? `Ranked #${ranking.yourRank} with ${ranking.yourShare}% share.` : 'No presence yet. Enter this territory with focused content.'}</p>
        </div>
      ) : null}
    </SlideDrawer>
  );
}

