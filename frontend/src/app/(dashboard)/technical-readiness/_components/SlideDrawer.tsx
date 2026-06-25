'use client';

import { useEffect } from 'react';
import { X } from 'lucide-react';
import { AFFECTED_PAGES } from './tech-readiness-data';

interface SlideDrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  type: 'pages' | 'dimension';
  dimensionName?: string;
}

export function SlideDrawer({ open, onClose, title, type, dimensionName }: SlideDrawerProps) {
  useEffect(() => {
    function handleEsc(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    if (open) {
      document.addEventListener('keydown', handleEsc);
      return () => document.removeEventListener('keydown', handleEsc);
    }
  }, [open, onClose]);

  if (!open) return null;

  const pages = AFFECTED_PAGES.sort((a, b) => a.score - b.score);

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40"
        style={{ backgroundColor: 'rgba(0,0,0,0.3)' }}
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        className="fixed top-0 right-0 bottom-0 z-50 overflow-y-auto"
        style={{
          width: '50%',
          minWidth: 400,
          backgroundColor: 'var(--surface)',
          borderLeft: '1px solid var(--border)',
          boxShadow: 'var(--shadow-float)',
          animation: 'slideInRight 200ms ease',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-6 py-5 border-b border-[var(--border)]"
          style={{ position: 'sticky', top: 0, zIndex: 10, backgroundColor: 'var(--surface)' }}
        >
          <div>
            <p
              className="text-[10px] uppercase tracking-[0.06em] font-semibold mb-1"
              style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}
            >
              {type === 'pages' ? 'Pages Affected' : 'Dimension Detail'}
            </p>
            <h3
              className="text-[16px] font-semibold"
              style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
            >
              {title}
            </h3>
          </div>
          <button
            className="w-[30px] h-[30px] flex items-center justify-center rounded-[var(--radius-sm)] hover:bg-[var(--accent-subtle)] transition-colors"
            onClick={onClose}
          >
            <X size={16} style={{ color: 'var(--text-secondary)' }} />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-5">
          {type === 'pages' && (
            <div className="flex flex-col gap-2">
              {pages.map((page) => (
                <div
                  key={page.url}
                  className="border border-[var(--border)] rounded-[var(--radius-md)] p-3 hover:border-[var(--border-strong)] transition-colors"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span
                      className="text-[12px]"
                      style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}
                    >
                      {page.url}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span
                        className="text-[10px] uppercase tracking-[0.05em]"
                        style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}
                      >
                        Score:
                      </span>
                      <span
                        className="text-[13px] font-medium"
                        style={{
                          fontFamily: 'var(--font-mono)',
                          color: page.score < 20 ? 'var(--error)' : page.score < 40 ? 'var(--warning)' : 'var(--success)',
                        }}
                      >
                        {page.score}
                      </span>
                    </span>
                  </div>
                  <p
                    className="text-[13px] mb-1"
                    style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
                  >
                    {page.title}
                  </p>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className="text-[11px]"
                      style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}
                    >
                      Published: {page.published}
                    </span>
                    <span className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>|</span>
                    <span
                      className="text-[10px] uppercase tracking-[0.05em]"
                      style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}
                    >
                      Missing:
                    </span>
                    {page.missing.map((item) => (
                      <span
                        key={item}
                        className="text-[10px] px-1.5 py-0.5 rounded-[var(--radius-sm)] border border-[var(--border)]"
                        style={{
                          color: 'var(--text-secondary)',
                          fontFamily: 'var(--font-display)',
                          backgroundColor: 'var(--error-subtle)',
                        }}
                      >
                        {item}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {type === 'dimension' && dimensionName && (
            <div>
              <p
                className="text-[13px] leading-[1.6] mb-4"
                style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}
              >
                Detailed findings for the <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{dimensionName}</span> dimension.
                Click on individual findings to see affected pages and recommended actions.
              </p>
              <div className="flex flex-col gap-2">
                {pages.slice(0, 6).map((page) => (
                  <div
                    key={page.url}
                    className="border border-[var(--border)] rounded-[var(--radius-md)] p-3"
                  >
                    <span className="text-[12px]" style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>
                      {page.url}
                    </span>
                    <p className="text-[13px] mt-1" style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
                      {page.title}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
