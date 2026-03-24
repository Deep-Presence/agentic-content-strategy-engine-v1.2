'use client';

import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle, AlertCircle, Info, X } from 'lucide-react';
import { useEffect } from 'react';

interface ToastProps {
  open: boolean;
  onClose: () => void;
  variant?: 'success' | 'error' | 'info';
  message: string;
  duration?: number;
}

const icons = {
  success: CheckCircle,
  error: AlertCircle,
  info: Info,
};

export function Toast({ open, onClose, variant = 'info', message, duration = 4000 }: ToastProps) {
  const Icon = icons[variant];

  useEffect(() => {
    if (open && duration > 0) {
      const timer = setTimeout(onClose, duration);
      return () => clearTimeout(timer);
    }
  }, [open, duration, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0, y: 20, x: '-50%' }}
          animate={{ opacity: 1, y: 0, x: '-50%' }}
          exit={{ opacity: 0, y: 20, x: '-50%' }}
          transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          className={cn(
            'fixed bottom-6 left-1/2 z-50',
            'flex items-start gap-2 px-[10px] py-2 max-w-[320px]',
            'bg-surface border rounded-md shadow-float',
            variant === 'success' && 'border-success',
            variant === 'error' && 'border-error',
            variant === 'info' && 'border-border',
          )}
        >
          <Icon
            size={14}
            strokeWidth={1.5}
            className={cn(
              'mt-0.5 flex-shrink-0',
              variant === 'success' && 'text-success',
              variant === 'error' && 'text-error',
              variant === 'info' && 'text-accent',
            )}
          />
          <span className="text-[12px] text-text-primary flex-1">{message}</span>
          <button
            onClick={onClose}
            className="p-0.5 text-text-tertiary hover:text-text-primary cursor-pointer"
          >
            <X size={12} strokeWidth={1.5} />
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
