'use client';

import { useState, useMemo } from 'react';
import { ArrowUp, ArrowDown, Minus, ChevronRight, Check, X as XIcon, ExternalLink } from 'lucide-react';
import { BrandLogo } from './brand-logo';
import { SlideDrawer } from './slide-drawer';
import { CITATION_URLS, PLATFORM_DOMAINS, getURLDrawerDetail, type CitationURL } from './data';
import { AreaChart, Area, ResponsiveContainer } from 'recharts';

type SortKey = 'citations' | 'queries' | 'cps' | 'velocity';
type SortDir = 'asc' | 'desc';

const PLATFORM_ORDER = ['chatgpt', 'claude', 'perplexity', 'google_ai', 'gemini'] as const;
const PLATFORM_LABELS: Record<string, string> = {
  chatgpt: 'ChatGPT', claude: 'Claude', perplexity: 'Perplexity', google_ai: 'Google AI', gemini: 'Gemini',
};

function VelocityCell({ velocity, trend }: { velocity: number; trend: 'up' | 'down' | 'flat' }) {
  const Icon = trend === 'up' ? ArrowUp : trend === 'down' ? ArrowDown : Minus;
  const color = velocity >= 3.0 ? 'var(--success)' : trend === 'down' ? 'var(--error)' : 'var(--text-secondary)';
  return (
    <div className="flex items-center gap-0.5">
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color }}>{velocity.toFixed(1)}</span>
      <Icon size={11} style={{ color }} />
    </div>
  );
}

function CPSCell({ cps }: { cps: number }) {
  const color = cps >= 0.6 ? 'var(--success)' : cps >= 0.45 ? 'var(--warning)' : 'var(--error)';
  return (
    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color }}>{cps.toFixed(3)}</span>
  );
}

function PlatformDots({ platforms }: { platforms: CitationURL['platforms'] }) {
  return (
    <div className="flex items-center gap-1">
      {PLATFORM_ORDER.map((pk) => {
        const val = platforms[pk];
        const domain = PLATFORM_DOMAINS[PLATFORM_LABELS[pk]] || pk;
        if (val > 0) {
          return <BrandLogo key={pk} domain={domain} size={14} />;
        }
        return (
          <span
            key={pk}
            className="inline-block w-[14px] h-[14px] rounded-full"
            style={{ border: '1px solid var(--border-strong)' }}
          />
        );
      })}
    </div>
  );
}

function SortHeader({ label, sortKey, currentSort, currentDir, onSort }: {
  label: string;
  sortKey: SortKey;
  currentSort: SortKey;
  currentDir: SortDir;
  onSort: (k: SortKey) => void;
}) {
  const isActive = currentSort === sortKey;
  return (
    <button
      onClick={() => onSort(sortKey)}
      className="flex items-center gap-0.5 text-[10px] uppercase font-semibold tracking-[0.05em] transition-colors duration-150"
      style={{ fontFamily: 'var(--font-body)', color: isActive ? 'var(--text-primary)' : 'var(--text-tertiary)' }}
    >
      {label}
      {isActive && (currentDir === 'desc' ? <ArrowDown size={9} /> : <ArrowUp size={9} />)}
    </button>
  );
}

function URLDrawerContent({ url }: { url: CitationURL }) {
  const detail = getURLDrawerDetail(url.url);
  const trendChartData = detail.trendData.map((v, i) => ({ day: i + 1, citations: v }));

  return (
    <div className="space-y-5">
      {/* URL + metadata */}
      <div>
        <a
          href={`https://${url.url}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[13px] flex items-center gap-1 transition-colors duration-150"
          style={{ fontFamily: 'var(--font-body)', color: 'var(--accent)' }}
        >
          {url.url} <ExternalLink size={11} />
        </a>
        <span className="text-[12px]" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-tertiary)' }}>
          First cited: {url.firstCited}
        </span>
      </div>

      {/* Citation Trend */}
      <div>
        <div className="text-[10px] uppercase font-semibold tracking-[0.05em] mb-2" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
          Citation Trend
        </div>
        <ResponsiveContainer width="100%" height={140}>
          <AreaChart data={trendChartData} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="urlTrend" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.3} />
                <stop offset="95%" stopColor="var(--accent)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <Area type="monotone" dataKey="citations" stroke="var(--accent)" fill="url(#urlTrend)" strokeWidth={1.5} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Platform Breakdown */}
      <div>
        <div className="text-[10px] uppercase font-semibold tracking-[0.05em] mb-2" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
          Platform Breakdown
        </div>
        <div className="grid gap-2" style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
          {PLATFORM_ORDER.map((pk) => {
            const count = url.platforms[pk];
            const cited = count > 0;
            const domain = PLATFORM_DOMAINS[PLATFORM_LABELS[pk]];
            return (
              <div
                key={pk}
                className="text-center rounded-[var(--radius-sm)] p-2"
                style={{ border: '1px solid var(--border)', background: 'var(--surface)' }}
              >
                <div className="flex justify-center mb-1">
                  <BrandLogo domain={domain} size={16} />
                </div>
                <div className="text-[10px] mb-0.5" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-tertiary)' }}>
                  {PLATFORM_LABELS[pk]}
                </div>
                <div className="text-[16px] font-bold" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                  {count}
                </div>
                <div
                  className="text-[10px] font-medium mt-0.5"
                  style={{ fontFamily: 'var(--font-body)', color: cited ? 'var(--success)' : 'var(--error)' }}
                >
                  {cited ? 'Cited' : 'Not'} {cited ? <Check size={9} className="inline" /> : <XIcon size={9} className="inline" />}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Queries citing this URL */}
      <div>
        <div className="text-[10px] uppercase font-semibold tracking-[0.05em] mb-2" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
          Queries That Cite This URL ({detail.queriesCiting.length})
        </div>
        {detail.queriesCiting.map((q, i) => (
          <div key={i} className="flex items-center justify-between py-1.5" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
            <span className="text-[13px]" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-primary)' }}>
              &quot;{q.query}&quot;
            </span>
            <div className="flex items-center gap-1 flex-shrink-0">
              {q.platforms.map((p) => (
                <BrandLogo key={p} domain={PLATFORM_DOMAINS[p] || ''} size={12} />
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Structural Signals */}
      <div>
        <div className="text-[10px] uppercase font-semibold tracking-[0.05em] mb-2" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
          Structural Signals
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[13px]" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
          {detail.structuralSignals.map((s) => (
            <span key={s.label}>
              {s.label}: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', fontWeight: 500 }}>{s.value}</span>
            </span>
          ))}
        </div>
      </div>

      {/* How to Improve */}
      <div
        className="rounded-[var(--radius-md)] p-3.5"
        style={{ border: '1px solid var(--border)', background: 'var(--surface)' }}
      >
        <div className="text-[14px] font-semibold mb-1" style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}>
          How to Improve This Page&apos;s Citations
        </div>
        <p className="text-[12px] mb-3" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
          Based on what top-cited content in your clusters looks like:
        </p>
        <div className="space-y-2">
          {detail.improvements.map((item, i) => (
            <div key={i} className="flex items-start gap-2">
              {item.good ? (
                <Check size={13} className="flex-shrink-0 mt-0.5" style={{ color: 'var(--success)' }} />
              ) : (
                <XIcon size={13} className="flex-shrink-0 mt-0.5" style={{ color: 'var(--error)' }} />
              )}
              <div>
                <span
                  className="text-[13px]"
                  style={{ fontFamily: 'var(--font-body)', color: item.good ? 'var(--text-primary)' : 'var(--error)' }}
                >
                  {item.text}
                </span>
                {item.detail !== 'good' && (
                  <span className="text-[11px] ml-1" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-tertiary)' }}>
                    &mdash; {item.detail}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
        <div
          className="mt-3 p-2 rounded-[var(--radius-sm)] text-[13px] font-medium"
          style={{ background: 'var(--success-subtle)', border: '1px solid var(--border-subtle)', fontFamily: 'var(--font-body)', color: 'var(--success)' }}
        >
          Estimated improvement if fixes applied: <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{detail.estimatedImpact}</span>
        </div>
        <button
          className="mt-3 flex items-center gap-1.5 h-[30px] px-3 rounded-[var(--radius-sm)] text-[12px] font-medium transition-colors duration-150"
          style={{ fontFamily: 'var(--font-body)', color: 'var(--text-on-accent)', background: 'var(--accent)' }}
        >
          Open in Content Studio <ArrowUp size={11} className="rotate-45" />
        </button>
      </div>
    </div>
  );
}

export function CitationURLsTable() {
  const [sortKey, setSortKey] = useState<SortKey>('citations');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [selectedUrl, setSelectedUrl] = useState<CitationURL | null>(null);

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir(sortDir === 'desc' ? 'asc' : 'desc');
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const sorted = useMemo(() => {
    return [...CITATION_URLS].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      return sortDir === 'desc' ? (bv as number) - (av as number) : (av as number) - (bv as number);
    });
  }, [sortKey, sortDir]);

  return (
    <div>
      <div className="mb-2">
        <h2 className="text-[16px] font-semibold" style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}>
          Citation URLs
        </h2>
        <p className="text-[12px]" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
          Ranked by citation count
        </p>
      </div>

      <div className="rounded-[var(--radius-md)] overflow-hidden" style={{ border: '1px solid var(--border)' }}>
        {/* Table Header */}
        <div
          className="grid items-center px-3"
          style={{
            gridTemplateColumns: '18% 18% 7% 10% 6% 7% 9% 7% 3%',
            height: 44,
            background: 'var(--surface)',
            borderBottom: '1px solid var(--border)',
          }}
        >
          <span className="text-[10px] uppercase font-semibold tracking-[0.05em]" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-tertiary)' }}>URL</span>
          <span className="text-[10px] uppercase font-semibold tracking-[0.05em]" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-tertiary)' }}>Title</span>
          <SortHeader label="Citations" sortKey="citations" currentSort={sortKey} currentDir={sortDir} onSort={handleSort} />
          <span className="text-[10px] uppercase font-semibold tracking-[0.05em]" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-tertiary)' }}>Platforms</span>
          <SortHeader label="Queries" sortKey="queries" currentSort={sortKey} currentDir={sortDir} onSort={handleSort} />
          <SortHeader label="CPS" sortKey="cps" currentSort={sortKey} currentDir={sortDir} onSort={handleSort} />
          <span className="text-[10px] uppercase font-semibold tracking-[0.05em]" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-tertiary)' }}>First Cited</span>
          <SortHeader label="Velocity" sortKey="velocity" currentSort={sortKey} currentDir={sortDir} onSort={handleSort} />
          <span />
        </div>

        {/* Table Body */}
        {sorted.map((row, i) => (
          <div
            key={row.url}
            className="grid items-center px-3 cursor-pointer transition-colors duration-150"
            style={{
              gridTemplateColumns: '18% 18% 7% 10% 6% 7% 9% 7% 3%',
              height: 48,
              borderBottom: i < sorted.length - 1 ? '1px solid var(--border-subtle)' : undefined,
              animation: `fadeUp 200ms ease ${i * 25}ms both`,
            }}
            onClick={() => setSelectedUrl(row)}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            <div className="truncate pr-2">
              <div className="text-[13px] truncate" style={{ fontFamily: 'var(--font-body)', color: 'var(--accent)' }}>
                /{row.url.split('/').slice(2).join('/')}
              </div>
              <div className="text-[10px] truncate" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-tertiary)' }}>
                {row.url.split('/')[0]}
              </div>
            </div>
            <span className="text-[13px] font-medium truncate pr-2" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-primary)' }}>
              {row.title}
            </span>
            <span className="text-[14px] font-semibold" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
              {row.citations}
            </span>
            <PlatformDots platforms={row.platforms} />
            <span className="text-[13px]" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
              {row.queries}
            </span>
            <CPSCell cps={row.cps} />
            <span className="text-[12px]" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
              {row.firstCited}
            </span>
            <VelocityCell velocity={row.velocity} trend={row.velocityTrend} />
            <ChevronRight size={14} style={{ color: 'var(--text-tertiary)' }} />
          </div>
        ))}
      </div>

      <SlideDrawer
        open={!!selectedUrl}
        onClose={() => setSelectedUrl(null)}
        title={selectedUrl?.title ?? ''}
        subtitle={selectedUrl ? `${selectedUrl.citations} total citations` : ''}
      >
        {selectedUrl && <URLDrawerContent url={selectedUrl} />}
      </SlideDrawer>
    </div>
  );
}
