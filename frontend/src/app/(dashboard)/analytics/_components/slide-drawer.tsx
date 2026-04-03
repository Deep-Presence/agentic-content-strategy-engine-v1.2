'use client';

import { useEffect, useCallback } from 'react';
import { X } from 'lucide-react';

interface SlideDrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}

export function SlideDrawer({ open, onClose, title, subtitle, children }: SlideDrawerProps) {
  const handleEsc = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    },
    [onClose],
  );

  useEffect(() => {
    if (open) {
      document.addEventListener('keydown', handleEsc);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleEsc);
      document.body.style.overflow = '';
    };
  }, [open, handleEsc]);

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40"
        style={{ background: 'rgba(0,0,0,0.15)', animation: 'fadeIn 150ms ease' }}
        onClick={onClose}
      />
      {/* Drawer */}
      <div
        className="fixed top-0 right-0 bottom-0 z-50 flex flex-col"
        style={{
          width: '50%',
          minWidth: 480,
          background: 'var(--surface)',
          borderLeft: '1px solid var(--border)',
          boxShadow: 'var(--shadow-float)',
          animation: 'slideInRight 200ms ease',
        }}
      >
        {/* Header */}
        <div
          className="flex items-start justify-between px-6 pt-5 pb-4 flex-shrink-0"
          style={{ borderBottom: '1px solid var(--border)' }}
        >
          <div>
            <h3 className="text-[16px] font-semibold" style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}>
              {title}
            </h3>
            {subtitle && (
              <p className="text-[13px] mt-0.5" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
                {subtitle}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="w-[30px] h-[30px] flex items-center justify-center rounded-[var(--radius-sm)] transition-colors duration-150"
            style={{ color: 'var(--text-tertiary)', border: '1px solid transparent' }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--accent-subtle)';
              e.currentTarget.style.borderColor = 'var(--border)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
              e.currentTarget.style.borderColor = 'transparent';
            }}
          >
            <X size={16} />
          </button>
        </div>
        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {children}
        </div>
      </div>
    </>
  );
}
