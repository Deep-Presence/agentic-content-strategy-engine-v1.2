'use client';

import { useState, type ReactNode } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

export function Collapsible({ title, subtitle, count, defaultOpen = false, children }: {
  title: string; subtitle?: string; count?: number; defaultOpen?: boolean; children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 8, padding: '12px 14px',
          border: 'none', background: open ? 'var(--surface)' : 'var(--bg)', cursor: 'pointer',
          borderBottom: open ? '1px solid var(--border)' : 'none', transition: 'background 0.15s',
          textAlign: 'left',
        }}
        onMouseEnter={(e) => { if (!open) e.currentTarget.style.background = 'var(--accent-subtle)'; }}
        onMouseLeave={(e) => { if (!open) e.currentTarget.style.background = 'var(--bg)'; }}
      >
        {open ? <ChevronDown size={14} style={{ color: 'var(--text-tertiary)', flexShrink: 0 }} /> : <ChevronRight size={14} style={{ color: 'var(--text-tertiary)', flexShrink: 0 }} />}
        <div style={{ flex: 1 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>{title}</span>
          {subtitle && <span style={{ fontSize: 11, color: 'var(--text-secondary)', marginLeft: 8 }}>{subtitle}</span>}
        </div>
        {count !== undefined && (
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-tertiary)', padding: '1px 6px', borderRadius: 9999, background: 'var(--surface)', border: '1px solid var(--border)' }}>{count}</span>
        )}
      </button>
      {open && <div>{children}</div>}
    </div>
  );
}
