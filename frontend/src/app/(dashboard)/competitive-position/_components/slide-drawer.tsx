'use client';

import { useEffect, useCallback, type ReactNode } from 'react';
import { X } from 'lucide-react';

export function SlideDrawer({ isOpen, onClose, title, subtitle, width = '50vw', children }: {
  isOpen: boolean; onClose: () => void; title: string; subtitle?: string; width?: string; children: ReactNode;
}) {
  const esc = useCallback((e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); }, [onClose]);
  useEffect(() => { if (isOpen) { document.addEventListener('keydown', esc); return () => document.removeEventListener('keydown', esc); } }, [isOpen, esc]);
  if (!isOpen) return null;
  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.2)', zIndex: 40, animation: 'fadeIn 150ms ease' }} />
      <div style={{ position: 'fixed', top: 0, right: 0, bottom: 0, width, maxWidth: '100vw', background: 'var(--surface)', borderLeft: '1px solid var(--border)', boxShadow: 'var(--shadow-float)', zIndex: 50, display: 'flex', flexDirection: 'column', animation: 'slideInRight 200ms ease' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexShrink: 0 }}>
          <div>
            <h2 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>{title}</h2>
            {subtitle && <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>{subtitle}</p>}
          </div>
          <button onClick={onClose} style={{ width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center', border: 'none', background: 'transparent', cursor: 'pointer', borderRadius: 4, color: 'var(--text-secondary)' }}>
            <X size={15} strokeWidth={1.5} />
          </button>
        </div>
        <div style={{ flex: 1, overflow: 'auto', padding: '0 20px 20px' }}>{children}</div>
      </div>
    </>
  );
}
