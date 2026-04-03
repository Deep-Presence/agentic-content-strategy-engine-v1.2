'use client';

import { TrendingUp, TrendingDown } from 'lucide-react';
import { KPIS } from './data';

interface KPICardProps {
  label: string;
  value: string;
  delta: string;
  deltaPositive: boolean;
  accentBorder?: string;
  onClick?: () => void;
  clickableText?: string;
  onClickableText?: () => void;
  delay: number;
  valueFontSize?: number;
}

function KPICard({ label, value, delta, deltaPositive, accentBorder, onClick, clickableText, onClickableText, delay, valueFontSize = 28 }: KPICardProps) {
  return (
    <div
      className="flex-1 min-w-0 cursor-pointer transition-colors duration-150"
      onClick={onClick}
      style={{
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
        padding: 14,
        borderLeft: accentBorder ? `3px solid ${accentBorder}` : undefined,
        background: 'var(--surface)',
        animation: `fadeUp 300ms ease ${delay}ms both`,
      }}
      onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.borderColor = 'var(--border-strong)')}
      onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.borderColor = 'var(--border)')}
    >
      <div
        className="text-[10px] uppercase font-semibold tracking-[0.05em]"
        style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)', marginBottom: 6 }}
      >
        {label}
      </div>
      <div
        className="font-semibold"
        style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', lineHeight: 1.1, fontSize: valueFontSize }}
      >
        {value}
      </div>
      <div className="flex items-center gap-1 mt-1.5">
        {deltaPositive ? (
          <TrendingUp size={12} style={{ color: 'var(--success)' }} />
        ) : (
          <TrendingDown size={12} style={{ color: 'var(--error)' }} />
        )}
        <span
          className="text-[12px] font-medium"
          style={{ fontFamily: 'var(--font-mono)', color: deltaPositive ? 'var(--success)' : 'var(--error)' }}
        >
          {delta}
        </span>
        {clickableText && (
          <button
            onClick={(e) => { e.stopPropagation(); onClickableText?.(); }}
            className="underline transition-colors duration-150 text-[12px] font-medium cursor-pointer"
            style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}
          >
            {clickableText}
          </button>
        )}
      </div>
    </div>
  );
}

interface KPIStripProps {
  onUncitedClick?: () => void;
}

export function KPIStrip({ onUncitedClick }: KPIStripProps) {
  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div className="grid grid-cols-4 gap-3">
      <KPICard
        label="Total Citations"
        value={KPIS.totalCitations.toLocaleString()}
        delta={`+${KPIS.citationsDelta} this period`}
        deltaPositive
        accentBorder="var(--accent)"
        onClick={() => scrollTo('citation-momentum')}
        delay={0}
        valueFontSize={36}
      />
      <KPICard
        label="Citation Rate"
        value={`${KPIS.citationRate}%`}
        delta={`from ${KPIS.citationRatePrev}%`}
        deltaPositive
        onClick={() => scrollTo('visibility-pipeline')}
        delay={40}
      />
      <KPICard
        label="Mention-to-Cite Gap"
        value={`${KPIS.mentionToCitationGap}%`}
        delta={`${KPIS.uncitedQueries} queries`}
        deltaPositive={false}
        accentBorder={KPIS.mentionToCitationGap > 15 ? 'var(--warning)' : undefined}
        onClick={() => scrollTo('visibility-pipeline')}
        clickableText={`${KPIS.uncitedQueries} queries`}
        onClickableText={onUncitedClick}
        delay={80}
      />
      <KPICard
        label="Avg Citation Position"
        value={KPIS.avgPosition.toFixed(1)}
        delta={`from ${KPIS.avgPositionPrev}`}
        deltaPositive
        onClick={() => scrollTo('platform-intelligence')}
        delay={120}
      />
    </div>
  );
}
