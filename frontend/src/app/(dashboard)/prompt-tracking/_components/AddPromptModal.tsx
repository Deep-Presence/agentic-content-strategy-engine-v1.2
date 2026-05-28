'use client';

import { useState } from 'react';
import { X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import { useAuth } from '@/hooks/useAuth';
import { createPrompt } from '../_lib/api';
import { CATEGORY_DISPLAY_MAP } from '../_lib/adapters';
import { ApiError } from '@/lib/api-client';

interface AddPromptModalProps {
  open: boolean;
  onClose: () => void;
  /** Called after successful prompt creation. Passes promptId + optional fanoutTaskId for SSE tracking. */
  onCreated: (promptId: string, fanoutTaskId: string | null) => void;
}

const CATEGORIES = Object.entries(CATEGORY_DISPLAY_MAP).map(([value, { name }]) => ({
  value,
  label: name,
}));

export function AddPromptModal({ open, onClose, onCreated }: AddPromptModalProps) {
  const { companyName } = useAuth();
  const [text, setText] = useState('');
  const [category, setCategory] = useState('');
  const [tagsInput, setTagsInput] = useState('');
  const [generateFanout, setGenerateFanout] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    const trimmed = text.trim();
    if (!trimmed) return;

    setSubmitting(true);
    setError(null);

    try {
      const tags = tagsInput
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean);

      const result = await createPrompt({
        text: trimmed,
        category: category || undefined,
        tags: tags.length > 0 ? tags : undefined,
        generate_fanout: generateFanout,
        brand_name: companyName || undefined,
      });

      // Reset form and notify parent
      setText('');
      setCategory('');
      setTagsInput('');
      setGenerateFanout(true);
      onCreated(result.prompt.id, result.fanout_task_id);
      onClose();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError('Failed to create prompt. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && text.trim()) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    height: 34,
    padding: '0 10px',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    background: 'transparent',
    fontSize: 13,
    color: 'var(--text-primary)',
    outline: 'none',
  };

  const labelStyle: React.CSSProperties = {
    fontSize: 12,
    fontWeight: 500,
    color: 'var(--text-secondary)',
    marginBottom: 4,
    display: 'block',
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 bg-black/20 z-[70]"
            onClick={onClose}
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.2 }}
            className="fixed z-[71] top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2"
            style={{
              width: 480,
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)',
              boxShadow: 'var(--shadow-float)',
            }}
          >
            {/* Header */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '16px 20px',
                borderBottom: '1px solid var(--border)',
              }}
            >
              <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                Add Prompt
              </h3>
              <button
                onClick={onClose}
                className={cn(
                  'size-[30px] inline-flex items-center justify-center',
                  'rounded-sm text-text-tertiary cursor-pointer',
                  'hover:text-text-primary hover:bg-surface-raised transition-colors',
                )}
              >
                <X size={16} strokeWidth={1.5} />
              </button>
            </div>

            {/* Body */}
            <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
              {/* Prompt text */}
              <div>
                <label style={labelStyle}>Prompt question</label>
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="e.g. What is the best AI app builder for startups?"
                  rows={2}
                  style={{
                    ...inputStyle,
                    height: 'auto',
                    padding: '8px 10px',
                    resize: 'vertical',
                    minHeight: 60,
                    fontFamily: 'inherit',
                  }}
                />
              </div>

              {/* Category */}
              <div>
                <label style={labelStyle}>Category</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  style={{ ...inputStyle, cursor: 'pointer' }}
                >
                  <option value="">None</option>
                  {CATEGORIES.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Tags */}
              <div>
                <label style={labelStyle}>Tags (comma-separated)</label>
                <input
                  type="text"
                  value={tagsInput}
                  onChange={(e) => setTagsInput(e.target.value)}
                  placeholder="e.g. branded, comparison"
                  style={inputStyle}
                />
              </div>

              {/* Generate fanout toggle */}
              <label
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  fontSize: 13,
                  color: 'var(--text-secondary)',
                  cursor: 'pointer',
                }}
              >
                <input
                  type="checkbox"
                  checked={generateFanout}
                  onChange={(e) => setGenerateFanout(e.target.checked)}
                  style={{ width: 14, height: 14, accentColor: 'var(--accent)' }}
                />
                Auto-generate query fanouts
              </label>

              {/* Error */}
              {error && (
                <div style={{ fontSize: 13, color: 'var(--error)' }}>{error}</div>
              )}
            </div>

            {/* Footer */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'flex-end',
                gap: 8,
                padding: '12px 20px',
                borderTop: '1px solid var(--border)',
              }}
            >
              <button
                onClick={onClose}
                className="cursor-pointer"
                style={{
                  height: 30,
                  padding: '0 14px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border)',
                  background: 'transparent',
                  fontSize: 12,
                  fontWeight: 500,
                  color: 'var(--text-primary)',
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={!text.trim() || submitting}
                className="cursor-pointer"
                style={{
                  height: 30,
                  padding: '0 14px',
                  borderRadius: 'var(--radius-sm)',
                  border: 'none',
                  background: !text.trim() || submitting ? 'var(--border)' : 'var(--accent)',
                  color: 'white',
                  fontSize: 12,
                  fontWeight: 500,
                  opacity: submitting ? 0.7 : 1,
                }}
              >
                {submitting ? 'Creating...' : 'Add Prompt'}
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
