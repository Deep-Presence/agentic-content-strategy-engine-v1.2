'use client';

import { useState } from 'react';
import { Check, Circle, X, ArrowRight } from 'lucide-react';
import { CLUSTER_RANKINGS, CLUSTER_DETAILS, type ClusterRanking } from './data';
import { BrandLogo } from './brand-logo';
import { SlideDrawer } from './slide-drawer';

function StatusDot({ status }: { status: string }) {
  const color = status === 'winning' ? 'var(--success)' : status === 'competitive' ? 'var(--warning)' : 'var(--error)';
  const Icon = status === 'winning' ? Check : status === 'competitive' ? Circle : X;
  return <Icon size={12} strokeWidth={2.5} style={{ color, flexShrink: 0 }} />;
}

function ClusterTableRow({ c, onClick, idx }: { c: ClusterRanking; onClick: () => void; idx: number }) {
  const isWhiteSpace = c.yourRank === null;
  const gapColor = c.status === 'winning' ? 'var(--success)' : c.status === 'competitive' ? 'var(--warning)' : 'var(--error)';

  return (
    <div
      onClick={onClick}
      style={{
        display: 'grid',
        gridTemplateColumns: '20px 1fr 100px 120px 80px 70px',
        alignItems: 'center',
        padding: '0 14px',
        height: 40,
        borderBottom: '1px solid var(--border-subtle)',
        cursor: 'pointer',
        transition: 'background 0.15s',
        animation: `fadeUp 250ms ease ${idx * 25}ms both`,
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
    >
      {/* Status dot */}
      <StatusDot status={c.status} />

      {/* Cluster name + white space badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, overflow: 'hidden' }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {c.cluster}
        </span>
        {isWhiteSpace && (
          <span style={{ fontSize: 9, fontWeight: 700, padding: '1px 5px', borderRadius: 9999, background: 'var(--error)', color: '#FFFFFF', textTransform: 'uppercase', letterSpacing: '0.05em', flexShrink: 0 }}>
            White Space
          </span>
        )}
      </div>

      {/* Your rank */}
      <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 500, color: isWhiteSpace ? 'var(--text-tertiary)' : 'var(--text-primary)' }}>
        {isWhiteSpace ? 'No presence' : `#${c.yourRank} · ${c.yourShare}%`}
      </span>

      {/* Leader */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, overflow: 'hidden' }}>
        <BrandLogo domain={c.leaderDomain} size={12} />
        <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'var(--font-body)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {c.leaderShare}%
        </span>
      </div>

      {/* Gap */}
      <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 600, color: gapColor, textAlign: 'right' }}>
        {c.gap !== null ? `${c.gap > 0 ? '+' : ''}${c.gap}` : '—'}
      </span>

      {/* Coverage */}
      <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)', textAlign: 'right' }}>
        {c.coverage}
      </span>
    </div>
  );
}

export function WinningLosing() {
  const [drawerCluster, setDrawerCluster] = useState<string | null>(null);

  const winning = CLUSTER_RANKINGS.filter((c) => c.status === 'winning');
  const competitive = CLUSTER_RANKINGS.filter((c) => c.status === 'competitive');
  const losing = CLUSTER_RANKINGS.filter((c) => c.status === 'losing');

  const clusterDetail = drawerCluster ? CLUSTER_DETAILS[drawerCluster] : null;
  const clusterRanking = drawerCluster ? CLUSTER_RANKINGS.find((c) => c.cluster === drawerCluster) : null;

  const groups = [
    { label: 'Winning', color: 'var(--success)', bg: 'var(--success-subtle)', items: winning },
    { label: 'Competitive', color: 'var(--warning)', bg: 'var(--warning-subtle)', items: competitive },
    { label: 'Losing', color: 'var(--error)', bg: 'var(--error-subtle)', items: losing },
  ];

  let rowIdx = 0;

  return (
    <>
      <div style={{ border: '1px solid var(--border)', borderRadius: 6, overflow: 'hidden' }}>
        {/* Header */}
        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
            Where You&apos;re Winning and Losing
          </h3>
        </div>

        {/* Table header */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '20px 1fr 100px 120px 80px 70px',
            alignItems: 'center',
            padding: '0 14px',
            height: 28,
            borderBottom: '1px solid var(--border)',
            background: 'var(--bg)',
          }}
        >
          <span />
          <span style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)' }}>
            Cluster
          </span>
          <span style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)' }}>
            Your Position
          </span>
          <span style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)' }}>
            Leader
          </span>
          <span style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)', textAlign: 'right' }}>
            Gap
          </span>
          <span style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)', textAlign: 'right' }}>
            Queries
          </span>
        </div>

        {/* Grouped rows */}
        {groups.map((group) => {
          if (group.items.length === 0) return null;
          return (
            <div key={group.label}>
              {/* Section label */}
              <div style={{ padding: '4px 14px', background: group.bg, borderBottom: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: group.color }}>
                  {group.label}
                </span>
              </div>
              {group.items.map((c) => {
                const currentIdx = rowIdx++;
                return (
                  <ClusterTableRow
                    key={c.cluster}
                    c={c}
                    onClick={() => setDrawerCluster(c.cluster)}
                    idx={currentIdx}
                  />
                );
              })}
            </div>
          );
        })}
      </div>

      {/* Cluster Detail Drawer */}
      <SlideDrawer
        isOpen={!!drawerCluster}
        onClose={() => setDrawerCluster(null)}
        title={clusterRanking ? `${clusterRanking.cluster} — Cluster Detail` : ''}
        subtitle={
          clusterDetail
            ? `${clusterDetail.totalCitations} citations · ${clusterDetail.totalDomains} domains · Your presence: ${clusterRanking?.yourRank ? `#${clusterRanking.yourRank}` : 'None'}`
            : clusterRanking
            ? `${clusterRanking.coverage} queries covered · Your presence: ${clusterRanking.yourRank ? `#${clusterRanking.yourRank}` : 'None'}`
            : undefined
        }
      >
        {clusterDetail ? (
          <div style={{ paddingTop: 16 }}>
            {/* Queries */}
            <p style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', marginBottom: 8 }}>
              Queries in this Cluster ({clusterDetail.queries.length})
            </p>
            {clusterDetail.queries.map((q) => (
              <div key={q.query} style={{ padding: '10px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                <p style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>&ldquo;{q.query}&rdquo;</p>
                <div style={{ marginTop: 4, display: 'flex', flexDirection: 'column', gap: 2 }}>
                  {q.topCited.map((tc, i) => (
                    <span key={i} style={{ fontSize: 11, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 4 }}>
                      #{i + 1} <BrandLogo domain={tc.domain} size={10} /> {tc.domain}
                      <span style={{ color: 'var(--text-tertiary)' }}>({tc.platforms.join(', ')})</span>
                    </span>
                  ))}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 4 }}>
                  <span style={{ fontSize: 11, color: q.yourContent ? 'var(--text-secondary)' : 'var(--error)' }}>
                    Your content: {q.yourContent || 'None'}
                  </span>
                  <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--error)' }}>
                    Gap: {q.gap}%
                  </span>
                </div>
                {!q.yourContent && (
                  <button
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 4,
                      height: 24,
                      padding: '0 8px',
                      borderRadius: 4,
                      border: '1px solid var(--accent)',
                      background: 'transparent',
                      color: 'var(--accent)',
                      fontSize: 11,
                      fontWeight: 500,
                      cursor: 'pointer',
                      marginTop: 6,
                      fontFamily: 'var(--font-display)',
                    }}
                  >
                    Create content <ArrowRight size={10} strokeWidth={1.5} />
                  </button>
                )}
              </div>
            ))}

            {/* Who Dominates */}
            <div style={{ marginTop: 20 }}>
              <p style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', marginBottom: 8 }}>
                Who Dominates This Cluster
              </p>
              {[
                { label: 'Direct competitors', items: clusterDetail.dominators.direct },
                { label: 'Mind share', items: clusterDetail.dominators.mindshare },
                { label: 'Authority sources', items: clusterDetail.dominators.authority },
              ].map((group) => (
                <div key={group.label} style={{ marginBottom: 6 }}>
                  <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-secondary)' }}>{group.label}: </span>
                  {group.items.map((item, i) => (
                    <span key={item.domain} style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                      {i > 0 && ', '}
                      <BrandLogo domain={item.domain} size={10} className="inline" /> {item.domain} ({item.citations} cit)
                    </span>
                  ))}
                </div>
              ))}
            </div>

            {/* Strategy */}
            <div
              style={{
                marginTop: 16,
                padding: 16,
                background: 'var(--accent-subtle)',
                border: '1px solid rgba(91,164,196,0.2)',
                borderRadius: 6,
              }}
            >
              <p style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--accent)', marginBottom: 6 }}>
                Recommended Strategy
              </p>
              <p style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.6 }}>
                {clusterDetail.strategy}
              </p>
            </div>
          </div>
        ) : clusterRanking ? (
          <div style={{ paddingTop: 16 }}>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              Detailed query-level data for the <strong>{clusterRanking.cluster}</strong> cluster.
              Coverage: {clusterRanking.coverage} queries.
              {clusterRanking.yourRank
                ? ` You're ranked #${clusterRanking.yourRank} with ${clusterRanking.yourShare}% share.`
                : ' You currently have no presence in this cluster.'}
            </p>
            <p style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 8 }}>
              {clusterRanking.assessment}
            </p>
          </div>
        ) : null}
      </SlideDrawer>
    </>
  );
}
