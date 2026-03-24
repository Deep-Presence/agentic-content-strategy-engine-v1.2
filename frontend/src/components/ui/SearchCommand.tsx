'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { Search } from 'lucide-react';
import { useEffect, useState, useCallback } from 'react';

interface SearchResult {
  id: string;
  label: string;
  description?: string;
  href?: string;
}

interface SearchCommandProps {
  open: boolean;
  onClose: () => void;
  results?: SearchResult[];
  onSelect?: (result: SearchResult) => void;
  placeholder?: string;
}

export function SearchCommand({ open, onClose, results = [], onSelect, placeholder = 'Search...' }: SearchCommandProps) {
  const [query, setQuery] = useState('');

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      if (open) onClose();
    }
    if (e.key === 'Escape') onClose();
  }, [open, onClose]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  useEffect(() => {
    if (!open) setQuery('');
  }, [open]);

  const filtered = results.filter(r =>
    r.label.toLowerCase().includes(query.toLowerCase()) ||
    r.description?.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/40 z-50"
            onClick={onClose}
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className="fixed top-[20%] left-1/2 -translate-x-1/2 z-50 w-[520px] max-w-[90vw]"
          >
            <div className="bg-surface-raised border border-border rounded-lg shadow-float overflow-hidden">
              <div className="flex items-center gap-2 px-3 border-b border-border">
                <Search size={14} strokeWidth={1.5} className="text-text-tertiary" />
                <input
                  autoFocus
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={placeholder}
                  className="flex-1 h-[40px] bg-transparent text-[13px] text-text-primary outline-none placeholder:text-text-tertiary"
                />
                <kbd className="text-[10px] px-1 py-0.5 rounded bg-bg border border-border text-text-tertiary">ESC</kbd>
              </div>
              {filtered.length > 0 && (
                <div className="max-h-[300px] overflow-y-auto py-1">
                  {filtered.map((r) => (
                    <button
                      key={r.id}
                      onClick={() => onSelect?.(r)}
                      className="w-full text-left px-3 py-2 hover:bg-accent-subtle transition-colors cursor-pointer"
                    >
                      <div className="text-[12px] font-medium text-text-primary">{r.label}</div>
                      {r.description && (
                        <div className="text-[11px] text-text-tertiary mt-0.5">{r.description}</div>
                      )}
                    </button>
                  ))}
                </div>
              )}
              {query && filtered.length === 0 && (
                <div className="px-3 py-6 text-center text-[12px] text-text-tertiary">
                  No results found
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
