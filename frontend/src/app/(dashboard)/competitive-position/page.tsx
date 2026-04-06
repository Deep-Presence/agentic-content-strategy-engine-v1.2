'use client';

import { useState, useRef, useEffect } from 'react';
import { Calendar } from 'lucide-react';
import { KPIStrip } from './_components/kpi-strip';
import { SOVHeroSection } from './_components/sov-hero';
import { LandscapeGrid } from './_components/landscape-grid';
import { HeadToHead } from './_components/head-to-head';
import { ClusterAndDimensions } from './_components/cluster-cards';
import { ActivityFeed } from './_components/activity-feed';
import { CompetitorDrawer, ClusterDrawer } from './_components/drawers';
import { clusterOptions, platformOptions } from './_components/data';

// ─── Date Range Picker ──────────────────────────────────────────────────────

function DateRangePicker({ value, onChange }: { value: [string, string]; onChange: (r: [string, string]) => void }) {
  const [isOpen, setIsOpen] = useState(false);
  const [selecting, setSelecting] = useState<'start' | 'end'>('start');
  const [tempStart, setTempStart] = useState(value[0]);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { if (!isOpen) return; const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) { setIsOpen(false); setSelecting('start'); } }; document.addEventListener('mousedown', h); return () => document.removeEventListener('mousedown', h); }, [isOpen]);
  const fmt = (d: string) => new Date(d + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  const monthDays = (y: number, m: number) => { const f = new Date(y, m, 1).getDay(); const d = new Date(y, m + 1, 0).getDate(); const days: (number | null)[] = Array(f).fill(null); for (let i = 1; i <= d; i++) days.push(i); return days; };
  const mN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const dN = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];
  const click = (y: number, m: number, d: number) => { const ds = `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`; if (selecting === 'start') { setTempStart(ds); setSelecting('end'); } else { const s = tempStart < ds ? tempStart : ds; const e = tempStart < ds ? ds : tempStart; onChange([s, e]); setSelecting('start'); setIsOpen(false); } };
  const inR = (y: number, m: number, d: number) => { const ds = `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`; return ds >= value[0] && ds <= value[1]; };
  const isE = (y: number, m: number, d: number) => { const ds = `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`; return ds === value[0] || ds === value[1]; };
  const renderMonth = (y: number, m: number) => (
    <div>
      <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-primary)', textAlign: 'center', marginBottom: 6 }}>{mN[m]} {y}</p>
      <div className="grid grid-cols-7 gap-0">
        {dN.map((d) => <div key={d} style={{ fontSize: 8, fontWeight: 500, color: 'var(--text-tertiary)', textAlign: 'center', padding: '3px 0' }}>{d}</div>)}
        {monthDays(y, m).map((d, i) => !d ? <div key={`e-${i}`} /> : (
          <button key={d} onClick={() => click(y, m, d)} style={{ height: 24, width: 24, margin: '0 auto', fontSize: 10, borderRadius: 2, border: 'none', cursor: 'pointer', background: isE(y, m, d) ? 'var(--accent)' : inR(y, m, d) ? 'var(--accent-subtle)' : 'transparent', color: isE(y, m, d) ? '#fff' : 'var(--text-secondary)' }}>{d}</button>
        ))}
      </div>
    </div>
  );
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setIsOpen(!isOpen)} className="flex items-center gap-2" style={{ height: 28, padding: '0 8px', border: '1px solid var(--border)', borderRadius: 4, background: 'var(--surface)', fontSize: 11, color: 'var(--text-primary)', cursor: 'pointer' }}>
        <Calendar size={12} strokeWidth={1.5} style={{ color: 'var(--text-tertiary)' }} /><span>{fmt(value[0])} {fmt(value[1])}</span>
      </button>
      {isOpen && (
        <div style={{ position: 'absolute', top: '100%', left: 0, marginTop: 4, background: 'var(--surface-raised)', border: '1px solid var(--border)', borderRadius: 6, boxShadow: 'var(--shadow-float)', padding: 14, zIndex: 50 }}>
          <div className="flex gap-5">{renderMonth(2026, 2)}{renderMonth(2026, 3)}</div>
          {selecting === 'end' && <p style={{ fontSize: 9, color: 'var(--accent)', marginTop: 6, textAlign: 'center' }}>Click end date</p>}
        </div>
      )}
    </div>
  );
}

// ─── Main Page ──────────────────────────────────────────────────────────────

export default function CompetitivePositionPage() {
  const [dateRange, setDateRange] = useState<[string, string]>(['2026-03-01', '2026-03-28']);
  const [cluster, setCluster] = useState('all');
  const [platform, setPlatform] = useState('all');

  const [compDrawer, setCompDrawer] = useState<string | null>(null);
  const [clusterDrawer, setClusterDrawer] = useState<string | null>(null);

  const sel = { height: 28, padding: '0 8px', border: '1px solid var(--border)', borderRadius: 4, background: 'var(--surface)', fontSize: 11, color: 'var(--text-primary)', cursor: 'pointer', outline: 'none', fontFamily: 'var(--font-display)' } as const;

  return (
    <div style={{ padding: '14px 24px 40px' }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)', letterSpacing: '-0.02em', fontFamily: 'var(--font-display)' }}>Competitive Position</h1>
        <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 1 }}>Your competitive standing across AI engines</p>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-2" style={{ height: 40, marginLeft: -24, marginRight: -24, paddingLeft: 24, paddingRight: 24, borderBottom: '1px solid var(--border)' }}>
        <DateRangePicker value={dateRange} onChange={setDateRange} />
        <div style={{ height: 14, width: 1, background: 'var(--border)' }} />
        <select value={cluster} onChange={(e) => setCluster(e.target.value)} style={sel}>{clusterOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select>
        <div style={{ height: 14, width: 1, background: 'var(--border)' }} />
        <select value={platform} onChange={(e) => setPlatform(e.target.value)} style={sel}>{platformOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select>
        <button onClick={() => { setDateRange(['2026-03-01', '2026-03-28']); setCluster('all'); setPlatform('all'); }} style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-tertiary)', background: 'none', border: 'none', cursor: 'pointer' }}>Clear</button>
      </div>

      {/* Page content */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24, marginTop: 16 }}>
        {/* 1. KPIs */}
        <KPIStrip />

        {/* 2. Market Share + SOV Trend + Rising Threats */}
        <SOVHeroSection onCompetitorClick={setCompDrawer} />

        {/* 3. Competitive Landscape (full-width stacked) */}
        <LandscapeGrid onBrandClick={setCompDrawer} />

        {/* 4. Head-to-Head (pinnable cards + expandable table) */}
        <div id="head-to-head">
          <HeadToHead onCompetitorClick={setCompDrawer} />
        </div>

        {/* 5. Competitive Breakdown + Cluster Cards */}
        <ClusterAndDimensions onClusterClick={setClusterDrawer} />

        {/* 6. Activity Feed */}
        <ActivityFeed onEventClick={() => {}} />
      </div>

      {/* Drawers */}
      <CompetitorDrawer domain={compDrawer} onClose={() => setCompDrawer(null)} />
      <ClusterDrawer cluster={clusterDrawer} onClose={() => setClusterDrawer(null)} />
    </div>
  );
}
