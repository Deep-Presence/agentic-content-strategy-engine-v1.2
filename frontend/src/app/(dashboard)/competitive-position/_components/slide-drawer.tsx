'use client';

import { useEffect, useCallback, type ReactNode } from 'react';
import { X } from 'lucide-react';

interface SlideDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  width?: string;
  children: ReactNode;
}

export function SlideDrawer({ isOpen, onClose, title, subtitle, width = '50vw', children }: SlideDrawerProps) {
  const handleEscape = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    },
    [onClose],
  );

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [isOpen, handleEscape]);

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0,0,0,0.15)',
          zIndex: 40,
          animation: 'fadeIn 200ms ease',
        }}
      />

      {/* Drawer */}
      <div
        style={{
          position: 'fixed',
          top: 0,
          right: 0,
          bottom: 0,
          width,
          maxWidth: '100vw',
          background: 'var(--surface)',
          borderLeft: '1px solid var(--border)',
          boxShadow: 'var(--shadow-float)',
          zIndex: 50,
          display: 'flex',
          flexDirection: 'column',
          animation: 'slideInRight 200ms ease',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '20px 24px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            gap: '16px',
            flexShrink: 0,
          }}
        >
          <div>
            <h2
              style={{
                fontSize: '16px',
                fontWeight: 600,
                color: 'var(--text-primary)',
                fontFamily: 'var(--font-display)',
              }}
            >
              {title}
            </h2>
            {subtitle && (
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                {subtitle}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            style={{
              width: '30px',
              height: '30px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              borderRadius: '4px',
              color: 'var(--text-secondary)',
              transition: 'background 0.15s',
              flexShrink: 0,
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            <X size={16} strokeWidth={1.5} />
          </button>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflow: 'auto', padding: '0 24px 24px' }}>
          {children}
        </div>
      </div>
    </>
  );
}
