'use client';

import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import { useEffect } from 'react';

interface SlideDrawerProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  /** Optional metadata line below the title */
  subtitle?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  /** Width as CSS value. Defaults to 50vw. */
  width?: string;
}

export function SlideDrawer({
  open,
  onClose,
  title,
  subtitle,
  children,
  className,
  width = '50vw',
}: SlideDrawerProps) {
  // Escape key closes drawer
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  // Prevent body scroll when open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = '';
      };
    }
  }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Overlay — semi-transparent, table/content stays visible */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 bg-black/20 z-40"
            onClick={onClose}
          />

          {/* Drawer panel */}
          <motion.aside
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: 0.25, ease: [0.32, 0.72, 0, 1] }}
            className={cn(
              'fixed top-0 right-0 bottom-0 z-50',
              'bg-surface border-l border-border',
              'shadow-[var(--shadow-float)]',
              'flex flex-col overflow-hidden',
              className,
            )}
            style={{ width }}
          >
            {/* Header */}
            {(title || subtitle) && (
              <div className="shrink-0 px-6 py-5 border-b border-border">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    {title && (
                      <h2 className="text-[16px] font-semibold text-text-primary font-body truncate">
                        {title}
                      </h2>
                    )}
                    {subtitle && (
                      <div className="text-[13px] text-text-secondary font-body mt-0.5">
                        {subtitle}
                      </div>
                    )}
                  </div>
                  <button
                    onClick={onClose}
                    className={cn(
                      'shrink-0 size-[30px] inline-flex items-center justify-center',
                      'rounded-sm text-text-tertiary cursor-pointer',
                      'hover:text-text-primary hover:bg-surface-raised transition-colors',
                    )}
                  >
                    <X size={16} strokeWidth={1.5} />
                  </button>
                </div>
              </div>
            )}

            {/* Close button when no header */}
            {!title && !subtitle && (
              <button
                onClick={onClose}
                className={cn(
                  'absolute top-4 right-4 z-10',
                  'size-[30px] inline-flex items-center justify-center',
                  'rounded-sm text-text-tertiary cursor-pointer',
                  'hover:text-text-primary hover:bg-surface-raised transition-colors',
                )}
              >
                <X size={16} strokeWidth={1.5} />
              </button>
            )}

            {/* Scrollable content */}
            <div className="flex-1 overflow-y-auto px-6 py-6">
              {children}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
