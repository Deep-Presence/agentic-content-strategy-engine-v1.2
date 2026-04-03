'use client';

import { ArrowRight, Plus, Wrench } from 'lucide-react';
import { BrandLogo } from './brand-logo';
import { SlideDrawer } from './slide-drawer';
import { UNCITED_QUERIES, ENGINE_DOMAINS } from './data';

interface UncitedQueriesDrawerProps {
  open: boolean;
  onClose: () => void;
}

export function UncitedQueriesDrawer({ open, onClose }: UncitedQueriesDrawerProps) {
  return (
    <SlideDrawer
      open={open}
      onClose={onClose}
      title="Queries That Mention Without Citing"
      subtitle={`${UNCITED_QUERIES.length} conversion opportunities — AI engines know about you but don't link to your content`}
    >
      <div className="space-y-0">
        {UNCITED_QUERIES.map((q, i) => (
          <div
            key={q.query}
            className="py-3 transition-colors duration-150"
            style={{
              borderBottom: '1px solid var(--border-subtle)',
              animation: `fadeUp 200ms ease ${i * 30}ms both`,
            }}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="text-[13px] font-medium" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-primary)' }}>
                  &quot;{q.query}&quot;
                </div>
                <div className="flex items-center gap-1.5 mt-1">
                  <span className="text-[11px]" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-tertiary)' }}>
                    Mentioned on:
                  </span>
                  {q.engines.map((eng) => (
                    <BrandLogo key={eng} domain={ENGINE_DOMAINS[eng] || eng} size={14} />
                  ))}
                </div>
                <div className="text-[12px] mt-1" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
                  {q.note}
                </div>
              </div>
              <button
                className="flex items-center gap-1 h-[28px] px-2.5 rounded-[var(--radius-sm)] text-[11px] font-medium flex-shrink-0 transition-colors duration-150"
                style={{
                  fontFamily: 'var(--font-body)',
                  color: q.action === 'improve' ? 'var(--accent)' : 'var(--success)',
                  border: `1px solid ${q.action === 'improve' ? 'var(--accent)' : 'var(--success)'}`,
                  background: 'transparent',
                }}
              >
                {q.action === 'improve' ? <Wrench size={11} /> : <Plus size={11} />}
                {q.action === 'improve' ? 'Improve' : 'Create'}
                <ArrowRight size={11} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </SlideDrawer>
  );
}
