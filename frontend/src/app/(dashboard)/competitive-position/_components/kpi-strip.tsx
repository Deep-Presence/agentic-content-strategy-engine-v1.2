'use client';

import { Trophy, Target, AlertTriangle, Map } from 'lucide-react';
import { YOUR_DATA, CLUSTER_RANKINGS } from './data';

export function KPIStrip() {
  const d = YOUR_DATA;
  const clustersLed = CLUSTER_RANKINGS.filter((c) => c.status === 'winning').length;
  const totalClusters = CLUSTER_RANKINGS.length;

  return (
    <div className="grid grid-cols-4" style={{ gap: 12 }}>
      <KPI icon={<Target size={14} />} iconColor={d.winRate >= 30 ? 'var(--warning)' : 'var(--error)'} label="Win Rate" value={`${d.winRate}%`} delta={`+${d.gapsNet} gaps closed this month`} deltaColor="var(--success)" sectionId="head-to-head" />
      <KPI icon={<Trophy size={14} />} iconColor="var(--accent)" label="Competitive Rank" value={`#${d.rank} of ${d.totalTracked}`} delta={`Up from #${d.previousRank} last month`} deltaColor="var(--success)" sectionId="rank-hero" />
      <KPI icon={<AlertTriangle size={14} />} iconColor="var(--error)" label="Citations at Risk" value={String(d.atRisk + d.lost)} delta={`${d.lost} lost · ${d.atRisk - d.lost} weakening`} deltaColor="var(--error)" sectionId="watchlist" />
      <KPI icon={<Map size={14} />} iconColor="var(--success)" label="Territory Control" value={`${clustersLed} of ${totalClusters}`} delta={`Leading ${clustersLed} clusters`} deltaColor="var(--success)" sectionId="territory" />
    </div>
  );
}

function KPI({ icon, iconColor, label, value, delta, deltaColor, sectionId }: {
  icon: React.ReactNode; iconColor: string; label: string; value: string; delta: string; deltaColor: string; sectionId: string;
}) {
  const scrollTo = () => {
    const el = document.getElementById(sectionId);
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div
      onClick={scrollTo}
      style={{
        border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: 14,
        background: 'var(--surface)', cursor: 'pointer', transition: 'border-color 0.15s',
        display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--border-strong)')}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
    >
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 6 }}>
          <div style={{ width: 22, height: 22, borderRadius: 5, display: 'flex', alignItems: 'center', justifyContent: 'center', color: iconColor, background: `color-mix(in srgb, ${iconColor} 12%, transparent)` }}>{icon}</div>
          <span style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}>{label}</span>
        </div>
        <p style={{ fontSize: 22, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', lineHeight: 1 }}>{value}</p>
        <p style={{ fontSize: 11, color: deltaColor, marginTop: 4, fontFamily: 'var(--font-mono)', fontWeight: 500 }}>{delta}</p>
      </div>
    </div>
  );
}
