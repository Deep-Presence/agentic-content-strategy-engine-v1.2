'use client';

import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import { useEffect } from 'react';

interface SlideDrawerProps {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
  className?: string;
}

export function SlideDrawer({ open, onClose, children, className }: SlideDrawerProps) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop: spec says rgba(0,0,0,0.15) */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-40"
            style={{ background: 'rgba(0,0,0,0.15)' }}
            onClick={onClose}
          />
          {/* Drawer panel: 50% viewport width */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            className={cn(
              'fixed top-0 right-0 h-full w-[50vw] z-50',
              'flex flex-col overflow-hidden',
              className
            )}
            style={{
              background: 'var(--surface)',
              borderLeft: '1px solid var(--border)',
              boxShadow: 'var(--shadow-float)',
            }}
          >
            {/* Close button: 32px hit target */}
            <button
              onClick={onClose}
              className="absolute top-3 right-3 z-10 flex items-center justify-center cursor-pointer"
              style={{
                width: 32,
                height: 32,
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-tertiary)',
                transition: 'color 0.12s, background 0.12s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = 'var(--text-primary)';
                e.currentTarget.style.background = 'var(--surface-raised)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = 'var(--text-tertiary)';
                e.currentTarget.style.background = 'transparent';
              }}
            >
              <X size={14} strokeWidth={1.5} />
            </button>
            <div className="flex-1 overflow-y-auto">
              {children}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
