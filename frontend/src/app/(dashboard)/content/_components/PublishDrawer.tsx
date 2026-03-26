'use client';

import { useState, useMemo, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, ExternalLink, Check } from 'lucide-react';
import { Button, Card, Badge, Input, Skeleton } from '@/components/ui';
import { isSafeUrl } from '@/lib/utils';
import type { CMSCategoryItem, CMSPublishResponse } from '@/lib/api/types';

interface PublishDrawerProps {
  open: boolean;
  onClose: () => void;
  brief: { id: string; title: string; content_preview?: string };
  categories: CMSCategoryItem[];
  categoriesLoading: boolean;
  onPublish: (data: {
    brief_id: string;
    status: 'draft' | 'publish';
    slug_override: string;
    categories: string[];
  }) => void;
  isPublishing: boolean;
  publishResult: CMSPublishResponse | null;
  publishError: string | null;
}

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 200);
}

export function PublishDrawer({
  open,
  onClose,
  brief,
  categories,
  categoriesLoading,
  onPublish,
  isPublishing,
  publishResult,
  publishError,
}: PublishDrawerProps) {
  const defaultSlug = useMemo(() => slugify(brief.title), [brief.title]);
  const [slug, setSlug] = useState(defaultSlug);
  const [status, setStatus] = useState<'draft' | 'publish'>('draft');
  const [selectedCategories, setSelectedCategories] = useState<Set<string>>(new Set());
  const drawerRef = useRef<HTMLDivElement>(null);

  // F10: Escape key to close
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onClose]);

  // F10: Auto-focus drawer on open
  useEffect(() => {
    if (open) drawerRef.current?.focus();
  }, [open]);

  const toggleCategory = (name: string) => {
    setSelectedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const handlePublish = () => {
    onPublish({
      brief_id: brief.id,
      status,
      slug_override: slug,
      categories: Array.from(selectedCategories),
    });
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
            className="fixed inset-0 bg-black/20 z-40"
            onClick={onClose}
          />

          {/* Drawer — F10: dialog semantics + focus */}
          <motion.div
            ref={drawerRef}
            role="dialog"
            aria-modal="true"
            aria-label="Publish to CMS"
            tabIndex={-1}
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 30, stiffness: 300 }}
            className="fixed right-0 top-0 h-full w-[400px] bg-bg border-l border-border z-50 overflow-y-auto outline-none"
          >
            <div className="p-4">
              {/* Header */}
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-[16px] font-semibold text-text-primary">Publish to CMS</h3>
                <button
                  type="button"
                  onClick={onClose}
                  className="p-1 text-text-tertiary hover:text-text-primary transition-colors rounded"
                  aria-label="Close publish drawer"
                >
                  <X size={16} strokeWidth={1.5} />
                </button>
              </div>

              {publishResult ? (
                /* ── Success State ──────────────────────────── */
                <Card className="p-4 border-success/30 bg-success/5">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-5 h-5 rounded-full bg-success flex items-center justify-center">
                      <Check size={12} strokeWidth={2} className="text-white" />
                    </div>
                    <span className="text-[13px] font-medium text-text-primary">Published successfully</span>
                  </div>
                  <div className="space-y-2">
                    <div>
                      <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Title</p>
                      <p className="text-[12px] text-text-primary">{publishResult.title}</p>
                    </div>
                    <div>
                      <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">URL</p>
                      {/* F9: Validate URL before rendering as link */}
                      {isSafeUrl(publishResult.url) ? (
                        <a
                          href={publishResult.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[12px] text-accent hover:underline flex items-center gap-1"
                        >
                          {publishResult.url}
                          <ExternalLink size={10} strokeWidth={1.5} />
                        </a>
                      ) : (
                        <span className="text-[12px] text-text-primary">{publishResult.url}</span>
                      )}
                    </div>
                    <div className="flex gap-4">
                      <div>
                        <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Status</p>
                        <Badge variant={publishResult.status === 'publish' ? 'success' : 'info'}>
                          {publishResult.status}
                        </Badge>
                      </div>
                      <div>
                        <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Words</p>
                        <p className="text-[12px] text-text-primary font-mono">{publishResult.word_count.toLocaleString()}</p>
                      </div>
                    </div>
                  </div>
                  <Button variant="secondary" size="sm" className="mt-4" onClick={onClose}>
                    Close
                  </Button>
                </Card>
              ) : (
                /* ── Form State ─────────────────────────────── */
                <div className="space-y-4">
                  {/* Brief info */}
                  <div>
                    <h4 className="text-[14px] font-medium text-text-primary mb-1">{brief.title}</h4>
                    {brief.content_preview && (
                      <p className="text-[11px] text-text-tertiary line-clamp-3">{brief.content_preview}</p>
                    )}
                  </div>

                  {/* Slug */}
                  <div>
                    <label className="block text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-1">
                      URL Slug
                    </label>
                    <Input
                      value={slug}
                      onChange={(e) => setSlug(slugify(e.target.value))}
                      placeholder="url-slug"
                      disabled={isPublishing}
                    />
                  </div>

                  {/* Status toggle */}
                  <div>
                    <label className="block text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-1">
                      Publish Status
                    </label>
                    <div className="flex gap-1">
                      <Button
                        size="sm"
                        variant={status === 'draft' ? 'primary' : 'ghost'}
                        onClick={() => setStatus('draft')}
                        disabled={isPublishing}
                      >
                        Draft
                      </Button>
                      <Button
                        size="sm"
                        variant={status === 'publish' ? 'primary' : 'ghost'}
                        onClick={() => setStatus('publish')}
                        disabled={isPublishing}
                      >
                        Publish
                      </Button>
                    </div>
                  </div>

                  {/* Categories */}
                  <div>
                    <label className="block text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-1">
                      Categories
                    </label>
                    {categoriesLoading ? (
                      <div className="space-y-1">
                        {Array.from({ length: 3 }).map((_, i) => (
                          <Skeleton key={i} className="h-[24px] w-full rounded-sm" />
                        ))}
                      </div>
                    ) : categories.length === 0 ? (
                      <p className="text-[11px] text-text-tertiary">No categories found in CMS</p>
                    ) : (
                      <div className="max-h-[200px] overflow-y-auto border border-border rounded-sm p-2 space-y-1">
                        {categories.map((cat) => (
                          <label
                            key={cat.cms_id}
                            className="flex items-center gap-2 px-1 py-0.5 rounded hover:bg-surface-raised cursor-pointer"
                          >
                            <input
                              type="checkbox"
                              checked={selectedCategories.has(cat.name)}
                              onChange={() => toggleCategory(cat.name)}
                              disabled={isPublishing}
                              className="accent-accent w-3 h-3"
                            />
                            <span className="text-[12px] text-text-primary flex-1">{cat.name}</span>
                            <span className="text-[10px] text-text-tertiary">{cat.post_count}</span>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Error */}
                  {publishError && (
                    <p className="text-[11px] text-error">{publishError}</p>
                  )}

                  {/* Submit */}
                  <Button
                    variant="primary"
                    onClick={handlePublish}
                    disabled={isPublishing || !slug.trim()}
                  >
                    {isPublishing ? 'Publishing...' : 'Confirm Publish'}
                  </Button>
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
